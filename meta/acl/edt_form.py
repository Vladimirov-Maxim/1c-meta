"""Перекладка управляемой формы: `Form.xml` выгрузки <-> `Form.form` проекта EDT.

Форма EDT — объект EMF (`form:Form`), и устроена иначе, чем форма выгрузки:

* элемент — обобщённый `items` с `xsi:type` класса (`form:FormField`,
  `form:FormGroup`, `form:Decoration`, `form:Button`, `form:Table`,
  `form:Addition`) и видом в поле `type`;
* свойства, общие для класса, лежат в самом элементе, а свойства своего вида —
  в `extInfo` с классом вида (`form:InputFieldExtInfo`);
* спутники элемента (расширенная подсказка, контекстное меню, командная
  панель, дополнения таблицы) — свойства с именем и `id`;
* умолчания платформы EDT записывает явно (`visible`, `enabled`,
  `userVisible`, у кнопки `placementArea`): EMF их не знает, их знает импорт
  EDT. Таблица умолчаний снята с корпуса и с оракула EDT
  (`edt_form_defaults.py`, `tools/edt_form_check.py --умолчания`).

Порядок свойств и умолчания EMF — метамодель (`edt_model`).

Прямая перекладка (`FormTranslation`) пишет форму, которую создал или
дополнил инструмент: чего она не понимает, она называет (`problems`), а не
теряет — запись с потерей получает отказ. Обратная (`ReverseForm`) нужна, чтобы
править существующую форму EDT тем же редактором, что и форму выгрузки: она
даёт дерево формы выгрузки, из которого прямая перекладка возвращает исходный
файл байт в байт. Что выгрузкой не выражается, едет переходником (`EdtRaw`)
нетронутым; элемент, круг которого не сходится, — «скелетом»: имя, `id`, вид,
дети и спутники, остальное переходником.
"""

from . import edt_model
from .edt_card import (
    FLAGS_BACK,
    LOCAL_STRING,
    MCORE,
    PRIMITIVE_BACK,
    QUALIFIERS_BACK,
    RAW,
    TYPE_DESCRIPTION,
    VALUE,
    Reverse,
    Translation,
    item_part,
    plain,
    raw,
    restore_raw,
)
from .edt_form_defaults import DEFAULTS
from .mapping import Node

FORM = "com._1c.g5.v8.dt.form.model."
MDCLASS = "com._1c.g5.v8.dt.metadata.mdclass."
ADJUSTABLE = MDCLASS + "AdjustableBoolean"

#: Вид элемента выгрузки -> (класс EDT, вид в поле `type`; None — вид из `<Type>`).
KINDS = {
    "UsualGroup": ("FormGroup", "UsualGroup"), "Pages": ("FormGroup", "Pages"),
    "Page": ("FormGroup", "Page"), "ColumnGroup": ("FormGroup", "ColumnGroup"),
    "Popup": ("FormGroup", "Popup"), "CommandBar": ("FormGroup", "CommandBar"),
    "ButtonGroup": ("FormGroup", "ButtonGroup"),
    "LabelDecoration": ("Decoration", "Label"), "PictureDecoration": ("Decoration", "Picture"),
    "Button": ("Button", None), "Table": ("Table", None),
    "SearchStringAddition": ("Addition", "SearchStringAddition"),
    "ViewStatusAddition": ("Addition", "ViewStatusAddition"),
    "SearchControlAddition": ("Addition", "SearchControlAddition"),
    "InputField": ("FormField", "InputField"), "LabelField": ("FormField", "LabelField"),
    "CheckBoxField": ("FormField", "CheckBoxField"), "RadioButtonField": ("FormField", "RadioButtonField"),
    "PictureField": ("FormField", "PictureField"),
    "SpreadSheetDocumentField": ("FormField", "SpreadsheetDocumentField"),
    "TextDocumentField": ("FormField", "TextDocumentField"),
    "HTMLDocumentField": ("FormField", "HTMLDocumentField"),
    "FormattedDocumentField": ("FormField", "FormattedDocumentField"),
    "ProgressBarField": ("FormField", "ProgressBarField"),
    "GraphicalSchemaField": ("FormField", "GraphicalSchemaField"),
    "ChartField": ("FormField", "ChartField"), "CalendarField": ("FormField", "CalendarField"),
    "PlannerField": ("FormField", "PlannerField"), "PeriodField": ("FormField", "PeriodField"),
    "TrackBarField": ("FormField", "TrackBarField"), "DendrogramField": ("FormField", "DendrogramField"),
    "GanttChartField": ("FormField", "GanttChartField"),
    "GeographicalSchemaField": ("FormField", "GeographicalSchemaField"),
    "PDFDocumentField": ("FormField", "PDFDocumentField"),
}
#: (класс EDT, вид) -> вид элемента выгрузки (обратное `KINDS`; кнопка — отдельно).
KINDS_BACK = {kind: tag for tag, kind in KINDS.items() if kind[1] is not None}

#: Вид элемента выгрузки -> класс `extInfo` (замер — все формы корпуса: однозначно).
EXT_INFO = {
    "UsualGroup": "UsualGroupExtInfo", "Pages": "PagesGroupExtInfo", "Page": "PageGroupExtInfo",
    "ColumnGroup": "ColumnGroupExtInfo", "Popup": "PopupGroupExtInfo", "CommandBar": "CommandBarExtInfo",
    "ButtonGroup": "ButtonGroupExtInfo",
    "LabelDecoration": "LabelDecorationExtInfo", "PictureDecoration": "PictureDecorationExtInfo",
    "ExtendedTooltip": "LabelDecorationExtInfo",
    "SearchStringAddition": "SearchStringAdditionExtInfo", "ViewStatusAddition": "ViewStatusAdditionExtInfo",
    "SearchControlAddition": "SearchControlAdditionExtInfo",
    "InputField": "InputFieldExtInfo", "LabelField": "LabelFieldExtInfo",
    "CheckBoxField": "CheckBoxFieldExtInfo", "RadioButtonField": "RadioButtonsFieldExtInfo",
    "PictureField": "ImageFieldExtInfo", "SpreadSheetDocumentField": "SpreadSheetDocFieldExtInfo",
    "TextDocumentField": "TextDocFieldExtInfo", "HTMLDocumentField": "HtmlFieldExtInfo",
    "FormattedDocumentField": "FormattedDocFieldExtInfo", "ProgressBarField": "ProgressBarFieldExtInfo",
    "GraphicalSchemaField": "FlowchartFieldExtInfo", "ChartField": "ChartFieldExtInfo",
    "CalendarField": "CalendarFieldExtInfo", "PlannerField": "PlannerFieldExtInfo",
    "PeriodField": "PeriodFieldExtInfo", "TrackBarField": "TrackBarFieldExtInfo",
    "DendrogramField": "DendrogramFieldExtInfo", "GanttChartField": "GanttChartFieldExtInfo",
    "GeographicalSchemaField": "GeographicalMapFieldExtInfo", "PDFDocumentField": "PDFDocumentFieldExtInfo",
}

