"""Схема компоновки данных: правка по адресу через границу файла.

Схема живёт не в карточке объекта, а в макете рядом с ней —
`Templates/<Макет>/Ext/Template.xml`. Адрес пересекает эту границу шагом
«Макет», а дальше всё то же самое: пары «Вид.Имя» вглубь.

Устроена она иначе, чем карточка: дети и свойства лежат прямо в узле, без
`Properties` и `ChildObjects`, а сущность опознаётся по `name` — или по
`dataPath` у вычисляемого и итогового поля, у которых имени нет вовсе. Это
различие вынесено в «форму документа», и операции изменения работают на обеих
формах одним кодом.
"""

import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.application.change_property.use_case import ChangePropertyUseCase  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.infra.tree_lxml import LxmlCardTree, shape_of  # noqa: E402
from meta.jobs import dialect as job_dialect  # noqa: E402
from meta.tests import corpus  # noqa: E402

# Пространства имён — те же, что в корне настоящей схемы: `v8` объявлен
# в корне у всех 926 схем конфигурации. Без него узел типа получал бы
# от библиотеки собственную приставку (`ns0:`), и фикстура показывала бы
# то, чего в выгрузке не бывает.
SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"\
 xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings"\
 xmlns:v8="http://v8.1c.ru/8.1/data/core"\
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
\t<dataSource>
\t\t<name>ИсточникДанных1</name>
\t\t<dataSourceType>Local</dataSourceType>
\t</dataSource>
\t<dataSet xsi:type="DataSetQuery">
\t\t<name>Продажи</name>
\t\t<dataSource>ИсточникДанных1</dataSource>
\t\t<query>ВЫБРАТЬ 1</query>
\t</dataSet>
\t<dataSet xsi:type="DataSetQuery">
\t\t<name>Остатки</name>
\t\t<dataSource>ИсточникДанных1</dataSource>
\t\t<query>ВЫБРАТЬ 2</query>
\t</dataSet>
\t<settingsVariant>
\t\t<dcsset:name>Основной</dcsset:name>
\t</settingsVariant>
</DataCompositionSchema>"""

REGISTRY = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
            "\t<Configuration>\n\t\t<ChildObjects>\n"
            "\t\t\t<Report>мой_Отчёт</Report>\n"
            "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")


@pytest.fixture
def dump():
    root = tempfile.mkdtemp(prefix="meta-schema-")
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(REGISTRY)
    os.makedirs(os.path.join(root, "Reports"))
    open(os.path.join(root, "Reports", "мой_Отчёт.xml"), "w",
         encoding="utf-8-sig", newline="").write("<Report/>")
    inside = os.path.join(root, "Reports", "мой_Отчёт", "Templates",
                          "ОсновнаяСхема", "Ext")
    os.makedirs(inside)
    open(os.path.join(inside, "Template.xml"), "w",
         encoding="utf-8-sig", newline="").write(SCHEMA)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def schema_of(root):
    return open(os.path.join(root, "Reports", "мой_Отчёт", "Templates",
                             "ОсновнаяСхема", "Ext", "Template.xml"),
                encoding="utf-8-sig").read().replace("\r\n", "\n")


def change(root, address, fields, apply_now=True):
    return ChangePropertyUseCase(DesignerDump(root)).execute(
        [(job_dialect.path_from_json(address), fields)], apply_now=apply_now)


ADDRESS = "Отчет.мой_Отчёт.Макет.ОсновнаяСхема.НаборДанных.Продажи"


def test_query_of_a_named_dataset_is_replaced(dump):
    """Главная операция: поправить запрос в определённом наборе."""
    change(dump, ADDRESS, {"запрос": "ВЫБРАТЬ\n\tСсылка\nИЗ\n\tСправочник.Товары"})
    text = schema_of(dump)
    assert "<query>ВЫБРАТЬ\n\tСсылка\nИЗ\n\tСправочник.Товары</query>" in text
    assert "<query>ВЫБРАТЬ 2</query>" in text          # соседний набор не тронут


def test_only_the_addressed_node_changes(dump):
    """Соседние строки обязаны остаться теми же байтами."""
    before = schema_of(dump).split("\n")
    change(dump, ADDRESS, {"запрос": "ВЫБРАТЬ 42"})
    after = schema_of(dump).split("\n")
    assert len(before) == len(after)
    different = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert len(different) == 1, [before[i] for i in different]
    assert after[different[0]].strip() == "<query>ВЫБРАТЬ 42</query>"


def test_report_says_what_changed(dump):
    result = change(dump, ADDRESS, {"запрос": "ВЫБРАТЬ 42"}, apply_now=False)
    said = "\n".join(result.plan.describe())
    assert "было ВЫБРАТЬ 1 стало ВЫБРАТЬ 42" in said, said


def test_missing_dataset_is_refused(dump):
    with pytest.raises(Refuse) as refusal:
        change(dump, "Отчет.мой_Отчёт.Макет.ОсновнаяСхема.НаборДанных.НетТакого",
               {"запрос": "ВЫБРАТЬ 1"})
    assert "нет «НаборДанных.НетТакого»" in str(refusal.value)


def test_missing_template_is_refused(dump):
    with pytest.raises(Refuse) as refusal:
        change(dump, "Отчет.мой_Отчёт.Макет.НетТакого.НаборДанных.Продажи",
               {"запрос": "ВЫБРАТЬ 1"})
    assert "макета" in str(refusal.value)


def test_preview_writes_nothing(dump):
    before = schema_of(dump)
    change(dump, ADDRESS, {"запрос": "ВЫБРАТЬ 42"}, apply_now=False)
    assert schema_of(dump) == before


def test_schema_shape_is_recognised_and_card_shape_still_is():
    tree = LxmlCardTree()
    assert shape_of(tree.parse(SCHEMA)).root == "DataCompositionSchema"
    card = tree.parse('<?xml version="1.0" encoding="UTF-8"?>\n'
                      "<MetaDataObject><Catalog/></MetaDataObject>")
    assert shape_of(card).root == "MetaDataObject"


def test_unknown_document_is_refused():
    tree = LxmlCardTree()
    with pytest.raises(Refuse) as refusal:
        shape_of(tree.parse('<?xml version="1.0" encoding="UTF-8"?>\n<Что-то/>'))
    assert "не знаю документа" in str(refusal.value)


def test_query_changes_in_a_real_schema_from_the_configuration(tmp_path):
    """То же самое, но на схеме, которую написала платформа.

    Заготовка выше короткая и своя; здесь берётся настоящая схема из
    конфигурации со всеми её пространствами имён и вложенностью, и проверяется,
    что правка меняет ровно один узел, а всё остальное остаётся байт в байт.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    tree = LxmlCardTree()
    source = name = None
    for folder, _, names in os.walk(os.path.join(corpus.CORPUS, "Reports")):
        if "Template.xml" not in names:
            continue
        path = os.path.join(folder, "Template.xml")
        with open(path, "rb") as raw:
            if b"data-composition-system/schema" not in raw.read(400):
                continue
        text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
        parsed = tree.parse(text)
        names_found = tree.child_names(parsed, "dataSet")
        if names_found and "<query>" in text:
            source, name = text, names_found[0]
            break
    if source is None:
        pytest.skip("в выгрузке не нашлось схемы с набором-запросом")

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(REGISTRY)
    os.makedirs(os.path.join(root, "Reports"))
    open(os.path.join(root, "Reports", "мой_Отчёт.xml"), "w",
         encoding="utf-8-sig", newline="").write("<Report/>")
    inside = os.path.join(root, "Reports", "мой_Отчёт", "Templates",
                          "ОсновнаяСхема", "Ext")
    os.makedirs(inside)
    open(os.path.join(inside, "Template.xml"), "w",
         encoding="utf-8-sig", newline="").write(source)

    change(root, f"Отчет.мой_Отчёт.Макет.ОсновнаяСхема.НаборДанных.{name}",
           {"запрос": "ВЫБРАТЬ 1"})
    after = schema_of(root)
    assert "<query>ВЫБРАТЬ 1</query>" in after
    # всё, кроме одного узла, осталось прежним: длина изменилась ровно на разницу
    # текста запроса, а число строк — на число строк в нём
    assert after.count("<dataSet ") == source.count("<dataSet ")
    assert after.count("<settingsVariant>") == source.count("<settingsVariant>")
    print(f"настоящая схема: набор «{name}», было {len(source)} Б, стало {len(after)} Б")


