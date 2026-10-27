"""Таблица метамодели EDT: порядок свойств, атрибуты XML, умолчания.

Таблица снята с метамодели установленного EDT; правила, по которым EDT пишет
по ней файл (порядок EMF, `producedTypes` первым, умолчания не пишутся,
`Uuid` и идентификаторы — атрибутами), сверяются здесь с карточками, которые
записал сам EDT, — на образцах и, если задан проект (`META_EDT_CORPUS`), на
всех его карточках и формах.
"""

import importlib.util
import os
import sys

import pytest
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import edt_model  # noqa: E402
from meta.acl import edt_model as _edt_model  # noqa: E402

#: Таблица метамодели EDT не хранится в репозитории — без неё эти тесты не о чем.
pytestmark = pytest.mark.skipif(not _edt_model.available(), reason="таблица метамодели EDT не сгенерирована: "
                                "py -3 tools/edt_model_from_xcore.py")

MDCLASS = "com._1c.g5.v8.dt.metadata.mdclass."

#: Справочник, записанный EDT 2025.2 при импорте выгрузки (сокращён до порядка).
CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:core="http://g5.1c.ru/v8/dt/mcore" xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" uuid="0a9ab05b-6d3d-48cc-aa08-e73fdbfa3d35">
  <producedTypes>
    <objectType typeId="1564d18e-01b8-40d8-b46c-b09bfa151256" valueTypeId="884f1498-a7c7-4ab6-938a-3bcf3c0cc7c5"/>
  </producedTypes>
  <name>мой_Пример</name>
  <useStandardCommands>true</useStandardCommands>
  <fullTextSearchOnInputByString>DontUse</fullTextSearchOnInputByString>
  <createOnInput>Use</createOnInput>
  <levelCount>2</levelCount>
  <codeType>String</codeType>
  <attributes uuid="3be5dbdc-fb38-4914-bd29-f0c4e78e4001">
    <name>Комментарий</name>
    <type>
      <types>String</types>
      <stringQualifiers>
        <length>100</length>
      </stringQualifiers>
    </type>
    <minValue xsi:type="core:UndefinedValue"/>
    <fillValue xsi:type="core:StringValue"/>
    <fullTextSearch>Use</fullTextSearch>
    <dataHistory>Use</dataHistory>
  </attributes>
  <tabularSections uuid="832f69c1-0dbd-40de-9c52-886907ad4f36">
    <name>Строки</name>
    <attributes uuid="f0d98d82-6c64-45ac-a492-f7e93cc26191">
      <name>Дата</name>
      <dataHistory>Use</dataHistory>
      <fullTextSearch>Use</fullTextSearch>
    </attributes>
  </tabularSections>
</mdclass:Catalog>
"""


def _checker():
    path = os.path.join(ROOT, "tools", "edt_order_check.py")
    description = importlib.util.spec_from_file_location("edt_order_check", path)
    module = importlib.util.module_from_spec(description)
    description.loader.exec_module(module)
    return module


def test_produced_types_go_first_then_emf_order():
    names = [f.name for f in edt_model.features(MDCLASS + "Catalog")]
    assert names[0] == "producedTypes"
    assert names.index("uuid") < names.index("name") < names.index("useStandardCommands") \
        < names.index("levelCount") < names.index("attributes") < names.index("tabularSections")


def test_the_order_of_a_member_depends_on_its_class():
    """Реквизит справочника пишет историю данных после полнотекстового поиска,
    реквизит табличной части — до: у классов разные суперклассы."""
    def before_(cls_name, a, b):
        return edt_model.position(MDCLASS + cls_name, a) < edt_model.position(MDCLASS + cls_name, b)

    assert before_("CatalogAttribute", "fullTextSearch", "dataHistory")
    assert before_("TabularSectionAttribute", "dataHistory", "fullTextSearch")


def test_defaults_and_xml_attributes():
    f = edt_model.feature(MDCLASS + "Catalog", "codeType")
    assert edt_model.is_default(f, "Number") and not edt_model.is_default(f, "String")
    assert edt_model.is_default(edt_model.feature(MDCLASS + "Catalog", "hierarchical"), "false")
    assert edt_model.is_xml_attribute(edt_model.feature(MDCLASS + "Catalog", "uuid"))
    assert not edt_model.is_xml_attribute(edt_model.feature(MDCLASS + "Catalog", "name"))
    value = edt_model.feature("com._1c.g5.v8.dt.mcore.NumberValue", "value")
    assert not edt_model.is_default(value, "0")              # BigDecimal: умолчание — null


def test_a_card_written_by_edt_obeys_the_table():
    module, расхождения = _checker(), {}
    root = etree.fromstring(CATALOG.encode("utf-8"))
    from collections import defaultdict
    расхождения = defaultdict(list)
    module.check(root, module.class_of_element(root), "образец", расхождения)
    assert dict(расхождения) == {}


def test_a_card_out_of_order_is_caught():
    module = _checker()
    from collections import defaultdict
    расхождения = defaultdict(list)
    испорчена = CATALOG.replace("  <levelCount>2</levelCount>\n", "").replace(
        "  <attributes uuid=", "  <levelCount>2</levelCount>\n  <attributes uuid=", 1)
    root = etree.fromstring(испорчена.encode("utf-8"))
    module.check(root, module.class_of_element(root), "образец", расхождения)
    assert any(what == "порядок" for what, _ in расхождения)


@pytest.mark.skipif(not os.environ.get("META_EDT_CORPUS"), reason="не задан проект EDT META_EDT_CORPUS")
def test_every_card_and_form_of_the_project_obeys_the_table(capsys):
    module = _checker()
    os.environ["EDT_SUFFIXES"] = ".mdo,.form"
    module.SUFFIXES = (".mdo", ".form")
    module.main([os.environ["META_EDT_CORPUS"]])
    output = capsys.readouterr().out
    assert "видов расхождений: 0" in output, output
