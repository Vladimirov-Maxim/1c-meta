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

VENDOR_MODULE = "Documents/Вендорский/Ext/ObjectModule.bsl"
OURS = "Documents/мой_Наш/Ext/ObjectModule.bsl"
PROFILE = {"приставка": ["мой_", "ОМ_мой_"], "метки": {"тег": "#TEAM"}}
CARD = ["<MetaDataObject/>"]


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_file(root, rel, lines, eol="\r\n", bom=True, final=True):
    path = os.path.join(str(root), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = eol.join(lines) + (eol if final else "")
    with open(path, "wb") as file:
        file.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def commit(root, message="базлайн"):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def dump_dir(tmp_path, autocrlf=False):
    """Выгрузка под git: вендорский объект и свой объект прошлой задачи в базе."""
    root = tmp_path / "cf"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "true" if autocrlf else "false"),
                           ("core.quotepath", "false")):
        git(root, "config", key, value)
    write_file(root, "Configuration.xml", ["<MetaDataObject/>"])
    write_file(root, VENDOR_MODULE, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 1;", "КонецПроцедуры"])
    write_file(root, "Documents/Вендорский.xml", CARD)
    write_file(root, OURS, ["Процедура ОбработкаПроведения(Отказ, РежимПроведения)", "\tЗначение = 1;",
                         "КонецПроцедуры"])
    write_file(root, "Documents/мой_Наш.xml", CARD)
    commit(root)
    return root


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return str(path)


def check(capsys, profile, *arguments):
    """(код возврата, текст, находки JSON)."""
    answer = os.path.join(os.path.dirname(profile), "ответ.json")
    if os.path.exists(answer):
        os.remove(answer)
    capsys.readouterr()
    code = main(["--проверить", *map(str, arguments), "--профиль", profile, "--json", answer])
    text = capsys.readouterr().out
    data = json.load(open(answer, encoding="utf-8")) if os.path.exists(answer) else None
    return code, text, data


def codes(data):
    return sorted(f["код"] for f in data["находки"])


# --- приставка и состав --------------------------------------------------------------------


def test_a_test_module_prefix_is_ours_and_a_bare_object_is_not(tmp_path, capsys, profile):
    """Тестовые модули зовутся «ОМ_<приставка>…» — это свои; объект без
    приставки — нарушение."""
    root = dump_dir(tmp_path)
    write_file(root, "CommonModules/ОМ_мой_Новый.xml", CARD)
    code, text, data = check(capsys, profile, root)
    assert code == 0 and codes(data) == [], text
    assert "A  CommonModules/ОМ_мой_Новый.xml" in text            # состав напечатан
    write_file(root, "CommonModules/ЧужойМодуль.xml", CARD)
    code, _, data = check(capsys, profile, root)
    assert code == 1 and codes(data) == ["МД-ПРЕФИКС"]
    assert data["находки"][0]["файл"] == "CommonModules/ЧужойМодуль.xml"


def test_without_a_task_the_foreign_insertion_rule_is_named_skipped(tmp_path, capsys, profile):
    """Пропуск виден в итоге: «чисто» при пропусках не выдаётся."""
    root = dump_dir(tmp_path)
    code, text, data = check(capsys, profile, root)
    assert code == 0 and "НЕПОЛНЫЙ ПРОГОН" in text and "ЧИСТО" not in text
    assert data["пропущено"] == [{"что": "ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ", "почему": "не задан ИД задачи"}]
    code, text, data = check(capsys, profile, root, "--задача", "TASK-1")
    assert "ЧИСТО" in text and data["пропущено"] == []


def test_a_service_file_in_the_changes_is_found(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, "ConfigDumpInfo.xml", ["<ConfigDumpInfo/>"])
    _, _, data = check(capsys, profile, root)
    assert codes(data) == ["ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ"]


def test_a_dump_deeper_in_the_repository_sees_only_its_own_new_files(tmp_path, capsys, profile):
    """Новые файлы git называет от корня репозитория; выгрузка, лежащая в нём
    глубже, отрезает свою приставку и чужих новых файлов не видит."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git(repo, "config", key, value)
    root = repo / "src" / "cf"
    write_file(root, "Configuration.xml", ["<MetaDataObject/>"])
    commit(repo)
    write_file(root, "Documents/мой_Новый.xml", CARD)
    write_file(repo, "Documents/Чужой.xml", CARD)
    code, text, data = check(capsys, profile, root)
    assert "A  Documents/мой_Новый.xml" in text and "Чужой" not in text, text
    assert "Файлов задачи: 1" in text


# --- BOM и переводы строк -----------------------------------------------------------------


def test_line_endings_are_checked_against_the_repository(tmp_path, capsys, profile):
    """Файл, единообразный внутри себя, но целиком чужой репозиторию: новый
    модуль — в LF при CRLF во всех остальных."""
    root = dump_dir(tmp_path)
    write_file(root, "CommonModules/мой_Новый/Ext/Module.bsl",
             ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    _, _, data = check(capsys, profile, root)
    assert codes(data) == ["ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"]
    assert "переводы строк LF, в репозитории приняты CRLF" in data["находки"][0]["текст"]


def test_where_git_normalizes_line_endings_they_are_not_checked(tmp_path, capsys, profile):
    root = dump_dir(tmp_path, autocrlf=True)
    write_file(root, "CommonModules/мой_Новый/Ext/Module.bsl",
             ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    _, text, data = check(capsys, profile, root)
    assert codes(data) == [] and "core.autocrlf" in text


def test_a_file_without_bom_is_found(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, "CommonModules/мой_Новый/Ext/Module.bsl",
             ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], bom=False)
    _, _, data = check(capsys, profile, root)
    assert codes(data) == ["ФАЙЛ-БЕЗ-BOM"]


# --- метки вставок ------------------------------------------------------------------------


def test_a_new_method_needs_a_marker_except_in_a_module_created_by_the_task(tmp_path, capsys, profile):
    """Принадлежность объекта основанием не является: новый метод в своём
    модуле прошлой задачи оборачивается на общих основаниях."""
    root = dump_dir(tmp_path)
    before_ = ["Процедура ОбработкаПроведения(Отказ, РежимПроведения)", "\tЗначение = 1;", "КонецПроцедуры"]
    write_file(root, OURS, before_ + ["", "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;", "КонецПроцедуры"])
    _, _, data = check(capsys, profile, root)
    assert codes(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ"] and data["находки"][0]["файл"] == OURS

    write_file(root, OURS, before_ + ["", "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1",
                              "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;",
                              "КонецПроцедуры // } Автор, 31.08.2026"])
    _, _, data = check(capsys, profile, root)
    assert codes(data) == []

    write_file(root, "CommonModules/мой_Созданный/Ext/Module.bsl",
             ["Процедура Новая() Экспорт", "\tВозврат;", "КонецПроцедуры"])
    _, _, data = check(capsys, profile, root)
    assert codes(data) == []


def test_a_vendor_edit_without_a_marker_is_found(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, VENDOR_MODULE, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 42;", "КонецПроцедуры"])
    code, _, data = check(capsys, profile, root)
    assert code == 1 and codes(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]


def test_without_markers_in_the_profile_an_unwrapped_edit_is_fine(tmp_path, capsys):
    """Команда без меток вставок («метки.ставить»: false): правка вне вставки —
    не находка; правила меток выключены все."""
    path = tmp_path / "без-меток.json"
    path.write_text(json.dumps({**PROFILE, "метки": {"ставить": False}}, ensure_ascii=False),
                    encoding="utf-8")
    root = dump_dir(tmp_path)
    write_file(root, VENDOR_MODULE, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 42;", "КонецПроцедуры"])
    code, _, data = check(capsys, str(path), root)
    assert code == 0 and codes(data) == []


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
def test_the_marker_itself_is_checked(tmp_path, capsys, profile, marker, code):
    root = dump_dir(tmp_path)
    write_file(root, VENDOR_MODULE, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)", marker,
                                "\t", "\t//Значение = 1;", "\t", "\tЗначение = 2;", "\t",
                                "\t// } Автор, 31.08.2026", "КонецПроцедуры"])
    _, _, data = check(capsys, profile, root)
    assert codes(data) == ([code] if code else [])


def test_an_unclosed_insertion_and_a_method_closed_on_its_own_line(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, VENDOR_MODULE, [
        "Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)", "\tЗначение = 1;", "КонецПроцедуры",
        "",
        "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
        "Процедура мой_Первый()", "\tЗначение = 2;", "КонецПроцедуры",
        "// } Тест, 26.09.2026",
        "",
        "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
        "Процедура мой_Второй()", "\tЗначение = 3;", "КонецПроцедуры"])
    _, _, data = check(capsys, profile, root)
    assert [(f["код"], f["строка"]) for f in data["находки"]] == [
        ("ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ", 8), ("ВСТАВКА-НЕ-ЗАКРЫТА", 11)]


def test_a_line_replaced_by_itself_with_other_whitespace(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, VENDOR_MODULE, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                                "\tЗначение = 1; ", "КонецПроцедуры"])
    _, _, data = check(capsys, profile, root)
    assert "ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ" in codes(data)
    assert next(f for f in data["находки"] if f["код"] == "ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ")["строка"] == 2


# --- права на новые объекты -----------------------------------------------------------


def role(root, name, obj, value="true"):
    write_file(root, f"Roles/{name}.xml", CARD)
    write_file(root, f"Roles/{name}/Ext/Rights.xml", [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.21">',
        "\t<object>", f"\t\t<name>{obj}</name>",
        "\t\t<right>", "\t\t\t<name>View</name>", f"\t\t\t<value>{value}</value>", "\t\t</right>",
        "\t</object>", "</Rights>"])


def test_a_new_object_without_its_own_role_is_found(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, "CommonCommands/мой_НоваяКоманда.xml", CARD)
    code, _, data = check(capsys, profile, root)
    assert code == 1 and codes(data) == ["ПРАВА-НЕ-ВЫДАНЫ"]
    assert data["находки"][0]["файл"] is None
    assert data["находки"][0]["текст"].startswith("ОбщаяКоманда.мой_НоваяКоманда")
    role(root, "мой_атом_НоваяКоманда", "CommonCommand.мой_НоваяКоманда")
    code, _, data = check(capsys, profile, root)
    assert code == 0 and codes(data) == []


def test_a_false_right_and_a_vendor_role_do_not_count(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, "InformationRegisters/мой_НовыйРегистр.xml", CARD)
    role(root, "мой_атом_Выключено", "InformationRegister.мой_НовыйРегистр", "false")
    _, _, data = check(capsys, profile, root)
    assert codes(data) == ["ПРАВА-НЕ-ВЫДАНЫ"]

    foreign_one = dump_dir(tmp_path / "чужая")              # типовая роль — в базе, объект — новый
    role(foreign_one, "ПолныеПрава", "InformationRegister.мой_НовыйРегистр")
    commit(foreign_one, "типовая роль")
    write_file(foreign_one, "InformationRegisters/мой_НовыйРегистр.xml", CARD)
    _, _, data = check(capsys, profile, foreign_one)
    assert codes(data) == ["ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ"] and "(ПолныеПрава)" in data["находки"][0]["текст"]


def test_kinds_without_rights_need_none_and_revisions_are_read_from_history(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, "CommonModules/мой_НовыйМодуль.xml", CARD)
    write_file(root, "Enums/мой_НовоеПеречисление.xml", CARD)
    _, _, data = check(capsys, profile, root)
    assert codes(data) == []

    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    write_file(root, "Reports/мой_НовыйОтчет.xml", CARD)
    role(root, "мой_атом_НовыйОтчет", "Report.мой_НовыйОтчет")
    commit(root, "задача")
    code, text, data = check(capsys, profile, root, "--база", base, "--ревизия", "HEAD")
    assert code == 0 and codes(data) == [], text
    assert "ревизия HEAD против" in text


# --- пара каталогов ---------------------------------------------------------------------------


def pair(tmp_path):
    reference_node, copy_ = tmp_path / "эталон", tmp_path / "копия"
    for root in (reference_node, copy_):
        write_file(root, "Обработка/Ext/ObjectModule.bsl",
                 ["Процедура Сформировать()", "\tЗначение = 1;  ", "\tДругое = 2;", "КонецПроцедуры"])
        write_file(root, "Обработка.xml", CARD)
    return reference_node, copy_


def test_a_directory_pair_is_checked_like_a_repository(tmp_path, capsys, profile):
    """Обработка вне репозитория: исходный эталон против правленой копии."""
    reference_node, copy_ = pair(tmp_path)
    code, text, data = check(capsys, profile, "--эталон", reference_node, "--копия", copy_)
    assert code == 0 and codes(data) == [] and "Файлов задачи: 0" in text
    write_file(copy_, "Обработка/Ext/ObjectModule.bsl",
             ["Процедура Сформировать()", "\tЗначение = 1;", "\tДругое = 3;", "КонецПроцедуры"])
    _, text, data = check(capsys, profile, "--эталон", reference_node, "--копия", copy_)
    assert codes(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ", "ФАЙЛ-ХВОСТЫ-СРЕЗАНЫ"]
    assert "копия" in text and "против эталона" in text


# --- ошибки входа ------------------------------------------------------------------------------


def test_an_input_error_is_code_two_not_clean(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    assert check(capsys, profile, tmp_path / "нет-такой")[0] == 2
    code, text, data = check(capsys, profile, root, "--база", "0000000")
    assert code == 2 and "ревизии «0000000» в репозитории нет" in text and data is None
    assert check(capsys, profile, "--эталон", tmp_path)[0] == 2


# --- главный кейс: что записала правка вставками, проверка принимает ---------------------------


def test_what_code_apply_writes_verify_accepts(tmp_path, capsys, profile):
    root = dump_dir(tmp_path)
    write_file(root, "CommonModules/мой_Старый/Ext/Module.bsl", [
        "#Область ПрограммныйИнтерфейс", "",
        "Процедура Тест() Экспорт", "\tЗначение = 1;", "\tВозврат;", "КонецПроцедуры", "",
        "#КонецОбласти"])
    write_file(root, "CommonModules/мой_Старый.xml", CARD)
    commit(root, "прошлая задача")
    job_spec = {"repo": str(root), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "ОбщийМодуль.мой_Старый", "edits": [
                   {"line": 4, "lines": 1, "first_line": "\tЗначение = 1;", "last_line": "\tЗначение = 1;",
                    "code": "\tЗначение = 2;"},
                   {"line": 8, "lines": 0, "first_line": "#КонецОбласти",
                    "code": "Процедура Новая() Экспорт\n\tВозврат;\nКонецПроцедуры"}]},
                   {"модуль": "Документ.Вендорский.МодульОбъекта", "edits": [
                       {"line": 3, "lines": 0, "first_line": "КонецПроцедуры", "code": "\tПроверка();"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    assert main(["--apply", str(path), "--профиль", profile]) == 0
    code, text, data = check(capsys, profile, root, "--задача", "TASK-1")
    assert code == 0 and codes(data) == [], text
    assert "M  CommonModules/мой_Старый/Ext/Module.bsl" in text and f"M  {VENDOR_MODULE}" in text


# --- канал MCP ------------------------------------------------------------------------------


def test_the_agent_gets_the_same_check_through_mcp(tmp_path):
    """Тот же сценарий и тот же текст — только чтение, но в пределах разрешённых
    выгрузок, как и показ."""
    import asyncio

    from meta.composition import mcp_server
    from meta.domain.conventions import Conventions

    root = dump_dir(tmp_path)
    write_file(root, "CommonModules/ЧужойМодуль.xml", CARD)
    server = mcp_server(roots=[str(root)], conventions=Conventions(prefix="мой_"))

    def call_tool(**arguments):
        answer = asyncio.run(server.call_tool("verify", arguments))
        if isinstance(answer, tuple):
            answer = answer[0]
        return "\n".join(block.text for block in answer)

    text = call_tool(repo=str(root), task="TASK-1")
    assert "[МД-ПРЕФИКС] CommonModules/ЧужойМодуль.xml" in text and "НАРУШЕНИЙ: 1" in text
    assert call_tool(repo=str(tmp_path)).startswith("ОТКАЗ: выгрузка")
    assert call_tool().startswith("ОТКАЗ: не задано, что проверять")
