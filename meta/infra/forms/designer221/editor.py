"""Правки описания формы 2.21: чтение того, что есть, и вставка нового.

Документ — дерево lxml, разобранное `LxmlCardTree`: у него доказан
побайтный круг `serialize(parse(x)) == x`, и всё, чего правка не касается,
остаётся как было. Здесь только знание формы 2.21:

* где лежат элементы (`ChildItems` корня, спутников и контейнеров), реквизиты
  (`Attributes`), команды (`Commands`), события (`Events`);
* чем элемент опознаётся — атрибутом `name`; имена уникальны в пределах формы
  (350 065 элементов корпуса, ноль повторов), спутники и автоматические
  панели живут в том же пространстве;
* как раздаются `id`: элементы, спутники и панели — одно пространство, новый
  получает `max + 1`, дальше по порядку документа (спутник — сразу за своим
  элементом, 312 771 из 350 065); реквизиты, команды и колонки каждого
  реквизита — свои счётчики;
* что пишется у только что созданного элемента (`vocabulary.BORN`) и в каком
  порядке (`vocabulary.ELEMENT_ORDER`).
"""

from lxml import etree

from ....acl import mapping
from ....acl.mapping import Node
from ....domain import form_properties as fp
from ....domain import forms as fm
from ....domain import model as dm
from ....domain.model import Refuse
from ...tree_lxml import LxmlCardTree, _depth, _indent, _relayout
from . import vocabulary as voc
from .birth import auto_title, multilang, text_node

TREE = LxmlCardTree()
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"

#: Теги, у которых атрибут `name` — имя элемента формы или спутника.
NAMED_HOLDERS = set(voc.ELEMENT_ORDER) | set(voc.SATELLITES) | {
    "RadioButtonField", "PictureField", "SpreadSheetDocumentField", "HTMLDocumentField",
    "TextDocumentField", "FormattedDocumentField", "PDFDocumentField",
    "GraphicalSchemaField", "ChartField", "GanttChartField", "PlannerField",
    "CalendarField", "ProgressBarField", "TrackBarField", "PeriodField",
    "GeographicalSchemaField", "DendrogramField"}

#: Родители, внутри которых кнопка — кнопка командной панели.
BAR_KINDS = ("CommandBar", "ButtonGroup", "Popup", "AutoCommandBar", "ContextMenu")


def local(node):
    return etree.QName(node).localname


def children_of(node):
    return [c for c in node if isinstance(c.tag, str)]


def child_by_tag(node, tag):
    for child in children_of(node):
        if local(child) == tag:
            return child
    return None


# --- чтение -------------------------------------------------------------------

def named_nodes(root):
    """Имя -> узел для всего, что носит имя элемента: элементы, спутники,
    автоматические панели. События не входят: `<Event name="OnChange">`
    носит `name` наравне с элементом, и повторы там законны."""
    found = {}

    def walk(node):
        for child in children_of(node):
            tag = local(child)
            if tag == "Events":
                continue
            if tag in NAMED_HOLDERS and child.get("name") is not None:
                found[child.get("name")] = child
            walk(child)

    walk(root)
    return found


def element_parent_name(node):
    """Имя ближайшего именованного предка; `None` — корень формы."""
    parent = node.getparent()
    while parent is not None:
        if local(parent) in NAMED_HOLDERS and parent.get("name") is not None:
            return parent.get("name")
        if local(parent) == "Form":
            return None
        parent = parent.getparent()
    return None


def max_id(nodes):
    best = 0
    for node in nodes:
        try:
            best = max(best, int(node.get("id")))
        except (TypeError, ValueError):
            continue
    return best


def attribute_type_text(attribute):
    """Тип реквизита как он записан в файле — `cfg:DocumentObject.X`.

    Нужен там, где решение принимается по тегу: динамический список,
    назначение формы. Человеку и заданию тип показывается словами домена
    (`attribute_type`).
    """
    type_node = child_by_tag(attribute, "Type")
    if type_node is None:
        return None
    return " ".join((c.text or "").strip() for c in children_of(type_node)
                    if local(c) in ("Type", "TypeSet"))


