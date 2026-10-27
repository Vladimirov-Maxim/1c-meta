"""Проверка правок задачи — через терминал, на настоящем git и паре каталогов.

Каждый кейс и ловит, и не даёт ложного. Выгрузки — синтетические, во временном
каталоге; рабочие исходники не трогаются никогда.

Главный кейс — запись правкой вставками и проверка того же модуля: что
записал инструмент, проверка принимает без находок по меткам.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402

ВЕНДОРСКИЙ = "Documents/Вендорский/Ext/ObjectModule.bsl"
НАШ = "Documents/мой_Наш/Ext/ObjectModule.bsl"
ПРОФИЛЬ = {"приставка": ["мой_", "ОМ_мой_"], "метки": {"тег": "#TEAM"}}
КАРТОЧКА = ["<MetaDataObject/>"]


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def написать(root, rel, lines, eol="\r\n", bom=True, final=True):
    path = os.path.join(str(root), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = eol.join(lines) + (eol if final else "")
    with open(path, "wb") as file:
        file.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def зафиксировать(root, сообщение="базлайн"):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", сообщение)


def выгрузка(tmp_path, autocrlf=False):
    """Выгрузка под git: вендорский объект и свой объект прошлой задачи в базе."""
    root = tmp_path / "cf"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "true" if autocrlf else "false"),
                           ("core.quotepath", "false")):
        git(root, "config", key, value)
    написать(root, "Configuration.xml", ["<MetaDataObject/>"])
    написать(root, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 1;", "КонецПроцедуры"])
    написать(root, "Documents/Вендорский.xml", КАРТОЧКА)
    написать(root, НАШ, ["Процедура ОбработкаПроведения(Отказ, РежимПроведения)", "\tЗначение = 1;",
                         "КонецПроцедуры"])
    написать(root, "Documents/мой_Наш.xml", КАРТОЧКА)
    зафиксировать(root)
    return root


@pytest.fixture
def профиль(tmp_path):
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(path)


def check(capsys, профиль, *arguments):
    """(код возврата, текст, находки JSON)."""
    ответ = os.path.join(os.path.dirname(профиль), "ответ.json")
    if os.path.exists(ответ):
        os.remove(ответ)
    capsys.readouterr()
    code = main(["--проверить", *map(str, arguments), "--профиль", профиль, "--json", ответ])
    text = capsys.readouterr().out
    data = json.load(open(ответ, encoding="utf-8")) if os.path.exists(ответ) else None
    return code, text, data


def коды(data):
    return sorted(f["код"] for f in data["находки"])


# --- приставка и состав --------------------------------------------------------------------


def test_a_test_module_prefix_is_ours_and_a_bare_object_is_not(tmp_path, capsys, профиль):
    """Тестовые модули зовутся «ОМ_<приставка>…» — это свои; объект без
    приставки — нарушение."""
    root = выгрузка(tmp_path)
    написать(root, "CommonModules/ОМ_мой_Новый.xml", КАРТОЧКА)
    code, text, data = check(capsys, профиль, root)
    assert code == 0 and коды(data) == [], text
    assert "A  CommonModules/ОМ_мой_Новый.xml" in text            # состав напечатан
    написать(root, "CommonModules/ЧужойМодуль.xml", КАРТОЧКА)
    code, _, data = check(capsys, профиль, root)
    assert code == 1 and коды(data) == ["МД-ПРЕФИКС"]
    assert data["находки"][0]["файл"] == "CommonModules/ЧужойМодуль.xml"


def test_without_a_task_the_foreign_insertion_rule_is_named_skipped(tmp_path, capsys, профиль):
    """Пропуск виден в итоге: «чисто» при пропусках не выдаётся."""
    root = выгрузка(tmp_path)
    code, text, data = check(capsys, профиль, root)
    assert code == 0 and "НЕПОЛНЫЙ ПРОГОН" in text and "ЧИСТО" not in text
    assert data["пропущено"] == [{"что": "ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ", "почему": "не задан ИД задачи"}]
    code, text, data = check(capsys, профиль, root, "--задача", "TASK-1")
    assert "ЧИСТО" in text and data["пропущено"] == []


def test_a_service_file_in_the_changes_is_found(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, "ConfigDumpInfo.xml", ["<ConfigDumpInfo/>"])
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == ["ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ"]


def test_a_dump_deeper_in_the_repository_sees_only_its_own_new_files(tmp_path, capsys, профиль):
    """Новые файлы git называет от корня репозитория; выгрузка, лежащая в нём
    глубже, отрезает свою приставку и чужих новых файлов не видит."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git(repo, "config", key, value)
    root = repo / "src" / "cf"
    написать(root, "Configuration.xml", ["<MetaDataObject/>"])
    зафиксировать(repo)
    написать(root, "Documents/мой_Новый.xml", КАРТОЧКА)
    написать(repo, "Documents/Чужой.xml", КАРТОЧКА)
    code, text, data = check(capsys, профиль, root)
    assert "A  Documents/мой_Новый.xml" in text and "Чужой" not in text, text
    assert "Файлов задачи: 1" in text


