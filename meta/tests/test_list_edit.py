"""Правка поля-перечня: «состав» подсистемы и «движения» документа.

При создании объекта перечень задаётся списком — объекта ещё нет, заменять
нечего. При правке существующего голый список заменял бы перечень целиком:
подсистема с десятками объектов теряла бы их молча, ответом «замечаний нет».
Поэтому в правке режим называется явно — добавить, убрать или заменить.
"""

import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.domain.model import ListEdit, Refuse  # noqa: E402
from meta.jobs import dialect  # noqa: E402

ЭТАЛОНЫ = os.path.join(ROOT, "meta", "tests", "эталоны")
ПРОФИЛЬ = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")


def задание(tmp_path, данные):
    путь = tmp_path / "задание.json"
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return [str(путь), "--apply", "--профиль", ПРОФИЛЬ]


@pytest.fixture
def выгрузка(tmp_path):
    """Пустая конфигурация, два справочника и подсистема с одним из них."""
    root = tmp_path / "cf"
    (root / "Languages").mkdir(parents=True)
    shutil.copy(os.path.join(ЭТАЛОНЫ, "формы", "Configuration.xml"), root)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import edt_oracle
    (root / "Languages" / "Русский.xml").write_text(edt_oracle.LANGUAGE, encoding="utf-8-sig")
    объекты = [{"вид": "Справочник", "поля": {"имя": имя, "синоним": имя}}
               for имя in ("мой_А", "мой_Б", "мой_В")]
    объекты.append({"вид": "Подсистема", "поля": {
        "имя": "мой_Раздел", "синоним": "Раздел", "включатьСправкуВСодержание": False,
        "включатьВКомандныйИнтерфейс": True, "состав": ["Справочник.мой_А", "Справочник.мой_Б"]}})
    assert main(задание(tmp_path, {"repo": str(root), "objects": объекты})) == 0
    return root


def состав(root):
    текст = (root / "Subsystems" / "мой_Раздел.xml").read_text(encoding="utf-8-sig")
    return [строка.strip() for строка in текст.splitlines() if "<xr:Item" in строка]


def правка(root, поле):
    return {"repo": str(root), "changes": [{"путь": "Подсистема.мой_Раздел", "поля": {"состав": поле}}]}


def test_a_bare_list_in_a_change_is_refused(выгрузка, tmp_path):
    """Голый список — отказ с подсказкой режимов; файл не тронут."""
    было = состав(выгрузка)
    with pytest.raises(Refuse, match="голый список заменил бы перечень целиком"):
        main(задание(tmp_path, правка(выгрузка, ["Справочник.мой_В"])))
    assert состав(выгрузка) == было


def test_add_keeps_what_was_there(выгрузка, tmp_path):
    """«добавить» дописывает в конец; прежние объекты на месте."""
    assert main(задание(tmp_path, правка(выгрузка, {"добавить": ["Справочник.мой_В"]}))) == 0
    assert [x.split(">")[1].split("<")[0] for x in состав(выгрузка)] == [
        "Catalog.мой_А", "Catalog.мой_Б", "Catalog.мой_В"]


def test_remove_drops_only_what_is_named(выгрузка, tmp_path):
    assert main(задание(tmp_path, правка(выгрузка, {"убрать": ["Справочник.мой_А"]}))) == 0
    assert [x.split(">")[1].split("<")[0] for x in состав(выгрузка)] == ["Catalog.мой_Б"]


def test_removing_what_is_absent_is_an_error(выгрузка, tmp_path, capsys):
    было = состав(выгрузка)
    assert main(задание(tmp_path, правка(выгрузка, {"убрать": ["Справочник.мой_В"]}))) != 0
    assert "ПЕРЕЧЕНЬ-УБРАТЬ-НЕТ" in capsys.readouterr().out
    assert состав(выгрузка) == было


def test_an_added_object_must_exist(выгрузка, tmp_path, capsys):
    """Добавляемое проверяется, как при создании: несуществующего — нельзя."""
    assert main(задание(tmp_path, правка(выгрузка, {"добавить": ["Справочник.мой_Нет"]}))) != 0
    assert "ПОДСИСТЕМА-СОСТАВ-НЕТ" in capsys.readouterr().out


def test_adding_what_is_there_is_a_warning_not_a_duplicate(выгрузка, tmp_path, capsys):
    было = состав(выгрузка)
    assert main(задание(tmp_path, правка(выгрузка, {"добавить": ["Справочник.мой_А"]}))) == 0
    assert "ПЕРЕЧЕНЬ-УЖЕ-ЕСТЬ" in capsys.readouterr().out
    assert состав(выгрузка) == было


def test_replace_is_explicit_and_names_what_leaves(выгрузка, tmp_path, capsys):
    """«заменить» — можно, но ответ называет, что уходит."""
    assert main(задание(tmp_path, правка(выгрузка, {"заменить": ["Справочник.мой_В"]}))) == 0
    assert "уходит 2: Справочник.мой_А, Справочник.мой_Б" in capsys.readouterr().out
    assert [x.split(">")[1].split("<")[0] for x in состав(выгрузка)] == ["Catalog.мой_В"]


@pytest.mark.parametrize("значение, слова", [
    ({"заменить": [], "добавить": []}, "один, без"),
    ({"добавлять": []}, "ключи правки перечня"),
    ({"добавить": "Справочник.мой_А"}, "список обозначений"),
])
def test_malformed_list_edits_are_refused(значение, слова):
    with pytest.raises(Refuse, match=слова):
        dialect.change_job_from_json({"путь": "Подсистема.мой_Раздел", "поля": {"состав": значение}})


def test_creation_still_takes_a_plain_list():
    """При создании список — сам перечень: заменять нечего."""
    spec = dialect.spec_from_json({"вид": "Подсистема", "поля": {
        "имя": "мой_Р", "синоним": "Р", "состав": ["Справочник.мой_А"]}})
    assert spec.get("состав") == ["Справочник.мой_А"]


def test_list_edit_order_and_duplicates():
    правка_ = ListEdit(add=["В", "А"], remove=["Б"])
    assert правка_.applied(["А", "Б"]) == (["А", "В"], ["А"], [])