def attribute_type(attribute):
    """Тип реквизита словами домена — `Строка(20)`, `Справочник.Х (Ссылка)`."""
    type_node = child_by_tag(attribute, "Type")
    if type_node is None:
        return None
    if "DynamicList" in (attribute_type_text(attribute) or ""):
        # Тип формы, а не конфигурации: перекладка общих типов его не знает,
        # и знать не должна — динамический список бывает только у формы.
        return dm.PlatformType(fm.DYNAMIC_LIST)
    try:
        return mapping._тип_из_узлов(TREE.to_node(type_node).children)
    except Refuse:
        return attribute_type_text(attribute)


def _element_events(node):
    """События элемента: русское имя -> обработчик."""
    section = child_by_tag(node, "Events")
    if section is None:
        return ()
    return tuple((voc.ELEMENT_EVENTS_BACK.get(e.get("name"), e.get("name")),
                  (e.text or "").strip()) for e in children_of(section))


def _command_of(node):
    """Команда кнопки словами задания: своя — именем, платформенная — с меткой."""
    text = next((c.text or "" for c in children_of(node) if local(c) == "CommandName"), "")
    if text.startswith("Form.Command."):
        return text[len("Form.Command."):]
    if text.startswith("Form.StandardCommand."):
        return "Стандартная." + text[len("Form.StandardCommand."):]
    return text or None


#: Слово группировки по тегу `Group` — обратное к словарю свойств формы.
_LAYOUT = {англ: рус for словарь in ("ГруппировкаПодчиненныхЭлементовФормы", "ГруппировкаКолонок")
           for рус, англ in fp.ENUMS.get(словарь, {}).items()}


def view(root, owner, name):
    """Документ -> `FormView`."""
    elements = {}
    order = []
    for element_name, node in named_nodes(root).items():
        kind = voc.DOMAIN_KIND.get(local(node), local(node))
        path = next((c.text for c in children_of(node) if local(c) == "DataPath"), None)
        # Группировка — ответ на «встанет ли рядом»: иначе её искали бы
        # поиском по Form.xml. Показывается заданная явно.
        group = next((c.text for c in children_of(node) if local(c) == "Group"), None)
        elements[element_name] = fm.ViewItem(
            kind, element_parent_name(node), path,
            _command_of(node) if local(node) == "Button" else None,
            _element_events(node), local(node) in voc.SATELLITES,
            _LAYOUT.get(group, group))
        order.append(element_name)
    attributes = {}
    dynamic_lists = set()
    main = None
    main_type = ""
    attributes_section = child_by_tag(root, "Attributes")
    for attribute in children_of(attributes_section) if attributes_section is not None else []:
        # В разделе реквизитов лежит и условное оформление формы (563 формы
        # корпуса) — это не реквизит, и имени у него нет.
        if local(attribute) != "Attribute":
            continue
        attributes[attribute.get("name")] = attribute_type(attribute)
        if "DynamicList" in (attribute_type_text(attribute) or ""):
            dynamic_lists.add(attribute.get("name"))
        flag = child_by_tag(attribute, "MainAttribute")
        if flag is not None and (flag.text or "").strip() == "true":
            main = attribute.get("name")
            main_type = attribute_type_text(attribute) or ""
    commands_section = child_by_tag(root, "Commands")
    commands, actions = [], {}
    for command in children_of(commands_section) if commands_section is not None else []:
        commands.append(command.get("name"))
        actions[command.get("name")] = next(
            ((c.text or "").strip() for c in children_of(command) if local(c) == "Action"), None)
    events = {}
    events_section = child_by_tag(root, "Events")
    for event in children_of(events_section) if events_section is not None else []:
        events[voc.FORM_EVENTS_BACK.get(event.get("name"), event.get("name"))] = event.text
    return fm.FormView(owner, name, elements, attributes, commands, events, main,
                       _assignment_of(main, main_type, name, owner), dynamic_lists,
                       order, actions)


