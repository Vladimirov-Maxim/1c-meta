"""Формат управляемой формы проекта EDT (`Form.form`) — реализация договора
`FormFormat`, пока только для чтения.

Форма EDT — объект EMF (`form:Form`), и устроена иначе, чем `Form.xml`
выгрузки: элементы — обобщённые `items` с `xsi:type` (`form:FormField`,
`form:FormGroup`, `form:Decoration`, `form:Button`, `form:Table`) и видом в
поле `type`; спутники (контекстное меню, расширенная подсказка, командная
панель, дополнения таблицы) — свойства элемента с именем и `id`; реквизиты —
`attributes` с `valueType`; команды — `formCommands`; события — `handlers`
(`event`, `name`). Разбор и запись текста — `infra.edt_xml`: круг на всех
11 058 формах проекта крупной типовой конфигурации — байт в байт.

Читается всё, что нужно показу формы и коду доработки типовой формы (она
читает форму, чтобы знать соседей и места вставки). Писать XML формы EDT
инструмент пока не умеет: у EDT умолчания платформы для каждого вида элемента
записаны явно, и родить элемент «наугад» нельзя — отказ, а не догадка.
"""

from ...acl import edt_model, mdo
from ...domain import form_properties as fp
from ...domain import forms as fm
from ...domain import model as dm
from ...domain.model import Refuse
from .. import edt_xml
from .designer221 import module
from .designer221 import vocabulary as voc

FORM = "com._1c.g5.v8.dt.form.model."

#: Вид элемента EDT -> тег вида выгрузки (по нему — слово домена). Поле и
#: группа несут вид в `type` теми же словами, что теги выгрузки.
DECORATIONS = {"Label": "LabelDecoration", "Picture": "PictureDecoration"}
#: Спутники элемента: свойство EDT -> тег выгрузки.
SATELLITES = {"extendedTooltip": "ExtendedTooltip", "contextMenu": "ContextMenu",
              "autoCommandBar": "AutoCommandBar", "searchStringAddition": "SearchStringAddition",
              "viewStatusAddition": "ViewStatusAddition", "searchControlAddition": "SearchControlAddition"}

#: Слово группировки по значению EDT — обратное к словарю свойств формы.
LAYOUT = {англ: рус for словарь in ("ГруппировкаПодчиненныхЭлементовФормы", "ГруппировкаКолонок")
          for рус, англ in fp.ENUMS.get(словарь, {}).items()}

WRITE_REFUSAL = ("запись формы проекта EDT (Form.form) инструмент пока не умеет: у EDT умолчания платформы "
                 "для каждого вида элемента записаны явно, и родить элемент наугад нельзя. Типовую форму "
                 "дорабатывают кодом («код»: true) — он работает и с формой EDT")


def _by_tag(node, tag):
    return next((c for c in node.children if c.tag == tag), None)


def _text(node, tag):
    found = _by_tag(node, tag)
    return found.text if found is not None else None


def _kind_tag(item):
    """Тег вида выгрузки для элемента EDT. Вид, равный умолчанию EMF, EDT не
    пишет (`ButtonGroup` у группы, `Picture` у декорации) — он берётся из
    метамодели."""
    класс = item.attrs.get("xsi:type", "").partition(":")[2]
    вид = _text(item, "type")
    if вид is None:
        f = edt_model.feature(FORM + класс, "type")
        вид = edt_model.default_text(f) if f is not None else None
    if класс == "Decoration":
        return DECORATIONS.get(вид, вид)
    if класс == "Button":
        return "Button"
    if класс == "Table":
        return "Table"
    return вид or класс


def _command(item):
    text = _text(item, "commandName") or ""
    if text.startswith("Form.Command."):
        return text[len("Form.Command."):]
    if text.startswith("Form.StandardCommand."):
        return "Стандартная." + text[len("Form.StandardCommand."):]
    return text or None


def _events(node):
    return tuple((voc.ELEMENT_EVENTS_BACK.get(_text(h, "event"), _text(h, "event")), _text(h, "name") or "")
                 for h in node.children if h.tag == "handlers")


