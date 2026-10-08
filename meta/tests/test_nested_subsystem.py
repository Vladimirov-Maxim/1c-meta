"""Вложенная подсистема: своя карточка в каталоге родителя.

В выгрузке — `Subsystems/Родитель/Subsystems/Дочерняя.xml`, в проекте EDT —
`Subsystems/Родитель/Subsystems/Дочерняя/Дочерняя.mdo`; в карточке родителя
о ней только имя. Адрес — цепочкой «Подсистема.Родитель.Подсистема.Дочерняя»:
так её называет и обратный поиск ссылок.
"""

import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import edt_model, vocabulary  # noqa: E402
from meta.add import main  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402
from meta.infra import layout  # noqa: E402

ЭТАЛОНЫ = os.path.join(ROOT, "meta", "tests", "эталоны")
ПРОФИЛЬ = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")
АДРЕС = "Подсистема.мой_Раздел.Подсистема.мой_Вложенный"

#: Запись в проект EDT без таблицы метамодели невозможна — такие тесты пропускаются.
с_edt = pytest.mark.skipif(not edt_model.available(), reason="таблица метамодели EDT не сгенерирована")


def задание(tmp_path, данные):
    путь = tmp_path / "задание.json"
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return [str(путь), "--apply", "--профиль", ПРОФИЛЬ]


def правка(root, состав):
    return {"repo": str(root), "changes": [{"путь": АДРЕС, "поля": {"состав": состав}}]}


@pytest.fixture
def проект(tmp_path):
    """Проект EDT из эталона и вложенная подсистема в «мой_Раздел»."""
    src = tmp_path / "src"
    shutil.copytree(os.path.join(ЭТАЛОНЫ, "edt", "ожидание"), src)
    родитель = src / "Subsystems" / "мой_Раздел"
    вложенная = родитель / "Subsystems" / "мой_Вложенный"
    вложенная.mkdir(parents=True)
    текст = (родитель / "мой_Раздел.mdo").read_text(encoding="utf-8")
    текст = (текст.replace("мой_Раздел", "мой_Вложенный")
             .replace("70e28184-043b-4405-b6af-f1fad2efa257", "70e28184-043b-4405-b6af-000000000001")
             .replace("  <content>Enum.мой_ВидыЗаявок</content>\n", ""))
    (вложенная / "мой_Вложенный.mdo").write_text(текст, encoding="utf-8", newline="\n")
    return src


@с_edt
def test_a_nested_subsystem_of_an_edt_project_is_edited_in_its_own_card(проект, tmp_path):
    родитель = (проект / "Subsystems" / "мой_Раздел" / "мой_Раздел.mdo").read_bytes()
    assert main(задание(tmp_path, правка(проект, {"добавить": [
        "Документ.мой_Заявка", "Роль.мой_атом_Документ_мой_Заявка_Просмотр"]}))) == 0
    текст = (проект / "Subsystems" / "мой_Раздел" / "Subsystems" / "мой_Вложенный"
             / "мой_Вложенный.mdo").read_text(encoding="utf-8")
    assert [s.strip() for s in текст.splitlines() if "<content>" in s] == [
        "<content>Catalog.мой_Пример</content>", "<content>Document.мой_Заявка</content>",
        "<content>Role.мой_атом_Документ_мой_Заявка_Просмотр</content>"]
    assert (проект / "Subsystems" / "мой_Раздел" / "мой_Раздел.mdo").read_bytes() == родитель


@с_edt
def test_a_role_in_the_composition_reads_back_in_russian(проект, tmp_path, capsys):
    """Роль в составе печатается «Роль.Имя» — так её и пишут в задании, и
    повторное добавление узнаётся, а не дублируется."""
    assert main(задание(tmp_path, правка(проект, {"добавить": [
        "Роль.мой_атом_Документ_мой_Заявка_Просмотр"]}))) == 0
    capsys.readouterr()
    assert main(задание(tmp_path, правка(проект, {"добавить": [
        "Роль.мой_атом_Документ_мой_Заявка_Просмотр"]}))) == 0
    assert "ПЕРЕЧЕНЬ-УЖЕ-ЕСТЬ" in capsys.readouterr().out


@с_edt
def test_a_missing_nested_subsystem_is_named_with_its_path(проект, tmp_path):
    with pytest.raises(Refuse, match="подсистемы нет"):
        main(задание(tmp_path, {"repo": str(проект), "changes": [
            {"путь": "Подсистема.мой_Раздел.Подсистема.мой_Нет", "поля": {
                "состав": {"добавить": ["Документ.мой_Заявка"]}}}]}))


def test_a_nested_subsystem_of_a_designer_dump(tmp_path):
    """Выгрузка конфигуратора: карточка вложенной — `Subsystems/Р/Subsystems/В.xml`."""
    from meta.infra.designer import DesignerDump
    root = tmp_path / "cf"
    папка = root / "Subsystems" / "Р" / "Subsystems"
    папка.mkdir(parents=True)
    (root / "Configuration.xml").write_text("<x/>", encoding="utf-8")
    (папка / "В.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.21">\n'
        '\t<Subsystem uuid="u1">\n\t\t<Properties>\n\t\t\t<Name>В</Name>\n'
        '\t\t\t<Content>\n\t\t\t\t<xr:Item xsi:type="xr:MDObjectRef">Role.мой_Роль</xr:Item>\n'
        '\t\t\t</Content>\n\t\t</Properties>\n\t\t<ChildObjects/>\n\t</Subsystem>\n</MetaDataObject>',
        encoding="utf-8-sig")
    spec, _ = DesignerDump(str(root)).read_spec([("Подсистема", "Р"), ("Подсистема", "В")])
    assert spec.get("состав") == ["Роль.мой_Роль"]


def test_every_object_folder_has_its_word():
    """Слова обозначений сверены с раскладкой: у каждого каталога выгрузки,
    кроме языков, есть слово — иначе состав подсистемы с объектом этого вида
    не записать и не прочитать по-русски."""
    for вид, слово in layout.RIGHTS_WORD.items():
        assert vocabulary.OBJECT_WORDS.get(вид) == слово, вид
