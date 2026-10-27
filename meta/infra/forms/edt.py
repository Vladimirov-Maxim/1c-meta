"""Формат управляемой формы проекта EDT (`Form.form`) — реализация договора
`FormFormat` и перекладка в форму выгрузки и обратно.

Форма EDT — объект EMF (`form:Form`), и устроена иначе, чем `Form.xml`
выгрузки: элементы — обобщённые `items` с `xsi:type` (`form:FormField`,
`form:FormGroup`, `form:Decoration`, `form:Button`, `form:Table`) и видом в
поле `type`; спутники (контекстное меню, расширенная подсказка, командная
панель, дополнения таблицы) — свойства элемента с именем и `id`; реквизиты —
`attributes` с `valueType`; команды — `formCommands`; события — `handlers`
(`event`, `name`). Разбор и запись текста — `infra.edt_xml`: круг на всех
11 058 формах проекта крупной типовой конфигурации — байт в байт.

Показ формы и код доработки типовой формы читают `Form.form` сами. Запись
идёт через форму выгрузки: площадка EDT перекладывает `Form.form` в `Form.xml`
(`designer_text`, обратная перекладка `acl.edt_form.ReverseForm`), правит её
тем же редактором, что и форму выгрузки, и перекладывает обратно
(`edt_files`, `acl.edt_form.FormTranslation`). Круг сверен на всех формах
проекта EDT крупной типовой конфигурации, запись новых форм — с тем, что
пишет сам EDT при импорте той же выгрузки.

Настройки динамического списка (`ListSettings`) EDT держит не в `Form.form`,
а файлом `Attributes/<реквизит>/ExtInfo/ListSettings.dcss` рядом с ним — тело
тех же настроек отдельным документом.
"""

import re

from lxml import etree

from ...acl import edt_form, edt_model, mdo
from ...domain import form_properties as fp
from ...domain import forms as fm
from ...domain import model as dm
from ...domain.model import Refuse
from .. import edt_xml
from ..tree_lxml import LxmlCardTree
from . import module
from . import platform as voc

FORM = "com._1c.g5.v8.dt.form.model."

#: Вид элемента EDT -> тег вида выгрузки (по нему — слово домена). Поле и
#: группа несут вид в `type` теми же словами, что теги выгрузки.
DECORATIONS = {"Label": "LabelDecoration", "Picture": "PictureDecoration"}
#: Спутники элемента: свойство EDT -> тег выгрузки.
SATELLITES = {"extendedTooltip": "ExtendedTooltip", "contextMenu": "ContextMenu",
              "autoCommandBar": "AutoCommandBar", "searchStringAddition": "SearchStringAddition",
              "viewStatusAddition": "ViewStatusAddition", "searchControlAddition": "SearchControlAddition"}

#: Слово группировки по значению EDT — обратное к словарю свойств формы.
LAYOUT = {en: ru for vocabulary in ("ГруппировкаПодчиненныхЭлементовФормы", "ГруппировкаКолонок")
          for ru, en in fp.ENUMS.get(vocabulary, {}).items()}

TREE = LxmlCardTree()

#: Шапка файла настроек динамического списка — так её пишет EDT (оракул
#: `tools/edt_oracle.py`, установленный EDT; в проектах, созданных старыми
#: версиями, бывает ещё `xmlns:lf`).
DCSS_ROOT = ('<Settings xmlns="http://v8.1c.ru/8.1/data-composition-system/settings" '
             'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
             'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
             'xmlns:pal="http://v8.1c.ru/8.1/data/ui/colors/palette" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
             'xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" '
             'xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
             'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" '
             'xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core">')
LOGFORM = "http://v8.1c.ru/8.3/xcf/logform"
#: Глубина `<ListSettings>` в `Form.xml`: Form/Attributes/Attribute/Settings/ListSettings.
LIST_SETTINGS_DEPTH = 4

WRITE_REFUSAL = ("форму проекта EDT (Form.form) правит площадка EDT через форму выгрузки "
                 "(designer_text -> правка -> files), а не реализация формата напрямую")


def _by_tag(node, tag):
    return next((c for c in node.children if c.tag == tag), None)