#: Спутник выгрузки -> (свойство EDT, вид в `type`).
SATELLITES = {
    "ExtendedTooltip": ("extendedTooltip", "Label"), "ContextMenu": ("contextMenu", None),
    "AutoCommandBar": ("autoCommandBar", None),
    "SearchStringAddition": ("searchStringAddition", "SearchStringAddition"),
    "ViewStatusAddition": ("viewStatusAddition", "ViewStatusAddition"),
    "SearchControlAddition": ("searchControlAddition", "SearchControlAddition"),
}
SATELLITES_BACK = {prop: tag for tag, (prop, _) in SATELLITES.items()}

#: Свойство выгрузки -> имя свойства EDT там, где оно не «то же с маленькой буквы».
RENAMED = {"Events": "handlers", "Autofill": "autoFill", "Hiperlink": "hyperlink",
           "AdditionSource": "source", "CommandSet": "excludedCommands", "Customizable": "allowFormCustomize",
           "AutoURL": "autoUrl", "ModifiesSavedData": "modifiesStoredData", "RadioButtonType": "radioButtonsType",
           "HorizontalLocation": "horizontalAlign", "ChildItemsWidth": "slaveItemsWidth",
           "FillCheck": "fillChecking", "AutoShowState": "showState", "ReportFormType": "settingsForm",
           "DetailsData": "detailsInformation", "ReportResult": "reportResult",
           "CustomSettingsFolder": "userSettingsGroup", "EqualColumnsWidth": "equalElementsWidth",
           "EqualItemsWidth": "equalElementsWidth"}
#: Обратное: имя EDT -> тег выгрузки (у неоднозначных — любой из тегов, прямая
#: перекладка вернёт то же свойство).
RENAMED_BACK = {edt: tag for tag, edt in RENAMED.items()
                if edt not in ("handlers", "source", "horizontalAlign")}

#: Где EDT держит обработчик события: у формы и таблицы — в самом элементе,
#: кроме событий объекта и динамического списка (они в `extInfo`); у поля — в
#: `extInfo`, кроме `OnChange`; у декораций и групп — в `extInfo`. Замер — все
#: формы корпуса: ни одно событие одного класса не встречается в обоих местах.
EXT_EVENTS = {
    "Form": {"AfterWrite", "AfterWriteAtServer", "BeforeLoadUserSettingsAtServer", "BeforeLoadVariantAtServer",
             "BeforeStart", "BeforeWrite", "BeforeWriteAtServer", "OnLoadUserSettingsAtServer",
             "OnLoadVariantAtServer", "OnReadAtServer", "OnSaveUserSettingsAtServer", "OnSaveVariantAtServer",
             "OnUpdateUserSettingSetAtServer", "OnWriteAtServer"},
    "Table": {"BeforeLoadUserSettingsAtServer", "OnGetDataAtServer", "OnLoadUserSettingsAtServer",
              "OnSaveUserSettingsAtServer", "OnUpdateUserSettingSetAtServer"},
}
OWN_EVENTS = {"FormField": {"OnChange"}}

#: Настройка реквизита выгрузки -> свойство `extInfo` EDT, где имя другое.
ATTRIBUTE_SETTINGS = {"ManualQuery": "customQuery"}
ATTRIBUTE_SETTINGS_BACK = {edt: tag for tag, edt in ATTRIBUTE_SETTINGS.items()}

#: Тип основного реквизита -> класс `extInfo` формы (замер — все формы корпуса).
FORM_EXT_INFO = {
    "DynamicList": "DynamicListFormExtInfo", "DataProcessorObject": "ObjectFormExtInfo",
    "ExchangePlanObject": "ObjectFormExtInfo", "ChartOfAccountsObject": "ObjectFormExtInfo",
    "CatalogObject": "CatalogFormExtInfo", "DocumentObject": "DocumentFormExtInfo",
    "InformationRegisterRecordManager": "InformationRegisterManagerFormExtInfo",
    "InformationRegisterRecordSet": "RecordSetFormExtInfo", "ReportObject": "ReportFormExtInfo",
    "ChartOfCharacteristicTypesObject": "ChartOfCharacteristicTypesFormExtInfo",
    "ConstantsSet": "ConstantsFormExtInfo", "TaskObject": "TaskFormExtInfo",
    "BusinessProcessObject": "BusinessProcesFormExtInfo",
}

#: Приставка ссылки выгрузки -> приставка EDT (цвет, шрифт, рамка).
REF_PREFIXES = {"style": "Style", "web": "Web", "win": "Windows", "sys": "System"}
REF_PREFIXES_BACK = {edt: dump for dump, edt in REF_PREFIXES.items()}

#: Командный интерфейс формы, которого выгрузка не задала (замер — все формы корпуса).
EMPTY_COMMAND_INTERFACE = Node("commandInterface", children=[Node("navigationPanel"), Node("commandBar")])

#: Признак переходника «умолчания платформы не дописывать»: всё записано явно.
ALL = "*"
#: Шрифт выгрузки: атрибут -> свойство EDT.
FONT_ATTRIBUTES = ("faceName", "height", "bold", "italic", "underline", "strikeout", "scale")


def ref_word(text):
    """`style:ВажныйЦвет` -> `Style.ВажныйЦвет`; незнакомая приставка — None."""
    prefix, _, name = (text or "").partition(":")
    return f"{REF_PREFIXES[prefix]}.{name}" if prefix in REF_PREFIXES and name else None


def ref_back(word):
    """`Style.ВажныйЦвет` -> `style:ВажныйЦвет`; незнакомое — None."""
    prefix, _, name = (word or "").partition(".")
    return f"{REF_PREFIXES_BACK[prefix]}:{name}" if prefix in REF_PREFIXES_BACK and name else None


def feature_name(tag):
    return RENAMED.get(tag) or tag[:1].lower() + tag[1:]


def feature_names(tag):
    """Кандидаты имени свойства EDT по тегу выгрузки: то же с маленькой буквы,
    затем переименованное (`HorizontalLocation` — у дополнения так и есть,
    у командной панели — `horizontalAlign`)."""
    direct = tag[:1].lower() + tag[1:]
    return [direct] + ([RENAMED[tag]] if tag in RENAMED and RENAMED[tag] != direct else [])


def designer_tag(name):
    return RENAMED_BACK.get(name) or name[:1].upper() + name[1:]


def _by_tag(node, tag):
    return next((c for c in node.children if c.tag == tag), None)


def _is_satellite(node):
    return "name" in node.attrs and "id" in node.attrs


def _key(cls_or_feature, type_):
    """Ключ таблицы умолчаний: `класс|вид` (вид — как записан: умолчание EMF пусто)."""
    return f"{cls_or_feature}|{type_ or ''}"


def default_value(n):
    """Значение узла EDT в записи таблицы умолчаний: текст простого свойства;
    плоский объект — `@класс|поле=значение;…`; вложенный — None."""
    if not n.children:
        if "xsi:type" in n.attrs or n.text is None:
            return f"@{n.attrs.get('xsi:type', '')}|"
        return n.text
    if any(c.children for c in n.children):
        return None
    return f"@{n.attrs.get('xsi:type', '')}|" + ";".join(f"{c.tag}={c.text or ''}" for c in n.children)


def default_node(name, text):
    """Запись таблицы умолчаний -> узел EDT."""
    if not text.startswith("@"):
        return Node(name, text=text)
    cls_name, _, fields = text[1:].partition("|")
    node = Node(name, attrs={"xsi:type": cls_name} if cls_name else {})
    for pair in filter(None, fields.split(";")):
        attr_name, _, value = pair.partition("=")
        node.children.append(Node(attr_name, text=value))
    return node


