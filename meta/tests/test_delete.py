"""Удаление: обратный поиск ссылок, вырезание узла, снятие объекта целиком.

Главный инвариант операции — «не удалять то, на что ссылаются». Он держится
не на аккуратности удаляющего, а на обратном поиске по выгрузке: обозначение
ссылки одно на все места, где имя встречается, и ищется оно везде, где ссылки
бывают, — в карточках объектов и в правах ролей.

Чего поиск не покрывает, сказано вслух и проверено тестом: формы и код BSL
инструмент не смотрит. Молчать об этом хуже, чем отказаться проверять.
"""

import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.application.delete.use_case import DeleteUseCase  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.jobs import dialect as job_dialect  # noqa: E402

CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">
\t<Catalog uuid="c1">
\t\t<Properties>
\t\t\t<Name>мой_Цель</Name>
\t\t</Properties>
\t\t<ChildObjects>
\t\t\t<Attribute uuid="a1">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Первый</Name>
\t\t\t\t</Properties>
\t\t\t</Attribute>
\t\t\t<TabularSection uuid="t1">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Строки</Name>
\t\t\t\t</Properties>
\t\t\t\t<ChildObjects>
\t\t\t\t\t<Attribute uuid="a2">
\t\t\t\t\t\t<Properties>
\t\t\t\t\t\t\t<Name>Вложенный</Name>
\t\t\t\t\t\t</Properties>
\t\t\t\t\t</Attribute>
\t\t\t\t</ChildObjects>
\t\t\t</TabularSection>
\t\t</ChildObjects>
\t</Catalog>
</MetaDataObject>"""

# Карточка-держатель: её реквизит ссылается на `мой_Цель`.
HOLDER = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">
\t<Document uuid="d1">
\t\t<Properties>
\t\t\t<Name>мой_Держатель</Name>
\t\t\t<Type>
\t\t\t\t<v8:Type>cfg:CatalogRef.мой_Цель</v8:Type>
\t\t\t</Type>
\t\t</Properties>
\t\t<ChildObjects/>
\t</Document>
</MetaDataObject>"""

REGISTRY = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
            "\t<Configuration>\n\t\t<ChildObjects>\n"
            "\t\t\t<Catalog>мой_Цель</Catalog>\n"
            "\t\t\t<Catalog>мой_Свободный</Catalog>\n"
            "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")

FREE = CATALOG.replace("мой_Цель", "мой_Свободный")


@pytest.fixture
def dump(request):
    """Выгрузка из трёх карточек. `holder` в метке — добавить держателя ссылки."""
    root = tempfile.mkdtemp(prefix="meta-delete-")
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(REGISTRY)
    os.makedirs(os.path.join(root, "Catalogs"))
    for name, text in (("мой_Цель", CATALOG), ("мой_Свободный", FREE)):
        open(os.path.join(root, "Catalogs", name + ".xml"), "w",
             encoding="utf-8-sig", newline="").write(text)
    if "holder" in request.keywords:
        os.makedirs(os.path.join(root, "Documents"))
        open(os.path.join(root, "Documents", "мой_Держатель.xml"), "w",
             encoding="utf-8-sig", newline="").write(HOLDER)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def card_of(root, name="мой_Цель", folder="Catalogs"):
    return open(os.path.join(root, folder, name + ".xml"),
                encoding="utf-8-sig").read().replace("\r\n", "\n")


def delete(root, address, apply_now=True):
    return DeleteUseCase(DesignerDump(root)).execute(
        [job_dialect.delete_job_from_json(address)], apply_now=apply_now)


def card(root, folder, name, text):
    """Положить карточку в выгрузку: `<каталог>/<путь>.xml`, BOM, как у платформы."""
    path = os.path.join(root, folder, name + ".xml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8-sig", newline="").write(text)


@pytest.mark.holder
def test_referenced_object_is_not_deleted(dump):
    """Ссылка держит: карточка остаётся на месте, файлы не тронуты."""
    result = delete(dump, "Справочник.мой_Цель", apply_now=False)
    assert [f.code for f in result.errors] == ["УДАЛЕНИЕ-ЕСТЬ-ССЫЛКИ"]
    assert "мой_Держатель" in result.errors[0].message
    assert os.path.isfile(os.path.join(dump, "Catalogs", "мой_Цель.xml"))