def _text(node, tag):
    found = _by_tag(node, tag)
    return found.text if found is not None else None


def _kind_tag(item):
    """Тег вида выгрузки для элемента EDT. Вид, равный умолчанию EMF, EDT не
    пишет (`ButtonGroup` у группы, `Picture` у декорации) — он берётся из
    метамодели."""
    cls_name = item.attrs.get("xsi:type", "").partition(":")[2]
    kind = _text(item, "type")
    if kind is None:
        f = edt_model.feature(FORM + cls_name, "type")
        kind = edt_model.default_text(f) if f is not None else None
    if cls_name == "Decoration":
        return DECORATIONS.get(kind, kind)
    if cls_name == "Button":
        return "Button"
    if cls_name == "Table":
        return "Table"
    return kind or cls_name


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
    cls_name = FORM + ext.attrs.get("xsi:type", "").partition(":")[2]
    f = edt_model.feature(cls_name, "group")
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
                item_name = _text(child, "name")
                tag = _kind_tag(child)
                path = _by_tag(child, "dataPath")
                elements[item_name] = fm.ViewItem(
                    voc.DOMAIN_KIND.get(tag, tag), parent,
                    _text(path, "segments") if path is not None else None,
                    _command(child) if tag == "Button" else None,
                    _events(child), False, _layout(child))
                order.append(item_name)
                walk(child, item_name)
            elif child.tag in SATELLITES and _text(child, "name"):
                item_name = _text(child, "name")
                tag = SATELLITES[child.tag]
                elements[item_name] = fm.ViewItem(voc.DOMAIN_KIND.get(tag, tag), parent, None, None, (), True)
                order.append(item_name)
                walk(child, item_name)

    walk(root, None)
    attributes, dynamic_lists, main, main_type = {}, set(), None, ""
    for attribute in (c for c in root.children if c.tag == "attributes"):
        item_name = _text(attribute, "name")
        type_node = _by_tag(attribute, "valueType")
        words = " ".join(c.text or "" for c in type_node.children if c.tag == "types") if type_node else ""
        if "DynamicList" in words:
            attributes[item_name] = dm.PlatformType(fm.DYNAMIC_LIST)
            dynamic_lists.add(item_name)
        else:
            attributes[item_name] = mdo.type_of(type_node) if type_node is not None else None
        if _text(attribute, "main") == "true":
            main, main_type = item_name, words
    commands, actions = [], {}
    for command in (c for c in root.children if c.tag == "formCommands"):
        item_name = _text(command, "name")
        commands.append(item_name)
        action = _by_tag(command, "action")
        handler = _by_tag(action, "handler") if action is not None else None
        actions[item_name] = _text(handler, "name") if handler is not None else None
    events = {voc.FORM_EVENTS_BACK.get(event, event): handler
              for event, handler in ((_text(h, "event"), _text(h, "name"))
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
    for word, purpose in (("RecordManager", "Записи"), ("DocumentObject", "Документа"),
                              ("DataProcessorObject", "Обработки"), ("ReportObject", "Отчета")):
        if word in main_type:
            return purpose
    if "CatalogObject" in main_type:
        return "Группы" if name == "ФормаГруппы" else "Элемента"
    return "Произвольная"


def _foreign_events(root):
    """События, записанные не словом EDT: `<event>ПриОткрытии</event>` вместо
    `<event>OnOpen</event>`. EDT называет события только латиницей, и такое
    событие он не узнаёт — обработчик не вызывается. Круг перекладки на нём не
    сходится, но падает там, где сошёлся первым не он, и отказ назвал бы
    невиновный элемент. Поэтому событие ищется заранее и называется само."""
    found = []

    def walk(node, owner, table):
        for child in node.children:
            if child.tag == "handlers":
                event = next((c.text for c in child.children if c.tag == "event"), "") or ""
                if re.search("[А-Яа-яЁё]", event):
                    english = table.get(event)
                    found.append(f"{owner}: событие «{event}» — "
                                 + (f"в EDT оно называется «{english}»" if english
                                    else "в EDT события называются латиницей"))
            elif child.tag in ("items", *SATELLITES):
                name = next((c.text for c in child.children if c.tag == "name"), "") or child.tag
                walk(child, f"элемент «{name}»", voc.ELEMENT_EVENTS)

    walk(root, "форма", voc.FORM_EVENTS)
    return found


def _misplaced(root):
    """Свойства формы не на своём месте: EDT пишет их в порядке метамодели, и
    чужой порядок (блок, дописанный в конец файла) круг перекладки не пройдёт.
    Пусто, если порядок верный или таблицы метамодели нет."""
    if not edt_model.available():
        return []
    cls = FORM + "Form"
    found, last, last_tag = [], -1, None
    for child in root.children:
        place = edt_model.position(cls, child.tag)
        if place < 0 or child.tag == last_tag:
            continue
        if place < last:
            found.append(f"«{child.tag}» стоит после «{last_tag}»")
        else:
            last, last_tag = place, child.tag
    return found


def designer_text(edt_text):
    """`Form.form` -> текст `Form.xml`, из которого `edt_files` вернёт тот же
    `Form.form` байт в байт."""
    from .registry import for_version  # реестр знает и эту реализацию
    root = edt_xml.parse(edt_text.encode("utf-8"))
    foreign = _foreign_events(root)
    if foreign:
        raise Refuse("форма EDT испорчена — имя события записано не словом EDT, такой обработчик "
                     "не вызывается (поправьте в EDT или в файле): " + "; ".join(foreign))
    try:
        tree = edt_form.ReverseForm().form(root)
    except ValueError as problem:
        misplaced = _misplaced(root)
        if misplaced:
            raise Refuse("форма EDT записана не в порядке EDT — так её пишет не EDT, а правка "
                         "в обход него (пересохраните форму в EDT): " + "; ".join(misplaced)) from problem
        raise Refuse(f"форма EDT не перекладывается в форму выгрузки: {problem}") from problem
    return for_version("2.21").document_text(tree)


def edt_files(form_xml):
    """Текст `Form.xml` -> (текст `Form.form`, {путь относительно каталога формы:
    текст} — настройки динамических списков). Чего перекладка не умеет — отказ."""
    tree = TREE.parse(form_xml)
    files = {}
    for attribute in tree.iter(f"{{{LOGFORM}}}Attribute"):
        settings = attribute.find(f"{{{LOGFORM}}}Settings/{{{LOGFORM}}}ListSettings")
        if settings is not None:
            files[f"Attributes/{attribute.get('name')}/ExtInfo/ListSettings.dcss"] = dcss_text(settings)
    translation = edt_form.FormTranslation()
    form = translation.form(TREE.to_node(tree))
    if translation.problems:
        raise Refuse("форма в формат EDT не перекладывается: " + "; ".join(translation.problems))
    return edt_xml.render(form), files


def dcss_text(list_settings):
    """`<ListSettings>` формы выгрузки -> текст `ListSettings.dcss`: те же узлы
    отдельным документом, пространство настроек — по умолчанию."""
    text = etree.tostring(list_settings, encoding="unicode")
    body = text[text.index(">") + 1:text.rindex("</")]
    body = re.sub(r"(</?)dcsset:", r"\1", body)
    body = body.replace('"dcsset:', '"')
    lines = []
    for line in body.split("\n"):
        if line.startswith("\t" * LIST_SETTINGS_DEPTH):
            line = line[LIST_SETTINGS_DEPTH:]
        lines.append(line)
    body = "\n".join(lines).rstrip("\t")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + DCSS_ROOT + body + "</Settings>\n"


class FormatEdt:
    """Форма проекта EDT: чтение — сама, запись — через форму выгрузки."""

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
        # правит форму выгрузки, переложенную из этой (`designer_text`), — площадка EDT
        raise Refuse(WRITE_REFUSAL)

    def born(self, form, uuid, new_id=None):
        raise Refuse(WRITE_REFUSAL)

    @staticmethod
    def designer_text(text):
        return designer_text(text)

    @staticmethod
    def files(form_xml):
        return edt_files(form_xml)

    def module_text(self, handlers, edits):
        return module.module_text(handlers, edits)

    def handler_procedures(self, handlers, edits):
        return module.procedures(handlers, edits)[0]

    def __repr__(self):
        return "FormatEdt()"