def same(a, b):
    """Два узла EDT равны так, как их запишет текст."""
    if a.tag != b.tag or dict(a.attrs) != dict(b.attrs) or len(a.children) != len(b.children):
        return False
    if not a.children:
        return a.text == b.text
    return all(same(x, y) for x, y in zip(a.children, b.children, strict=True))


class Assembly:
    """Объект EDT в сборке: свойства по местам, `extInfo` вида, что задано явно."""

    def __init__(self, tag, attrs, cls, ext_name=None):
        self.tag, self.attrs, self.cls = tag, attrs, cls
        self.ext_name = ext_name
        self.ext_cls = FORM + ext_name if ext_name else None
        self.parts = []                # (место, узел)
        self.ext = []                  # (место, узел)
        self.specified = set()         # имена свойств (у свойств вида — `extInfo/имя`)
        self.raw_ext = None            # [узлы] переходника всего `extInfo` (пустой — `extInfo` нет)
        self.all = False               # всё записано явно: умолчаний не дописывать
        self.auto_edit = False

    def add(self, name, nodes):
        self.parts += [(edt_model.position(self.cls, name), n) for n in nodes]

    def add_ext(self, name, nodes):
        self.ext += [(edt_model.position(self.ext_cls, name), n) for n in nodes]

    def has(self, name):
        return name in self.specified or any(n.tag == name for _, n in self.parts)

    def has_ext(self, name):
        return "extInfo/" + name in self.specified or any(n.tag == name for _, n in self.ext)

    def node(self, defaults_key):
        if not self.all:
            for path, text in DEFAULTS.get(defaults_key, {}).items():
                if path.startswith("extInfo/"):
                    name = path[len("extInfo/"):]
                    if self.ext_cls is not None and self.raw_ext is None and not self.has_ext(name) \
                            and edt_model.feature(self.ext_cls, name) is not None:
                        self.add_ext(name, [default_node(name, text)])
                elif not self.has(path) and edt_model.feature(self.cls, path) is not None:
                    self.add(path, [default_node(path, text)])
        if self.raw_ext is not None:
            self.add("extInfo", self.raw_ext)
        elif self.ext_cls is not None:
            ext = Node("extInfo", attrs={"xsi:type": "form:" + self.ext_name},
                       children=[n for _, n in sorted(self.ext, key=lambda pair: pair[0])])
            self.add("extInfo", [ext])
        return Node(self.tag, attrs=self.attrs, children=[n for _, n in sorted(self.parts, key=lambda pt: pt[0])])