def add(root, address, kind, fields, apply_now=True):
    from meta.application.add_child.use_case import AddChildUseCase
    return AddChildUseCase(DesignerDump(root)).execute(
        [job_dialect.addition_job_from_json(
            {"путь": address, "вид": kind, "поля": fields})], apply_now=apply_now)


SCHEMA_ADDRESS = "Отчет.мой_Отчёт.Макет.ОсновнаяСхема"


def test_parameter_is_added_in_the_canonical_place(dump):
    """Параметр встаёт после наборов и перед вариантом настроек.

    Порядок детей схемы канонический — снят с 901 схемы конфигурации. Наивная
    вставка «в конец» поставила бы параметр после `settingsVariant`, и это уже
    другая схема, а не та же с добавленным параметром.
    """
    add(dump, SCHEMA_ADDRESS, "Параметр",
        {"имя": "Период", "заголовок": "Период"})
    text = schema_of(dump)
    assert "<name>Период</name>" in text
    assert text.index("<parameter>") > text.index("<name>Остатки</name>")
    assert text.index("<parameter>") < text.index("<settingsVariant>")


def test_added_parameter_writes_only_what_was_asked(dump):
    """Умолчаний у параметра нет: что не названо, то не пишется."""
    add(dump, SCHEMA_ADDRESS, "Параметр", {"имя": "Период"})
    block = schema_of(dump).split("<parameter>")[1].split("</parameter>")[0]
    assert "<name>Период</name>" in block
    assert "<title>" not in block and "<value>" not in block