# Держатель с двумя местами ссылки: реквизит объекта и реквизит табличной части.
RECEIPT = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">
\t<Document uuid="d2">
\t\t<Properties>
\t\t\t<Name>мой_Приход</Name>
\t\t</Properties>
\t\t<ChildObjects>
\t\t\t<Attribute uuid="a3">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Основной</Name>
\t\t\t\t\t<Type>
\t\t\t\t\t\t<v8:Type>cfg:CatalogRef.мой_Цель</v8:Type>
\t\t\t\t\t</Type>
\t\t\t\t</Properties>
\t\t\t</Attribute>
\t\t\t<TabularSection uuid="t2">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Товары</Name>
\t\t\t\t</Properties>
\t\t\t\t<ChildObjects>
\t\t\t\t\t<Attribute uuid="a4">
\t\t\t\t\t\t<Properties>
\t\t\t\t\t\t\t<Name>Склад</Name>
\t\t\t\t\t\t\t<Type>
\t\t\t\t\t\t\t\t<v8:Type>cfg:CatalogRef.мой_Свободный</v8:Type>
\t\t\t\t\t\t\t\t<v8:Type>cfg:CatalogRef.мой_Цель</v8:Type>
\t\t\t\t\t\t\t</Type>
\t\t\t\t\t\t</Properties>
\t\t\t\t\t</Attribute>
\t\t\t\t</ChildObjects>
\t\t\t</TabularSection>
\t\t</ChildObjects>
\t</Document>
</MetaDataObject>"""


def test_the_refusal_names_the_attribute_and_its_property(dump):
    """Отказ называет место ссылки: реквизит, а не одного держателя.

    Одного «ссылаются: Документ.мой_Приход» мало: у документа бывают сотни
    реквизитов, и ссылка нередко в реквизите табличной части. Место названо
    адресом до реквизита, свойство — словом задания; правка типа реквизита
    и правка записи прав — разные правки, и это видно сразу.
    """
    card(dump, "Documents", "мой_Приход", RECEIPT)
    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == [
        "Документ.мой_Приход.Реквизит.Основной (тип)",
        "Документ.мой_Приход.ТабличнаяЧасть.Товары.Реквизит.Склад (тип)"]
    сказано = delete(dump, "Справочник.мой_Цель", apply_now=False).errors[0].message
    assert "ссылаются (2)" in сказано
    assert "ТабличнаяЧасть.Товары.Реквизит.Склад (тип)" in сказано


JOURNAL = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.21">
\t<DocumentJournal uuid="j1">
\t\t<Properties>
\t\t\t<Name>мой_Журнал</Name>
\t\t</Properties>
\t\t<ChildObjects>
\t\t\t<Column uuid="g1">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Склад</Name>
\t\t\t\t\t<References>
\t\t\t\t\t\t<xr:Item xsi:type="xr:MDObjectRef">Document.мой_Приход.Attribute.Основной</xr:Item>
\t\t\t\t\t</References>
\t\t\t\t</Properties>
\t\t\t</Column>
\t\t</ChildObjects>
\t</DocumentJournal>
</MetaDataObject>"""


def test_an_unmodelled_member_is_named_and_an_unknown_property_kept_as_tag(dump):
    """Графа журнала — сущность, которой инструмент не создаёт, но ссылки держит.

    Её слово взято из синтакс-помощника («ОбъектМетаданных: Графа»). Своего
    поля у свойства `References` в задании нет — и оно остаётся тегом
    выгрузки: точный тег находится поиском в файле, придуманное слово — нет.
    """
    card(dump, "Documents", "мой_Приход", RECEIPT)
    card(dump, "DocumentJournals", "мой_Журнал", JOURNAL)
    assert DesignerDump(dump).references_to(
        [("Документ", "мой_Приход"), ("Реквизит", "Основной")]) == [
        "ЖурналДокументов.мой_Журнал.Графа.Склад (References)"]