class FormTranslation(Translation):
    """Форма выгрузки (узел `Form`) -> корень формы EDT (`form:Form`)."""

    def __init__(self, satellite=None):
        super().__init__(satellite)
        #: ключ объекта (`id` элемента, `Form`, `attributes:Имя`…) -> что выгрузка задала явно
        self.specified_by_id = {}
        #: реквизиты-динамические списки: таблица на них — `DynamicListTableExtInfo`
        self.dynamic_lists = set()

    def form(self, root):
        attributes = _by_tag(root, "Attributes")
        self.dynamic_lists = {a.attrs.get("name") for a in (attributes.children if attributes else ())
                              if self._attribute_ext(a) == "DynamicListExtInfo"}
        main_one = self._main_type(root)
        sb = Assembly("form:Form", {}, FORM + "Form", FORM_EXT_INFO.get(main_one))
        for part in root.children:
            if part.tag == "ChildItems":
                sb.add("items", self.items(part, "Form"))
            elif part.tag == "Attributes":
                sb.add("attributes", [self.attribute(a) for a in part.children])
            elif part.tag == "Commands":
                sb.add("formCommands", [self.command(c) for c in part.children])
            elif part.tag == "Parameters":
                sb.add("parameters", [self.parameter(p) for p in part.children])
            elif part.tag in SATELLITES and _is_satellite(part):
                self.satellite_node(part, sb)
            elif part.tag == "Events":
                self.events(part, "Form", sb)
            elif part.tag == "CommandInterface":
                sb.specified.add("commandInterface")
                self.problem("Form.CommandInterface", "командный интерфейс формы не перекладывается")
            else:
                self.property(part, sb, "Form")
        if not sb.has("commandInterface"):
            sb.add("commandInterface", [Node("commandInterface", children=[Node("navigationPanel"),
                                                                            Node("commandBar")])])
        self.specified_by_id["Form"] = set(sb.specified)
        return sb.node("Form|")

    @staticmethod
    def _main_type(root):
        attributes = _by_tag(root, "Attributes")
        for a in attributes.children if attributes else ():
            main = _by_tag(a, "MainAttribute")
            if main is not None and main.text == "true":
                type_ = _by_tag(a, "Type")
                word = _by_tag(type_, "Type") if type_ is not None else None
                return (word.text or "").partition(":")[2].split(".")[0] if word is not None else None
        return None

    # --- элементы ---

    def items(self, child_items, where):
        nodes = []
        for child in child_items.children:
            if child.tag == RAW:                      # элемент вида, которого выгрузка не пишет
                nodes += [restore_raw(n) for n in child.children]
                continue
            node = self.item(child, where)
            if node is not None:
                nodes.append(node)
        return nodes

    def item(self, x, where):
        kind = KINDS.get(x.tag)
        if kind is None:
            self.problem(where, f"вид элемента «{x.tag}» не перекладывается")
            return None
        cls_name, type_ = kind
        if type_ is None and x.tag == "Button":
            tk = _by_tag(x, "Type")
            type_ = tk.text if tk is not None else "CommandBarButton"
        return self.element(x, "items", cls_name, type_, x.tag, xsi=True)

    def satellite_node(self, x, owner):
        name, type_ = SATELLITES[x.tag]
        f = edt_model.feature(owner.cls, name)
        if f is None:
            self.problem(x.tag, f"спутника нет у {owner.cls.rsplit('.', 1)[-1]}")
            return
        owner.add(name, [self.element(x, name, f.type.rsplit(".", 1)[-1], type_, x.tag, xsi=False)])

    def element(self, x, tag, cls_name, type_, kind, xsi):
        cls = FORM + cls_name
        where = f"{kind} «{x.attrs.get('name', '')}»"
        ext_name = EXT_INFO.get(kind)
        if kind == "Table" and self._data_path_root(x) in self.dynamic_lists:
            ext_name = "DynamicListTableExtInfo"
        sb = Assembly(tag, {"xsi:type": "form:" + cls_name} if xsi else {}, cls, ext_name)
        sb.add("name", [Node("name", text=x.attrs.get("name", ""))])
        sb.add("id", [Node("id", text=x.attrs.get("id", ""))])
        written = None
        f = edt_model.feature(cls, "type") if type_ is not None else None
        if f is not None and not edt_model.is_default(f, type_, cls):
            written = type_
            sb.add("type", [Node("type", text=type_)])
        for c in x.children:
            if c.tag == "ChildItems":
                sb.add("items", self.items(c, where))
            elif c.tag in SATELLITES and _is_satellite(c):
                self.satellite_node(c, sb)
            elif c.tag == "Type" and kind == "Button":
                continue
            elif c.tag == "Events":
                self.events(c, cls_name, sb)
            else:
                self.property(c, sb, where)
        if sb.auto_edit:
            sb.parts = [pair for pair in sb.parts if pair[1].tag != "editMode"]
            sb.add("editMode", [Node("editMode", text="Auto")])
        self.specified_by_id[x.attrs.get("id", "")] = set(sb.specified)
        return sb.node(_key(cls_name if xsi else tag, written))

    @staticmethod
    def _data_path_root(x):
        path = _by_tag(x, "DataPath")
        return (path.text or "").split(".")[0] if path is not None else None

    # --- свойства ---

    def property(self, prop, sb, where):
        """Свойство выгрузки -> узлы в сборке `сб` (свойство вида — в `extInfo`)."""
        if prop.tag == RAW:
            self.raw_property(prop, sb)
            return
        if self.special(prop, sb):
            return
        for name in feature_names(prop.tag):
            f = edt_model.feature(sb.cls, name)
            if f is not None:
                sb.specified.add(name)
                sb.add(name, self.form_value(prop, f, sb.cls, f"{where}.{prop.tag}"))
                return
            f = edt_model.feature(sb.ext_cls, name) if sb.ext_cls is not None else None
            if f is not None:
                sb.specified.add("extInfo/" + name)
                sb.add_ext(name, self.form_value(prop, f, sb.ext_cls, f"{where}.{prop.tag}"))
                return
        sb.specified.add(feature_name(prop.tag))
        if not self._empty(prop):
            self.problem(where, f"свойства «{prop.tag}» нет у {sb.cls.rsplit('.', 1)[-1]}")

    @staticmethod
    def raw_property(prop, sb):
        """Переходник обратной перекладки: узлы EDT — на своё место как были."""
        address = prop.attrs.get("feature", "")
        nodes = [restore_raw(n) for n in prop.children]
        if address == ALL:
            sb.all = True
        elif address == "extInfo":
            sb.raw_ext = nodes
        elif address.startswith("extInfo/"):
            sb.specified.add(address)
            if nodes:
                sb.add_ext(address[len("extInfo/"):], nodes)
        else:
            sb.specified.add(address)
            if nodes:
                sb.add(address, nodes)

    def special(self, prop, sb):
        """Свойства, которые ложатся в EDT не по имени; True — обработано."""
        if prop.tag == "AutoEditMode":
            # режим «автоматически» — в выгрузке флагом при режиме, в EDT — значением режима
            sb.specified.add("editMode")
            sb.auto_edit = sb.auto_edit or prop.text == "true"
            return True
        if prop.tag == "ShowCommandBar" and prop.text == "auto" and sb.cls == FORM + "Table":
            sb.specified.add("showCommandBar")
            sb.add("showCommandBarNeedDereferenced", [Node("showCommandBarNeedDereferenced", text="true")])
            return True
        return False

    def form_value(self, prop, f, cls, where):
        """Значение свойства выгрузки -> узлы EDT."""
        if f.type == ADJUSTABLE:
            return [self.adjustable(prop, f.name, where)]
        if f.type.endswith("AbstractDataPath"):
            if not (prop.text or "").strip():
                return []
            return [Node(f.name, attrs={"xsi:type": "form:DataPath"},
                         children=[Node("segments", text=prop.text)])]
        if f.name == "source" and prop.tag == "AdditionSource":
            element = _by_tag(prop, "Item")
            return [Node("source", text=element.text)] if element is not None and element.text else []
        type_ = f.type.rsplit(".", 1)[-1]
        if f.type == MCORE + "Color":
            return self.color(prop, f.name, where)
        if f.type == MCORE + "Font":
            return self.font(prop, f.name, where)
        if f.type == MCORE + "Picture":
            return self.picture(prop, f.name, where)
        if f.type == MCORE + "Border":
            return self.border(prop, f.name)
        if f.type == MCORE + "StandardPeriod":
            return [self.period(prop, f.name)]
        if type_ == "FormChoiceListDesTimeValue":
            return self.choice_list(prop, f.name, where)
        return self.value_nodes(prop, f, cls, where)

    # --- значения оформления ---

    def color(self, prop, name, where):
        text = (prop.text or "").strip()
        if text in ("", "auto"):
            return []
        if text.startswith("#") and len(text) == 7:
            node = Node(name, attrs={"xsi:type": "core:ColorDef"})
            for channel, part in (("red", text[1:3]), ("green", text[3:5]), ("blue", text[5:7])):
                if int(part, 16):
                    node.children.append(Node(channel, text=str(int(part, 16))))
            return [node]
        word = ref_word(text)
        if word is None:
            self.problem(where, f"незнакомый цвет «{text}»")
            return []
        return [Node(name, attrs={"xsi:type": "core:ColorRef"}, children=[Node("color", text=word)])]

    def font(self, prop, name, where):
        kind = prop.attrs.get("kind")
        if kind == "AutoFont":
            node = Node(name, attrs={"xsi:type": "core:AutoFont"})
        elif kind in ("StyleItem", "WindowsFont") and ref_word(prop.attrs.get("ref")):
            node = Node(name, attrs={"xsi:type": "core:FontRef"},
                        children=[Node("font", text=ref_word(prop.attrs["ref"]))])
        else:
            self.problem(where, f"незнакомый шрифт вида «{kind}»")
            return []
        for attr_name in FONT_ATTRIBUTES:
            if attr_name in prop.attrs:
                value = prop.attrs[attr_name]
                if attr_name == "height" and "." not in value:
                    value += ".0"
                node.children.append(Node(attr_name, text=value))
        return [node]

    def picture(self, prop, name, where):
        ref = _by_tag(prop, "Ref")
        if ref is not None and ref.text:
            return [Node(name, attrs={"xsi:type": "core:PictureRef"}, children=[Node("picture", text=ref.text)])]
        if self._empty(prop):
            return []
        self.problem(where, "картинка не из библиотеки не перекладывается")
        return []

    @staticmethod
    def border(prop, name):
        node = Node(name, attrs={"xsi:type": "core:BorderDef"})
        style = _by_tag(prop, "style")
        if style is not None and style.text:
            node.children.append(Node("style", text=style.text))
        if prop.attrs.get("width") not in (None, "0"):
            node.children.append(Node("width", text=prop.attrs["width"]))
        return [node]

    @staticmethod
    def period(prop, name):
        node = Node(name)
        variant = _by_tag(prop, "variant")
        if variant is not None and variant.text and variant.text != "Custom":
            node.children.append(Node("variant", text=variant.text))
        for tag in ("startDate", "endDate"):
            part = _by_tag(prop, tag)
            if part is not None and part.text:
                node.children.append(Node(tag, text=part.text))
        return node

    def choice_list(self, prop, name, where):
        nodes = []
        for element in prop.children:
            value = _by_tag(element, "Value")
            if value is None or value.attrs.get("type") != "FormChoiceListDesTimeValue":
                self.problem(where, "незнакомый элемент списка выбора")
                continue
            node = Node(name)
            presentation = _by_tag(value, "Presentation")
            if presentation is not None:
                node.children += [Node("presentation", children=[Node("key", text=item_part(i, "lang")),
                                                                 Node("value", text=item_part(i, "content"))])
                                  for i in presentation.children if i.tag == "item"]
            inside = _by_tag(value, "Value")
            if inside is not None:
                v = self.value(inside, "value", where)
                if v is not None:
                    node.children.append(v)
            nodes.append(node)
        return nodes

    def events(self, events, cls_name, sb):
        """События элемента -> обработчики: в самом элементе или в `extInfo` вида."""
        for e in events.children:
            if e.tag != "Event":
                continue
            event = e.attrs.get("name", "")
            node = Node("handlers", children=[Node("event", text=event), Node("name", text=e.text or "")])
            if cls_name in EXT_EVENTS:
                self_node = event not in EXT_EVENTS[cls_name]
            else:
                self_node = event in OWN_EVENTS.get(cls_name, ())
            if not self_node and (sb.ext_cls is None or edt_model.feature(sb.ext_cls, "handlers") is None):
                self_node = True
            if self_node:
                sb.add("handlers", [node])
            else:
                sb.add_ext("handlers", [node])

    def adjustable(self, prop, name, where):
        node = Node(name)
        common = _by_tag(prop, "Common")
        if common is not None and common.text == "true":
            node.children.append(Node("common", text="true"))
        if any(value.tag == "Value" for value in prop.children):
            self.problem(where, "значение по ролям не перекладывается")
        return node

    # --- реквизиты, команды, параметры ---

    def attribute(self, a):
        attribute_name = a.attrs.get("name", "")
        where = f"Attribute «{attribute_name}»"
        ext_name = self._attribute_ext(a)
        sb = Assembly("attributes", {}, FORM + "FormAttribute", ext_name)
        sb.add("name", [Node("name", text=attribute_name)])
        sb.add("id", [Node("id", text=a.attrs.get("id", ""))])
        for c in a.children:
            if c.tag == "Type":
                sb.specified.add("valueType")
                sb.add("valueType", [self.type_description(c, "valueType", where)])
            elif c.tag == "MainAttribute":
                sb.specified.add("main")
                if c.text == "true":
                    sb.add("main", [Node("main", text="true")])
            elif c.tag == "SavedData":
                sb.specified.add("savedData")
                if c.text == "true":
                    sb.add("savedData", [Node("savedData", text="true")])
            elif c.tag in ("UseAlways", "Save"):
                name = "notDefaultUseAlwaysAttributes" if c.tag == "UseAlways" else "settingsSavedData"
                sb.specified.add(name)
                sb.add(name, [Node(name, attrs={"xsi:type": "form:DataPath"}, children=[Node("segments", text=pt.text)])
                             for pt in c.children if pt.text])
            elif c.tag == "Columns":
                sb.add("columns", [self.column(kk, where) for kk in c.children if kk.tag == "Column"])
            elif c.tag == "Settings":
                self.settings(c, sb, where)
            else:
                self.property(c, sb, where)
        self.specified_by_id["attributes:" + attribute_name] = set(sb.specified)
        return sb.node(_key("attributes", ext_name))

    def settings(self, settings, sb, where):
        if sb.ext_cls is None:
            self.problem(where, "настройки реквизита этого типа не перекладываются")
            return
        for part in settings.children:
            if part.tag == "ListSettings":
                continue                                  # отдельным файлом ListSettings.dcss — площадка
            if part.tag == RAW:
                self.raw_property(part, sb)
                continue
            name = ATTRIBUTE_SETTINGS.get(part.tag) or feature_name(part.tag)
            f = edt_model.feature(sb.ext_cls, name)
            sb.specified.add("extInfo/" + name)
            if f is None:
                if not self._empty(part):
                    self.problem(where, f"настройки «{part.tag}» нет у {sb.ext_name}")
                continue
            sb.add_ext(name, self.form_value(part, f, sb.ext_cls, f"{where}.{part.tag}"))

    @staticmethod
    def _attribute_ext(a):
        """Класс `extInfo` реквизита — по типу (замер — все формы корпуса)."""
        type_ = _by_tag(a, "Type")
        words = [c.text or "" for c in type_.children] if type_ is not None else []
        settings = _by_tag(a, "Settings")
        if any(ss.partition(":")[2] == "DynamicList" for ss in words):
            return "DynamicListExtInfo"
        if any(ss.endswith(":SpreadsheetDocument") for ss in words):
            return "SpreadsheetDocumentExtInfo"
        if any(ss.partition(":")[2] == "ValueListType" for ss in words) and settings is not None:
            return "ValueListExtInfo"
        if any(ss.endswith(":FlowchartContextType") for ss in words):
            return "GraphicalSchemeExtInfo"
        return None

    def column(self, kk, where):
        key = f"columns:{where}.{kk.attrs.get('name', '')}"
        where = f"{where}.Column «{kk.attrs.get('name', '')}»"
        sb = Assembly("columns", {}, FORM + "FormAttributeColumn")
        sb.add("name", [Node("name", text=kk.attrs.get("name", ""))])
        sb.add("id", [Node("id", text=kk.attrs.get("id", ""))])
        for c in kk.children:
            if c.tag == "Type":
                sb.specified.add("valueType")
                sb.add("valueType", [self.type_description(c, "valueType", where)])
            else:
                self.property(c, sb, where)
        self.specified_by_id[key] = set(sb.specified)
        return sb.node("columns|")

    def command(self, kk):
        where = f"Command «{kk.attrs.get('name', '')}»"
        sb = Assembly("formCommands", {}, FORM + "FormCommand")
        sb.add("name", [Node("name", text=kk.attrs.get("name", ""))])
        sb.add("id", [Node("id", text=kk.attrs.get("id", ""))])
        for c in kk.children:
            if c.tag == "Action":
                sb.specified.add("action")
                sb.add("action", [Node("action", attrs={"xsi:type": "form:FormCommandHandlerContainer"},
                                       children=[Node("handler", children=[Node("name", text=c.text or "")])])])
            else:
                self.property(c, sb, where)
        self.specified_by_id["formCommands:" + kk.attrs.get("name", "")] = set(sb.specified)
        return sb.node("formCommands|")

    def parameter(self, pt):
        where = f"Parameter «{pt.attrs.get('name', '')}»"
        sb = Assembly("parameters", {}, FORM + "FormParameter")
        sb.add("name", [Node("name", text=pt.attrs.get("name", ""))])
        for c in pt.children:
            if c.tag == "Type":
                sb.specified.add("valueType")
                sb.add("valueType", [self.type_description(c, "valueType", where)])
            else:
                self.property(c, sb, where)
        return sb.node("parameters|")