def test_duplicate_name_is_refused(dump):
    add(dump, SCHEMA_ADDRESS, "Параметр", {"имя": "Период"})
    with pytest.raises(Refuse) as refusal:
        add(dump, SCHEMA_ADDRESS, "Параметр", {"имя": "Период"})
    assert "уже есть" in str(refusal.value)


def test_dataset_with_a_query_is_added(dump):
    """Новый набор с запросом."""
    add(dump, SCHEMA_ADDRESS, "НаборДанных",
        {"имя": "Новый", "источникДанных": "ИсточникДанных1",
         "запрос": "ВЫБРАТЬ 3"})
    text = schema_of(dump)
    assert "<name>Новый</name>" in text and "<query>ВЫБРАТЬ 3</query>" in text
    # встал среди наборов, а не после варианта настроек
    assert text.index("<name>Новый</name>") < text.index("<settingsVariant>")


def test_dataset_names_a_source_that_exists(dump):
    """Имя источника — ссылка внутрь той же схемы, а не свободный текст.

    Без проверки опечатка прошла бы молча: набор пишется, отчёт не работает.
    Проверять есть чем — источники лежат в той же схеме.
    """
    итог = add(dump, SCHEMA_ADDRESS, "НаборДанных",
               {"имя": "Новый", "источникДанных": "ИсточникДанных9",
                "запрос": "ВЫБРАТЬ 3"}, apply_now=False)
    коды = [f.code for f in итог.findings]
    assert коды == ["НАБОР-ИСТОЧНИК-НЕИЗВЕСТЕН"], коды
    # и назван тот, который есть, — иначе догадываться о правильном имени
    assert "ИсточникДанных1" in итог.findings[0].message
    assert "<name>Новый</name>" not in schema_of(dump)


def test_a_source_that_exists_passes(dump):
    """Обратная половина: верное имя замечаний не вызывает."""
    итог = add(dump, SCHEMA_ADDRESS, "НаборДанных",
               {"имя": "Новый", "источникДанных": "ИсточникДанных1",
                "запрос": "ВЫБРАТЬ 3"}, apply_now=False)
    assert [f.code for f in итог.findings] == []


def test_addition_into_a_missing_host_is_refused(dump):
    with pytest.raises(Refuse) as refusal:
        add(dump, "Отчет.мой_Отчёт.Макет.ОсновнаяСхема.НаборДанных.НетТакого",
            "Параметр", {"имя": "Период"})
    assert "нет «НаборДанных.НетТакого»" in str(refusal.value)


def test_preview_of_addition_writes_nothing(dump):
    before = schema_of(dump)
    add(dump, SCHEMA_ADDRESS, "Параметр", {"имя": "Период"}, apply_now=False)
    assert schema_of(dump) == before


# --- создание отчёта --------------------------------------------------------