OPTION = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.21">
\t<FunctionalOption uuid="f1">
\t\t<Properties>
\t\t\t<Name>мой_Опция</Name>
\t\t\t<Content>
\t\t\t\t<xr:Object>Catalog.мой_Цель</xr:Object>
\t\t\t</Content>
\t\t</Properties>
\t</FunctionalOption>
</MetaDataObject>"""


def test_a_holder_of_an_unmodelled_kind_is_named_by_its_kind(dump):
    """Держатель вида, которого инструмент не создаёт, назван словом вида.

    Каталог выгрузки в сообщении («FunctionalOptions.мой_Опция») — это адрес
    файла, а не объекта. Поле «состав» общее: тот же `Content`, что у подсистемы.
    """
    card(dump, "FunctionalOptions", "мой_Опция", OPTION)
    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == [
        "ФункциональнаяОпция.мой_Опция (состав)"]


RIGHTS = """<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Rights" version="2.21">
\t<setForNewObjects>false</setForNewObjects>
\t<setForAttributesByDefault>true</setForAttributesByDefault>
\t<independentRightsOfChildObjects>false</independentRightsOfChildObjects>
\t<object>
\t\t<name>Catalog.мой_Цель</name>
\t\t<right>
\t\t\t<name>Read</name>
\t\t\t<value>true</value>
\t\t</right>
\t</object>
</Rights>"""


def test_a_role_is_named_as_a_whole(dump):
    """Право роли — запись файла прав, а не свойство сущности: держатель целиком."""
    card(dump, "Roles", os.path.join("мой_Роль", "Ext", "Rights"), RIGHTS)
    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == [
        "Роль.мой_Роль (права)"]


def test_a_deletion_preview_does_not_speak_of_defaults(dump):
    """У удаляемого объекта умолчаний нет — и строки о них в ответе тоже.

    Строка из просмотра создания — «ещё N полей не названо в задании —
    значения по умолчанию» — под удаляемым объектом была бы неправдой:
    поля существующего объекта остаются такими, какие записаны.
    """
    from meta.report.result import result_lines

    сказано = "\n".join(result_lines(delete(dump, "Справочник.мой_Свободный",
                                            apply_now=False)))
    assert "Справочник мой_Свободный" in сказано
    assert "по умолчанию" not in сказано, сказано


def test_free_object_is_deleted_whole(dump):
    """Карточка, запись в реестре — всё разом."""
    delete(dump, "Справочник.мой_Свободный")
    assert not os.path.exists(os.path.join(dump, "Catalogs", "мой_Свободный.xml"))
    registry = open(os.path.join(dump, "Configuration.xml"),
                    encoding="utf-8-sig").read()
    assert "мой_Свободный" not in registry
    assert "<Catalog>мой_Цель</Catalog>" in registry


def test_satellites_and_their_folders_go_too(dump):
    """Спутники объекта удаляются вместе с ним, пустые каталоги не остаются."""
    folder = os.path.join(dump, "Catalogs", "мой_Свободный", "Ext")
    os.makedirs(folder)
    open(os.path.join(folder, "ObjectModule.bsl"), "w", encoding="utf-8-sig").write("//")
    delete(dump, "Справочник.мой_Свободный")
    assert not os.path.exists(os.path.join(dump, "Catalogs", "мой_Свободный"))


def test_nested_attribute_is_cut_out_and_nothing_else_moves(dump):
    """Вырезается блок реквизита табличной части — и только он.

    Глубина отступов берётся у самого узла: пересчёт по фиксированной глубине
    сдвинул бы всю карточку и переформатировал соседние строки. Здесь это
    проверяется буквально.
    """
    before = card_of(dump)
    delete(dump, "Справочник.мой_Цель.ТабличнаяЧасть.Строки.Реквизит.Вложенный")
    expected = before.replace(
        "\t\t\t\t<ChildObjects>\n"
        '\t\t\t\t\t<Attribute uuid="a2">\n'
        "\t\t\t\t\t\t<Properties>\n"
        "\t\t\t\t\t\t\t<Name>Вложенный</Name>\n"
        "\t\t\t\t\t\t</Properties>\n"
        "\t\t\t\t\t</Attribute>\n"
        "\t\t\t\t</ChildObjects>\n",
        "\t\t\t\t<ChildObjects/>\n")
    assert card_of(dump) == expected


def test_last_child_leaves_a_self_closed_section(dump):
    """Пустой раздел возвращается к `<ChildObjects/>` — так его пишет платформа."""
    delete(dump, "Справочник.мой_Цель.ТабличнаяЧасть.Строки.Реквизит.Вложенный")
    text = card_of(dump)
    assert "\t\t\t\t<ChildObjects/>\n" in text


def test_missing_target_is_refused(dump):
    with pytest.raises(Refuse) as refusal:
        delete(dump, "Справочник.мой_Цель.Реквизит.НетТакого")
    assert "нет «Реквизит.НетТакого»" in str(refusal.value)


def test_preview_writes_nothing(dump):
    before = card_of(dump)
    delete(dump, "Справочник.мой_Цель.Реквизит.Первый", apply_now=False)
    assert card_of(dump) == before


def test_unchecked_scope_is_said_out_loud(dump):
    """Формы и код BSL не проверяются — и об этом сказано каждый раз."""
    result = delete(dump, "Справочник.мой_Свободный", apply_now=False)
    codes = [f.code for f in result.findings]
    assert codes == ["УДАЛЕНИЕ-КОД-НЕ-ПРОВЕРЕН"]
    assert not result.errors
    assert "формы, код BSL, тексты запросов" in result.findings[0].message
    # Названо и то, что как раз проверяется, — иначе предупреждение читается
    # как «ничего не проверено», и человек перепроверяет уже проверенное.
    # Про схемы сказано «в типах»: там имя ищется английским обозначением
    # (`d4p1:CatalogRef.Имя`), а текст запроса называет объект по-русски и
    # под него не подходит — его предупреждение проверенным не называет.
    assert "типах схем компоновки" in result.findings[0].message


def test_object_and_its_part_in_one_job_are_refused(dump):
    """Удалять часть того, что удаляется целиком, незачем — и это ошибка."""
    with pytest.raises(Refuse) as refusal:
        DeleteUseCase(DesignerDump(dump)).execute([
            job_dialect.delete_job_from_json("Справочник.мой_Свободный"),
            job_dialect.delete_job_from_json(
                "Справочник.мой_Свободный.Реквизит.Первый"),
        ], apply_now=True)
    assert "удаляется целиком" in str(refusal.value)


def test_reference_pattern_does_not_catch_a_longer_name(dump):
    """`мой_Цель` не должен находиться внутри `мой_ЦельДругая`."""
    other = os.path.join(dump, "Catalogs", "мой_ЦельДругая.xml")
    open(other, "w", encoding="utf-8-sig", newline="").write(
        CATALOG.replace("мой_Цель", "мой_ЦельДругая"))
    platform = DesignerDump(dump)
    assert platform.references_to([("Справочник", "мой_Цель")]) == []


SUBSYSTEM = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.21">
\t<Subsystem uuid="s1">
\t\t<Properties>
\t\t\t<Name>Дочерняя</Name>
\t\t\t<Content>
\t\t\t\t<xr:Item>Catalog.мой_Цель</xr:Item>
\t\t\t</Content>
\t\t</Properties>
\t\t<ChildObjects/>
\t</Subsystem>
</MetaDataObject>"""


