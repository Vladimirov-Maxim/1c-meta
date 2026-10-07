"""Рождение формы в формате 2.21: карточка и скелет описания.

Что здесь написано, снято с корпуса (11 042 формы) и проверено кругом через
платформу на пустой форме документа: карточка, скелет с главным реквизитом,
запись у хозяина — байт в байт.

Скелет — только то, что конфигуратор пишет форме без содержимого: свойства
корня по назначению, автоматическая командная панель, главный реквизит.
Всё остальное приходит правками (`editor.py`) — рождение и наполнение
разделены, чтобы один и тот же код вставки работал и для новой формы,
и для существующей.
"""

import re

from ....acl import mapping
from ....acl.mapping import Node
from ....domain import model as dm
from . import vocabulary as voc

XSI_TYPE = "xsi:type"


def auto_title(name):
    """«НачалоПериода» -> «Начало периода»: так конфигуратор образует
    заголовок из имени. Слова — по заглавным буквам, аббревиатура (подряд
    заглавные) остаётся как есть; подчёркивание — пробел.

    Совпадает с заголовком у 71 040 реквизитов форм из 89 457; остальные
    правлены руками. Приставка доработок («мой_») в заголовок не идёт:
    у реквизитов с приставкой заголовок обычно пишут без неё, а «Мой флаг»
    на форме не пишет никто.
    """
    name = re.sub(r"^[a-zа-яё]+_", "", name)
    text = re.sub(r"(?<=[a-zа-яё0-9])(?=[A-ZА-ЯЁ])", " ", name.replace("_", " "))
    text = re.sub(r"(?<=[A-ZА-ЯЁ])(?=[A-ZА-ЯЁ][a-zа-яё])", " ", text)
    words = text.split()
    out = []
    for index, word in enumerate(words):
        if word.isupper() and len(word) > 1:
            out.append(word)
        elif index == 0:
            out.append(word[:1].upper() + word[1:])
        else:
            out.append(word.lower())
    return " ".join(out)


def text_node(tag, value):
    return Node(tag, text=value) if value != "" else Node(tag)


def multilang(tag, value):
    return Node(tag, children=mapping.multilang(value))


def card_node(form, uuid):
    """`Forms/<Имя>.xml` (у общей формы — `CommonForms/<Имя>.xml`).

    Семь свойств у всех 10 732 форм в одном порядке; общая форма несёт ещё
    три. `UsePurposes` — обе платформы: 10 715 форм из 10 732.
    """
    properties = [
        text_node("Name", form.name),
        multilang("Synonym", form.synonym or auto_title(form.name)),
        Node("Comment"),
        text_node("FormType", "Managed"),
        text_node("IncludeHelpInContents", "false"),
        Node("UsePurposes", children=[
            Node("v8:Value", attrs={XSI_TYPE: "app:ApplicationUsePurpose"},
                 text="PlatformApplication"),
            Node("v8:Value", attrs={XSI_TYPE: "app:ApplicationUsePurpose"},
                 text="MobilePlatformApplication"),
        ]),
        text_node("UseInInterfaceCompatibilityMode", "Any"),
    ]
    element = "Form"
    if form.owner is None:
        element = "CommonForm"
        properties += [text_node("UseStandardCommands", "false"),
                       Node("ExtendedPresentation"), Node("Explanation")]
    return Node("MetaDataObject", attrs={"version": mapping.FORMAT_VERSION}, children=[
        Node(element, attrs={"uuid": uuid}, children=[
            Node("Properties", children=properties)])])


def skeleton_node(form, new_id=None):
    """`Ext/Form.xml` только что созданной формы."""
    children = {}
    if form.title:
        children["Title"] = multilang("Title", form.title)
        children["AutoTitle"] = text_node("AutoTitle", "false")
    for tag, value in voc.ROOT_BORN[form.assignment]:
        children[tag] = text_node(tag, value)
    children["AutoCommandBar"] = Node("AutoCommandBar",
                                      attrs={"name": voc.AUTO_COMMAND_BAR, "id": "-1"})
    main = form.main_attribute
    children["Attributes"] = Node("Attributes", children=[
        main_attribute_node(form, main, new_id)] if main is not None else [])
    ordered = [children[tag] for tag in voc.ROOT_ORDER if tag in children]
    # Пространства имён — атрибутами корня: сборщик дерева объявляет их
    # в этом порядке, а платформа пишет так же — умолчание первым, дальше
    # по алфавиту приставки.
    attrs = {("xmlns" if not prefix else f"xmlns:{prefix}"): uri
             for prefix, uri in voc.NAMESPACES}
    attrs["version"] = voc.FORMAT_VERSION
    return Node("Form", attrs=attrs, children=ordered)


def main_attribute_node(form, main, new_id):
    children = {}
    if isinstance(main.value_type, dm.PlatformType):
        type_node = Node("Type", children=[Node("v8:Type", text="cfg:DynamicList")])
    else:
        type_node = Node("Type", children=[
            Node("v8:Type", text=mapping.type_notation(main.value_type))])
    children["Type"] = type_node
    children["MainAttribute"] = text_node("MainAttribute", "true")
    for tag, value in voc.MAIN_ATTRIBUTE_BORN[form.assignment]:
        if tag == "UseAlways":
            children[tag] = Node("UseAlways", children=[
                Node("Field", text=field) for field in value])
        elif tag == "Settings":
            children[tag] = dynamic_list_settings(form, new_id)
        else:
            children[tag] = text_node(tag, value)
    ordered = [children[tag] for tag in voc.ATTRIBUTE_ORDER if tag in children]
    return Node("Attribute", attrs={"name": main.name, "id": "1"}, children=ordered)


#: Идентификаторы пользовательских настроек динамического списка — не новые
#: значения, а **константы платформы**: на 3099 форм корпуса у отбора,
#: порядка и условного оформления по одному значению на всех. Выдуманные
#: uuid платформа при круге «записали — загрузили — выгрузили» заменяет на эти.
LIST_SETTING_IDS = {
    "dcsset:filter": "dfcece9d-5077-440b-b6b3-45a5cb4538eb",
    "dcsset:order": "88619765-ccb3-46c6-ac52-38e9c992ebd4",
    "dcsset:conditionalAppearance": "b75fecce-942b-4aed-abc9-e6a02e460fb3",
    "items": "911b6018-f537-43e8-a417-da56b22f9aec",
}


def dynamic_list_settings(form, new_id=None):
    """Настройки динамического списка при рождении: основная таблица —
    хозяин, идентификаторы настроек — постоянные."""
    main_table = mapping.object_notation(f"{form.owner_kind}.{form.owner_name}")
    sections = []
    for tag in ("dcsset:filter", "dcsset:order", "dcsset:conditionalAppearance"):
        sections.append(Node(tag, children=[
            Node("dcsset:viewMode", text="Normal"),
            Node("dcsset:userSettingID", text=LIST_SETTING_IDS[tag])]))
    sections += [Node("dcsset:itemsViewMode", text="Normal"),
                 Node("dcsset:itemsUserSettingID", text=LIST_SETTING_IDS["items"])]
    return Node("Settings", attrs={XSI_TYPE: "DynamicList"}, children=[
        text_node("ManualQuery", "false"),
        text_node("DynamicDataRead", "true"),
        text_node("MainTable", main_table),
        Node("ListSettings", children=sections),
    ])