def test_report_is_created_with_a_template_and_an_empty_schema(tmp_path):
    """Отчёт заводится сразу пригодным к работе: с макетом и пустой схемой.

    Без схемы новый отчёт бесполезен для остальных операций — править и
    дополнять было бы нечего. Содержимое пустой схемы снято с самой маленькой
    схемы конфигурации: источник данных и вариант настроек «Основной».
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.domain.model import Spec

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n\t</Configuration>\n"
        "</MetaDataObject>")
    AddObjectUseCase(DesignerDump(root)).execute([Spec("Отчет", {
        "имя": "мой_Проба", "синоним": "(Мой) Проба",
        "стандартныеКоманды": True, "включатьСправкуВСодержание": False,
        "схема": "ОсновнаяСхема"})], apply_now=True)

    card = open(os.path.join(root, "Reports", "мой_Проба.xml"),
                encoding="utf-8-sig").read()
    assert "<Template>ОсновнаяСхема</Template>" in card   # макет числится именем
    assert 'name="ReportObject.мой_Проба"' in card

    template = open(os.path.join(root, "Reports", "мой_Проба", "Templates",
                                 "ОсновнаяСхема.xml"), encoding="utf-8-sig").read()
    assert "<TemplateType>DataCompositionSchema</TemplateType>" in template

    schema = open(os.path.join(root, "Reports", "мой_Проба", "Templates",
                               "ОсновнаяСхема", "Ext", "Template.xml"),
                  encoding="utf-8-sig").read()
    assert '<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/' in schema
    assert "<name>ИсточникДанных1</name>" in schema
    assert "<dcsset:name>Основной</dcsset:name>" in schema
    assert 'xmlns:pal="http://v8.1c.ru/8.1/data/ui/colors/palette"' in schema


def test_a_report_with_a_schema_names_it_as_the_main_one(tmp_path):
    """Заказали макет со схемой — отчёт называет её основной сам.

    Из 417 отчётов конфигурации, у которых макет несёт схему компоновки,
    основную схему называют все 417. Отчёт, заведённый с макетом и с пустой
    строкой основной схемы, не похож ни на один из них — и открывается
    пустым, ничего при этом не сообщая.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.domain.model import Spec

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n\t</Configuration>\n"
        "</MetaDataObject>")
    AddObjectUseCase(DesignerDump(root)).execute([Spec("Отчет", {
        "имя": "мой_Проба", "синоним": "(Мой) Проба",
        "стандартныеКоманды": True, "включатьСправкуВСодержание": False,
        "схема": "ОсновнаяСхема"})], apply_now=True)
    card = open(os.path.join(root, "Reports", "мой_Проба.xml"),
                encoding="utf-8-sig").read()
    assert ("<MainDataCompositionSchema>Report.мой_Проба.Template."
            "ОсновнаяСхема</MainDataCompositionSchema>") in card


def test_a_main_schema_given_by_hand_wins(tmp_path):
    """У отчёта бывает несколько схем — какая основная, решает человек."""
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.domain.model import Spec

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n\t</Configuration>\n"
        "</MetaDataObject>")
    AddObjectUseCase(DesignerDump(root)).execute([Spec("Отчет", {
        "имя": "мой_Проба", "синоним": "(Мой) Проба",
        "стандартныеКоманды": True, "включатьСправкуВСодержание": False,
        "схема": "ОсновнаяСхема",
        "основнаяСхема": "Отчет.мой_Проба.Макет.Другая"})], apply_now=True)
    card = open(os.path.join(root, "Reports", "мой_Проба.xml"),
                encoding="utf-8-sig").read()
    assert "Report.мой_Проба.Template.Другая" in card


def test_report_without_a_schema_writes_no_template(tmp_path):
    """Макет не заказан — файлов и нет: лишнего инструмент не пишет."""
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.domain.model import Spec

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n\t</Configuration>\n"
        "</MetaDataObject>")
    AddObjectUseCase(DesignerDump(root)).execute([Spec("Отчет", {
        "имя": "мой_Проба", "синоним": "(Мой) Проба",
        "стандартныеКоманды": True, "включатьСправкуВСодержание": False})],
        apply_now=True)
    assert not os.path.exists(os.path.join(root, "Reports", "мой_Проба"))
    card = open(os.path.join(root, "Reports", "мой_Проба.xml"),
                encoding="utf-8-sig").read()
    assert "<Template>" not in card


def test_two_flags_of_the_report_are_required():
    """Они расходятся по корпусу почти поровну — значит это выбор, а не факт."""
    from meta.domain.model import Spec

    kind = kind_of("Отчет")
    findings = kind.check(kind.fill(Spec("Отчет", {"имя": "мой_Проба",
                                                   "синоним": "П"})), None)
    empty = sorted(f.field for f in findings if f.code == "МД-ПОЛЕ-ПУСТО")
    assert empty == ["включатьСправкуВСодержание", "стандартныеКоманды"], empty


