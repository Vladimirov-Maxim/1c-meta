"""Переименование: имя живёт в четырёх местах, и меняются все четыре.

Собственная карточка (`<Name>`, имена порождаемых типов, ввод по строке), имя
файла и каталога-спутника, запись в реестре конфигурации и каждая чужая
карточка со ссылкой. Сделать одно из четырёх — сломать конфигурацию, поэтому
операция отдельная, а не правка поля «имя».
"""

import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.application.rename.use_case import RenameUseCase  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.jobs import dialect as job_dialect  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402

CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.21">
\t<Catalog uuid="c1">
\t\t<InternalInfo>
\t\t\t<xr:GeneratedType name="CatalogRef.мой_Старое" category="Ref">
\t\t\t\t<xr:TypeId>t1</xr:TypeId>
\t\t\t\t<xr:ValueId>v1</xr:ValueId>
\t\t\t</xr:GeneratedType>
\t\t\t<xr:GeneratedType name="CatalogTabularSection.мой_Старое.Строки" category="TabularSection">
\t\t\t\t<xr:TypeId>t2</xr:TypeId>
\t\t\t\t<xr:ValueId>v2</xr:ValueId>
\t\t\t</xr:GeneratedType>
\t\t</InternalInfo>
\t\t<Properties>
\t\t\t<Name>мой_Старое</Name>
\t\t\t<InputByString>
\t\t\t\t<xr:Field>Catalog.мой_Старое.StandardAttribute.Code</xr:Field>
\t\t\t</InputByString>
\t\t</Properties>
\t\t<ChildObjects/>
\t</Catalog>
</MetaDataObject>"""

HOLDER = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">
\t<Document uuid="d1">
\t\t<Properties>
\t\t\t<Name>мой_Держатель</Name>
\t\t\t<Type>
\t\t\t\t<v8:Type>cfg:CatalogRef.мой_Старое</v8:Type>
\t\t\t</Type>
\t\t</Properties>
\t\t<ChildObjects/>
\t</Document>
</MetaDataObject>"""

REGISTRY = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
            "\t<Configuration>\n\t\t<ChildObjects>\n"
            "\t\t\t<Catalog>мой_Старое</Catalog>\n"
            "\t\t\t<Catalog>мой_Занято</Catalog>\n"
            "\t\t\t<Document>мой_Держатель</Document>\n"
            "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")


@pytest.fixture
def dump():
    root = tempfile.mkdtemp(prefix="meta-rename-")
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(REGISTRY)
    os.makedirs(os.path.join(root, "Catalogs"))
    os.makedirs(os.path.join(root, "Documents"))
    open(os.path.join(root, "Catalogs", "мой_Старое.xml"), "w",
         encoding="utf-8-sig", newline="").write(CATALOG)
    open(os.path.join(root, "Catalogs", "мой_Занято.xml"), "w",
         encoding="utf-8-sig", newline="").write(
             CATALOG.replace("мой_Старое", "мой_Занято"))
    open(os.path.join(root, "Documents", "мой_Держатель.xml"), "w",
         encoding="utf-8-sig", newline="").write(HOLDER)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def text_of(root, *parts):
    return open(os.path.join(root, *parts), encoding="utf-8-sig").read()


def rename(root, address, new_name, apply_now=True):
    return RenameUseCase(DesignerDump(root), ТЕСТ).execute(
        [job_dialect.rename_job_from_json({"путь": address, "имя": new_name})],
        apply_now=apply_now)


def test_own_card_is_rewritten_everywhere(dump):
    """Имя, порождаемые типы и ввод по строке — всё в одной карточке."""
    rename(dump, "Справочник.мой_Старое", "мой_Новое")
    card = text_of(dump, "Catalogs", "мой_Новое.xml")
    assert "мой_Старое" not in card
    assert "<Name>мой_Новое</Name>" in card
    assert 'name="CatalogRef.мой_Новое"' in card
    assert 'name="CatalogTabularSection.мой_Новое.Строки"' in card
    assert "Catalog.мой_Новое.StandardAttribute.Code" in card
    assert not os.path.exists(os.path.join(dump, "Catalogs", "мой_Старое.xml"))


