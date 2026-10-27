"""Проект EDT: проверка правок, нормализация, сверка плана и правка кода — на
синтетическом проекте в подкаталоге git-репозитория.

Проект EDT отличается от выгрузки конфигуратора раскладкой и видом текста:
объект — `<Каталог>/<Имя>/<Имя>.mdo`, модули — в каталоге объекта без `Ext`,
права роли — `Roles/<Роль>/Rights.rights`, файлы — UTF-8 без BOM и LF.
Исходники лежат глубже корня репозитория (`project/src`), и пути находок — от них.

Кейсы — те же, что у выгрузки (`test_verify.py`), и кейсы проверок для EDT:
префикс у нового `.mdo`, право в `Rights.rights`, необёрнутая правка
`ObjectModule.bsl`, чтение по ревизиям из подкаталога, BOM по репозиторию.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402

ПРОФИЛЬ = {"приставка": ["мой_", "ОМ_мой_"], "метки": {"тег": "#TEAM"}}
ВЕНДОРСКИЙ = "Documents/Вендорский/ObjectModule.bsl"
MDCLASS = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          ).stdout.decode("utf-8", "replace").strip()


def написать(root, rel, lines, eol="\n", bom=False, final=True):
    path = os.path.join(str(root), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = eol.join(lines) + (eol if final else "")
    with open(path, "wb") as file:
        file.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def прочитать(root, rel):
    with open(os.path.join(str(root), *rel.split("/")), "rb") as file:
        return file.read()


def card(kind, name, *children):
    """Карточка `.mdo`: корень вида, имя и дети — уже готовыми строками."""
    return ['<?xml version="1.0" encoding="UTF-8"?>',
            f'<mdclass:{kind} xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" {MDCLASS} '
            f'uuid="7d1e2824-b889-41a0-a83e-d45103c58d47">',
            f"  <name>{name}</name>", *children, f"</mdclass:{kind}>"]


def member(tag, name, *types):
    """Ребёнок карточки с типом: `типы` — строки внутри `<type>`."""
    return [f'  <{tag} uuid="f3d110c5-c64c-426a-9525-b612dbab0753">', f"    <name>{name}</name>",
            "    <type>", *[f"      {tk}" for tk in types], "    </type>", f"  </{tag}>"]


def rights(obj):
    return ['<?xml version="1.0" encoding="UTF-8"?>',
            '<Rights xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://v8.1c.ru/8.2/roles" '
            'xsi:type="Rights">',
            "\t<object>", f"\t\t<name>{obj}</name>", "\t\t<right>", "\t\t\t<name>Read</name>",
            "\t\t\t<value>true</value>", "\t\t</right>", "\t</object>", "</Rights>"]


def зафиксировать(repo, сообщение="базлайн"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", сообщение)


def проект(tmp_path, autocrlf=False):
    """(репозиторий, исходники): проект EDT в `project/src`, вендорский документ и модуль в базе."""
    repo = tmp_path / "repo"
    src = repo / "project" / "src"
    src.mkdir(parents=True)
    git(repo, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "true" if autocrlf else "false"),
                           ("core.quotepath", "false")):
        git(repo, "config", key, value)
    написать(repo, "project/DT-INF/PROJECT.PMF", ["Manifest-Version: 1.0"])
    написать(src, "Configuration/Configuration.mdo", card("Configuration", "Конфигурация"))
    написать(src, "Documents/Вендорский/Вендорский.mdo", card("Document", "Вендорский"))
    написать(src, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                               "\tЗначение = 1;", "КонецПроцедуры"])
    написать(src, "CommonModules/ВендорскийМодуль/ВендорскийМодуль.mdo",
             card("CommonModule", "ВендорскийМодуль"))
    написать(src, "CommonModules/ВендорскийМодуль/Module.bsl", [
        "#Область ПрограммныйИнтерфейс", "Функция Публичный() Экспорт", "\tВозврат 1;", "КонецФункции",
        "#КонецОбласти"])
    зафиксировать(repo)
    return repo, src


@pytest.fixture
def профиль(tmp_path):
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(path)


def check(capsys, профиль, *arguments):
    """(код возврата, текст, ответ JSON)."""
    answer = os.path.join(os.path.dirname(профиль), "ответ.json")
    if os.path.exists(answer):
        os.remove(answer)
    capsys.readouterr()
    code = main(["--проверить", *map(str, arguments), "--профиль", профиль, "--json", answer])
    text = capsys.readouterr().out
    data = json.load(open(answer, encoding="utf-8")) if os.path.exists(answer) else None
    return code, text, data


def codes(data):
    return sorted(f["код"] for f in data["находки"])


# --- проверка правок ------------------------------------------------------------------------


def test_paths_are_from_the_sources_and_files_outside_them_are_not_in_scope(tmp_path, capsys, профиль):
    """Исходники в подкаталоге репозитория: пути — от них, служебный файл проекта
    выше них в предмет проверок не входит; новый `.mdo` без приставки пойман."""
    repo, src = проект(tmp_path)
    написать(repo, "project/DT-INF/PROJECT.PMF", ["Manifest-Version: 2.0"])
    написать(src, "Catalogs/Чужой/Чужой.mdo", card("Catalog", "Чужой"))
    code, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 1 and codes(data) == ["МД-ПРЕФИКС", "ПРАВА-НЕ-ВЫДАНЫ"], text
    [prefix] = [f for f in data["находки"] if f["код"] == "МД-ПРЕФИКС"]
    assert prefix["файл"] == "Catalogs/Чужой/Чужой.mdo"
    assert "A  Catalogs/Чужой/Чужой.mdo" in text and "PROJECT.PMF" not in text
    assert data["источник"].startswith("проект EDT")


def test_a_new_object_needs_a_right_in_rights_rights(tmp_path, capsys, профиль):
    """Права на новый объект ищутся в `Roles/<Роль>/Rights.rights`."""
    repo, src = проект(tmp_path)
    написать(src, "Catalogs/мой_Новый/мой_Новый.mdo", card("Catalog", "мой_Новый"))
    _, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert codes(data) == ["ПРАВА-НЕ-ВЫДАНЫ"], text
    написать(src, "Roles/мой_атом_Новый/мой_атом_Новый.mdo", card("Role", "мой_атом_Новый"))
    написать(src, "Roles/мой_атом_Новый/Rights.rights", rights("Catalog.мой_Новый"))
    code, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 0 and codes(data) == [], text
    # право только в чужой роли — своё нарушение
    os.remove(os.path.join(src, "Roles", "мой_атом_Новый", "Rights.rights"))
    написать(src, "Roles/Чужая/Rights.rights", rights("Catalog.мой_Новый"))
    _, _, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert "ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ" in codes(data)


def test_an_unwrapped_edit_of_a_module_without_ext_is_found(tmp_path, capsys, профиль):
    repo, src = проект(tmp_path)
    написать(src, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                               "\tЗначение = 42;", "КонецПроцедуры"])
    code, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 1 and codes(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ"], text
    assert data["находки"][0]["файл"] == ВЕНДОРСКИЙ


def test_revisions_are_read_from_the_subfolder(tmp_path, capsys, профиль):
    """Ревизия против базы: файлы читаются `show <ревизия>:./<путь>` из подкаталога."""
    repo, src = проект(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    написать(src, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                               "\tЗначение = 42;", "КонецПроцедуры"])
    написать(src, "CommonModules/мой_Новый/мой_Новый.mdo", card("CommonModule", "мой_Новый"))
    написать(src, "CommonModules/мой_Новый/Module.bsl", ["Функция Посчитать() Экспорт", "\tВозврат 1;",
                                                         "КонецФункции"])
    зафиксировать(repo, "задача")
    code, text, data = check(capsys, профиль, src, "--база", base, "--ревизия", "HEAD",
                                   "--задача", "TASK-1")
    assert code == 1 and codes(data) == ["ПРАВКА-ВНЕ-ВСТАВКИ"], text
    assert "A  CommonModules/мой_Новый/Module.bsl" in text and f"M  {ВЕНДОРСКИЙ}" in text


def test_bom_is_checked_against_the_repository(tmp_path, capsys, профиль):
    """В проекте EDT файлы без BOM: отсутствие — норма, BOM — нарушение."""
    repo, src = проект(tmp_path)
    написать(src, "CommonModules/мой_БезBOM/мой_БезBOM.mdo", card("CommonModule", "мой_БезBOM"))
    написать(src, "CommonModules/мой_БезBOM/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"])
    code, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 0 and codes(data) == [], text
    написать(src, "CommonModules/мой_БезBOM/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"],
             bom=True)
    code, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 1 and codes(data) == ["ФАЙЛ-ЛИШНИЙ-BOM"], text
    assert "лишний BOM: CommonModules/мой_БезBOM/Module.bsl" in text


def test_line_endings_are_those_of_the_repository(tmp_path, capsys, профиль):
    repo, src = проект(tmp_path)
    написать(src, "CommonModules/мой_М/мой_М.mdo", card("CommonModule", "мой_М"))
    написать(src, "CommonModules/мой_М/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"], eol="\r\n")
    _, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert codes(data) == ["ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"], text


def test_the_service_file_rule_is_not_applicable_and_does_not_make_the_run_incomplete(
        tmp_path, capsys, профиль):
    repo, src = проект(tmp_path)
    code, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 0 and "ЧИСТО" in text and data["пропущено"] == [], text
    assert any("ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ" in explanation for explanation in data["пояснения"])


def test_type_sets_of_new_members_are_read_from_mdo(tmp_path, capsys, профиль):
    """Составы типов новых членов читаются из карточки `.mdo`."""
    repo, src = проект(tmp_path)
    написать(src, "Catalogs/мой_А/мой_А.mdo", card("Catalog", "мой_А"))
    написать(src, "Roles/мой_Р/Rights.rights", rights("Catalog.мой_А"))
    зафиксировать(repo, "прошлая задача")
    написать(src, "Catalogs/мой_А/мой_А.mdo", card(
        "Catalog", "мой_А",
        *member("attributes", "Источник", "<types>CatalogRef.Контрагенты</types>",
              "<types>CatalogRef.Организации</types>", "<types>CatalogRef.ФизическиеЛица</types>"),
        *member("attributes", "Получатель", "<types>CatalogRef.Контрагенты</types>",
              "<types>CatalogRef.Организации</types>")))
    _, text, data = check(capsys, профиль, src, "--задача", "TASK-1")
    assert codes(data) == ["СОСТАВ-ТИПОВ-УЖЕ"], text


# --- нормализация ---------------------------------------------------------------------------


def нормализовать(capsys, *arguments):
    capsys.readouterr()
    code = main(["--нормализовать", *map(str, arguments)])
    return code, capsys.readouterr().out


def test_normalization_keeps_the_edt_format(tmp_path, capsys):
    """Нормализация приводит к принятому в проекте EDT: без BOM, LF; файл в норме
    не трогает и BOM ему не добавляет."""
    repo, src = проект(tmp_path)
    module = "CommonModules/мой_Н/Module.bsl"
    написать(src, "CommonModules/мой_Н/мой_Н.mdo", card("CommonModule", "мой_Н"))
    написать(src, module, ["Процедура А() Экспорт", "КонецПроцедуры"])
    code, text = нормализовать(capsys, src)
    assert code == 0, text
    написать(src, module, ["Процедура А() Экспорт", "КонецПроцедуры"], bom=True, eol="\r\n")
    code, text = нормализовать(capsys, src)
    assert code == 1 and "снять BOM" in text and "CRLF -> LF" in text, text
    assert нормализовать(capsys, src, "--apply")[0] == 0
    assert прочитать(src, module) == "Процедура А() Экспорт\nКонецПроцедуры\n".encode()
    assert нормализовать(capsys, src)[0] == 0             # идемпотентна


# --- сверка плана ---------------------------------------------------------------------------


def test_the_plan_is_checked_against_mdo(tmp_path, capsys):
    """План по факту читает состав `.mdo` с типами, и сверка его принимает."""
    repo, src = проект(tmp_path)
    написать(src, "InformationRegisters/мой_Остатки/мой_Остатки.mdo", card(
        "InformationRegister", "мой_Остатки",
        *member("resources", "Сумма", "<types>Number</types>", "<numberQualifiers>",
              "  <precision>15</precision>", "  <scale>2</scale>", "</numberQualifiers>"),
        *member("dimensions", "Договор", "<types>CatalogRef.ДоговорыКонтрагентов</types>"),
        *member("dimensions", "Вид", "<types>DefinedType.ВидДоговора</types>"),
        *member("attributes", "Комментарий", "<types>String</types>", "<stringQualifiers>",
              "  <length>200</length>", "</stringQualifiers>")))
    написать(src, "InformationRegisters/мой_Остатки/ManagerModule.bsl", [
        "Процедура Зарегистрировать() Экспорт", "КонецПроцедуры"])
    capsys.readouterr()
    assert main(["--план-по-факту", str(src)]) == 0
    plan = json.loads(capsys.readouterr().out)
    [obj] = [ob for ob in plan["объекты"] if ob["имя"] == "мой_Остатки"]
    assert obj["действие"] == "создать"
    assert obj["ресурсы"] == {"Сумма": ["Число(15,2)"]}
    assert obj["измерения"] == {"Договор": ["Справочник.ДоговорыКонтрагентов"],
                                   "Вид": ["ОпределяемыйТип.ВидДоговора"]}
    assert obj["реквизиты"] == {"Комментарий": ["Строка(200)"]}
    assert obj["модули"] == {"МодульМенеджера": ["Зарегистрировать"]}
    file = tmp_path / "план.json"
    file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    assert main(["--сверить-план", str(src), "--план", str(file)]) == 0
    plan["объекты"] = [ob for ob in plan["объекты"] if ob["имя"] != "мой_Остатки"] + [
        dict(obj, ресурсы={"Сумма": ["Строка(10)"]})]
    file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["--сверить-план", str(src), "--план", str(file)]) == 1
    assert "ПЛАН-ТИПЫ-РАСХОДЯТСЯ" in capsys.readouterr().out


# --- правка кода вставками ------------------------------------------------------------------


def test_code_apply_writes_an_edt_module_in_its_format_and_verify_accepts_it(tmp_path, capsys, профиль):
    """Модуль EDT называется адресом, лежит без `Ext`, остаётся без BOM и в LF —
    и проверка правок принимает записанное без находок."""
    repo, src = проект(tmp_path)
    job_spec = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.Вендорский.МодульОбъекта", "edits": [
                   {"line": 2, "lines": 1, "first_line": "\tЗначение = 1;", "last_line": "\tЗначение = 1;",
                    "code": "\tЗначение = 2;"}]},
                   {"модуль": "ОбщийМодуль.ВендорскийМодуль", "edits": [
                       {"line": 5, "lines": 0, "first_line": "#КонецОбласти",
                        "code": "Функция Новая() Экспорт\n\tВозврат 2;\nКонецФункции"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    assert main(["--apply", str(path), "--профиль", профиль]) == 0
    data = прочитать(src, ВЕНДОРСКИЙ)
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data
    assert "#TEAM Автор #TASK-1" in data.decode("utf-8")
    code, text, answer = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 0 and codes(answer) == [], text


def test_a_missing_edt_module_names_the_modules_the_object_has(tmp_path, capsys):
    """Модуля, которого у вида не бывает (набор записей у документа), правка не
    создаёт: отказ называет модули, которые у объекта есть."""
    repo, src = проект(tmp_path)
    job_spec = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.Вендорский.МодульНабораЗаписей", "edits": [
                   {"line": 1, "lines": 0, "first_line": "x", "code": "\tА = 1;"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    from meta.domain.model import Refuse

    with pytest.raises(Refuse, match="у объекта есть: Документ.Вендорский.МодульОбъекта"):
        main([str(path)])


def test_a_missing_module_of_an_existing_object_is_created_without_markers(tmp_path, capsys, профиль):
    """Модуль менеджера, которого у документа ещё нет: правка его создаёт — без
    BOM, переводы строк как у проекта, без меток (модуль создан задачей); ответ
    говорит, что модуль новый; проверка правок записанное принимает."""
    repo, src = проект(tmp_path)
    job_spec = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.Вендорский.МодульМенеджера", "edits": [
                   {"line": 1, "lines": 0, "code": "Функция Новая() Экспорт\n\tВозврат 1;\nКонецФункции"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["--apply", str(path), "--профиль", профиль]) == 0
    text = capsys.readouterr().out
    assert "новый: модуля не было, правка его создаёт" in text, text
    data = прочитать(src, "Documents/Вендорский/ManagerModule.bsl")
    assert data == "Функция Новая() Экспорт\n\tВозврат 1;\nКонецФункции\n".encode()
    code, text, answer = check(capsys, профиль, src, "--задача", "TASK-1")
    assert code == 0 and codes(answer) == [], text


def test_a_module_of_a_missing_object_is_not_created(tmp_path):
    repo, src = проект(tmp_path)
    job_spec = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.Нет.МодульМенеджера", "edits": [
                   {"line": 1, "lines": 0, "code": "А = 1;"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    from meta.domain.model import Refuse

    with pytest.raises(Refuse, match="в выгрузке нет"):
        main([str(path)])


# --- раскладка ------------------------------------------------------------------------------


def test_both_layouts_address_modules_the_same_way():
    """Адрес один, файлы разные: выгрузка — через `Ext`, EDT — без него; обратно
    путь даёт тот же адрес."""
    from meta.acl.modules import DESIGNER, EDT
    from meta.domain.modules import ModuleAddress

    случаи = [
        (ModuleAddress("ОбщийМодуль", "Х", "Модуль"), "CommonModules/Х/Ext/Module.bsl",
         "CommonModules/Х/Module.bsl"),
        (ModuleAddress("Документ", "Х", "МодульОбъекта"), "Documents/Х/Ext/ObjectModule.bsl",
         "Documents/Х/ObjectModule.bsl"),
        (ModuleAddress("Документ", "Х", "Форма", "Ф"), "Documents/Х/Forms/Ф/Ext/Form/Module.bsl",
         "Documents/Х/Forms/Ф/Module.bsl"),
        (ModuleAddress("Документ", "Х", "Команда", "К"), "Documents/Х/Commands/К/Ext/CommandModule.bsl",
         "Documents/Х/Commands/К/CommandModule.bsl"),
        (ModuleAddress("ОбщаяФорма", "Х", "Форма"), "CommonForms/Х/Ext/Form/Module.bsl",
         "CommonForms/Х/Module.bsl"),
        (ModuleAddress("ОбщаяКоманда", "Х", "МодульКоманды"), "CommonCommands/Х/Ext/CommandModule.bsl",
         "CommonCommands/Х/CommandModule.bsl"),
        (ModuleAddress("Конфигурация", "", "МодульСеанса"), "Ext/SessionModule.bsl",
         "Configuration/SessionModule.bsl"),
    ]
    for address, выгрузка, edt in случаи:
        assert "/".join(DESIGNER.module_file(address)) == выгрузка
        assert "/".join(EDT.module_file(address)) == edt
        assert DESIGNER.address_of_file(выгрузка.split("/")) == address
        assert EDT.address_of_file(edt.split("/")) == address
        assert EDT.address_of_file(выгрузка.split("/")) is None