def test_a_nested_subsystem_holds_the_reference(dump):
    """Состав подчинённой подсистемы виден обратному поиску.

    Плоское перечисление каталогов дошло бы до `Subsystems/Родитель.xml`
    и остановилось, а подчинённая подсистема лежит на уровень глубже —
    `Subsystems/Родитель/Subsystems/Дочерняя.xml`. В замеренной конфигурации
    таких карточек 1257 с 19 208 ссылками. Без них объект с такой ссылкой
    удалился бы с вердиктом «ссылок нет», и вышла бы конфигурация, которую
    платформа не грузит.
    """
    nested = os.path.join(dump, "Subsystems", "Родитель", "Subsystems")
    os.makedirs(nested)
    open(os.path.join(nested, "Дочерняя.xml"), "w",
         encoding="utf-8-sig", newline="").write(SUBSYSTEM)

    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == [
        "Подсистема.Родитель.Подсистема.Дочерняя (состав)"]
    result = delete(dump, "Справочник.мой_Цель", apply_now=False)
    assert [f.code for f in result.errors] == ["УДАЛЕНИЕ-ЕСТЬ-ССЫЛКИ"]


def test_modules_and_templates_are_not_read_as_cards(dump):
    """Из `Ext` берутся права и схемы: модуль и обычный макет — нет.

    Проверяются оба случая, а не один: схема компоновки лежит в `Ext` рядом
    с обычным макетом, и отличает их содержимое, а не место.
    """
    folder = os.path.join(dump, "Catalogs", "мой_Свободный", "Ext")
    os.makedirs(folder)
    open(os.path.join(folder, "ObjectModule.bsl"), "w",
         encoding="utf-8-sig").write("// Справочники.мой_Цель")
    _template(dump, PLAIN_TEMPLATE, template="Табличный")
    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == []


