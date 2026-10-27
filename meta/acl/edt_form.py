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
KINDS_BACK = {kind: тег for тег, kind in KINDS.items() if kind[1] is not None}

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
SATELLITES_BACK = {свойство: тег for тег, (свойство, _) in SATELLITES.items()}

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
RENAMED_BACK = {edt: тег for тег, edt in RENAMED.items()
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
ATTRIBUTE_SETTINGS_BACK = {edt: тег for тег, edt in ATTRIBUTE_SETTINGS.items()}

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
REF_PREFIXES_BACK = {edt: выгр for выгр, edt in REF_PREFIXES.items()}

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
    прямое = tag[:1].lower() + tag[1:]
    return [прямое] + ([RENAMED[tag]] if tag in RENAMED and RENAMED[tag] != прямое else [])


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
    класс, _, fields = text[1:].partition("|")
    узел = Node(name, attrs={"xsi:type": класс} if класс else {})
    for pair in filter(None, fields.split(";")):
        attr_name, _, value = pair.partition("=")
        узел.children.append(Node(attr_name, text=value))
    return узел


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
        реквизиты = _by_tag(root, "Attributes")
        self.dynamic_lists = {a.attrs.get("name") for a in (реквизиты.children if реквизиты else ())
                              if self._attribute_ext(a) == "DynamicListExtInfo"}
        основной = self._main_type(root)
        сб = Assembly("form:Form", {}, FORM + "Form", FORM_EXT_INFO.get(основной))
        for part in root.children:
            if part.tag == "ChildItems":
                сб.add("items", self.items(part, "Form"))
            elif part.tag == "Attributes":
                сб.add("attributes", [self.attribute(a) for a in part.children])
            elif part.tag == "Commands":
                сб.add("formCommands", [self.command(c) for c in part.children])
            elif part.tag == "Parameters":
                сб.add("parameters", [self.parameter(p) for p in part.children])
            elif part.tag in SATELLITES and _is_satellite(part):
                self.satellite_node(part, сб)
            elif part.tag == "Events":
                self.events(part, "Form", сб)
            elif part.tag == "CommandInterface":
                сб.specified.add("commandInterface")
                self.problem("Form.CommandInterface", "командный интерфейс формы не перекладывается")
            else:
                self.property(part, сб, "Form")
        if not сб.has("commandInterface"):
            сб.add("commandInterface", [Node("commandInterface", children=[Node("navigationPanel"),
                                                                            Node("commandBar")])])
        self.specified_by_id["Form"] = set(сб.specified)
        return сб.node("Form|")

    @staticmethod
    def _main_type(root):
        реквизиты = _by_tag(root, "Attributes")
        for a in реквизиты.children if реквизиты else ():
            main = _by_tag(a, "MainAttribute")
            if main is not None and main.text == "true":
                type_ = _by_tag(a, "Type")
                word = _by_tag(type_, "Type") if type_ is not None else None
                return (word.text or "").partition(":")[2].split(".")[0] if word is not None else None
        return None

    # --- элементы ---

    def items(self, child_items, where):
        узлы = []
        for ребёнок in child_items.children:
            if ребёнок.tag == RAW:                      # элемент вида, которого выгрузка не пишет
                узлы += [restore_raw(n) for n in ребёнок.children]
                continue
            узел = self.item(ребёнок, where)
            if узел is not None:
                узлы.append(узел)
        return узлы

    def item(self, x, where):
        kind = KINDS.get(x.tag)
        if kind is None:
            self.problem(where, f"вид элемента «{x.tag}» не перекладывается")
            return None
        класс, type_ = kind
        if type_ is None and x.tag == "Button":
            tk = _by_tag(x, "Type")
            type_ = tk.text if tk is not None else "CommandBarButton"
        return self.element(x, "items", класс, type_, x.tag, xsi=True)

    def satellite_node(self, x, owner):
        name, type_ = SATELLITES[x.tag]
        f = edt_model.feature(owner.cls, name)
        if f is None:
            self.problem(x.tag, f"спутника нет у {owner.cls.rsplit('.', 1)[-1]}")
            return
        owner.add(name, [self.element(x, name, f.type.rsplit(".", 1)[-1], type_, x.tag, xsi=False)])

    def element(self, x, tag, класс, type_, kind, xsi):
        cls = FORM + класс
        where = f"{kind} «{x.attrs.get('name', '')}»"
        ext_name = EXT_INFO.get(kind)
        if kind == "Table" and self._data_path_root(x) in self.dynamic_lists:
            ext_name = "DynamicListTableExtInfo"
        сб = Assembly(tag, {"xsi:type": "form:" + класс} if xsi else {}, cls, ext_name)
        сб.add("name", [Node("name", text=x.attrs.get("name", ""))])
        сб.add("id", [Node("id", text=x.attrs.get("id", ""))])
        записанный = None
        f = edt_model.feature(cls, "type") if type_ is not None else None
        if f is not None and not edt_model.is_default(f, type_, cls):
            записанный = type_
            сб.add("type", [Node("type", text=type_)])
        for c in x.children:
            if c.tag == "ChildItems":
                сб.add("items", self.items(c, where))
            elif c.tag in SATELLITES and _is_satellite(c):
                self.satellite_node(c, сб)
            elif c.tag == "Type" and kind == "Button":
                continue
            elif c.tag == "Events":
                self.events(c, класс, сб)
            else:
                self.property(c, сб, where)
        if сб.auto_edit:
            сб.parts = [pair for pair in сб.parts if pair[1].tag != "editMode"]
            сб.add("editMode", [Node("editMode", text="Auto")])
        self.specified_by_id[x.attrs.get("id", "")] = set(сб.specified)
        return сб.node(_key(класс if xsi else tag, записанный))

    @staticmethod
    def _data_path_root(x):
        path = _by_tag(x, "DataPath")
        return (path.text or "").split(".")[0] if path is not None else None

    # --- свойства ---

    def property(self, свойство, сб, where):
        """Свойство выгрузки -> узлы в сборке `сб` (свойство вида — в `extInfo`)."""
        if свойство.tag == RAW:
            self.raw_property(свойство, сб)
            return
        if self.special(свойство, сб):
            return
        for name in feature_names(свойство.tag):
            f = edt_model.feature(сб.cls, name)
            if f is not None:
                сб.specified.add(name)
                сб.add(name, self.form_value(свойство, f, сб.cls, f"{where}.{свойство.tag}"))
                return
            f = edt_model.feature(сб.ext_cls, name) if сб.ext_cls is not None else None
            if f is not None:
                сб.specified.add("extInfo/" + name)
                сб.add_ext(name, self.form_value(свойство, f, сб.ext_cls, f"{where}.{свойство.tag}"))
                return
        сб.specified.add(feature_name(свойство.tag))
        if not self._empty(свойство):
            self.problem(where, f"свойства «{свойство.tag}» нет у {сб.cls.rsplit('.', 1)[-1]}")

    @staticmethod
    def raw_property(свойство, сб):
        """Переходник обратной перекладки: узлы EDT — на своё место как были."""
        address = свойство.attrs.get("feature", "")
        узлы = [restore_raw(n) for n in свойство.children]
        if address == ALL:
            сб.all = True
        elif address == "extInfo":
            сб.raw_ext = узлы
        elif address.startswith("extInfo/"):
            сб.specified.add(address)
            if узлы:
                сб.add_ext(address[len("extInfo/"):], узлы)
        else:
            сб.specified.add(address)
            if узлы:
                сб.add(address, узлы)

    def special(self, свойство, сб):
        """Свойства, которые ложатся в EDT не по имени; True — обработано."""
        if свойство.tag == "AutoEditMode":
            # режим «автоматически» — в выгрузке флагом при режиме, в EDT — значением режима
            сб.specified.add("editMode")
            сб.auto_edit = сб.auto_edit or свойство.text == "true"
            return True
        if свойство.tag == "ShowCommandBar" and свойство.text == "auto" and сб.cls == FORM + "Table":
            сб.specified.add("showCommandBar")
            сб.add("showCommandBarNeedDereferenced", [Node("showCommandBarNeedDereferenced", text="true")])
            return True
        return False

    def form_value(self, свойство, f, cls, where):
        """Значение свойства выгрузки -> узлы EDT."""
        if f.type == ADJUSTABLE:
            return [self.adjustable(свойство, f.name, where)]
        if f.type.endswith("AbstractDataPath"):
            if not (свойство.text or "").strip():
                return []
            return [Node(f.name, attrs={"xsi:type": "form:DataPath"},
                         children=[Node("segments", text=свойство.text)])]
        if f.name == "source" and свойство.tag == "AdditionSource":
            element = _by_tag(свойство, "Item")
            return [Node("source", text=element.text)] if element is not None and element.text else []
        type_ = f.type.rsplit(".", 1)[-1]
        if f.type == MCORE + "Color":
            return self.color(свойство, f.name, where)
        if f.type == MCORE + "Font":
            return self.font(свойство, f.name, where)
        if f.type == MCORE + "Picture":
            return self.picture(свойство, f.name, where)
        if f.type == MCORE + "Border":
            return self.border(свойство, f.name)
        if f.type == MCORE + "StandardPeriod":
            return [self.period(свойство, f.name)]
        if type_ == "FormChoiceListDesTimeValue":
            return self.choice_list(свойство, f.name, where)
        return self.value_nodes(свойство, f, cls, where)

    # --- значения оформления ---

    def color(self, свойство, name, where):
        text = (свойство.text or "").strip()
        if text in ("", "auto"):
            return []
        if text.startswith("#") and len(text) == 7:
            узел = Node(name, attrs={"xsi:type": "core:ColorDef"})
            for channel, part in (("red", text[1:3]), ("green", text[3:5]), ("blue", text[5:7])):
                if int(part, 16):
                    узел.children.append(Node(channel, text=str(int(part, 16))))
            return [узел]
        word = ref_word(text)
        if word is None:
            self.problem(where, f"незнакомый цвет «{text}»")
            return []
        return [Node(name, attrs={"xsi:type": "core:ColorRef"}, children=[Node("color", text=word)])]

    def font(self, свойство, name, where):
        kind = свойство.attrs.get("kind")
        if kind == "AutoFont":
            узел = Node(name, attrs={"xsi:type": "core:AutoFont"})
        elif kind in ("StyleItem", "WindowsFont") and ref_word(свойство.attrs.get("ref")):
            узел = Node(name, attrs={"xsi:type": "core:FontRef"},
                        children=[Node("font", text=ref_word(свойство.attrs["ref"]))])
        else:
            self.problem(where, f"незнакомый шрифт вида «{kind}»")
            return []
        for attr_name in FONT_ATTRIBUTES:
            if attr_name in свойство.attrs:
                value = свойство.attrs[attr_name]
                if attr_name == "height" and "." not in value:
                    value += ".0"
                узел.children.append(Node(attr_name, text=value))
        return [узел]

    def picture(self, свойство, name, where):
        ссылка = _by_tag(свойство, "Ref")
        if ссылка is not None and ссылка.text:
            return [Node(name, attrs={"xsi:type": "core:PictureRef"}, children=[Node("picture", text=ссылка.text)])]
        if self._empty(свойство):
            return []
        self.problem(where, "картинка не из библиотеки не перекладывается")
        return []

    @staticmethod
    def border(свойство, name):
        узел = Node(name, attrs={"xsi:type": "core:BorderDef"})
        стиль = _by_tag(свойство, "style")
        if стиль is not None and стиль.text:
            узел.children.append(Node("style", text=стиль.text))
        if свойство.attrs.get("width") not in (None, "0"):
            узел.children.append(Node("width", text=свойство.attrs["width"]))
        return [узел]

    @staticmethod
    def period(свойство, name):
        узел = Node(name)
        вариант = _by_tag(свойство, "variant")
        if вариант is not None and вариант.text and вариант.text != "Custom":
            узел.children.append(Node("variant", text=вариант.text))
        for tag in ("startDate", "endDate"):
            part = _by_tag(свойство, tag)
            if part is not None and part.text:
                узел.children.append(Node(tag, text=part.text))
        return узел

    def choice_list(self, свойство, name, where):
        узлы = []
        for element in свойство.children:
            value = _by_tag(element, "Value")
            if value is None or value.attrs.get("type") != "FormChoiceListDesTimeValue":
                self.problem(where, "незнакомый элемент списка выбора")
                continue
            узел = Node(name)
            presentation = _by_tag(value, "Presentation")
            if presentation is not None:
                узел.children += [Node("presentation", children=[Node("key", text=item_part(i, "lang")),
                                                                 Node("value", text=item_part(i, "content"))])
                                  for i in presentation.children if i.tag == "item"]
            inside = _by_tag(value, "Value")
            if inside is not None:
                v = self.value(inside, "value", where)
                if v is not None:
                    узел.children.append(v)
            узлы.append(узел)
        return узлы

    def events(self, events, класс, сб):
        """События элемента -> обработчики: в самом элементе или в `extInfo` вида."""
        for e in events.children:
            if e.tag != "Event":
                continue
            event = e.attrs.get("name", "")
            узел = Node("handlers", children=[Node("event", text=event), Node("name", text=e.text or "")])
            if класс in EXT_EVENTS:
                сам = event not in EXT_EVENTS[класс]
            else:
                сам = event in OWN_EVENTS.get(класс, ())
            if not сам and (сб.ext_cls is None or edt_model.feature(сб.ext_cls, "handlers") is None):
                сам = True
            if сам:
                сб.add("handlers", [узел])
            else:
                сб.add_ext("handlers", [узел])

    def adjustable(self, свойство, name, where):
        узел = Node(name)
        общий = _by_tag(свойство, "Common")
        if общий is not None and общий.text == "true":
            узел.children.append(Node("common", text="true"))
        if any(value.tag == "Value" for value in свойство.children):
            self.problem(where, "значение по ролям не перекладывается")
        return узел

    # --- реквизиты, команды, параметры ---

    def attribute(self, a):
        имя_реквизита = a.attrs.get("name", "")
        where = f"Attribute «{имя_реквизита}»"
        ext_name = self._attribute_ext(a)
        сб = Assembly("attributes", {}, FORM + "FormAttribute", ext_name)
        сб.add("name", [Node("name", text=имя_реквизита)])
        сб.add("id", [Node("id", text=a.attrs.get("id", ""))])
        for c in a.children:
            if c.tag == "Type":
                сб.specified.add("valueType")
                сб.add("valueType", [self.type_description(c, "valueType", where)])
            elif c.tag == "MainAttribute":
                сб.specified.add("main")
                if c.text == "true":
                    сб.add("main", [Node("main", text="true")])
            elif c.tag == "SavedData":
                сб.specified.add("savedData")
                if c.text == "true":
                    сб.add("savedData", [Node("savedData", text="true")])
            elif c.tag in ("UseAlways", "Save"):
                name = "notDefaultUseAlwaysAttributes" if c.tag == "UseAlways" else "settingsSavedData"
                сб.specified.add(name)
                сб.add(name, [Node(name, attrs={"xsi:type": "form:DataPath"}, children=[Node("segments", text=pt.text)])
                             for pt in c.children if pt.text])
            elif c.tag == "Columns":
                сб.add("columns", [self.column(к, where) for к in c.children if к.tag == "Column"])
            elif c.tag == "Settings":
                self.settings(c, сб, where)
            else:
                self.property(c, сб, where)
        self.specified_by_id["attributes:" + имя_реквизита] = set(сб.specified)
        return сб.node(_key("attributes", ext_name))

    def settings(self, settings, сб, where):
        if сб.ext_cls is None:
            self.problem(where, "настройки реквизита этого типа не перекладываются")
            return
        for part in settings.children:
            if part.tag == "ListSettings":
                continue                                  # отдельным файлом ListSettings.dcss — площадка
            if part.tag == RAW:
                self.raw_property(part, сб)
                continue
            name = ATTRIBUTE_SETTINGS.get(part.tag) or feature_name(part.tag)
            f = edt_model.feature(сб.ext_cls, name)
            сб.specified.add("extInfo/" + name)
            if f is None:
                if not self._empty(part):
                    self.problem(where, f"настройки «{part.tag}» нет у {сб.ext_name}")
                continue
            сб.add_ext(name, self.form_value(part, f, сб.ext_cls, f"{where}.{part.tag}"))

    @staticmethod
    def _attribute_ext(a):
        """Класс `extInfo` реквизита — по типу (замер — все формы корпуса)."""
        type_ = _by_tag(a, "Type")
        слова = [c.text or "" for c in type_.children] if type_ is not None else []
        settings = _by_tag(a, "Settings")
        if any(с.partition(":")[2] == "DynamicList" for с in слова):
            return "DynamicListExtInfo"
        if any(с.endswith(":SpreadsheetDocument") for с in слова):
            return "SpreadsheetDocumentExtInfo"
        if any(с.partition(":")[2] == "ValueListType" for с in слова) and settings is not None:
            return "ValueListExtInfo"
        if any(с.endswith(":FlowchartContextType") for с in слова):
            return "GraphicalSchemeExtInfo"
        return None

    def column(self, к, where):
        key = f"columns:{where}.{к.attrs.get('name', '')}"
        where = f"{where}.Column «{к.attrs.get('name', '')}»"
        сб = Assembly("columns", {}, FORM + "FormAttributeColumn")
        сб.add("name", [Node("name", text=к.attrs.get("name", ""))])
        сб.add("id", [Node("id", text=к.attrs.get("id", ""))])
        for c in к.children:
            if c.tag == "Type":
                сб.specified.add("valueType")
                сб.add("valueType", [self.type_description(c, "valueType", where)])
            else:
                self.property(c, сб, where)
        self.specified_by_id[key] = set(сб.specified)
        return сб.node("columns|")

    def command(self, к):
        where = f"Command «{к.attrs.get('name', '')}»"
        сб = Assembly("formCommands", {}, FORM + "FormCommand")
        сб.add("name", [Node("name", text=к.attrs.get("name", ""))])
        сб.add("id", [Node("id", text=к.attrs.get("id", ""))])
        for c in к.children:
            if c.tag == "Action":
                сб.specified.add("action")
                сб.add("action", [Node("action", attrs={"xsi:type": "form:FormCommandHandlerContainer"},
                                       children=[Node("handler", children=[Node("name", text=c.text or "")])])])
            else:
                self.property(c, сб, where)
        self.specified_by_id["formCommands:" + к.attrs.get("name", "")] = set(сб.specified)
        return сб.node("formCommands|")

    def parameter(self, pt):
        where = f"Parameter «{pt.attrs.get('name', '')}»"
        сб = Assembly("parameters", {}, FORM + "FormParameter")
        сб.add("name", [Node("name", text=pt.attrs.get("name", ""))])
        for c in pt.children:
            if c.tag == "Type":
                сб.specified.add("valueType")
                сб.add("valueType", [self.type_description(c, "valueType", where)])
            else:
                self.property(c, сб, where)
        return сб.node("parameters|")


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
    for ребёнок in node.children:
        if groups and groups[-1][0] == ребёнок.tag:
            groups[-1][1].append(ребёнок)
        else:
            groups.append((ребёнок.tag, [ребёнок]))
    return groups


def as_parsed(node):
    """Узел дерева выгрузки таким, каким его вернёт разбор файла (`to_node`):
    без приставок у тегов и атрибутов, текст без пробелов по краям. Круг
    проверяется на том, что увидит прямая перекладка, а не на том, что собрано."""
    return Node(node.tag.rpartition(":")[2], text=(node.text or "").strip() or None,
                attrs={k.rpartition(":")[2]: v for k, v in node.attrs.items()},
                children=[as_parsed(c) for c in node.children])


def _merge_events(дети):
    """Обработчики элемента и его `extInfo` -> одни `Events`, как в выгрузке
    (прямая перекладка разложит их обратно по тем же правилам)."""
    events = [c for c in дети if c.tag == "Events"]
    if len(events) < 2:
        return дети
    общий = Node("Events", children=[e for c in events for e in c.children])
    первый = дети.index(events[0])
    остальные = [c for c in дети if c.tag != "Events"]
    return остальные[:первый] + [общий] + остальные[первый:]


class ReverseForm:
    """Форма EDT -> дерево формы выгрузки, из которого `FormTranslation` даёт ту же
    форму EDT. Дерево — для правки редактором формы выгрузки, а не для конфигуратора."""

    def __init__(self):
        self.forward = FormTranslation()
        self.reverse_values = Reverse()
        #: сколько объектов ушло скелетом: [(вид, имя)]
        self.skeletons = []

    def form(self, root):
        реквизиты = [n for n in root.children if n.tag == "attributes"]
        self.forward.dynamic_lists = {self._name(a) for a in реквизиты
                                      if self._ext_class(a) == "DynamicListExtInfo"}
        богатое = self._form(root, rich=True)
        if self._forward_form(богатое, root):
            return богатое
        скелет = self._form(root, rich=False)
        self.skeletons.append(("Form", ""))
        if self._forward_form(скелет, root):
            return скелет
        raise ValueError("форма EDT не проходит круг перекладки даже скелетом")

    def _forward_form(self, designer, root):
        try:
            after_ = FormTranslation().form(as_parsed(designer))
            # объявления пространств имён корня текст вычисляет сам — их не сравнивать
            корень = Node(root.tag, attrs={k: v for k, v in root.attrs.items() if not k.startswith("xmlns:")},
                          children=root.children)
            return same(after_, корень)
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
        дети = []
        for name, узлы in _groups(root):
            if name == "items":
                дети.append(Node("ChildItems", children=[self.item(n) for n in узлы]))
            elif name == "attributes":
                дети.append(Node("Attributes", children=[self.attribute(n) for n in узлы]))
            elif name == "formCommands":
                дети.append(Node("Commands", children=[self.command(n) for n in узлы]))
            elif name == "parameters":
                дети.append(Node("Parameters", children=[self.parameter(n) for n in узлы]))
            elif name == "autoCommandBar":
                дети.append(self.satellite(узлы[0], cls, name))
            elif name == "commandInterface":
                if not (len(узлы) == 1 and same(узлы[0], EMPTY_COMMAND_INTERFACE)):
                    дети.append(raw(name, узлы))
            elif rich:
                дети += self.feature(cls, expected, name, узлы)
            else:
                дети.append(raw(name, узлы))
        if rich:
            дети = self.normalize(дети, root, cls, expected, "Form|")
        else:
            дети.append(raw(ALL, []))
            if not any(n.tag == "commandInterface" for n in root.children):
                дети.append(raw("commandInterface", []))
            if expected is not None and _by_tag(root, "extInfo") is None:
                дети.append(raw("extInfo", []))
        if rich and not any(n.tag == "commandInterface" for n in root.children):
            дети.append(raw("commandInterface", []))
        return Node("Form", children=_merge_events(дети))

    # --- элементы ---

    def item(self, n):
        класс = n.attrs.get("xsi:type", "").partition(":")[2]
        type_ = self._type(n, FORM + класс)
        if класс in ("Button", "Table"):              # вид в теге не различается: поле `type` — свойство
            тег = класс
        else:
            тег = KINDS_BACK.get((класс, type_))
        if тег is None:
            return raw("items", [n])                    # вид, которого выгрузка не пишет, — переходником
        return self.element(n, тег, класс, "items", type_)

    @staticmethod
    def _type(n, cls):
        tk = _by_tag(n, "type")
        if tk is not None:
            return tk.text
        f = edt_model.feature(cls, "type")
        return edt_model.default_text(f) if f is not None else None

    def satellite(self, n, owner_cls, feature):
        f = edt_model.feature(owner_cls, feature)
        класс = f.type.rsplit(".", 1)[-1]
        return self.element(n, SATELLITES_BACK[feature], класс, feature, self._type(n, FORM + класс))

    def element(self, n, тег, класс, feature, type_):
        богатое = self._element(n, тег, класс, type_, feature, rich=True)
        if self._forward_element(богатое, тег, класс, feature, n):
            return богатое
        скелет = self._element(n, тег, класс, type_, feature, rich=False)
        self.skeletons.append((тег, self._name(n)))
        if self._forward_element(скелет, тег, класс, feature, n):
            return скелет
        raise ValueError(f"элемент «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def _forward_element(self, designer, тег, класс, feature, n):
        вперёд = FormTranslation()
        вперёд.dynamic_lists = self.forward.dynamic_lists
        try:
            if feature == "items":
                узел = вперёд.item(as_parsed(designer), "")
            else:
                type_ = SATELLITES[тег][1]
                узел = вперёд.element(as_parsed(designer), feature, класс, type_, тег, xsi=False)
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False
        return узел is not None and not вперёд.problems and same(узел, n)

    def _element(self, n, тег, класс, type_, feature, rich):
        cls = FORM + класс
        if тег == "Table":
            path = _by_tag(n, "dataPath")
            сегмент = _by_tag(path, "segments") if path is not None else None
            корень = (сегмент.text or "").split(".")[0] if сегмент is not None else None
            expected = "DynamicListTableExtInfo" if корень in self.forward.dynamic_lists else None
        else:
            expected = EXT_INFO.get(тег)
        attrs = {"name": self._name(n), "id": next((c.text for c in n.children if c.tag == "id"), "") or ""}
        дети, детей, спутники = [], [], []
        if тег == "Button" and type_ != "CommandBarButton":
            дети.append(Node("Type", text=type_))
        for name, узлы in _groups(n):
            if name in ("name", "id", "type"):
                continue
            if name == "items":
                детей += [self.item(c) for c in узлы]
            elif name in SATELLITES_BACK and edt_model.feature(cls, name) is not None \
                    and edt_model.feature(cls, name).kind == "contains" and not edt_model.feature(cls, name).many:
                спутники.append(self.satellite(узлы[0], cls, name))
            elif rich:
                дети += self.feature(cls, expected, name, узлы)
            elif name == "dataPath" and self._plain_path(узлы):
                дети.append(Node("DataPath", text=_by_tag(узлы[0], "segments").text))
            else:
                дети.append(raw(name, узлы))
        записанный = type_ if _by_tag(n, "type") is not None else None
        if rich:
            дети = self.normalize(дети, n, cls, expected, _key(класс if feature == "items" else feature,
                                                                 записанный))
        else:
            дети.append(raw(ALL, []))
            if expected is not None and _by_tag(n, "extInfo") is None:
                дети.append(raw("extInfo", []))
        if детей:
            дети.append(Node("ChildItems", children=детей))
        return Node(тег, attrs=attrs, children=_merge_events(дети) + спутники)

    @staticmethod
    def _plain_path(узлы):
        if len(узлы) != 1 or узлы[0].attrs.get("xsi:type") != "form:DataPath" or len(узлы[0].children) != 1:
            return False
        сегмент = _by_tag(узлы[0], "segments")
        return сегмент is not None and plain(сегмент.text) and not сегмент.children

    # --- свойства ---

    def feature(self, cls, expected_ext, name, узлы):
        """Свойство EDT -> свойства выгрузки (непонятное — переходником)."""
        if name == "extInfo":
            ext = узлы[0]
            класс = ext.attrs.get("xsi:type", "").partition(":")[2]
            if len(узлы) != 1 or класс != expected_ext:
                return [raw("extInfo", узлы)]
            ext_cls = FORM + класс
            out = []
            for имя_ext, узлы_ext in _groups(ext):
                f = edt_model.feature(ext_cls, имя_ext)
                if f is None:
                    out.append(raw("extInfo/" + имя_ext, узлы_ext))
                elif имя_ext == "handlers":
                    out.append(self.events(узлы_ext))
                else:
                    out += self.value(f, узлы_ext, "extInfo/")
            return out
        f = edt_model.feature(cls, name)
        if f is None:
            return [raw(name, узлы)]
        if name == "handlers":
            return [self.events(узлы)]
        return self.value(f, узлы, "")

    def events(self, узлы):
        events = []
        for h in узлы:
            fields = {c.tag: c.text for c in h.children}
            if set(fields) != {"event", "name"} or not plain(fields["event"]) or not plain(fields["name"] or "x"):
                return raw("handlers", узлы)
            events.append(Node("Event", attrs={"name": fields["event"]}, text=fields["name"]))
        return Node("Events", children=events)

    def value(self, f, узлы, address):
        """Узлы EDT свойства `f` -> свойства выгрузки."""
        тег = designer_tag(f.name)
        переходник = [raw(address + f.name, узлы)]
        один = узлы[0] if len(узлы) == 1 else None
        if f.type == LOCAL_STRING:
            items = []
            for n in узлы:
                fields = {c.tag: c for c in n.children}
                if set(fields) != {"key", "value"} or any(c.children or c.attrs for c in n.children) \
                        or not all(plain(c.text) for c in n.children):
                    return переходник
                items.append(Node("v8:item", children=[Node("v8:lang", text=fields["key"].text),
                                                       Node("v8:content", text=fields["value"].text)]))
            return [Node(тег, children=items)]
        if один is None and not f.many:
            return переходник
        if f.type == ADJUSTABLE:
            if один.attrs or any(c.tag != "common" or c.text != "true" for c in один.children):
                return переходник
            value = "true" if один.children else "false"
            return [Node(тег, children=[Node("xr:Common", text=value)])]
        if f.type.endswith("AbstractDataPath") and not f.many:
            if not self._plain_path(узлы):
                return переходник
            return [Node(тег, text=_by_tag(один, "segments").text)]
        if f.type == TYPE_DESCRIPTION:
            type_ = self.type_description(один, тег)
            return [type_] if type_ is not None else переходник
        if f.type == VALUE:
            value = self.reverse_values.value(один, тег)
            if value is None:
                return переходник
            return [Node(тег, text=value.text,
                         attrs={("xsi:" + k): v for k, v in value.attrs.items()})]
        if f.type == MCORE + "Color":
            return self.color(один, тег) or переходник
        if f.type == MCORE + "Font":
            return self.font(один, тег) or переходник
        if f.type == MCORE + "Picture":
            return self.picture(один, тег) or переходник
        if f.type == MCORE + "Border":
            return self.border(один, тег) or переходник
        if f.kind in ("refers", "attribute"):
            if any(n.children or n.attrs or not plain(n.text) for n in узлы):
                return переходник
            if f.many:
                return [Node(тег, children=[Node("Item", text=n.text) for n in узлы])]
            return [Node(тег, text=один.text)]
        return переходник

    def type_description(self, узел, тег):
        type_ = self.reverse_values.type_description(узел, тег)
        if type_ is None:
            return None
        # прямая перекладка возьмёт из описания то же, что дал обратный ход;
        # пустые и пробельные тексты ей не пройти — переходником
        for c in type_.children:
            if c.text is not None and not plain(c.text):
                return None
        return Node(тег, children=[_v8(c) for c in type_.children])

    @staticmethod
    def color(n, тег):
        класс = n.attrs.get("xsi:type", "")
        if класс == "core:ColorRef" and len(n.children) == 1 and n.children[0].tag == "color":
            word = ref_back(n.children[0].text)
            return [Node(тег, text=word)] if word else None
        if класс == "core:ColorDef" and all(c.tag in ("red", "green", "blue") and not c.children
                                            for c in n.children):
            parts = {c.tag: int(c.text or "0") for c in n.children}
            if [c.tag for c in n.children] != [и for и in ("red", "green", "blue") if и in parts]:
                return None
            if any(not 0 < v < 256 for v in parts.values()):
                return None
            return [Node(тег, text="#" + "".join(f"{parts.get(и, 0):02X}" for и in ("red", "green", "blue")))]
        return None

    @staticmethod
    def font(n, тег):
        класс = n.attrs.get("xsi:type", "")
        attrs = {}
        fields = list(n.children)
        if класс == "core:FontRef":
            if not fields or fields[0].tag != "font":
                return None
            ссылка = ref_back(fields[0].text)
            if ссылка is None or not ссылка.startswith(("style:", "sys:")):
                return None
            attrs["ref"] = ссылка
            fields = fields[1:]
        elif класс != "core:AutoFont":
            return None
        порядок = [c.tag for c in fields]
        if порядок != [и for и in FONT_ATTRIBUTES if и in порядок] or any(c.children for c in fields):
            return None
        for c in fields:
            text = c.text or ""
            if c.tag == "height":
                if not text.endswith(".0"):
                    return None
                text = text[:-2]
            attrs[c.tag] = text
        if класс == "core:AutoFont":
            attrs["kind"] = "AutoFont"
        else:
            attrs["kind"] = "StyleItem" if attrs["ref"].startswith("style:") else "WindowsFont"
        return [Node(тег, attrs=attrs)]

    @staticmethod
    def picture(n, тег):
        if n.attrs.get("xsi:type") == "core:PictureRef" and len(n.children) == 1 \
                and n.children[0].tag == "picture" and plain(n.children[0].text):
            return [Node(тег, children=[Node("xr:Ref", text=n.children[0].text),
                                        Node("xr:LoadTransparent", text="true")])]
        return None

    @staticmethod
    def border(n, тег):
        if n.attrs.get("xsi:type") != "core:BorderDef":
            return None
        fields = {c.tag: c.text for c in n.children}
        if [c.tag for c in n.children] not in (["style", "width"], ["style"], ["width"], []):
            return None
        attrs = {"width": fields["width"]} if "width" in fields else {}
        дети = [Node("v8ui:style", attrs={"xsi:type": "v8ui:ControlBorderType"}, text=fields["style"])] \
            if "style" in fields else []
        return [Node(тег, attrs=attrs, children=дети)]

    # --- умолчания ---

    def normalize(self, дети, n, cls, expected_ext, key):
        """Свойства, совпавшие с умолчанием платформы, не пишутся (прямая
        перекладка их допишет); отсутствующее в EDT, но имеющее умолчание —
        переходником без узлов: «задано, писать нечего»."""
        умолчания = DEFAULTS.get(key, {})
        if not умолчания:
            return дети
        ext = _by_tag(n, "extInfo")
        ext_ok = ext is not None and ext.attrs.get("xsi:type", "").partition(":")[2] == expected_ext
        for path, text in умолчания.items():
            if path.startswith("extInfo/"):
                if not ext_ok:
                    continue
                узлы = [c for c in ext.children if c.tag == path[len("extInfo/"):]]
            else:
                узлы = [c for c in n.children if c.tag == path]
            if len(узлы) == 1 and default_value(узлы[0]) == text:
                тег = designer_tag(path.rpartition("/")[2])
                дети = [c for c in дети if not (c.tag == тег or (c.tag == RAW and c.attrs.get("feature") == path))]
            elif not узлы:
                дети.append(raw(path, []))
        return дети

    # --- реквизиты, команды, параметры ---

    def attribute(self, n):
        ext_name = self._ext_class(n)
        expected = ext_name if ext_name in ("DynamicListExtInfo", "SpreadsheetDocumentExtInfo",
                                            "ValueListExtInfo", "GraphicalSchemeExtInfo") else None
        богатое = self._attribute(n, expected, rich=True)
        if self._forward_named(богатое, n, "attribute"):
            return богатое
        скелет = self._attribute(n, expected, rich=False)
        self.skeletons.append(("Attribute", self._name(n)))
        if self._forward_named(скелет, n, "attribute"):
            return скелет
        raise ValueError(f"реквизит «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def _forward_named(self, designer, n, kind):
        вперёд = FormTranslation()
        try:
            узел = getattr(вперёд, kind)(as_parsed(designer))
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False
        return not вперёд.problems and same(узел, n)

    def _attribute(self, n, expected, rich):
        cls = FORM + "FormAttribute"
        attrs = {"name": self._name(n), "id": next((c.text for c in n.children if c.tag == "id"), "") or ""}
        дети, settings = [], []
        for name, узлы in _groups(n):
            if name in ("name", "id"):
                continue
            if name == "valueType":
                type_ = self.type_description(узлы[0], "Type") if len(узлы) == 1 else None
                дети.append(type_ if type_ is not None else raw(name, узлы))
            elif name == "main" and len(узлы) == 1 and узлы[0].text == "true":
                дети.append(Node("MainAttribute", text="true"))
            elif name == "columns":
                дети.append(Node("Columns", children=[self.column(c, attrs["name"]) for c in узлы]))
            elif name == "extInfo":
                класс = узлы[0].attrs.get("xsi:type", "").partition(":")[2]
                if not rich or len(узлы) != 1 or класс != expected:
                    дети.append(raw("extInfo", узлы))
                else:
                    settings += self.feature(cls, expected, name, узлы)
            elif rich:
                дети += self.feature(cls, expected, name, узлы)
            else:
                дети.append(raw(name, узлы))
        if expected is not None and _by_tag(n, "extInfo") is None:
            дети.append(raw("extInfo", []))
        if rich:
            дети = self.normalize(дети + settings, n, cls, expected, _key("attributes", expected))
            settings = [c for c in дети if c.tag == RAW and c.attrs.get("feature", "").startswith("extInfo/")
                         or c in settings]
            дети = [c for c in дети if c not in settings]
        else:
            дети.append(raw(ALL, []))
        if settings:
            дети.append(Node("Settings", children=[self._setting(c) for c in settings]))
        return Node("Attribute", attrs=attrs, children=дети)

    @staticmethod
    def _setting(c):
        if c.tag == RAW:
            return c
        return Node(ATTRIBUTE_SETTINGS_BACK.get(feature_name(c.tag), c.tag), text=c.text,
                    attrs=c.attrs, children=c.children)

    def column(self, n, attribute):
        богатое = self._simple(n, "Column", FORM + "FormAttributeColumn", "columns|", rich=True)
        вперёд = FormTranslation()
        try:
            if same(вперёд.column(as_parsed(богатое), f"Attribute «{attribute}»"), n) and not вперёд.problems:
                return богатое
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            pass
        return self._simple(n, "Column", FORM + "FormAttributeColumn", "columns|", rich=False)

    def command(self, n):
        богатое = self._simple(n, "Command", FORM + "FormCommand", "formCommands|", rich=True)
        if self._forward_named(богатое, n, "command"):
            return богатое
        скелет = self._simple(n, "Command", FORM + "FormCommand", "formCommands|", rich=False)
        self.skeletons.append(("Command", self._name(n)))
        if self._forward_named(скелет, n, "command"):
            return скелет
        raise ValueError(f"команда «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def parameter(self, n):
        богатое = self._simple(n, "Parameter", FORM + "FormParameter", "parameters|", rich=True)
        if self._forward_named(богатое, n, "parameter"):
            return богатое
        скелет = self._simple(n, "Parameter", FORM + "FormParameter", "parameters|", rich=False)
        if self._forward_named(скелет, n, "parameter"):
            return скелет
        raise ValueError(f"параметр «{self._name(n)}» не проходит круг перекладки даже скелетом")

    def _simple(self, n, тег, cls, key, rich):
        attrs = {"name": self._name(n)}
        number = next((c.text for c in n.children if c.tag == "id"), None)
        if number is not None:
            attrs["id"] = number
        дети = []
        for name, узлы in _groups(n):
            if name in ("name", "id"):
                continue
            if name == "valueType":
                type_ = self.type_description(узлы[0], "Type") if len(узлы) == 1 else None
                дети.append(type_ if type_ is not None else raw(name, узлы))
            elif name == "action" and self._action(узлы) is not None:
                дети.append(Node("Action", text=self._action(узлы)))
            elif rich:
                дети += self.feature(cls, None, name, узлы)
            else:
                дети.append(raw(name, узлы))
        if rich:
            дети = self.normalize(дети, n, cls, None, key)
        else:
            дети.append(raw(ALL, []))
        return Node(тег, attrs=attrs, children=дети)

    @staticmethod
    def _action(узлы):
        if len(узлы) != 1 or узлы[0].attrs.get("xsi:type") != "form:FormCommandHandlerContainer":
            return None
        обработчик = узлы[0].children
        if len(обработчик) != 1 or обработчик[0].tag != "handler" or len(обработчик[0].children) != 1:
            return None
        name = обработчик[0].children[0]
        return name.text if name.tag == "name" and plain(name.text) else None


__all__ = ["FormTranslation", "ReverseForm", "PRIMITIVE_BACK", "QUALIFIERS_BACK", "FLAGS_BACK"]