def _assignment_of(main, main_type, name, owner):
    """Назначение существующей формы — по главному реквизиту, иначе по имени."""
    if main is None:
        return "Произвольная"
    if "DynamicList" in main_type:
        # список или выбор — по имени формы, как решил бы мастер; иначе список
        by_name = fm.assignment_for(name, owner[0] if owner else None)
        return by_name if by_name in fm.LIST_ASSIGNMENTS else "Списка"
    if "RecordManager" in main_type:
        return "Записи"
    if "DocumentObject" in main_type:
        return "Документа"
    if "CatalogObject" in main_type:
        return "Группы" if name == "ФормаГруппы" else "Элемента"
    if "DataProcessorObject" in main_type:
        return "Обработки"
    if "ReportObject" in main_type:
        return "Отчета"
    return "Произвольная"


# --- правки ---------------------------------------------------------------------

class Editor:
    """Правки одного документа. Ничего не пишет на диск."""

    def __init__(self, root, edits, owner_spec=None, new_id=None):
        self.root = root
        self.edits = edits
        self.owner_spec = owner_spec
        self.new_id = new_id
        self.notes = []
        self.handlers = []          # (где, событие, обработчик, имя элемента)
        self.named = named_nodes(root)
        self.next_element_id = max_id(self.named.values()) + 1
        self.view = view(root, edits.owner, edits.name)
        self.form_attributes = dict(self.view.attributes)
        self.dynamic_lists = set(self.view.dynamic_lists)

    # --- вход ---

    def apply(self):
        for name in self.edits.remove_elements:
            self._remove_element(name)
        for name in self.edits.remove_attributes:
            self._remove_named(self._section("Attributes"), name, "реквизит")
        for name in self.edits.remove_commands:
            self._remove_named(self._section("Commands"), name, "команду")
        for attribute in self.edits.attributes:
            self._add_attribute(attribute)
        for command in self.edits.commands:
            self._add_command(command)
        for element in self.edits.elements:
            self._add_element(element)
        for event, handler in self.edits.events.items():
            self._add_form_event(event, handler)
        return self.notes, self.handlers

    # --- разделы корня ---

    def _section(self, tag, create=False):
        found = child_by_tag(self.root, tag)
        if found is not None or not create:
            return found
        index = self._index_by_order(self.root, tag, voc.ROOT_ORDER)
        return self._insert_section(self.root, index, tag)

    def _index_by_order(self, host, tag, order):
        """Куда встаёт раздел, которого ещё нет: по каноническому порядку."""
        if tag not in order:
            raise Refuse(f"не знаю места раздела «{tag}» у «{local(host)}»")
        position = order.index(tag)
        present = [local(c) for c in children_of(host)]
        for following in order[position + 1:]:
            if following in present:
                return present.index(following)
        return len(present)

    def _insert_section(self, host, index, tag):
        element = TREE._element(Node(tag), etree.QName(host).namespace)
        host.insert(index, element)
        _relayout(host, _depth(host))
        return element

    def _insert(self, host, index, node):
        """Вставить описанный узел и расставить отступы у него и у хозяина."""
        element = TREE._element(node, etree.QName(host).namespace)
        _indent(element, _depth(host) + 1)
        host.insert(index, element)
        _relayout(host, _depth(host))
        return element

    # --- удаление ---

    def _remove_element(self, name):
        node = self.named.get(name)
        if node is None:
            raise Refuse(f"элемента «{name}» в форме нет")
        self._remove_node(node)
        self.notes.append(f"убрать элемент «{name}»")
        self.named = named_nodes(self.root)

    def _remove_named(self, section, name, what):
        node = None
        for child in children_of(section) if section is not None else []:
            if child.get("name") == name:
                node = child
        if node is None:
            raise Refuse(f"{what} «{name}» в форме не нашёл")
        self._remove_node(node)
        self.notes.append(f"убрать {what} «{name}»")

    @staticmethod
    def _remove_node(node):
        holder = node.getparent()
        holder.remove(node)
        if len(holder):
            _relayout(holder, _depth(holder))
        else:
            # Опустевший раздел возвращается к одиночному тегу — так его
            # пишет платформа у формы без содержимого.
            holder.text = None

    # --- реквизиты ---

    def _add_attribute(self, attribute):
        if attribute.table:
            self._add_column(attribute)
            return
        section = self._section("Attributes", create=True)
        node = Node("Attribute", attrs={"name": attribute.name,
                                        "id": str(max_id(children_of(section)) + 1)},
                    children=self._attribute_children(attribute))
        self._insert(section, self._after_last(section, "Attribute"), node)
        self.form_attributes[attribute.name] = attribute.value_type
        self.notes.append(f"реквизит формы «{attribute.name}»: {attribute.value_type}")

    def _attribute_children(self, attribute):
        children = {
            "Title": multilang("Title", attribute.title or auto_title(attribute.name)),
            "Type": Node("Type", children=mapping.type_children(attribute.value_type)),
        }
        if attribute.columns:
            columns = []
            for index, column in enumerate(attribute.columns, 1):
                columns.append(self._column_node(column, str(index)))
            children["Columns"] = Node("Columns", children=columns)
        return [children[tag] for tag in voc.ATTRIBUTE_ORDER if tag in children]

    @staticmethod
    def _column_node(column, column_id):
        return Node("Column", attrs={"name": column.name, "id": column_id}, children=[
            multilang("Title", column.title or auto_title(column.name)),
            Node("Type", children=mapping.type_children(column.value_type)),
        ])

    @staticmethod
    def _after_last(section, tag):
        """Место сразу за последним узлом такого вида.

        Конец раздела не годится: последним ребёнком раздела реквизитов бывает
        условное оформление формы, и у всех 563 форм корпуса, где оно
        есть, оно стоит именно последним — новый реквизит идёт перед ним.
        """
        children = children_of(section)
        places = [index for index, node in enumerate(children) if local(node) == tag]
        return places[-1] + 1 if places else 0

    def _add_column(self, attribute):
        section = self._section("Attributes")
        holder = None
        for candidate in children_of(section) if section is not None else []:
            if candidate.get("name") == attribute.table:
                holder = candidate
        if holder is None:
            raise Refuse(f"реквизита-таблицы «{attribute.table}» в форме нет")
        columns = child_by_tag(holder, "Columns")
        if columns is None:
            index = self._index_by_order(holder, "Columns", voc.ATTRIBUTE_ORDER)
            columns = self._insert_section(holder, index, "Columns")
        node = self._column_node(attribute, str(max_id(children_of(columns)) + 1))
        self._insert(columns, len(children_of(columns)), node)
        self.notes.append(f"колонка «{attribute.name}» у «{attribute.table}»: "
                          f"{attribute.value_type}")

    # --- команды ---

    def _add_command(self, command):
        """Команда формы. Заголовок и подсказка пишутся, только если названы:
        у новой команды конфигуратор пишет один `Action` (эталон), а заголовок
        берёт из имени уже интерфейс."""
        section = self._section("Commands", create=True)
        children = []
        if command.title:
            children += [multilang("Title", command.title),
                         multilang("ToolTip", command.title)]
        children.append(text_node("Action", command.action))
        node = Node("Command", attrs={"name": command.name,
                                      "id": str(max_id(children_of(section)) + 1)},
                    children=children)
        self._insert(section, len(children_of(section)), node)
        self.handlers.append(("команда", None, command.action, command.name))
        self.notes.append(f"команда «{command.name}» -> {command.action}")

    # --- события формы ---

    def _add_form_event(self, event, handler):
        english = voc.FORM_EVENTS.get(event)
        if english is None:
            raise Refuse(f"не знаю события формы «{event}»; известны: "
                         + ", ".join(voc.FORM_EVENTS))
        section = self._section("Events", create=True)
        for existing in children_of(section):
            if existing.get("name") == english:
                if (existing.text or "").strip() == handler:
                    return
                raise Refuse(f"событие «{event}» уже обрабатывается процедурой "
                             f"«{existing.text}»")
        self._insert(section, len(children_of(section)),
                     Node("Event", attrs={"name": english}, text=handler))
        self.handlers.append(("форма", event, handler, ""))
        self.notes.append(f"событие формы {event} -> {handler}")

    # --- элементы ---

    def _add_element(self, element):
        host, host_kind = self._host_of(element)
        holder = self._child_items(host, host_kind)
        index = self._position(holder, element)
        node = self._element_node(element, host_kind, self._inside_table(host))
        self._insert(holder, index, node)
        self.named = named_nodes(self.root)
        where = f" в «{element.parent}»" if element.parent else ""
        self.notes.append(f"элемент {element.kind} «{element.name}»{where}"
                          + (f" перед «{element.before}»" if element.before else "")
                          + (f" после «{element.after}»" if element.after else ""))

    def _host_of(self, element):
        if element.parent is None:
            return self.root, "Form"
        host = self.named.get(element.parent)
        if host is None:
            raise Refuse(f"родителя «{element.parent}» в форме нет")
        return host, local(host)

    def _child_items(self, host, host_kind):
        found = child_by_tag(host, "ChildItems")
        if found is not None:
            return found
        order = voc.ROOT_ORDER if host_kind == "Form" else voc.ELEMENT_ORDER.get(host_kind)
        if order is None:
            # спутники (автоматическая панель, контекстное меню): дети — последние
            return self._insert_section(host, len(children_of(host)), "ChildItems")
        return self._insert_section(host, self._index_by_order(host, "ChildItems", order),
                                    "ChildItems")

    @staticmethod
    def _position(holder, element):
        siblings = children_of(holder)
        if element.before is None and element.after is None:
            return len(siblings)
        anchor = element.before or element.after
        for index, sibling in enumerate(siblings):
            if sibling.get("name") == anchor:
                return index if element.before else index + 1
        raise Refuse(f"соседа «{anchor}» рядом с «{element.name}» не нашёл")

    @staticmethod
    def _inside_table(host):
        node = host
        while node is not None and isinstance(node.tag, str):
            if local(node) in ("Table", "ColumnGroup"):
                return True
            node = node.getparent()
        return False

    def _element_node(self, element, host_kind, in_table):
        """Описание нового элемента: рождённое + сказанное, спутники, события, дети."""
        kind = voc.XML_KIND[element.kind]
        node_id = self._take_id()
        properties = {}
        if element.path and kind in ("InputField", "LabelField", "CheckBoxField", "Table",
                                     "PictureField", "RadioButtonField"):
            properties["DataPath"] = text_node("DataPath", element.path)
        if kind == "Button":
            in_bar = host_kind in BAR_KINDS
            properties["Type"] = text_node("Type", "CommandBarButton" if in_bar else "UsualButton")
            properties["CommandName"] = text_node("CommandName", self._command_name(element))
        born = voc.BORN.get(self._born_key(kind, element, in_table),
                            {"properties": (), "satellites": ()})
        for tag, value in born["properties"]:
            if isinstance(value, Node):
                properties[tag] = value
            elif isinstance(value, dict):
                properties[tag] = Node(tag, attrs=value)
            else:
                properties[tag] = text_node(tag, value)
        for name, value in element.properties.items():
            tag, node = self._property_node(element.kind, name, value)
            properties[tag] = node
        if kind in voc.TOOLTIP_AS_TITLE:
            # У контейнеров конфигуратор пишет заголовок всегда, а подсказку —
            # тем же текстом (эталон: группа, страницы, страница, панель).
            title = element.properties.get("Заголовок") or auto_title(element.name)
            properties["Title"] = multilang("Title", title)
            properties.setdefault("ToolTip", multilang("ToolTip", title))
        if kind in voc.TITLE_AS_NAME:
            properties.setdefault("Title", multilang(
                "Title", element.properties.get("Заголовок") or auto_title(element.name)))
        if "Title" in properties and kind in voc.TITLE_ATTRS:
            properties["Title"].attrs.update(voc.TITLE_ATTRS[kind])
        satellites = {tag: self._satellite_node(tag, element.name)
                      for tag in born["satellites"]}
        events = None
        if element.events:
            where = ("таблица" if kind == "Table"
                     else "надпись" if kind == "LabelDecoration" else "элемент")
            events = Node("Events", children=[
                self._event_node(where, event, handler, element.name)
                for event, handler in element.events.items()])
        children = None
        if element.children:
            children = Node("ChildItems", children=[
                self._element_node(child, kind, in_table or kind == "Table")
                for child in element.children])
        # Тег, которого нет в порядке для этого вида, — отказ: иначе он молча
        # пропал бы — задание сказало, файл не получил, никто не заметил.
        # Порядок выведен по корпусу и содержит только то, что там
        # встречается, — чего в корпусе нет, того инструмент наугад не ставит.
        потеряно = [tag for tag in properties if tag not in voc.ELEMENT_ORDER[kind]]
        if потеряно:
            raise Refuse(f"не знаю, где у вида «{element.kind}» стоит "
                         f"{', '.join(sorted(потеряно))} — в замеренной выгрузке такого "
                         "не встречалось")
        ordered = []
        for tag in voc.ELEMENT_ORDER[kind]:
            if tag in properties:
                ordered.append(properties[tag])
            elif tag in satellites:
                ordered.append(satellites[tag])
            elif tag == "Events" and events is not None:
                ordered.append(events)
            elif tag == "ChildItems" and children is not None:
                ordered.append(children)
        return Node(kind, attrs={"name": element.name, "id": node_id}, children=ordered)

    @staticmethod
    def _picture_node(tag, value):
        """Картинка: ссылка плюс `LoadTransparent` — так её пишет платформа во
        всех 27 797 случаях корпуса."""
        источник, имя = value
        return Node(tag, children=[
            Node("xr:Ref", text=f"{voc.PICTURE_PREFIX[источник]}.{имя}"),
            Node("xr:LoadTransparent", text="true"),
        ])

    @staticmethod
    def _choice_list_node(tag, items):
        """Список выбора. Строение одинаково у всех 7090 элементов корпуса:
        внешнее `Presentation` пустое, состояние 0, а представление и значение
        лежат внутри `Value` вида `FormChoiceListDesTimeValue`."""
        children = []
        for значение, представление in items:
            children.append(Node("xr:Item", children=[
                Node("xr:Presentation"),
                Node("xr:CheckState", text="0"),
                Node("xr:Value", attrs={"xsi:type": "FormChoiceListDesTimeValue"}, children=[
                    multilang("Presentation", представление) if представление
                    else Node("Presentation"),
                    Editor._choice_value_node(значение),
                ]),
            ]))
        return Node(tag, children=children)

    @staticmethod
    def _choice_value_node(значение):
        """Значение списка со своим `xsi:type` — по тому, что это за значение."""
        if isinstance(значение, bool):
            return Node("Value", attrs={"xsi:type": "xs:boolean"},
                        text="true" if значение else "false")
        if isinstance(значение, (int, float)):
            return Node("Value", attrs={"xsi:type": "xs:decimal"}, text=str(значение))
        if значение.startswith("Перечисление."):
            _, вид, имя = значение.split(".")
            return Node("Value", attrs={"xsi:type": "xr:DesignTimeRef"},
                        text=f"Enum.{вид}.EnumValue.{имя}")
        return Node("Value", attrs={"xsi:type": "xs:string"}, text=значение)

    def _satellite_node(self, tag, element_name):
        """Спутник с именем и номером; дополнения таблицы — с содержимым."""
        node = Node(tag, attrs={"name": element_name + voc.SATELLITES[tag],
                                "id": self._take_id()})
        addition = voc.ADDITION_TYPES.get(tag)
        if addition:
            own = element_name + voc.SATELLITES[tag]
            node.children = [
                Node("AdditionSource", children=[Node("Item", text=element_name),
                                                 Node("Type", text=addition)]),
                Node("ContextMenu", attrs={"name": own + voc.SATELLITES["ContextMenu"],
                                           "id": self._take_id()}),
                Node("ExtendedTooltip", attrs={"name": own + voc.SATELLITES["ExtendedTooltip"],
                                               "id": self._take_id()}),
            ]
        return node

    def _take_id(self):
        value = self.next_element_id
        self.next_element_id += 1
        return str(value)

    def _event_node(self, where, event, handler, element_name):
        english = voc.ELEMENT_EVENTS.get(event)
        if english is None:
            raise Refuse(f"не знаю события «{event}» у элемента «{element_name}»; "
                         "известны: " + ", ".join(voc.ELEMENT_EVENTS))
        self.handlers.append((where, event, handler, element_name))
        return Node("Event", attrs={"name": english}, text=handler)

    def _born_key(self, kind, element, in_table):
        """Что рождается: у полей внутри таблицы состав другой, у таблицы
        табличной части и таблицы значений — одинаковый (эталон), а у таблицы
        динамического списка и дерева — свой: список читают, а не правят, у
        дерева же нет отбора строк (так их возвращает круг через платформу).

        Источник определяется по типу привязанного реквизита формы, включая
        заведённый этим же заданием: `form_attributes` знает и о нём.
        """
        if kind in ("InputField", "LabelField", "CheckBoxField") and in_table:
            return f"{kind}/в таблице"
        if kind == "Table":
            source = getattr(self.form_attributes.get(element.path or ""), "name", "")
            if (element.path or "") in self.dynamic_lists or source == "ДинамическийСписок":
                return "Table/динамический список"
            if source == "ДеревоЗначений":
                return "Table/дерево"
        return kind

    @staticmethod
    def _command_name(element):
        command = element.command or ""
        if command.startswith("Стандартная."):
            return "Form.StandardCommand." + command.partition(".")[2]
        return "Form.Command." + command

    @staticmethod
    def _property_node(kind, name, value):
        russian, english, value_kind, value = fm.check_property(kind, name, value)
        if english in voc.NOT_IN_DUMP:
            raise Refuse(f"свойство «{russian}» платформа в выгрузку не пишет")
        tag = voc.TAG_BY_PLATFORM_NAME.get(english, english)
        if value_kind == "Картинка":
            return tag, Editor._picture_node(tag, value)
        if value_kind == "СписокЗначений":
            return tag, Editor._choice_list_node(tag, value)
        if tag in voc.STRUCTURED_TAGS:
            raise Refuse(f"свойство «{russian}» имеет в файле собственную структуру "
                         "и заданием не выражается — правится в конфигураторе")
        if value_kind in ("Булево", "БулевоНеопределено"):
            return tag, text_node(tag, "true" if value else "false")
        if value_kind == "Число":
            return tag, text_node(tag, str(value))
        if value_kind == "Строка":
            if tag in voc.MULTILANG_TAGS:
                return tag, multilang(tag, value)
            return tag, text_node(tag, value)
        return tag, text_node(tag, fm.ENUMS[value_kind][value])