def test_same_name_in_another_kind_does_not_block_deletion(dump):
    """Одноимённые объекты разных видов — разные объекты.

    Сравнение по одному имени запретило бы удалить тем же заданием реквизит
    `Документ.Тёзка`, когда целиком удаляется `Справочник.Тёзка`.
    """
    for folder, root in (("Catalogs", "Catalog"), ("Documents", "Document")):
        os.makedirs(os.path.join(dump, folder), exist_ok=True)
        open(os.path.join(dump, folder, "Тёзка.xml"), "w",
             encoding="utf-8-sig", newline="").write(
            FREE.replace("мой_Свободный", "Тёзка").replace("Catalog", root))
    registry_path = os.path.join(dump, "Configuration.xml")
    registry = open(registry_path, encoding="utf-8-sig").read()
    open(registry_path, "w", encoding="utf-8-sig", newline="").write(
        registry.replace("\t\t</ChildObjects>",
                         "\t\t\t<Catalog>Тёзка</Catalog>\n"
                         "\t\t\t<Document>Тёзка</Document>\n\t\t</ChildObjects>"))

    result = DeleteUseCase(DesignerDump(dump)).execute([
        job_dialect.delete_job_from_json("Справочник.Тёзка"),
        job_dialect.delete_job_from_json("Документ.Тёзка.Реквизит.Первый"),
    ], apply_now=False)
    assert not result.errors


SCHEMA_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
\t<parameter>
\t\t<name>Организация</name>
\t\t<valueType>
\t\t\t<v8:Type>cfg:CatalogRef.мой_Цель</v8:Type>
\t\t</valueType>
\t</parameter>
</DataCompositionSchema>"""

PLAIN_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<document xmlns="http://v8.1c.ru/8.2/data/spreadsheet">
\t<area>CatalogRef.мой_Цель</area>
</document>"""


def _template(dump, text, template="Схема"):
    """Макет отчёта: карточка макета и его содержимое в `Ext`."""
    inside = os.path.join(dump, "Reports", "мой_Отчёт", "Templates", template, "Ext")
    os.makedirs(inside, exist_ok=True)
    open(os.path.join(inside, "Template.xml"), "w",
         encoding="utf-8-sig", newline="").write(text)
    return os.path.join(inside, "Template.xml")


def test_a_data_composition_schema_holds_the_reference(dump):
    """Схема компоновки в макете видна обратному поиску.

    Из каталогов `Ext` берётся не только файл прав: схема лежит именно там —
    `Templates/<Макет>/Ext/Template.xml`. В замеренной конфигурации таких
    ссылок 8037 в 696 макетах; без них справочник, названный типом параметра
    СКД, удалился бы с вердиктом «ссылок нет».
    """
    _template(dump, SCHEMA_TEMPLATE)
    кто = DesignerDump(dump).references_to([("Справочник", "мой_Цель")])
    assert кто == ["Отчет.мой_Отчёт.Макет.Схема.Параметр.Организация (типЗначения)"]
    result = delete(dump, "Справочник.мой_Цель", apply_now=False)
    assert [f.code for f in result.errors] == ["УДАЛЕНИЕ-ЕСТЬ-ССЫЛКИ"]


def test_a_plain_template_is_not_read(dump):
    """Макет, в котором не схема, не читается — и это замер, а не лень.

    Макетов в выгрузке 14 447 на 3,4 ГБ — в восемь раз дороже форм, которые
    исключены осознанно. Схем среди них 926 на 86 МБ. Отбор идёт по корню
    документа, тем же признаком, по которому разбор выбирает форму.
    """
    _template(dump, PLAIN_TEMPLATE, template="Табличный")
    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == []


