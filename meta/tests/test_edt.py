"""Проект EDT: проверка правок, нормализация, сверка плана и правка кода — на
синтетическом проекте в подкаталоге git-репозитория.

Проект EDT отличается от выгрузки конфигуратора раскладкой и видом текста:
объект — `<Каталог>/<Имя>/<Имя>.mdo`, модули — в каталоге объекта без `Ext`,
права роли — `Roles/<Роль>/Rights.rights`, файлы — UTF-8 без BOM и LF.
Исходники лежат глубже корня репозитория (`BF/src`), и пути находок — от них.

Кейсы — те же, что у выгрузки (`test_verify.py`), и кейсы конвейера для EDT:
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


def написать(root, rel, строки, eol="\n", bom=False, final=True):
    путь = os.path.join(str(root), *rel.split("/"))
    os.makedirs(os.path.dirname(путь), exist_ok=True)
    текст = eol.join(строки) + (eol if final else "")
    with open(путь, "wb") as файл:
        файл.write((b"\xef\xbb\xbf" if bom else b"") + текст.encode("utf-8"))


def прочитать(root, rel):
    with open(os.path.join(str(root), *rel.split("/")), "rb") as файл:
        return файл.read()


def карточка(вид, имя, *дети):
    """Карточка `.mdo`: корень вида, имя и дети — уже готовыми строками."""
    return ['<?xml version="1.0" encoding="UTF-8"?>',
            f'<mdclass:{вид} xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" {MDCLASS} '
            f'uuid="7d1e2824-b889-41a0-a83e-d45103c58d47">',
            f"  <name>{имя}</name>", *дети, f"</mdclass:{вид}>"]


def член(тег, имя, *типы):
    """Ребёнок карточки с типом: `типы` — строки внутри `<type>`."""
    return [f'  <{тег} uuid="f3d110c5-c64c-426a-9525-b612dbab0753">', f"    <name>{имя}</name>",
            "    <type>", *[f"      {т}" for т in типы], "    </type>", f"  </{тег}>"]


def права(объект):
    return ['<?xml version="1.0" encoding="UTF-8"?>',
            '<Rights xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://v8.1c.ru/8.2/roles" '
            'xsi:type="Rights">',
            "\t<object>", f"\t\t<name>{объект}</name>", "\t\t<right>", "\t\t\t<name>Read</name>",
            "\t\t\t<value>true</value>", "\t\t</right>", "\t</object>", "</Rights>"]


def зафиксировать(repo, сообщение="базлайн"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", сообщение)


def проект(tmp_path, autocrlf=False):
    """(репозиторий, исходники): проект EDT в `BF/src`, вендорский документ и модуль в базе."""
    repo = tmp_path / "repo"
    src = repo / "BF" / "src"
    src.mkdir(parents=True)
    git(repo, "init", "-q")
    for ключ, значение in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "true" if autocrlf else "false"),
                           ("core.quotepath", "false")):
        git(repo, "config", ключ, значение)
    написать(repo, "BF/DT-INF/PROJECT.PMF", ["Manifest-Version: 1.0"])
    написать(src, "Configuration/Configuration.mdo", карточка("Configuration", "Конфигурация"))
    написать(src, "Documents/Вендорский/Вендорский.mdo", карточка("Document", "Вендорский"))
    написать(src, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                               "\tЗначение = 1;", "КонецПроцедуры"])
    написать(src, "CommonModules/ВендорскийМодуль/ВендорскийМодуль.mdo",
             карточка("CommonModule", "ВендорскийМодуль"))
    написать(src, "CommonModules/ВендорскийМодуль/Module.bsl", [
        "#Область ПрограммныйИнтерфейс", "Функция Публичный() Экспорт", "\tВозврат 1;", "КонецФункции",
        "#КонецОбласти"])
    зафиксировать(repo)
    return repo, src


@pytest.fixture
def профиль(tmp_path):
    путь = tmp_path / "профиль.json"
    путь.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(путь)


def проверить(capsys, профиль, *аргументы):
    """(код возврата, текст, ответ JSON)."""
    ответ = os.path.join(os.path.dirname(профиль), "ответ.json")
    if os.path.exists(ответ):
        os.remove(ответ)
    capsys.readouterr()
    код = main(["--проверить", *map(str, аргументы), "--профиль", профиль, "--json", ответ])
    текст = capsys.readouterr().out
    данные = json.load(open(ответ, encoding="utf-8")) if os.path.exists(ответ) else None
    return код, текст, данные


def коды(данные):
    return sorted(f["код"] for f in данные["находки"])


# --- проверка правок ------------------------------------------------------------------------


def test_paths_are_from_the_sources_and_files_outside_them_are_not_in_scope(tmp_path, capsys, профиль):
    """Исходники в подкаталоге репозитория: пути — от них, служебный файл проекта
    выше них в предмет проверок не входит; новый `.mdo` без приставки пойман."""
    repo, src = проект(tmp_path)
    написать(repo, "BF/DT-INF/PROJECT.PMF", ["Manifest-Version: 2.0"])
    написать(src, "Catalogs/Чужой/Чужой.mdo", карточка("Catalog", "Чужой"))
    код, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 1 and коды(данные) == ["МД-ПРЕФИКС", "ПРАВА-НЕ-ВЫДАНЫ"], текст
    [приставка] = [f for f in данные["находки"] if f["код"] == "МД-ПРЕФИКС"]
    assert приставка["файл"] == "Catalogs/Чужой/Чужой.mdo"
    assert "A  Catalogs/Чужой/Чужой.mdo" in текст and "PROJECT.PMF" not in текст
    assert данные["источник"].startswith("проект EDT")


def test_a_new_object_needs_a_right_in_rights_rights(tmp_path, capsys, профиль):
    """Права на новый объект ищутся в `Roles/<Роль>/Rights.rights`."""
    repo, src = проект(tmp_path)
    написать(src, "Catalogs/мой_Новый/мой_Новый.mdo", карточка("Catalog", "мой_Новый"))
    _, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert коды(данные) == ["ПРАВА-НЕ-ВЫДАНЫ"], текст
    написать(src, "Roles/мой_атом_Новый/мой_атом_Новый.mdo", карточка("Role", "мой_атом_Новый"))
    написать(src, "Roles/мой_атом_Новый/Rights.rights", права("Catalog.мой_Новый"))
    код, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 0 and коды(данные) == [], текст
    # право только в чужой роли — своё нарушение
    os.remove(os.path.join(src, "Roles", "мой_атом_Новый", "Rights.rights"))
    написать(src, "Roles/Чужая/Rights.rights", права("Catalog.мой_Новый"))
    _, _, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert "ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ" in коды(данные)


def test_an_unwrapped_edit_of_a_module_without_ext_is_found(tmp_path, capsys, профиль):
    repo, src = проект(tmp_path)
    написать(src, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                               "\tЗначение = 42;", "КонецПроцедуры"])
    код, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 1 and коды(данные) == ["ПРАВКА-ВНЕ-ВСТАВКИ"], текст
    assert данные["находки"][0]["файл"] == ВЕНДОРСКИЙ


def test_revisions_are_read_from_the_subfolder(tmp_path, capsys, профиль):
    """Ревизия против базы: файлы читаются `show <ревизия>:./<путь>` из подкаталога."""
    repo, src = проект(tmp_path)
    база = git(repo, "rev-parse", "HEAD")
    написать(src, ВЕНДОРСКИЙ, ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)",
                               "\tЗначение = 42;", "КонецПроцедуры"])
    написать(src, "CommonModules/мой_Новый/мой_Новый.mdo", карточка("CommonModule", "мой_Новый"))
    написать(src, "CommonModules/мой_Новый/Module.bsl", ["Функция Посчитать() Экспорт", "\tВозврат 1;",
                                                         "КонецФункции"])
    зафиксировать(repo, "задача")
    код, текст, данные = проверить(capsys, профиль, src, "--база", база, "--ревизия", "HEAD",
                                   "--задача", "TASK-1")
    assert код == 1 and коды(данные) == ["ПРАВКА-ВНЕ-ВСТАВКИ"], текст
    assert "A  CommonModules/мой_Новый/Module.bsl" in текст and f"M  {ВЕНДОРСКИЙ}" in текст


def test_bom_is_checked_against_the_repository(tmp_path, capsys, профиль):
    """В проекте EDT файлы без BOM: отсутствие — норма, BOM — нарушение."""
    repo, src = проект(tmp_path)
    написать(src, "CommonModules/мой_БезBOM/мой_БезBOM.mdo", карточка("CommonModule", "мой_БезBOM"))
    написать(src, "CommonModules/мой_БезBOM/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"])
    код, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 0 and коды(данные) == [], текст
    написать(src, "CommonModules/мой_БезBOM/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"],
             bom=True)
    код, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 1 and коды(данные) == ["ФАЙЛ-ЛИШНИЙ-BOM"], текст
    assert "лишний BOM: CommonModules/мой_БезBOM/Module.bsl" in текст


def test_line_endings_are_those_of_the_repository(tmp_path, capsys, профиль):
    repo, src = проект(tmp_path)
    написать(src, "CommonModules/мой_М/мой_М.mdo", карточка("CommonModule", "мой_М"))
    написать(src, "CommonModules/мой_М/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"], eol="\r\n")
    _, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert коды(данные) == ["ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"], текст


def test_the_service_file_rule_is_not_applicable_and_does_not_make_the_run_incomplete(
        tmp_path, capsys, профиль):
    repo, src = проект(tmp_path)
    код, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 0 and "ЧИСТО" in текст and данные["пропущено"] == [], текст
    assert any("ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ" in пояснение for пояснение in данные["пояснения"])


def test_type_sets_of_new_members_are_read_from_mdo(tmp_path, capsys, профиль):
    """Составы типов новых членов читаются из карточки `.mdo`."""
    repo, src = проект(tmp_path)
    написать(src, "Catalogs/мой_А/мой_А.mdo", карточка("Catalog", "мой_А"))
    написать(src, "Roles/мой_Р/Rights.rights", права("Catalog.мой_А"))
    зафиксировать(repo, "прошлая задача")
    написать(src, "Catalogs/мой_А/мой_А.mdo", карточка(
        "Catalog", "мой_А",
        *член("attributes", "Источник", "<types>CatalogRef.Контрагенты</types>",
              "<types>CatalogRef.Организации</types>", "<types>CatalogRef.ФизическиеЛица</types>"),
        *член("attributes", "Получатель", "<types>CatalogRef.Контрагенты</types>",
              "<types>CatalogRef.Организации</types>")))
    _, текст, данные = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert коды(данные) == ["СОСТАВ-ТИПОВ-УЖЕ"], текст


# --- нормализация ---------------------------------------------------------------------------


def нормализовать(capsys, *аргументы):
    capsys.readouterr()
    код = main(["--нормализовать", *map(str, аргументы)])
    return код, capsys.readouterr().out


def test_normalization_keeps_the_edt_format(tmp_path, capsys):
    """Нормализация приводит к принятому в проекте EDT: без BOM, LF; файл в норме
    не трогает и BOM ему не добавляет."""
    repo, src = проект(tmp_path)
    модуль = "CommonModules/мой_Н/Module.bsl"
    написать(src, "CommonModules/мой_Н/мой_Н.mdo", карточка("CommonModule", "мой_Н"))
    написать(src, модуль, ["Процедура А() Экспорт", "КонецПроцедуры"])
    код, текст = нормализовать(capsys, src)
    assert код == 0, текст
    написать(src, модуль, ["Процедура А() Экспорт", "КонецПроцедуры"], bom=True, eol="\r\n")
    код, текст = нормализовать(capsys, src)
    assert код == 1 and "снять BOM" in текст and "CRLF -> LF" in текст, текст
    assert нормализовать(capsys, src, "--apply")[0] == 0
    assert прочитать(src, модуль) == "Процедура А() Экспорт\nКонецПроцедуры\n".encode()
    assert нормализовать(capsys, src)[0] == 0             # идемпотентна


# --- сверка плана ---------------------------------------------------------------------------


def test_the_plan_is_checked_against_mdo(tmp_path, capsys):
    """План по факту читает состав `.mdo` с типами, и сверка его принимает."""
    repo, src = проект(tmp_path)
    написать(src, "InformationRegisters/мой_Остатки/мой_Остатки.mdo", карточка(
        "InformationRegister", "мой_Остатки",
        *член("resources", "Сумма", "<types>Number</types>", "<numberQualifiers>",
              "  <precision>15</precision>", "  <scale>2</scale>", "</numberQualifiers>"),
        *член("dimensions", "Договор", "<types>CatalogRef.ДоговорыКонтрагентов</types>"),
        *член("dimensions", "Вид", "<types>DefinedType.ВидДоговора</types>"),
        *член("attributes", "Комментарий", "<types>String</types>", "<stringQualifiers>",
              "  <length>200</length>", "</stringQualifiers>")))
    написать(src, "InformationRegisters/мой_Остатки/ManagerModule.bsl", [
        "Процедура Зарегистрировать() Экспорт", "КонецПроцедуры"])
    capsys.readouterr()
    assert main(["--план-по-факту", str(src)]) == 0
    план = json.loads(capsys.readouterr().out)
    [объект] = [о for о in план["объекты"] if о["имя"] == "мой_Остатки"]
    assert объект["действие"] == "создать"
    assert объект["ресурсы"] == {"Сумма": ["Число(15,2)"]}
    assert объект["измерения"] == {"Договор": ["Справочник.ДоговорыКонтрагентов"],
                                   "Вид": ["ОпределяемыйТип.ВидДоговора"]}
    assert объект["реквизиты"] == {"Комментарий": ["Строка(200)"]}
    assert объект["модули"] == {"МодульМенеджера": ["Зарегистрировать"]}
    файл = tmp_path / "план.json"
    файл.write_text(json.dumps(план, ensure_ascii=False), encoding="utf-8")
    assert main(["--сверить-план", str(src), "--план", str(файл)]) == 0
    план["объекты"] = [о for о in план["объекты"] if о["имя"] != "мой_Остатки"] + [
        dict(объект, ресурсы={"Сумма": ["Строка(10)"]})]
    файл.write_text(json.dumps(план, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["--сверить-план", str(src), "--план", str(файл)]) == 1
    assert "ПЛАН-ТИПЫ-РАСХОДЯТСЯ" in capsys.readouterr().out


# --- правка кода вставками ------------------------------------------------------------------


def test_code_apply_writes_an_edt_module_in_its_format_and_verify_accepts_it(tmp_path, capsys, профиль):
    """Модуль EDT называется адресом, лежит без `Ext`, остаётся без BOM и в LF —
    и проверка правок принимает записанное без находок."""
    repo, src = проект(tmp_path)
    задание = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.Вендорский.МодульОбъекта", "edits": [
                   {"line": 2, "lines": 1, "first_line": "\tЗначение = 1;", "last_line": "\tЗначение = 1;",
                    "code": "\tЗначение = 2;"}]},
                   {"модуль": "ОбщийМодуль.ВендорскийМодуль", "edits": [
                       {"line": 5, "lines": 0, "first_line": "#КонецОбласти",
                        "code": "Функция Новая() Экспорт\n\tВозврат 2;\nКонецФункции"}]}]}
    путь = tmp_path / "код.json"
    путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    assert main(["--apply", str(путь), "--профиль", профиль]) == 0
    данные = прочитать(src, ВЕНДОРСКИЙ)
    assert not данные.startswith(b"\xef\xbb\xbf") and b"\r\n" not in данные
    assert "#TEAM Автор #TASK-1" in данные.decode("utf-8")
    код, текст, ответ = проверить(capsys, профиль, src, "--задача", "TASK-1")
    assert код == 0 and коды(ответ) == [], текст


def test_a_missing_edt_module_names_the_modules_the_object_has(tmp_path, capsys):
    repo, src = проект(tmp_path)
    задание = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.Вендорский.МодульМенеджера", "edits": [
                   {"line": 1, "lines": 0, "first_line": "x", "code": "\tА = 1;"}]}]}
    путь = tmp_path / "код.json"
    путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    from meta.domain.model import Refuse

    with pytest.raises(Refuse, match="у объекта есть: Документ.Вендорский.МодульОбъекта"):
        main([str(путь)])


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
    for адрес, выгрузка, edt in случаи:
        assert "/".join(DESIGNER.module_file(адрес)) == выгрузка
        assert "/".join(EDT.module_file(адрес)) == edt
        assert DESIGNER.address_of_file(выгрузка.split("/")) == адрес
        assert EDT.address_of_file(edt.split("/")) == адрес
        assert EDT.address_of_file(выгрузка.split("/")) is None