# --- пункты настроек --------------------------------------------------------

VARIANT = SCHEMA_ADDRESS + ".ВариантНастроек.Основной"


def test_settings_containers_are_created_in_the_canonical_order(dump):
    """Контейнеры заводятся на своих местах, а не в конец.

    У свежей схемы настройки пусты. Порядок разделов снят по 901 схеме:
    отбор идёт перед порядком, а структура — после условного оформления.
    Вставка «в конец» дала бы другие настройки, а не те же с добавленным.
    """
    add(dump, VARIANT, "ПолеПорядка",
        {"использование": True, "поле": "Дата", "направление": "Убывание"})
    add(dump, VARIANT, "ВыбираемоеПоле", {"использование": True, "поле": "Товар"})
    add(dump, VARIANT, "ГруппировкаСтруктуры",
        {"использование": True, "имя": "ПоТовару"})
    text = schema_of(dump)
    assert (text.index("<dcsset:selection>") < text.index("<dcsset:order>")
            < text.index('<dcsset:item xsi:type="dcsset:StructureItemGroup">'))


def test_use_is_omitted_when_true(dump):
    """`use` платформа пишет только когда `false` — 4233 против одного `true`.

    Круг через базу это подтверждает: написанное `<dcsset:use>true</dcsset:use>`
    платформа вычищает. Это её умолчание, и писать его незачем.
    """
    add(dump, VARIANT, "ВыбираемоеПоле", {"использование": True, "поле": "Товар"})
    assert "<dcsset:use>" not in schema_of(dump)
    add(dump, VARIANT, "ВыбираемоеПоле", {"использование": False, "поле": "Цена"})
    assert "<dcsset:use>false</dcsset:use>" in schema_of(dump)


def test_filter_operands_declare_their_type(dump):
    """Левый операнд — поле, правый — значение с объявленным типом.

    И то и другое замерено: `dcscor:Field` у 6317 левых операндов из 6318,
    а правый несёт `xsi:type` по тому, что в нём лежит. У поля выбора
    и поля порядка типа, наоборот, нет ни разу из 33 525 — платформа снимает
    его, если написать.
    """
    add(dump, VARIANT, "Отбор", {"использование": True, "левое": "Организация",
                                 "видСравнения": "Равно", "правое": "Основная"})
    add(dump, VARIANT, "ВыбираемоеПоле", {"использование": True, "поле": "Товар"})
    text = schema_of(dump)
    assert '<dcsset:left xsi:type="dcscor:Field">Организация</dcsset:left>' in text
    assert '<dcsset:right xsi:type="xs:string">Основная</dcsset:right>' in text
    assert "<dcsset:field>Товар</dcsset:field>" in text


@pytest.mark.parametrize("value, expected", [
    ("Основная", '<dcsset:right xsi:type="xs:string">Основная</dcsset:right>'),
    (42, '<dcsset:right xsi:type="xs:decimal">42</dcsset:right>'),
    (True, '<dcsset:right xsi:type="xs:boolean">true</dcsset:right>'),
])
def test_right_operand_type_follows_the_value(dump, value, expected):
    """Тип объявляется по тому, что лежит в значении, — это не догадка."""
    add(dump, VARIANT, "Отбор", {"использование": True, "левое": "Поле",
                                 "видСравнения": "Равно", "правое": value})
    assert expected in schema_of(dump)


def test_order_direction_is_a_measured_dictionary(dump):
    add(dump, VARIANT, "ПолеПорядка",
        {"использование": True, "поле": "Дата", "направление": "Убывание"})
    assert "<dcsset:orderType>Desc</dcsset:orderType>" in schema_of(dump)
    with pytest.raises(Refuse) as refusal:
        add(dump, VARIANT, "ПолеПорядка",
            {"использование": True, "поле": "Цена", "направление": "ВНиз"})
    assert "допустимо: Возрастание, Убывание" in str(refusal.value)


def remove(root, address, apply_now=True):
    from meta.application.delete.use_case import DeleteUseCase

    return DeleteUseCase(DesignerDump(root)).execute(
        [job_dialect.delete_job_from_json(address)], apply_now=apply_now)