def test_the_configuration_registry_holds_the_reference(dump):
    """Ссылка в реестре вне раздела детей держит объект.

    Исключить `Configuration.xml` целиком — «сам себе не ссылка» — нельзя.
    Про раздел детей это верно, но вне него реестр называет основные роли,
    хранилище вариантов отчётов, общие формы и язык — в замеренной
    конфигурации восемь ссылок, три из них на роли. А роль — один из видов,
    которые инструмент создаёт.
    """
    registry_path = os.path.join(dump, "Configuration.xml")
    registry = open(registry_path, encoding="utf-8-sig").read()
    open(registry_path, "w", encoding="utf-8-sig", newline="").write(
        registry.replace(
            "<MetaDataObject>",
            '<MetaDataObject xmlns:xr="http://v8.1c.ru/8.3/xcf/readable">').replace(
            "\t</Configuration>",
            "\t\t<Properties>\n\t\t\t<MainRoles>\n"
            "\t\t\t\t<xr:Item>Role.мой_Роль</xr:Item>\n"
            "\t\t\t</MainRoles>\n\t\t</Properties>\n\t</Configuration>"))
    os.makedirs(os.path.join(dump, "Roles"), exist_ok=True)
    open(os.path.join(dump, "Roles", "мой_Роль.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        CATALOG.replace("Catalog", "Role").replace("мой_Цель", "мой_Роль"))

    # Свойства реестра инструмент не пишет — у `MainRoles` своего слова нет.
    assert DesignerDump(dump).references_to(
        [("Роль", "мой_Роль")]) == ["Конфигурация (MainRoles)"]


def test_an_unparsable_holder_is_named_as_a_whole(dump):
    """Держатель, который дерево не разобрало, назван целиком, а не пропущен.

    Ссылку нашло обозначение, место не назвать — отказ всё равно обязан
    случиться: держатель целиком лучше молчания.
    """
    card(dump, "Documents", "мой_Битый", HOLDER.replace(
        "<Name>мой_Держатель</Name>", "<Name>мой_Битый<Name>"))
    assert DesignerDump(dump).references_to([("Справочник", "мой_Цель")]) == [
        "Документ.мой_Битый"]


def test_the_registry_entry_itself_is_not_a_reference(dump):
    """Своя запись в разделе детей ссылкой не считается.

    Иначе включение реестра в обход запретило бы удалять что угодно. Держится
    это не на вырезании раздела, а на устройстве обозначения: оно требует
    точки, а в именах записей её нет ни у одной из 22 285 в конфигурации.
    """
    assert "<Catalog>мой_Свободный</Catalog>" in open(
        os.path.join(dump, "Configuration.xml"), encoding="utf-8-sig").read()
    assert DesignerDump(dump).references_to([("Справочник", "мой_Свободный")]) == []


def test_configdumpinfo_is_not_consulted(dump):
    """`ConfigDumpInfo.xml` в обход не входит намеренно.

    Там названы все объекты подряд — 41 МБ и 87 134 обозначения, — и ссылка
    нашлась бы на что угодно. Платформа пересобирает этот файл при загрузке,
    инструмент его не трогает вовсе.
    """
    open(os.path.join(dump, "ConfigDumpInfo.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<ConfigDumpInfo>\n'
        '\t<ConfigVersions>\n\t\t<Metadata name="Catalog.мой_Свободный"/>\n'
        "\t</ConfigVersions>\n</ConfigDumpInfo>")
    assert DesignerDump(dump).references_to([("Справочник", "мой_Свободный")]) == []
    result = delete(dump, "Справочник.мой_Свободный", apply_now=False)
    assert not result.errors


def test_the_whole_object_guard_does_not_depend_on_order(dump):
    """Тот же запрет при обратном порядке строк задания.

    Проверка, которая смотрит только назад по собранному списку, отвергает
    «объект, потом его реквизит», а «реквизит, потом объект» пропускает —
    и план выходит самопротиворечивым: файл сначала переписывается
    с вырезанным реквизитом, потом удаляется целиком. Инвариант, который
    зависит от порядка строк задания, инвариантом не является.
    """
    for порядок in (["Справочник.мой_Свободный",
                     "Справочник.мой_Свободный.Реквизит.Первый"],
                    ["Справочник.мой_Свободный.Реквизит.Первый",
                     "Справочник.мой_Свободный"]):
        with pytest.raises(Refuse) as refusal:
            DeleteUseCase(DesignerDump(dump)).execute(
                [job_dialect.delete_job_from_json(а) for а in порядок],
                apply_now=True)
        assert "удаляется целиком" in str(refusal.value), порядок


def test_every_missing_address_is_named_at_once(dump):
    """Опечатки в адресах собираются все, как собираются неизвестные поля.

    Иначе пачка из двадцати правок с пятью опечатками потребует пяти запусков
    вместо одного: работа рвалась бы на первом же ненайденном.
    """
    with pytest.raises(Refuse) as refusal:
        DeleteUseCase(DesignerDump(dump)).execute([
            job_dialect.delete_job_from_json("Справочник.мой_Цель.Реквизит.НетА"),
            job_dialect.delete_job_from_json("Справочник.мой_Цель.Реквизит.НетБ"),
        ], apply_now=False)
    сказано = str(refusal.value)
    assert "НетА" in сказано and "НетБ" in сказано