# --- обратная перекладка -------------------------------------------------------------------


#: Части описания типа выгрузки, которые в форме пишутся с приставкой `v8:`.
V8_TYPE_TAGS = {"Type", "TypeSet", "StringQualifiers", "NumberQualifiers", "DateQualifiers",
                "BinaryDataQualifiers", "Length", "AllowedLength", "Digits", "FractionDigits",
                "AllowedSign", "DateFractions"}


def _v8(node):
    """Описание типа карточки -> описание типа формы: части — с приставкой `v8:`."""
    return Node(("v8:" + node.tag) if node.tag in V8_TYPE_TAGS else node.tag, text=node.text,
                attrs=node.attrs, children=[_v8(c) for c in node.children])


def _groups(node):
    """Дети узла EDT, собранные по свойству подряд: [(имя, [узлы])]."""
    groups = []
    for child in node.children:
        if groups and groups[-1][0] == child.tag:
            groups[-1][1].append(child)
        else:
            groups.append((child.tag, [child]))
    return groups


def as_parsed(node):
    """Узел дерева выгрузки таким, каким его вернёт разбор файла (`to_node`):
    без приставок у тегов и атрибутов, текст без пробелов по краям. Круг
    проверяется на том, что увидит прямая перекладка, а не на том, что собрано."""
    return Node(node.tag.rpartition(":")[2], text=(node.text or "").strip() or None,
                attrs={k.rpartition(":")[2]: v for k, v in node.attrs.items()},
                children=[as_parsed(c) for c in node.children])