def test_referencing_cards_are_rewritten(dump):
    rename(dump, "Справочник.мой_Старое", "мой_Новое")
    holder = text_of(dump, "Documents", "мой_Держатель.xml")
    assert "cfg:CatalogRef.мой_Новое" in holder
    assert "мой_Старое" not in holder


def test_registry_entry_moves_with_the_name(dump):
    rename(dump, "Справочник.мой_Старое", "мой_Новое")
    registry = text_of(dump, "Configuration.xml")
    assert "<Catalog>мой_Новое</Catalog>" in registry
    assert "мой_Старое" not in registry
    # запись осталась среди справочников, а не уехала к документам
    assert registry.index("<Catalog>мой_Новое</Catalog>") < registry.index("<Document>")


SCHEMA_WITH_QUERY = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<DataCompositionSchema'
    ' xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"'
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    '\t<dataSet xsi:type="DataSetQuery">\n'
    "\t\t<name>Набор</name>\n"
    "\t\t<query>ВЫБРАТЬ Ссылка ИЗ Справочник.мой_Старое</query>\n"
    "\t</dataSet>\n"
    "</DataCompositionSchema>")


def положить_схему(root):
    """Схема, где объект назван ТОЛЬКО в тексте запроса."""
    folder = os.path.join(root, "Documents", "мой_Держатель",
                          "Templates", "Отчёт", "Ext")
    os.makedirs(folder)
    путь = os.path.join(folder, "Template.xml")
    open(путь, "w", encoding="utf-8-sig", newline="").write(SCHEMA_WITH_QUERY)
    return путь


def test_a_name_used_only_in_a_query_is_reported(dump):
    """Текст запроса не переписывается — но и молчать о нём нельзя.

    Ссылки ищутся английским обозначением (`CatalogRef.Имя`), а запрос
    называет объект по-русски. Из 926 схем замеренной конфигурации в 608
    хотя бы один объект назван только так: без предупреждения переименование
    ответило бы «ссылок — 0» и оставило бы отчёт сломанным.
    """
    путь = положить_схему(dump)
    результат = rename(dump, "Справочник.мой_Старое", "мой_Новое")
    сказано = "\n".join(результат.plan.describe())
    assert "в текстах запросов" in сказано, сказано
    assert "макет Отчёт" in сказано, сказано
    # и сам текст запроса остался прежним: язык запросов инструмент не правит
    assert "Справочник.мой_Старое" in text_of(путь)


def test_a_query_mention_of_another_object_is_not_reported(dump):
    """Совпадение по имени соседа не считается: обозначение полное."""
    положить_схему(dump)
    результат = rename(dump, "Справочник.мой_Занято", "мой_Свободно")
    assert "в текстах запросов" not in "\n".join(результат.plan.describe())


def test_satellite_folder_moves_too(dump):
    """Модуль объекта переезжает вместе с ним, старый каталог не остаётся."""
    folder = os.path.join(dump, "Catalogs", "мой_Старое", "Ext")
    os.makedirs(folder)
    open(os.path.join(folder, "ObjectModule.bsl"), "w",
         encoding="utf-8-sig").write("// модуль")
    rename(dump, "Справочник.мой_Старое", "мой_Новое")
    assert os.path.isfile(os.path.join(dump, "Catalogs", "мой_Новое",
                                       "Ext", "ObjectModule.bsl"))
    assert not os.path.exists(os.path.join(dump, "Catalogs", "мой_Старое"))


def test_taken_name_is_refused(dump):
    result = rename(dump, "Справочник.мой_Старое", "мой_Занято", apply_now=False)
    assert [f.code for f in result.errors] == ["МД-ИМЯ-ЗАНЯТО"]
    assert os.path.isfile(os.path.join(dump, "Catalogs", "мой_Старое.xml"))


def test_new_name_obeys_the_prefix_rule(dump):
    result = rename(dump, "Справочник.мой_Старое", "Новое", apply_now=False)
    assert [f.code for f in result.errors] == ["МД-ПРЕФИКС"]