def _layout(item):
    """Группировка подчинённых, заданная явно. У EDT свои умолчания: свойства
    нет — значит умолчание EMF (`Horizontal`), а `Auto` — то, что в выгрузке
    не задано вовсе (сверено на формах оракула)."""
    ext = _by_tag(item, "extInfo")
    if ext is None:
        return None
    класс = FORM + ext.attrs.get("xsi:type", "").partition(":")[2]
    f = edt_model.feature(класс, "group")
    if f is None:
        return None
    group = _text(ext, "group") or edt_model.default_text(f)
    if group in (None, "Auto"):
        return None
    return LAYOUT.get(group, group)


def view(root, owner, name):
    """Форма EDT -> `FormView`."""
    elements, order = {}, []

    def walk(node, parent):
        for child in node.children:
            if child.tag == "items":
                имя = _text(child, "name")
                tag = _kind_tag(child)
                путь = _by_tag(child, "dataPath")
                elements[имя] = fm.ViewItem(
                    voc.DOMAIN_KIND.get(tag, tag), parent,
                    _text(путь, "segments") if путь is not None else None,
                    _command(child) if tag == "Button" else None,
                    _events(child), False, _layout(child))
                order.append(имя)
                walk(child, имя)
            elif child.tag in SATELLITES and _text(child, "name"):
                имя = _text(child, "name")
                tag = SATELLITES[child.tag]
                elements[имя] = fm.ViewItem(voc.DOMAIN_KIND.get(tag, tag), parent, None, None, (), True)
                order.append(имя)
                walk(child, имя)

    walk(root, None)
    attributes, dynamic_lists, main, main_type = {}, set(), None, ""
    for attribute in (c for c in root.children if c.tag == "attributes"):
        имя = _text(attribute, "name")
        тип_узел = _by_tag(attribute, "valueType")
        слова = " ".join(c.text or "" for c in тип_узел.children if c.tag == "types") if тип_узел else ""
        if "DynamicList" in слова:
            attributes[имя] = dm.PlatformType(fm.DYNAMIC_LIST)
            dynamic_lists.add(имя)
        else:
            attributes[имя] = mdo.type_of(тип_узел) if тип_узел is not None else None
        if _text(attribute, "main") == "true":
            main, main_type = имя, слова
    commands, actions = [], {}
    for command in (c for c in root.children if c.tag == "formCommands"):
        имя = _text(command, "name")
        commands.append(имя)
        действие = _by_tag(command, "action")
        обработчик = _by_tag(действие, "handler") if действие is not None else None
        actions[имя] = _text(обработчик, "name") if обработчик is not None else None
    events = {voc.FORM_EVENTS_BACK.get(событие, событие): обработчик
              for событие, обработчик in ((_text(h, "event"), _text(h, "name"))
                                          for h in root.children if h.tag == "handlers")}
    return fm.FormView(owner, name, elements, attributes, commands, events, main,
                       _assignment_of(main, main_type, name, owner), dynamic_lists, order, actions)


def _assignment_of(main, main_type, name, owner):
    """Назначение существующей формы — по главному реквизиту, иначе по имени
    (то же правило, что у формы выгрузки; слова типов — у EDT без `cfg:`)."""
    if main is None:
        return "Произвольная"
    if "DynamicList" in main_type:
        by_name = fm.assignment_for(name, owner[0] if owner else None)
        return by_name if by_name in fm.LIST_ASSIGNMENTS else "Списка"
    for слово, назначение in (("RecordManager", "Записи"), ("DocumentObject", "Документа"),
                              ("DataProcessorObject", "Обработки"), ("ReportObject", "Отчета")):
        if слово in main_type:
            return назначение
    if "CatalogObject" in main_type:
        return "Группы" if name == "ФормаГруппы" else "Элемента"
    return "Произвольная"


class FormatEdt:
    """Форма проекта EDT: чтение — полностью, запись — отказ."""

    version = "EDT"

    def matches(self, text):
        return "<form:Form " in text[:4096]

    def load(self, text):
        return edt_xml.parse(text.encode("utf-8"))

    def dump(self, document):
        return edt_xml.render(document)

    def view(self, document, owner, name):
        return view(document, owner, name)

    def apply(self, document, edits, owner_spec=None, new_id=None):
        raise Refuse(WRITE_REFUSAL)

    def born(self, form, uuid, new_id=None):
        raise Refuse(WRITE_REFUSAL)

    def module_text(self, handlers, edits):
        return module.module_text(handlers, edits)

    def handler_procedures(self, handlers, edits):
        return module.procedures(handlers, edits)[0]

    def __repr__(self):
        return "FormatEdt()"