# --- BOM и переводы строк -----------------------------------------------------------------


def test_line_endings_are_checked_against_the_repository(tmp_path, capsys, профиль):
    """Файл, единообразный внутри себя, но целиком чужой репозиторию: новый
    модуль — в LF при CRLF во всех остальных."""
    root = выгрузка(tmp_path)
    написать(root, "CommonModules/мой_Новый/Ext/Module.bsl",
             ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == ["ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"]
    assert "переводы строк LF, в репозитории приняты CRLF" in data["находки"][0]["текст"]


def test_where_git_normalizes_line_endings_they_are_not_checked(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path, autocrlf=True)
    написать(root, "CommonModules/мой_Новый/Ext/Module.bsl",
             ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    _, text, data = check(capsys, профиль, root)
    assert коды(data) == [] and "core.autocrlf" in text


def test_a_file_without_bom_is_found(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, "CommonModules/мой_Новый/Ext/Module.bsl",
             ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], bom=False)
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == ["ФАЙЛ-БЕЗ-BOM"]


# --- метки вставок ------------------------------------------------------------------------


def test_a_new_method_needs_a_marker_except_in_a_module_created_by_the_task(tmp_path, capsys, профиль):
    """Принадлежность объекта основанием не является: новый метод в своём
    модуле прошлой задачи оборачивается на общих основаниях."""
    root = выгрузка(tmp_path)
    before_ = ["Процедура ОбработкаПроведения(Отказ, РежимПроведения)", "\tЗначение = 1;", "КонецПроцедуры"]
    написать(root, НАШ, before_ + ["", "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;", "КонецПроцедуры"])
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ"] and data["находки"][0]["файл"] == НАШ

    написать(root, НАШ, before_ + ["", "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1",
                              "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;",
                              "КонецПроцедуры // } Автор, 31.08.2026"])
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == []

    написать(root, "CommonModules/мой_Созданный/Ext/Module.bsl",
             ["Процедура Новая() Экспорт", "\tВозврат;", "КонецПроцедуры"])
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == []


def test_a_vendor_edit_without_a_marker_is_found(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 42;", "КонецПроцедуры"])
    code, _, data = check(capsys, профиль, root)
    assert code == 1 and коды(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]


def test_without_markers_in_the_profile_an_unwrapped_edit_is_fine(tmp_path, capsys):
    """Команда без меток вставок («метки.ставить»: false): правка вне вставки —
    не находка; правила меток выключены все."""
    path = tmp_path / "без-меток.json"
    path.write_text(json.dumps({**ПРОФИЛЬ, "метки": {"ставить": False}}, ensure_ascii=False),
                    encoding="utf-8")
    root = выгрузка(tmp_path)
    написать(root, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 42;", "КонецПроцедуры"])
    code, _, data = check(capsys, str(path), root)
    assert code == 0 and коды(data) == []


def test_marker_rules_of_the_profile_are_the_verification_codes():
    """Список правил меток в соглашениях — те же коды, что у проверки правок."""
    from meta.domain import verification as v
    from meta.domain.conventions import MARKER_RULES
    assert set(MARKER_RULES) == {v.INSERTION_YO, v.INSERTION_WITHOUT_TYPE, v.INSERTION_WITHOUT_DATE,
                                  v.INSERTION_WITHOUT_TASK, v.OUTSIDE_INSERTION, v.IN_FOREIGN_INSERTION,
                                  v.NOT_CLOSED, v.METHOD_NOT_AT_END}


@pytest.mark.parametrize("marker, code", [
    ("\t// {[*](фрагмент ИЗМЕНЕН), 31.08.2026, #TEAM Автор #TASK-1", None),
    ("\t// {[*](фрагмент ИЗМЕНЁН), 31.08.2026, #TEAM Автор #TASK-1", "ВСТАВКА-БУКВА-Ё"),
    ("\t// {[*](фрагмент ИЗМЕНЕН), #TEAM Автор #TASK-1", "ВСТАВКА-БЕЗ-ДАТЫ"),
])
def test_the_marker_itself_is_checked(tmp_path, capsys, профиль, marker, code):
    root = выгрузка(tmp_path)
    написать(root, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)", marker,
                                "\t", "\t//Значение = 1;", "\t", "\tЗначение = 2;", "\t",
                                "\t// } Автор, 31.08.2026", "КонецПроцедуры"])
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == ([code] if code else [])


def test_an_unclosed_insertion_and_a_method_closed_on_its_own_line(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, ВЕНДОРСКИЙ, [
        "Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)", "\tЗначение = 1;", "КонецПроцедуры",
        "",
        "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
        "Процедура мой_Первый()", "\tЗначение = 2;", "КонецПроцедуры",
        "// } Тест, 26.09.2026",
        "",
        "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
        "Процедура мой_Второй()", "\tЗначение = 3;", "КонецПроцедуры"])
    _, _, data = check(capsys, профиль, root)
    assert [(f["код"], f["строка"]) for f in data["находки"]] == [
        ("ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ", 8), ("ВСТАВКА-НЕ-ЗАКРЫТА", 11)]


def test_a_line_replaced_by_itself_with_other_whitespace(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 1; ", "КонецПроцедуры"])
    _, _, data = check(capsys, профиль, root)
    assert "ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ" in коды(data)
    assert next(f for f in data["находки"] if f["код"] == "ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ")["строка"] == 2


# --- права на новые объекты -----------------------------------------------------------


def role(root, name, obj, value="true"):
    написать(root, f"Roles/{name}.xml", КАРТОЧКА)
    написать(root, f"Roles/{name}/Ext/Rights.xml", [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.21">',
        "\t<object>", f"\t\t<name>{obj}</name>",
        "\t\t<right>", "\t\t\t<name>View</name>", f"\t\t\t<value>{value}</value>", "\t\t</right>",
        "\t</object>", "</Rights>"])


def test_a_new_object_without_its_own_role_is_found(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, "CommonCommands/мой_НоваяКоманда.xml", КАРТОЧКА)
    code, _, data = check(capsys, профиль, root)
    assert code == 1 and коды(data) == ["ПРАВА-НЕ-ВЫДАНЫ"]
    assert data["находки"][0]["файл"] is None
    assert data["находки"][0]["текст"].startswith("ОбщаяКоманда.мой_НоваяКоманда")
    role(root, "мой_атом_НоваяКоманда", "CommonCommand.мой_НоваяКоманда")
    code, _, data = check(capsys, профиль, root)
    assert code == 0 and коды(data) == []


def test_a_false_right_and_a_vendor_role_do_not_count(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, "InformationRegisters/мой_НовыйРегистр.xml", КАРТОЧКА)
    role(root, "мой_атом_Выключено", "InformationRegister.мой_НовыйРегистр", "false")
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == ["ПРАВА-НЕ-ВЫДАНЫ"]

    чужая = выгрузка(tmp_path / "чужая")              # типовая роль — в базе, объект — новый
    role(чужая, "ПолныеПрава", "InformationRegister.мой_НовыйРегистр")
    зафиксировать(чужая, "типовая роль")
    написать(чужая, "InformationRegisters/мой_НовыйРегистр.xml", КАРТОЧКА)
    _, _, data = check(capsys, профиль, чужая)
    assert коды(data) == ["ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ"] and "(ПолныеПрава)" in data["находки"][0]["текст"]


def test_kinds_without_rights_need_none_and_revisions_are_read_from_history(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, "CommonModules/мой_НовыйМодуль.xml", КАРТОЧКА)
    написать(root, "Enums/мой_НовоеПеречисление.xml", КАРТОЧКА)
    _, _, data = check(capsys, профиль, root)
    assert коды(data) == []

    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    написать(root, "Reports/мой_НовыйОтчет.xml", КАРТОЧКА)
    role(root, "мой_атом_НовыйОтчет", "Report.мой_НовыйОтчет")
    зафиксировать(root, "задача")
    code, text, data = check(capsys, профиль, root, "--база", base, "--ревизия", "HEAD")
    assert code == 0 and коды(data) == [], text
    assert "ревизия HEAD против" in text


# --- пара каталогов ---------------------------------------------------------------------------


def pair(tmp_path):
    reference_node, copy_ = tmp_path / "эталон", tmp_path / "копия"
    for root in (reference_node, copy_):
        написать(root, "Обработка/Ext/ObjectModule.bsl",
                 ["Процедура Сформировать()", "\tЗначение = 1;  ", "\tДругое = 2;", "КонецПроцедуры"])
        написать(root, "Обработка.xml", КАРТОЧКА)
    return reference_node, copy_


def test_a_directory_pair_is_checked_like_a_repository(tmp_path, capsys, профиль):
    """Обработка вне репозитория: исходный эталон против правленой копии."""
    reference_node, copy_ = pair(tmp_path)
    code, text, data = check(capsys, профиль, "--эталон", reference_node, "--копия", copy_)
    assert code == 0 and коды(data) == [] and "Файлов задачи: 0" in text
    написать(copy_, "Обработка/Ext/ObjectModule.bsl",
             ["Процедура Сформировать()", "\tЗначение = 1;", "\tДругое = 3;", "КонецПроцедуры"])
    _, text, data = check(capsys, профиль, "--эталон", reference_node, "--копия", copy_)
    assert коды(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ", "ФАЙЛ-ХВОСТЫ-СРЕЗАНЫ"]
    assert "копия" in text and "против эталона" in text


# --- ошибки входа ------------------------------------------------------------------------------


def test_an_input_error_is_code_two_not_clean(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    assert check(capsys, профиль, tmp_path / "нет-такой")[0] == 2
    code, text, data = check(capsys, профиль, root, "--база", "0000000")
    assert code == 2 and "ревизии «0000000» в репозитории нет" in text and data is None
    assert check(capsys, профиль, "--эталон", tmp_path)[0] == 2


# --- главный кейс: что записала правка вставками, проверка принимает ---------------------------


def test_what_code_apply_writes_verify_accepts(tmp_path, capsys, профиль):
    root = выгрузка(tmp_path)
    написать(root, "CommonModules/мой_Старый/Ext/Module.bsl", [
        "#Область ПрограммныйИнтерфейс", "",
        "Процедура Тест() Экспорт", "\tЗначение = 1;", "\tВозврат;", "КонецПроцедуры", "",
        "#КонецОбласти"])
    написать(root, "CommonModules/мой_Старый.xml", КАРТОЧКА)
    зафиксировать(root, "прошлая задача")
    задание = {"repo": str(root), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "ОбщийМодуль.мой_Старый", "edits": [
                   {"line": 4, "lines": 1, "first_line": "\tЗначение = 1;", "last_line": "\tЗначение = 1;",
                    "code": "\tЗначение = 2;"},
                   {"line": 8, "lines": 0, "first_line": "#КонецОбласти",
                    "code": "Процедура Новая() Экспорт\n\tВозврат;\nКонецПроцедуры"}]},
                   {"модуль": "Документ.Вендорский.МодульОбъекта", "edits": [
                       {"line": 3, "lines": 0, "first_line": "КонецПроцедуры", "code": "\tПроверка();"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    assert main(["--apply", str(path), "--профиль", профиль]) == 0
    code, text, data = check(capsys, профиль, root, "--задача", "TASK-1")
    assert code == 0 and коды(data) == [], text
    assert "M  CommonModules/мой_Старый/Ext/Module.bsl" in text and f"M  {ВЕНДОРСКИЙ}" in text


# --- канал MCP ------------------------------------------------------------------------------


def test_the_agent_gets_the_same_check_through_mcp(tmp_path):
    """Тот же сценарий и тот же текст — только чтение, но в пределах разрешённых
    выгрузок, как и показ."""
    import asyncio

    from meta.composition import mcp_server
    from meta.domain.conventions import Conventions

    root = выгрузка(tmp_path)
    написать(root, "CommonModules/ЧужойМодуль.xml", КАРТОЧКА)
    сервер = mcp_server(roots=[str(root)], conventions=Conventions(prefix="мой_"))

    def вызвать(**arguments):
        ответ = asyncio.run(сервер.call_tool("verify", arguments))
        if isinstance(ответ, tuple):
            ответ = ответ[0]
        return "\n".join(block.text for block in ответ)

    text = вызвать(repo=str(root), task="TASK-1")
    assert "[МД-ПРЕФИКС] CommonModules/ЧужойМодуль.xml" in text and "НАРУШЕНИЙ: 1" in text
    assert вызвать(repo=str(tmp_path)).startswith("ОТКАЗ: выгрузка")
    assert вызвать().startswith("ОТКАЗ: не задано, что проверять")
