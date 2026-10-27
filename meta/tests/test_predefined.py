"""Предопределённые элементы справочника в проекте EDT — заданием `additions`.

В карточке `.mdo` они лежат блоком `predefined`: элемент `items` с
идентификатором, именем, наименованием (пустое EDT не пишет) и кодом — с
типом значения по типу кода справочника; группа — `isFolder`, её элементы —
`content`. Новый элемент ложится в конец блока (или группы), блока нет —
заводится на своём месте по метамодели. Остальная карточка не трогается.
В выгрузке конфигуратора предопределённые — отдельный файл, его инструмент
не ведёт: отказ. План изменений называет новые элементы группой
«предопределенные», сверка плана их проверяет.
"""

import json
import os
import random
import re
import subprocess
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import edt_model as _edt_model  # noqa: E402
from meta.add import main  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402

pytestmark = pytest.mark.skipif(not _edt_model.available(), reason="таблица метамодели EDT не сгенерирована: "
                                "py -3 tools/edt_model_from_xcore.py")

ПРОФИЛЬ = {"приставка": ["мой_"]}
MDCLASS = 'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass"'
ОБА = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:core="http://g5.1c.ru/v8/dt/mcore" ' + MDCLASS

РЕЕСТР = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Configuration {MDCLASS} uuid="f02dbb0b-64fd-42c8-a83c-d102640edbc0">
  <name>Конфигурация</name>
  <catalogs>Catalog.мой_Виды</catalogs>
  <catalogs>Catalog.мой_Пустой</catalogs>
  <catalogs>Catalog.мой_Числа</catalogs>
</mdclass:Configuration>
"""

ВИДЫ = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog {ОБА} uuid="7d1e2824-b889-41a0-a83e-d45103c58d47">
  <name>мой_Виды</name>
  <hierarchical>true</hierarchical>
  <codeLength>9</codeLength>
  <descriptionLength>80</descriptionLength>
  <codeType>String</codeType>
  <predefined>
    <items id="6b03b810-49bf-4115-99c0-f270108091b5">
      <name>Первый</name>
      <description>Первый вид</description>
      <code xsi:type="core:StringValue">
        <value>000000001</value>
      </code>
    </items>
    <items id="5b00370b-5540-4859-b689-0996f9fcfc6e">
      <name>Группа</name>
      <description>Группа видов</description>
      <code xsi:type="core:StringValue">
        <value></value>
      </code>
      <isFolder>true</isFolder>
    </items>
  </predefined>
</mdclass:Catalog>
"""

ПУСТОЙ = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog {MDCLASS} uuid="8d1e2824-b889-41a0-a83e-d45103c58d47">
  <name>мой_Пустой</name>
  <codeLength>9</codeLength>
  <descriptionLength>25</descriptionLength>
  <attributes uuid="f3d110c5-c64c-426a-9525-b612dbab0753">
    <name>Признак</name>
  </attributes>
</mdclass:Catalog>
"""

NUMBERS = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog {MDCLASS} uuid="9d1e2824-b889-41a0-a83e-d45103c58d47">
  <name>мой_Числа</name>
  <codeLength>5</codeLength>
  <codeType>Number</codeType>
</mdclass:Catalog>
"""