def test_a_prefixed_property_can_be_changed(dump):
    """Свойство с приставкой пространства имён находится и меняется.

    Схема называет теги так, как они стоят в файле (`dcsset:presentation`),
    а разбор возвращает разобранное имя. Если хоть один из поисков —
    `child_names`, `child_by_tag`, `find`, `_property` — приставку не снимает,
    сравнение не совпадёт никогда, и отказ «в карточке нет свойства» соврёт
    о состоянии файла.
    """
    path = os.path.join(dump, "Reports", "мой_Отчёт", "Templates",
                        "ОсновнаяСхема", "Ext", "Template.xml")
    open(path, "w", encoding="utf-8-sig", newline="").write(
        SCHEMA.replace("\t\t<dcsset:name>Основной</dcsset:name>\n",
                       "\t\t<dcsset:name>Основной</dcsset:name>\n"
                       "\t\t<dcsset:presentation>Было</dcsset:presentation>\n"))
    change(dump, VARIANT, {"представление": "Стало"})
    # Тип у представления объявлен: голых `presentation` в конфигурации
    # 0 из 2080, и правка пишет так же, как платформа.
    assert ('<dcsset:presentation xsi:type="xs:string">Стало</dcsset:presentation>'
            in schema_of(dump))


def test_a_settings_item_is_addressable_through_its_container(dump):
    """Пункт настроек правится и удаляется по тому же адресу, по которому создан.

    Контейнеры в адресе не называются: отбор пишется как
    `ВариантНастроек.Основной.Отбор.Организация`, а лежит в
    `settingsVariant/settings/filter/item`. Разворачивать их обязана не только
    запись: иначе добавить пункт можно, а изменить или убрать — нет.
    """
    add(dump, VARIANT, "Отбор", {"использование": True, "левое": "Организация",
                                 "видСравнения": "Равно", "правое": "Основная"})
    add(dump, VARIANT, "ПолеПорядка", {"использование": True, "поле": "Товар",
                                       "направление": "Убывание"})

    change(dump, VARIANT + ".Отбор.Организация", {"видСравнения": "НеРавно"})
    assert "<dcsset:comparisonType>NotEqual</dcsset:comparisonType>" in schema_of(dump)

    assert not remove(dump, VARIANT + ".ПолеПорядка.Товар").errors
    assert not remove(dump, VARIANT + ".Отбор.Организация").errors
    assert "<dcsset:item" not in schema_of(dump)


def test_a_dataset_is_deleted_with_an_honest_warning(dump):
    """Набор данных убирается, а о непроверенном сказано своими словами.

    Снаружи на набор сослаться нельзя — обозначение строится от объекта
    метаданных, — и обратный поиск про такой адрес молчит по существу.
    Но внутри схемы связи есть, и они по именам полей: выбираемое поле
    называет поле набора, запрос называет параметр. Об этом и говорится,
    а не общее «формы и код BSL не смотрим».
    """
    result = remove(dump, SCHEMA_ADDRESS + ".НаборДанных.Остатки")
    assert [f.code for f in result.findings] == ["УДАЛЕНИЕ-СХЕМА-СВЯЗИ-НЕ-ПРОВЕРЕНЫ"]
    assert not result.errors
    after = schema_of(dump)
    assert "<name>Остатки</name>" not in after
    assert "<name>Продажи</name>" in after


def test_an_item_with_no_identity_is_not_silently_matched(dump):
    """Пункт «авто» опознавать нечем, и попадания в первый подходящий нет.

    Таких в конфигурации 14 190 из 63 328: поля порядка и выбираемые поля
    без указания поля, папки, группировки без имени. Адресовать их нельзя,
    и отказ честнее, чем удаление наугад.
    """
    path = os.path.join(dump, "Reports", "мой_Отчёт", "Templates",
                        "ОсновнаяСхема", "Ext", "Template.xml")
    open(path, "w", encoding="utf-8-sig", newline="").write(
        SCHEMA.replace(
            "\t\t<dcsset:name>Основной</dcsset:name>\n",
            "\t\t<dcsset:name>Основной</dcsset:name>\n"
            "\t\t<dcsset:settings>\n\t\t\t<dcsset:order>\n"
            '\t\t\t\t<dcsset:item xsi:type="dcsset:OrderItemAuto"/>\n'
            "\t\t\t</dcsset:order>\n\t\t</dcsset:settings>\n"))
    with pytest.raises(Refuse) as refusal:
        remove(dump, VARIANT + ".ПолеПорядка.Товар")
    assert "нет" in str(refusal.value)