def _merge_events(children):
    """Обработчики элемента и его `extInfo` -> одни `Events`, как в выгрузке
    (прямая перекладка разложит их обратно по тем же правилам)."""
    events = [c for c in children if c.tag == "Events"]
    if len(events) < 2:
        return children
    common = Node("Events", children=[e for c in events for e in c.children])
    first_one = children.index(events[0])
    remaining = [c for c in children if c.tag != "Events"]
    return remaining[:first_one] + [common] + remaining[first_one:]


class ReverseForm:
    """Форма EDT -> дерево формы выгрузки, из которого `FormTranslation` даёт ту же
    форму EDT. Дерево — для правки редактором формы выгрузки, а не для конфигуратора."""

    def __init__(self):
        self.forward = FormTranslation()
        self.reverse_values = Reverse()
        #: сколько объектов ушло скелетом: [(вид, имя)]
        self.skeletons = []

    def form(self, root):
        attributes = [n for n in root.children if n.tag == "attributes"]
        self.forward.dynamic_lists = {self._name(a) for a in attributes
                                      if self._ext_class(a) == "DynamicListExtInfo"}
        rich_node = self._form(root, rich=True)
        if self._forward_form(rich_node, root):
            return rich_node
        skeleton = self._form(root, rich=False)
        self.skeletons.append(("Form", ""))
        if self._forward_form(skeleton, root):
            return skeleton
        raise ValueError("форма EDT не проходит круг перекладки даже скелетом")

    def _forward_form(self, designer, root):
        try:
            after_ = FormTranslation().form(as_parsed(designer))
            # объявления пространств имён корня текст вычисляет сам — их не сравнивать
            clean_root = Node(root.tag, attrs={k: v for k, v in root.attrs.items() if not k.startswith("xmlns:")},
                          children=root.children)
            return same(after_, clean_root)
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False

    @staticmethod
    def _name(n):
        return next((c.text for c in n.children if c.tag == "name"), "") or ""

    @staticmethod
    def _ext_class(n):
        ext = _by_tag(n, "extInfo")
        return ext.attrs.get("xsi:type", "").partition(":")[2] if ext is not None else None

    def _form(self, root, rich):
        cls = FORM + "Form"
        expected = None
        for a in (n for n in root.children if n.tag == "attributes"):
            if _by_tag(a, "main") is not None:
                types = _by_tag(a, "valueType")
                word = _by_tag(types, "types") if types is not None else None
                expected = FORM_EXT_INFO.get((word.text or "").split(".")[0]) if word is not None else None
        children = []
        for name, nodes in _groups(root):
            if name == "items":
                children.append(Node("ChildItems", children=[self.item(n) for n in nodes]))
            elif name == "attributes":
                children.append(Node("Attributes", children=[self.attribute(n) for n in nodes]))
            elif name == "formCommands":
                children.append(Node("Commands", children=[self.command(n) for n in nodes]))
            elif name == "parameters":
                children.append(Node("Parameters", children=[self.parameter(n) for n in nodes]))
            elif name == "autoCommandBar":
                children.append(self.satellite(nodes[0], cls, name))
            elif name == "commandInterface":
                if not (len(nodes) == 1 and same(nodes[0], EMPTY_COMMAND_INTERFACE)):
                    children.append(raw(name, nodes))
            elif rich:
                children += self.feature(cls, expected, name, nodes)
            else:
                children.append(raw(name, nodes))
        if rich:
            children = self.normalize(children, root, cls, expected, "Form|")
        else:
            children.append(raw(ALL, []))
            if not any(n.tag == "commandInterface" for n in root.children):
                children.append(raw("commandInterface", []))
            if expected is not None and _by_tag(root, "extInfo") is None:
                children.append(raw("extInfo", []))
        if rich and not any(n.tag == "commandInterface" for n in root.children):
            children.append(raw("commandInterface", []))
        return Node("Form", children=_merge_events(children))

    # --- элементы ---

    def item(self, n):
        cls_name = n.attrs.get("xsi:type", "").partition(":")[2]
        type_ = self._type(n, FORM + cls_name)
        if cls_name in ("Button", "Table"):              # вид в теге не различается: поле `type` — свойство
            tag = cls_name
        else:
            tag = KINDS_BACK.get((cls_name, type_))
        if tag is None:
            return raw("items", [n])                    # вид, которого выгрузка не пишет, — переходником
        return self.element(n, tag, cls_name, "items", type_)

    @staticmethod
    def _type(n, cls):
        tk = _by_tag(n, "type")
        if tk is not None:
            return tk.text
        f = edt_model.feature(cls, "type")
        return edt_model.default_text(f) if f is not None else None

    def satellite(self, n, owner_cls, feature):
        f = edt_model.feature(owner_cls, feature)
        cls_name = f.type.rsplit(".", 1)[-1]
        return self.element(n, SATELLITES_BACK[feature], cls_name, feature, self._type(n, FORM + cls_name))

    def element(self, n, tag, cls_name, feature, type_):
        rich_node = self._element(n, tag, cls_name, type_, feature, rich=True)
        if self._forward_element(rich_node, tag, cls_name, feature, n):
            return rich_node
        skeleton = self._element(n, tag, cls_name, type_, feature, rich=False)
        self.skeletons.append((tag, self._name(n)))
        if self._forward_element(skeleton, tag, cls_name, feature, n):
            return skeleton
        raise ValueError(f"элемент «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def _forward_element(self, designer, tag, cls_name, feature, n):
        forward = FormTranslation()
        forward.dynamic_lists = self.forward.dynamic_lists
        try:
            if feature == "items":
                node = forward.item(as_parsed(designer), "")
            else:
                type_ = SATELLITES[tag][1]
                node = forward.element(as_parsed(designer), feature, cls_name, type_, tag, xsi=False)
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False
        return node is not None and not forward.problems and same(node, n)

    def _element(self, n, tag, cls_name, type_, feature, rich):
        cls = FORM + cls_name
        if tag == "Table":
            path = _by_tag(n, "dataPath")
            segment = _by_tag(path, "segments") if path is not None else None
            root = (segment.text or "").split(".")[0] if segment is not None else None
            expected = "DynamicListTableExtInfo" if root in self.forward.dynamic_lists else None
        else:
            expected = EXT_INFO.get(tag)
        attrs = {"name": self._name(n), "id": next((c.text for c in n.children if c.tag == "id"), "") or ""}
        children, children_count, satellites = [], [], []
        if tag == "Button" and type_ != "CommandBarButton":
            children.append(Node("Type", text=type_))
        for name, nodes in _groups(n):
            if name in ("name", "id", "type"):
                continue
            if name == "items":
                children_count += [self.item(c) for c in nodes]
            elif name in SATELLITES_BACK and edt_model.feature(cls, name) is not None \
                    and edt_model.feature(cls, name).kind == "contains" and not edt_model.feature(cls, name).many:
                satellites.append(self.satellite(nodes[0], cls, name))
            elif rich:
                children += self.feature(cls, expected, name, nodes)
            elif name == "dataPath" and self._plain_path(nodes):
                children.append(Node("DataPath", text=_by_tag(nodes[0], "segments").text))
            else:
                children.append(raw(name, nodes))
        written = type_ if _by_tag(n, "type") is not None else None
        if rich:
            children = self.normalize(children, n, cls, expected, _key(cls_name if feature == "items" else feature,
                                                                 written))
        else:
            children.append(raw(ALL, []))
            if expected is not None and _by_tag(n, "extInfo") is None:
                children.append(raw("extInfo", []))
        if children_count:
            children.append(Node("ChildItems", children=children_count))
        return Node(tag, attrs=attrs, children=_merge_events(children) + satellites)

    @staticmethod
    def _plain_path(nodes):
        if len(nodes) != 1 or nodes[0].attrs.get("xsi:type") != "form:DataPath" or len(nodes[0].children) != 1:
            return False
        segment = _by_tag(nodes[0], "segments")
        return segment is not None and plain(segment.text) and not segment.children

    # --- свойства ---

    def feature(self, cls, expected_ext, name, nodes):
        """Свойство EDT -> свойства выгрузки (непонятное — переходником)."""
        if name == "extInfo":
            ext = nodes[0]
            cls_name = ext.attrs.get("xsi:type", "").partition(":")[2]
            if len(nodes) != 1 or cls_name != expected_ext:
                return [raw("extInfo", nodes)]
            ext_cls = FORM + cls_name
            out = []
            for name_ext, nodes_ext in _groups(ext):
                f = edt_model.feature(ext_cls, name_ext)
                if f is None:
                    out.append(raw("extInfo/" + name_ext, nodes_ext))
                elif name_ext == "handlers":
                    out.append(self.events(nodes_ext))
                else:
                    out += self.value(f, nodes_ext, "extInfo/")
            return out
        f = edt_model.feature(cls, name)
        if f is None:
            return [raw(name, nodes)]
        if name == "handlers":
            return [self.events(nodes)]
        return self.value(f, nodes, "")

    def events(self, nodes):
        events = []
        for h in nodes:
            fields = {c.tag: c.text for c in h.children}
            if set(fields) != {"event", "name"} or not plain(fields["event"]) or not plain(fields["name"] or "x"):
                return raw("handlers", nodes)
            events.append(Node("Event", attrs={"name": fields["event"]}, text=fields["name"]))
        return Node("Events", children=events)

    def value(self, f, nodes, address):
        """Узлы EDT свойства `f` -> свойства выгрузки."""
        tag = designer_tag(f.name)
        adapter = [raw(address + f.name, nodes)]
        single = nodes[0] if len(nodes) == 1 else None
        if f.type == LOCAL_STRING:
            items = []
            for n in nodes:
                fields = {c.tag: c for c in n.children}
                if set(fields) != {"key", "value"} or any(c.children or c.attrs for c in n.children) \
                        or not all(plain(c.text) for c in n.children):
                    return adapter
                items.append(Node("v8:item", children=[Node("v8:lang", text=fields["key"].text),
                                                       Node("v8:content", text=fields["value"].text)]))
            return [Node(tag, children=items)]
        if single is None and not f.many:
            return adapter
        if f.type == ADJUSTABLE:
            if single.attrs or any(c.tag != "common" or c.text != "true" for c in single.children):
                return adapter
            value = "true" if single.children else "false"
            return [Node(tag, children=[Node("xr:Common", text=value)])]
        if f.type.endswith("AbstractDataPath") and not f.many:
            if not self._plain_path(nodes):
                return adapter
            return [Node(tag, text=_by_tag(single, "segments").text)]
        if f.type == TYPE_DESCRIPTION:
            type_ = self.type_description(single, tag)
            return [type_] if type_ is not None else adapter
        if f.type == VALUE:
            value = self.reverse_values.value(single, tag)
            if value is None:
                return adapter
            return [Node(tag, text=value.text,
                         attrs={("xsi:" + k): v for k, v in value.attrs.items()})]
        if f.type == MCORE + "Color":
            return self.color(single, tag) or adapter
        if f.type == MCORE + "Font":
            return self.font(single, tag) or adapter
        if f.type == MCORE + "Picture":
            return self.picture(single, tag) or adapter
        if f.type == MCORE + "Border":
            return self.border(single, tag) or adapter
        if f.kind in ("refers", "attribute"):
            if any(n.children or n.attrs or not plain(n.text) for n in nodes):
                return adapter
            if f.many:
                return [Node(tag, children=[Node("Item", text=n.text) for n in nodes])]
            return [Node(tag, text=single.text)]
        return adapter

    def type_description(self, node, tag):
        type_ = self.reverse_values.type_description(node, tag)
        if type_ is None:
            return None
        # прямая перекладка возьмёт из описания то же, что дал обратный ход;
        # пустые и пробельные тексты ей не пройти — переходником
        for c in type_.children:
            if c.text is not None and not plain(c.text):
                return None
        return Node(tag, children=[_v8(c) for c in type_.children])

    @staticmethod
    def color(n, tag):
        cls_name = n.attrs.get("xsi:type", "")
        if cls_name == "core:ColorRef" and len(n.children) == 1 and n.children[0].tag == "color":
            word = ref_back(n.children[0].text)
            return [Node(tag, text=word)] if word else None
        if cls_name == "core:ColorDef" and all(c.tag in ("red", "green", "blue") and not c.children
                                            for c in n.children):
            parts = {c.tag: int(c.text or "0") for c in n.children}
            if [c.tag for c in n.children] != [ii for ii in ("red", "green", "blue") if ii in parts]:
                return None
            if any(not 0 < v < 256 for v in parts.values()):
                return None
            return [Node(tag, text="#" + "".join(f"{parts.get(ii, 0):02X}" for ii in ("red", "green", "blue")))]
        return None

    @staticmethod
    def font(n, tag):
        cls_name = n.attrs.get("xsi:type", "")
        attrs = {}
        fields = list(n.children)
        if cls_name == "core:FontRef":
            if not fields or fields[0].tag != "font":
                return None
            ref = ref_back(fields[0].text)
            if ref is None or not ref.startswith(("style:", "sys:")):
                return None
            attrs["ref"] = ref
            fields = fields[1:]
        elif cls_name != "core:AutoFont":
            return None
        order = [c.tag for c in fields]
        if order != [ii for ii in FONT_ATTRIBUTES if ii in order] or any(c.children for c in fields):
            return None
        for c in fields:
            text = c.text or ""
            if c.tag == "height":
                if not text.endswith(".0"):
                    return None
                text = text[:-2]
            attrs[c.tag] = text
        if cls_name == "core:AutoFont":
            attrs["kind"] = "AutoFont"
        else:
            attrs["kind"] = "StyleItem" if attrs["ref"].startswith("style:") else "WindowsFont"
        return [Node(tag, attrs=attrs)]

    @staticmethod
    def picture(n, tag):
        if n.attrs.get("xsi:type") == "core:PictureRef" and len(n.children) == 1 \
                and n.children[0].tag == "picture" and plain(n.children[0].text):
            return [Node(tag, children=[Node("xr:Ref", text=n.children[0].text),
                                        Node("xr:LoadTransparent", text="true")])]
        return None

    @staticmethod
    def border(n, tag):
        if n.attrs.get("xsi:type") != "core:BorderDef":
            return None
        fields = {c.tag: c.text for c in n.children}
        if [c.tag for c in n.children] not in (["style", "width"], ["style"], ["width"], []):
            return None
        attrs = {"width": fields["width"]} if "width" in fields else {}
        children = [Node("v8ui:style", attrs={"xsi:type": "v8ui:ControlBorderType"}, text=fields["style"])] \
            if "style" in fields else []
        return [Node(tag, attrs=attrs, children=children)]

    # --- умолчания ---

    def normalize(self, children, n, cls, expected_ext, key):
        """Свойства, совпавшие с умолчанием платформы, не пишутся (прямая
        перекладка их допишет); отсутствующее в EDT, но имеющее умолчание —
        переходником без узлов: «задано, писать нечего»."""
        defaults = DEFAULTS.get(key, {})
        if not defaults:
            return children
        ext = _by_tag(n, "extInfo")
        ext_ok = ext is not None and ext.attrs.get("xsi:type", "").partition(":")[2] == expected_ext
        for path, text in defaults.items():
            if path.startswith("extInfo/"):
                if not ext_ok:
                    continue
                nodes = [c for c in ext.children if c.tag == path[len("extInfo/"):]]
            else:
                nodes = [c for c in n.children if c.tag == path]
            if len(nodes) == 1 and default_value(nodes[0]) == text:
                tag = designer_tag(path.rpartition("/")[2])
                children = [c for c in children if not (c.tag == tag or (c.tag == RAW and c.attrs.get("feature") == path))]
            elif not nodes:
                children.append(raw(path, []))
        return children

    # --- реквизиты, команды, параметры ---

    def attribute(self, n):
        ext_name = self._ext_class(n)
        expected = ext_name if ext_name in ("DynamicListExtInfo", "SpreadsheetDocumentExtInfo",
                                            "ValueListExtInfo", "GraphicalSchemeExtInfo") else None
        rich_node = self._attribute(n, expected, rich=True)
        if self._forward_named(rich_node, n, "attribute"):
            return rich_node
        skeleton = self._attribute(n, expected, rich=False)
        self.skeletons.append(("Attribute", self._name(n)))
        if self._forward_named(skeleton, n, "attribute"):
            return skeleton
        raise ValueError(f"реквизит «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def _forward_named(self, designer, n, kind):
        forward = FormTranslation()
        try:
            node = getattr(forward, kind)(as_parsed(designer))
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False
        return not forward.problems and same(node, n)

    def _attribute(self, n, expected, rich):
        cls = FORM + "FormAttribute"
        attrs = {"name": self._name(n), "id": next((c.text for c in n.children if c.tag == "id"), "") or ""}
        children, settings = [], []
        for name, nodes in _groups(n):
            if name in ("name", "id"):
                continue
            if name == "valueType":
                type_ = self.type_description(nodes[0], "Type") if len(nodes) == 1 else None
                children.append(type_ if type_ is not None else raw(name, nodes))
            elif name == "main" and len(nodes) == 1 and nodes[0].text == "true":
                children.append(Node("MainAttribute", text="true"))
            elif name == "columns":
                children.append(Node("Columns", children=[self.column(c, attrs["name"]) for c in nodes]))
            elif name == "extInfo":
                cls_name = nodes[0].attrs.get("xsi:type", "").partition(":")[2]
                if not rich or len(nodes) != 1 or cls_name != expected:
                    children.append(raw("extInfo", nodes))
                else:
                    settings += self.feature(cls, expected, name, nodes)
            elif rich:
                children += self.feature(cls, expected, name, nodes)
            else:
                children.append(raw(name, nodes))
        if expected is not None and _by_tag(n, "extInfo") is None:
            children.append(raw("extInfo", []))
        if rich:
            children = self.normalize(children + settings, n, cls, expected, _key("attributes", expected))
            settings = [c for c in children if c.tag == RAW and c.attrs.get("feature", "").startswith("extInfo/")
                         or c in settings]
            children = [c for c in children if c not in settings]
        else:
            children.append(raw(ALL, []))
        if settings:
            children.append(Node("Settings", children=[self._setting(c) for c in settings]))
        return Node("Attribute", attrs=attrs, children=children)

    @staticmethod
    def _setting(c):
        if c.tag == RAW:
            return c
        return Node(ATTRIBUTE_SETTINGS_BACK.get(feature_name(c.tag), c.tag), text=c.text,
                    attrs=c.attrs, children=c.children)

    def column(self, n, attribute):
        rich_node = self._simple(n, "Column", FORM + "FormAttributeColumn", "columns|", rich=True)
        forward = FormTranslation()
        try:
            if same(forward.column(as_parsed(rich_node), f"Attribute «{attribute}»"), n) and not forward.problems:
                return rich_node
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            pass
        return self._simple(n, "Column", FORM + "FormAttributeColumn", "columns|", rich=False)

    def command(self, n):
        rich_node = self._simple(n, "Command", FORM + "FormCommand", "formCommands|", rich=True)
        if self._forward_named(rich_node, n, "command"):
            return rich_node
        skeleton = self._simple(n, "Command", FORM + "FormCommand", "formCommands|", rich=False)
        self.skeletons.append(("Command", self._name(n)))
        if self._forward_named(skeleton, n, "command"):
            return skeleton
        raise ValueError(f"команда «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def parameter(self, n):
        rich_node = self._simple(n, "Parameter", FORM + "FormParameter", "parameters|", rich=True)
        if self._forward_named(rich_node, n, "parameter"):
            return rich_node
        skeleton = self._simple(n, "Parameter", FORM + "FormParameter", "parameters|", rich=False)
        if self._forward_named(skeleton, n, "parameter"):
            return skeleton
        raise ValueError(f"параметр «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def _simple(self, n, tag, cls, key, rich):
        attrs = {"name": self._name(n)}
        number = next((c.text for c in n.children if c.tag == "id"), None)
        if number is not None:
            attrs["id"] = number
        children = []
        for name, nodes in _groups(n):
            if name in ("name", "id"):
                continue
            if name == "valueType":
                type_ = self.type_description(nodes[0], "Type") if len(nodes) == 1 else None
                children.append(type_ if type_ is not None else raw(name, nodes))
            elif name == "action" and self._action(nodes) is not None:
                children.append(Node("Action", text=self._action(nodes)))
            elif rich:
                children += self.feature(cls, None, name, nodes)
            else:
                children.append(raw(name, nodes))
        if rich:
            children = self.normalize(children, n, cls, None, key)
        else:
            children.append(raw(ALL, []))
        return Node(tag, attrs=attrs, children=children)

    @staticmethod
    def _action(nodes):
        if len(nodes) != 1 or nodes[0].attrs.get("xsi:type") != "form:FormCommandHandlerContainer":
            return None
        handler = nodes[0].children
        if len(handler) != 1 or handler[0].tag != "handler" or len(handler[0].children) != 1:
            return None
        name = handler[0].children[0]
        return name.text if name.tag == "name" and plain(name.text) else None


__all__ = ["FormTranslation", "ReverseForm", "PRIMITIVE_BACK", "QUALIFIERS_BACK", "FLAGS_BACK"]