def написать(src, rel, text):
    path = os.path.join(str(src), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as файл:
        файл.write(text.encode("utf-8"))


def прочитать(src, rel):
    with open(os.path.join(str(src), *rel.split("/")), "rb") as файл:
        return файл.read().decode("utf-8")


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def проект(tmp_path, monkeypatch):
    src = tmp_path / "src"
    for rel, text in (("Configuration/Configuration.mdo", РЕЕСТР),
                       ("Catalogs/мой_Виды/мой_Виды.mdo", ВИДЫ),
                       ("Catalogs/мой_Пустой/мой_Пустой.mdo", ПУСТОЙ),
                       ("Catalogs/мой_Числа/мой_Числа.mdo", NUMBERS)):
        написать(src, rel, text)
    rng = random.Random(7)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    return src


def add(src, tmp_path, *пункты, apply=True):
    задание = {"repo": str(src), "additions": [
        {"путь": path, "вид": "ПредопределенныйЭлемент", "поля": fields} for path, fields in пункты]}
    файл = tmp_path / "задание.json"
    файл.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    профиль = tmp_path / "профиль.json"
    профиль.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return main([str(файл), "--профиль", str(профиль)] + (["--apply"] if apply else []))


def test_a_predefined_item_goes_to_the_end_of_the_block(проект, tmp_path):
    assert add(проект, tmp_path, ("Справочник.мой_Виды", {"имя": "Новый", "наименование": "Новый вид",
                                                                  "код": "000000003"})) == 0
    text = прочитать(проект, "Catalogs/мой_Виды/мой_Виды.mdo")
    new = """    <items id="{id}">
      <name>Новый</name>
      <description>Новый вид</description>
      <code xsi:type="core:StringValue">
        <value>000000003</value>
      </code>
    </items>
  </predefined>"""
    id_ = re.search(r'<items id="([0-9a-f-]{36})">\n      <name>Новый<', text).group(1)
    assert text == ВИДЫ.replace("  </predefined>", new.format(id=id_), 1)


def test_an_item_goes_into_its_parent_group(проект, tmp_path):
    assert add(проект, tmp_path, ("Справочник.мой_Виды", {"имя": "ВГруппе", "родитель": "Группа"})) == 0
    text = прочитать(проект, "Catalogs/мой_Виды/мой_Виды.mdo")
    assert """      <isFolder>true</isFolder>
      <content id=""" in text
    assert """        <name>ВГруппе</name>
        <code xsi:type="core:StringValue">
          <value></value>
        </code>
      </content>
    </items>
  </predefined>""" in text


def test_the_block_is_created_in_its_place_when_there_is_none(проект, tmp_path):
    assert add(проект, tmp_path, ("Справочник.мой_Пустой", {"имя": "Первый", "группа": True})) == 0
    text = прочитать(проект, "Catalogs/мой_Пустой/мой_Пустой.mdo")
    assert text.index("<descriptionLength>") < text.index("<predefined>") < text.index("<attributes")
    assert "<isFolder>true</isFolder>" in text and "<description>" not in text


def test_a_number_code_is_written_as_a_number(проект, tmp_path):
    assert add(проект, tmp_path, ("Справочник.мой_Числа", {"имя": "Один", "код": "1"})) == 0
    assert '<code xsi:type="core:NumberValue">\n        <value>1</value>' in прочитать(
        проект, "Catalogs/мой_Числа/мой_Числа.mdo")


@pytest.mark.parametrize("path, fields, сказано", [
    ("Справочник.мой_Виды", {"имя": "Первый"}, "уже есть"),
    ("Справочник.мой_Виды", {"имя": "Сирота", "родитель": "Первый"}, "группы «Первый»"),
    ("Справочник.мой_Числа", {"имя": "Буквы", "код": "А1"}, "не число"),
    ("Справочник.мой_Числа", {"имя": "Длинный", "код": "123456"}, "длиннее кода"),
])
def test_wrong_items_are_refused(проект, tmp_path, capsys, path, fields, сказано):
    before = {rel: прочитать(проект, rel) for rel in ("Catalogs/мой_Виды/мой_Виды.mdo",
                                                    "Catalogs/мой_Числа/мой_Числа.mdo")}
    try:
        code = add(проект, tmp_path, (path, fields))
        text = capsys.readouterr().out
    except Refuse as refusal:
        code, text = 2, str(refusal)
    assert code != 0 and сказано in text, text
    assert {rel: прочитать(проект, rel) for rel in before} == before


def test_the_plan_names_new_predefined_items_and_checks_them(проект, tmp_path, capsys):
    """План по факту называет новый предопределённый элемент; сверка находит
    незаявленный и принимает заявленный."""
    git(проект, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.safecrlf", "false")):
        git(проект, "config", key, value)
    git(проект, "add", "-A")
    git(проект, "commit", "-q", "-m", "база")
    assert add(проект, tmp_path, ("Справочник.мой_Виды", {"имя": "Новый"})) == 0

    ответ = tmp_path / "план.json"
    capsys.readouterr()
    main(["--план-по-факту", str(проект), "--json", str(ответ)])
    plan = json.loads(ответ.read_text(encoding="utf-8"))
    assert {"вид": "Справочник", "имя": "мой_Виды", "действие": "изменить",
            "предопределенные": ["Новый"]} in plan["объекты"], plan

    def reconcile(obj):
        файл = tmp_path / "заявлено.json"
        файл.write_text(json.dumps({"объекты": [obj]}, ensure_ascii=False), encoding="utf-8")
        отчёт = tmp_path / "сверка.json"
        main(["--сверить-план", str(проект), "--план", str(файл), "--json", str(отчёт)])
        return [f["код"] for f in json.loads(отчёт.read_text(encoding="utf-8"))["находки"]]

    assert reconcile({"вид": "Справочник", "имя": "мой_Виды", "действие": "изменить"}) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"]
    assert reconcile({"вид": "Справочник", "имя": "мой_Виды", "действие": "изменить",
                    "предопределенные": ["Новый"]}) == []


def test_a_configurator_dump_refuses_predefined_items(tmp_path, capsys):
    cf = tmp_path / "cf"
    написать(cf, "Configuration.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject/>\n')
    написать(cf, "Catalogs/мой_Виды.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
             '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.21">\n'
             '\t<Catalog uuid="7d1e2824-b889-41a0-a83e-d45103c58d47">\n'
             '\t\t<Properties>\n\t\t\t<Name>мой_Виды</Name>\n\t\t</Properties>\n'
             '\t</Catalog>\n</MetaDataObject>\n')
    try:
        code = add(cf, tmp_path, ("Справочник.мой_Виды", {"имя": "Новый"}))
        text = capsys.readouterr().out
    except Refuse as refusal:
        code, text = 2, str(refusal)
    assert code != 0 and "только в проект EDT" in text, text