def test_invalid_name_is_refused(dump):
    result = rename(dump, "Справочник.мой_Старое", "мой Новое", apply_now=False)
    assert [f.code for f in result.errors] == ["МД-ИМЯ-НЕДОПУСТИМО"]


def test_only_whole_objects_are_renamed(dump):
    with pytest.raises(Refuse) as refusal:
        rename(dump, "Справочник.мой_Старое.Реквизит.Код", "Другое")
    assert "объект целиком" in str(refusal.value)


def test_preview_writes_nothing(dump):
    before = text_of(dump, "Catalogs", "мой_Старое.xml")
    rename(dump, "Справочник.мой_Старое", "мой_Новое", apply_now=False)
    assert text_of(dump, "Catalogs", "мой_Старое.xml") == before
    assert not os.path.exists(os.path.join(dump, "Catalogs", "мой_Новое.xml"))


def test_a_rename_preview_does_not_speak_of_defaults(dump):
    """Переименование обращается к существующему объекту: умолчаний у него нет."""
    from meta.report.result import result_lines

    сказано = "\n".join(result_lines(
        rename(dump, "Справочник.мой_Старое", "мой_Новое", apply_now=False)))
    assert "по умолчанию" not in сказано, сказано


def test_a_kind_whose_root_is_a_prefix_of_another_is_not_touched(dump):
    """`Document.Заявка` и `DocumentJournal.Заявка` — разные объекты.

    Корень одного вида бывает приставкой другого, и свободный хвост в
    обозначении переименовал бы журнал документов вместе с документом.
    Поэтому приставки перечислены, а не выведены как «любые буквы».
    """
    holder = os.path.join(dump, "Documents", "мой_Держатель.xml")
    open(holder, "w", encoding="utf-8-sig", newline="").write(
        HOLDER.replace("cfg:CatalogRef.мой_Старое",
                       "cfg:DocumentJournalRef.мой_Держатель"))
    assert DesignerDump(dump).references_to([("Документ", "мой_Держатель")]) == []


def test_unchanged_scope_is_said_out_loud(dump):
    result = rename(dump, "Справочник.мой_Старое", "мой_Новое", apply_now=False)
    codes = [f.code for f in result.findings]
    assert codes == ["ПЕРЕИМЕНОВАНИЕ-КОД-НЕ-ПРОВЕРЕН"]
    assert "код BSL" in result.findings[0].message


def test_batch_rename_does_not_lose_the_first(tmp_path):
    """Два переименования в одном задании, обе ссылки в одном документе.

    Вторая правка обязана работать с тем же деревом документа, что и первая,
    а не перечитывать его с диска: иначе она затрёт первую — в плане окажутся
    две записи на один путь, выиграет последняя, а старый файл к тому времени
    уже удалён. Останется висячая ссылка, конфигурация не загрузится, а `ok`
    при этом будет `True` и находок ноль.

    Одно дерево на файл — правило всех операций; этот тест держит его для
    переименования.
    """
    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects>\n"
        "\t\t\t<Catalog>мой_А</Catalog>\n\t\t\t<Catalog>мой_Б</Catalog>\n"
        "\t\t\t<Document>мой_Держатель</Document>\n"
        "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")
    os.makedirs(os.path.join(root, "Catalogs"))
    os.makedirs(os.path.join(root, "Documents"))
    for name in ("мой_А", "мой_Б"):
        open(os.path.join(root, "Catalogs", name + ".xml"), "w",
             encoding="utf-8-sig", newline="").write(
            CATALOG.replace("мой_Старое", name))
    open(os.path.join(root, "Documents", "мой_Держатель.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        HOLDER.replace("cfg:CatalogRef.мой_Старое",
                       "cfg:CatalogRef.мой_А</v8:Type>\n"
                       "\t\t\t\t<v8:Type>cfg:CatalogRef.мой_Б"))

    RenameUseCase(DesignerDump(root), ТЕСТ).execute([
        (job_dialect.path_from_json("Справочник.мой_А"), "мой_А2"),
        (job_dialect.path_from_json("Справочник.мой_Б"), "мой_Б2"),
    ], apply_now=True)

    holder = text_of(root, "Documents", "мой_Держатель.xml")
    assert "cfg:CatalogRef.мой_А2" in holder, "первое переименование затёрто"
    assert "cfg:CatalogRef.мой_Б2" in holder
    assert "мой_А<" not in holder and "мой_Б<" not in holder
    assert sorted(os.listdir(os.path.join(root, "Catalogs"))) == [
        "мой_А2.xml", "мой_Б2.xml"]
    registry = text_of(root, "Configuration.xml")
    assert "мой_А2" in registry and "мой_Б2" in registry
    assert "<Catalog>мой_А</Catalog>" not in registry