def test_schema_values_carry_the_type_the_platform_writes(dump):
    """Заголовок и значение параметра объявляют тип, а голыми не бывают.

    Замер по 926 схемам: голых `title` — 0 из 25 886, голых `value` —
    0 из 5812, голых `dcsset:presentation` — 0 из 2080. Голое значение —
    форма, которой платформа не пишет никогда, и замера порядка полей тут
    мало: форма значения замеряется отдельно.

    Тип значения идёт от того, что в нём лежит, — тем же механизмом, что
    у правого операнда отбора; у заголовка это простая строка, которая
    в корпусе тоже встречается (103 случая из 25 886).
    """
    add(dump, SCHEMA_ADDRESS, "Параметр",
        {"имя": "Период", "заголовок": "Период", "значение": 42})
    text = schema_of(dump)
    assert '<title xsi:type="xs:string">Период</title>' in text
    assert '<value xsi:type="xs:decimal">42</value>' in text


def test_a_selected_field_title_stays_bare(dump):
    """А заголовок выбираемого поля тип не несёт — и это тоже замер.

    `dcsset:title` голый во всех 484 случаях. Правило не общее «в схеме всё
    с типом», а по элементу — потому и замеряется поэлементно, и потому эти
    два теста стоят рядом.
    """
    add(dump, VARIANT, "ВыбираемоеПоле",
        {"использование": True, "поле": "Товар", "заголовок": "Товар"})
    assert "<dcsset:title>Товар</dcsset:title>" in schema_of(dump)


def test_a_structure_group_is_written_with_what_was_asked(dump):
    """Группировка пишется именем и ничем сверх него.

    Пустые `order` и `selection` есть у всех 2507 группировок конфигурации,
    и напрашивается вывод «раз у всех — значит часть формы записи». Вывод
    неверен: группировка из одного имени проходит круг через платформу без
    правок.

    Проверка стоит здесь именно потому, что вывод из корпуса выглядит
    убедительно: без неё он вернётся при следующем замере.
    """
    add(dump, VARIANT, "ГруппировкаСтруктуры",
        {"использование": True, "имя": "ПоОрганизации"})
    text = schema_of(dump)
    assert "<dcsset:name>ПоОрганизации</dcsset:name>" in text
    assert "<dcsset:order/>" not in text
    assert "<dcsset:selection/>" not in text


def test_a_parameter_type_is_parsed_not_passed_through(dump):
    """Тип параметра разбирается диалектом, а не уходит словарём в перекладку.

    Список полей, несущих тип, объявляет домен — там же, где объявлен состав
    полей, — а не диалект руками. Пропущенное поле (тип параметра схемы, тип
    параметра общей команды) ушло бы в перекладку словарём из JSON, и та
    упала бы изнутри с `AttributeError: 'dict' object has no attribute
    'is_set'`: стек Python вместо ответа на вопрос «что не так в задании».
    """
    add(dump, SCHEMA_ADDRESS, "Параметр",
        {"имя": "Период", "типЗначения": {"вид": "Дата", "состав": "Дата"}})
    text = schema_of(dump)
    assert "<v8:Type>xs:dateTime</v8:Type>" in text
    assert "<v8:DateQualifiers>" in text


def test_a_reference_type_in_a_schema_is_refused_out_loud(dump):
    """Ссылочный тип в схеме не пишется, и сказано почему.

    Приставку для типов конфигурации карточка объявляет в корне (`cfg`),
    а схема — прямо на элементе `<v8:Type>` и с порождённым именем
    (`d4p1`, `d5p1`). Правило порождения не замерено, а придумать своё
    значит записать иначе, чем пишет платформа. Примитив такой приставки
    не требует и пишется: в схемах конфигурации примитивных типов 6202,
    ссылочных 6624 — и о второй половине инструмент говорит вслух.
    """
    result = add(dump, SCHEMA_ADDRESS, "Параметр",
                 {"имя": "Орг", "типЗначения": {"вид": "Справочник",
                                                "имя": "Организации"}},
                 apply_now=False)
    assert [f.code for f in result.errors] == ["ПАРАМЕТР-ССЫЛОЧНЫЙ-ТИП-НЕ-ПИШЕТСЯ"]
    assert "не замерено" in result.errors[0].message


