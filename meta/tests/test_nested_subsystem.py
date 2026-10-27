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

GOLDEN = os.path.join(ROOT, "meta", "tests", "эталоны")
PROFILE = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")
ADDRESS = "Подсистема.мой_Раздел.Подсистема.мой_Вложенный"

#: Запись в проект EDT без таблицы метамодели невозможна — такие тесты пропускаются.
with_edt = pytest.mark.skipif(not edt_model.available(), reason="таблица метамодели EDT не сгенерирована")


def job_spec(tmp_path, data):
    path = tmp_path / "задание.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return [str(path), "--apply", "--профиль", PROFILE]


def edit_job(root, composition):
    return {"repo": str(root), "changes": [{"путь": ADDRESS, "поля": {"состав": composition}}]}


@pytest.fixture
def project(tmp_path):
    """Проект EDT из эталона и вложенная подсистема в «мой_Раздел»."""
    src = tmp_path / "src"
    shutil.copytree(os.path.join(GOLDEN, "edt", "ожидание"), src)
    parent = src / "Subsystems" / "мой_Раздел"
    nested_one = parent / "Subsystems" / "мой_Вложенный"
    nested_one.mkdir(parents=True)
    text = (parent / "мой_Раздел.mdo").read_text(encoding="utf-8")
    text = (text.replace("мой_Раздел", "мой_Вложенный")
             .replace("70e28184-043b-4405-b6af-f1fad2efa257", "70e28184-043b-4405-b6af-000000000001")
             .replace("  <content>Enum.мой_ВидыЗаявок</content>\n", ""))
    (nested_one / "мой_Вложенный.mdo").write_text(text, encoding="utf-8", newline="\n")
    return src


@with_edt
def test_a_nested_subsystem_of_an_edt_project_is_edited_in_its_own_card(project, tmp_path):
    parent = (project / "Subsystems" / "мой_Раздел" / "мой_Раздел.mdo").read_bytes()
    assert main(job_spec(tmp_path, edit_job(project, {"добавить": [
        "Документ.мой_Заявка", "Роль.мой_атом_Документ_мой_Заявка_Просмотр"]}))) == 0
    text = (project / "Subsystems" / "мой_Раздел" / "Subsystems" / "мой_Вложенный"
             / "мой_Вложенный.mdo").read_text(encoding="utf-8")
    assert [s.strip() for s in text.splitlines() if "<content>" in s] == [
        "<content>Catalog.мой_Пример</content>", "<content>Document.мой_Заявка</content>",
        "<content>Role.мой_атом_Документ_мой_Заявка_Просмотр</content>"]
    assert (project / "Subsystems" / "мой_Раздел" / "мой_Раздел.mdo").read_bytes() == parent


@with_edt
def test_a_role_in_the_composition_reads_back_in_russian(project, tmp_path, capsys):
    """Роль в составе печатается «Роль.Имя» — так её и пишут в задании, и
    повторное добавление узнаётся, а не дублируется."""
    assert main(job_spec(tmp_path, edit_job(project, {"добавить": [
        "Роль.мой_атом_Документ_мой_Заявка_Просмотр"]}))) == 0
    capsys.readouterr()
    assert main(job_spec(tmp_path, edit_job(project, {"добавить": [
        "Роль.мой_атом_Документ_мой_Заявка_Просмотр"]}))) == 0
    assert "ПЕРЕЧЕНЬ-УЖЕ-ЕСТЬ" in capsys.readouterr().out


@with_edt
def test_a_missing_nested_subsystem_is_named_with_its_path(project, tmp_path):
    with pytest.raises(Refuse, match="подсистемы нет"):
        main(job_spec(tmp_path, {"repo": str(project), "changes": [
            {"путь": "Подсистема.мой_Раздел.Подсистема.мой_Нет", "поля": {
                "состав": {"добавить": ["Документ.мой_Заявка"]}}}]}))


def test_a_nested_subsystem_of_a_designer_dump(tmp_path):
    """Выгрузка конфигуратора: карточка вложенной — `Subsystems/Р/Subsystems/В.xml`."""
    from meta.infra.designer import DesignerDump
    root = tmp_path / "cf"
    folder = root / "Subsystems" / "Р" / "Subsystems"
    folder.mkdir(parents=True)
    (root / "Configuration.xml").write_text("<x/>", encoding="utf-8")
    (folder / "В.xml").write_text(
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
    for kind, word in layout.RIGHTS_WORD.items():
        assert vocabulary.OBJECT_WORDS.get(kind) == word, kind