def test_rename_of_an_object_that_references_another_renamed_one(tmp_path):
    """Второй объект ссылается на первый — правка собственной карточки не теряется."""
    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects>\n"
        "\t\t\t<Catalog>мой_А</Catalog>\n"
        "\t\t\t<Document>мой_Б</Document>\n"
        "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")
    os.makedirs(os.path.join(root, "Catalogs"))
    os.makedirs(os.path.join(root, "Documents"))
    open(os.path.join(root, "Catalogs", "мой_А.xml"), "w",
         encoding="utf-8-sig", newline="").write(CATALOG.replace("мой_Старое", "мой_А"))
    open(os.path.join(root, "Documents", "мой_Б.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        HOLDER.replace("мой_Держатель", "мой_Б").replace("мой_Старое", "мой_А"))

    RenameUseCase(DesignerDump(root), ТЕСТ).execute([
        (job_dialect.path_from_json("Справочник.мой_А"), "мой_А2"),
        (job_dialect.path_from_json("Документ.мой_Б"), "мой_Б2"),
    ], apply_now=True)

    card = text_of(root, "Documents", "мой_Б2.xml")
    assert "cfg:CatalogRef.мой_А2" in card, "ссылка внутри переименованного потеряна"
    assert "<Name>мой_Б2</Name>" in card


def test_a_name_that_also_spells_a_notation_prefix_is_not_corrupted():
    """`Document` меняется как имя, а не как первое вхождение строки.

    У объекта с таким именем ссылка выглядит как `cfg:DocumentRef.Document`,
    и замена первого вхождения бьёт по приставке обозначения: получается
    `cfg:НовоеRef.Document` — вид, которого не существует, и конфигурация
    после такого переименования не грузится.
    """
    from meta.acl import mapping
    from meta.infra import repository

    pattern = mapping.reference_pattern([("Документ", "Document")])
    assert repository._rename_in(
        pattern, "<v8:Type>cfg:DocumentRef.Document</v8:Type>", "мой_Новый") == \
        "<v8:Type>cfg:DocumentRef.мой_Новый</v8:Type>"


def test_a_reference_in_the_registry_is_renamed_too(dump):
    """Ссылка в реестре вне раздела детей переписывается вместе с записью.

    Реестр правится один раз: запись раздела детей переставляет дерево,
    ссылки вне него переписывает обозначение. Двух писателей в один файл
    быть не должно — в плане оказались бы две записи на один путь.
    """
    registry_path = os.path.join(dump, "Configuration.xml")
    registry = open(registry_path, encoding="utf-8-sig").read()
    open(registry_path, "w", encoding="utf-8-sig", newline="").write(
        registry.replace(
            "\t</Configuration>",
            "\t\t<Properties>\n\t\t\t<DefaultCatalog>"
            "Catalog.мой_Старое</DefaultCatalog>\n"
            "\t\t</Properties>\n\t</Configuration>"))

    rename(dump, "Справочник.мой_Старое", "мой_Новое")
    стало = open(registry_path, encoding="utf-8-sig").read()
    assert "<DefaultCatalog>Catalog.мой_Новое</DefaultCatalog>" in стало
    assert "<Catalog>мой_Новое</Catalog>" in стало
    assert "мой_Старое" not in стало