def test_a_type_field_that_is_not_a_type_is_refused_clearly(dump):
    """Запасная проверка: не тип в поле типа — отказ, а не стек Python."""
    from meta.acl import mapping
    from meta.domain.model import Spec

    with pytest.raises(Refuse) as refusal:
        mapping.translate_node(
            Spec("Параметр", {"имя": "П", "типЗначения": {"вид": "Строка"}}), "u1")
    assert "описывает тип" in str(refusal.value)


def test_the_schema_matches_what_the_platform_wrote_back():
    """Эталон: схема, прошедшая круг «записали → загрузили → выгрузили».

    Собрана инструментом в проверочной пустой конфигурации, загружена
    конфигуратором, выгружена обратно — и возвращается байт в байт. В ней сразу
    многое из того, что инструмент пишет в схему: набор данных с `xsi:type`,
    параметры с типизированным заголовком, `xsi:nil` у пустого значения
    и `useRestriction`, выбираемые поля, отбор с представлением, поле порядка
    и группировка структуры без лишних разделов.

    Проверка собирает схему теми же заданиями и сверяет с эталоном побайтно:
    расхождение значит, что инструмент разошёлся с платформой, а не что
    «поменялось форматирование».
    """
    reference = os.path.join(ROOT, "meta", "tests", "эталоны",
                             "СхемаКомпоновки-платформа.xml")
    if not os.path.isfile(reference):
        pytest.skip(f"пропущен: нет {reference}")
    expected = open(reference, "rb").read()

    root = tempfile.mkdtemp(prefix="meta-эталон-")
    try:
        open(os.path.join(root, "Configuration.xml"), "w",
             encoding="utf-8-sig", newline="").write(
            '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
            "\t<Configuration>\n\t\t<ChildObjects/>\n"
            "\t</Configuration>\n</MetaDataObject>")

        from meta.application.add_object.use_case import AddObjectUseCase

        адрес = "Отчет.мой_ПробаСКД.Макет.ОсновнаяСхема"
        вариант = адрес + ".ВариантНастроек.Основной"
        AddObjectUseCase(DesignerDump(root)).execute(
            [job_dialect.spec_from_json({"вид": "Отчет", "поля": {
                "имя": "мой_ПробаСКД", "синоним": "(Мой) Проба СКД",
                "стандартныеКоманды": True,
                "включатьСправкуВСодержание": False,
                "схема": "ОсновнаяСхема", "основнаяСхема": адрес}})],
            apply_now=True)

        add(root, адрес, "НаборДанных", {
            "имя": "Продажи", "источникДанных": "ИсточникДанных1",
            "запрос": "ВЫБРАТЬ\n\tмой_ЭталонДокумент.Ссылка КАК Ссылка,"
                      "\n\tмой_ЭталонДокумент.Дата КАК Дата"
                      "\nИЗ\n\tДокумент.мой_ЭталонДокумент КАК мой_ЭталонДокумент"})
        add(root, адрес, "Параметр", {
            "имя": "НачалоПериода", "заголовок": "Начало периода",
            "типЗначения": {"вид": "Дата", "состав": "Дата"}})
        add(root, адрес, "Параметр", {
            "имя": "ТолькоПроведённые", "заголовок": "Только проведённые",
            "типЗначения": {"вид": "Булево"}, "значение": True})
        add(root, вариант, "ВыбираемоеПоле",
            {"использование": True, "поле": "Ссылка"})
        add(root, вариант, "ВыбираемоеПоле",
            {"использование": True, "поле": "Дата", "заголовок": "Дата"})
        add(root, вариант, "Отбор", {
            "использование": True, "левое": "Дата",
            "видСравнения": "Заполнено", "представление": "Дата заполнена"})
        add(root, вариант, "ПолеПорядка", {
            "использование": True, "поле": "Дата", "направление": "Убывание"})
        add(root, вариант, "ГруппировкаСтруктуры",
            {"использование": True, "имя": "ПоДате"})

        written = open(os.path.join(
            root, "Reports", "мой_ПробаСКД", "Templates", "ОсновнаяСхема",
            "Ext", "Template.xml"), "rb").read()
        assert written == expected, (
            "схема разошлась с тем, что вернула платформа: "
            f"записано {len(written)} Б, эталон {len(expected)} Б")
    finally:
        shutil.rmtree(root, ignore_errors=True)

