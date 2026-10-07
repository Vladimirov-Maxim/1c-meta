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
KINDS_BACK = {вид: тег for тег, вид in KINDS.items() if вид[1] is not None}

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
RENAMED_BACK = {edt: тег for тег, edt in RENAMED.items() if edt not in ("handlers", "source")}

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
    приставка, _, имя = (text or "").partition(":")
    return f"{REF_PREFIXES[приставка]}.{имя}" if приставка in REF_PREFIXES and имя else None


def ref_back(word):
    """`Style.ВажныйЦвет` -> `style:ВажныйЦвет`; незнакомое — None."""
    приставка, _, имя = (word or "").partition(".")
    return f"{REF_PREFIXES_BACK[приставка]}:{имя}" if приставка in REF_PREFIXES_BACK and имя else None


def feature_name(tag):
    return RENAMED.get(tag) or tag[:1].lower() + tag[1:]


def designer_tag(name):
    return RENAMED_BACK.get(name) or name[:1].upper() + name[1:]


def _by_tag(node, tag):
    return next((c for c in node.children if c.tag == tag), None)


def _is_satellite(node):
    return "name" in node.attrs and "id" in node.attrs


def _key(cls_or_feature, тип):
    """Ключ таблицы умолчаний: `класс|вид` (вид — как записан: умолчание EMF пусто)."""
    return f"{cls_or_feature}|{тип or ''}"


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


def default_node(name, текст):
    """Запись таблицы умолчаний -> узел EDT."""
    if not текст.startswith("@"):
        return Node(name, text=текст)
    класс, _, поля = текст[1:].partition("|")
    узел = Node(name, attrs={"xsi:type": класс} if класс else {})
    for пара in filter(None, поля.split(";")):
        имя, _, значение = пара.partition("=")
        узел.children.append(Node(имя, text=значение))
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
            for путь, текст in DEFAULTS.get(defaults_key, {}).items():
                if путь.startswith("extInfo/"):
                    имя = путь[len("extInfo/"):]
                    if self.ext_cls is not None and self.raw_ext is None and not self.has_ext(имя) \
                            and edt_model.feature(self.ext_cls, имя) is not None:
                        self.add_ext(имя, [default_node(имя, текст)])
                elif not self.has(путь) and edt_model.feature(self.cls, путь) is not None:
                    self.add(путь, [default_node(путь, текст)])
        if self.raw_ext is not None:
            self.add("extInfo", self.raw_ext)
        elif self.ext_cls is not None:
            ext = Node("extInfo", attrs={"xsi:type": "form:" + self.ext_name},
                       children=[n for _, n in sorted(self.ext, key=lambda пара: пара[0])])
            self.add("extInfo", [ext])
        return Node(self.tag, attrs=self.attrs, children=[n for _, n in sorted(self.parts, key=lambda п: п[0])])


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
        for часть in root.children:
            if часть.tag == "ChildItems":
                сб.add("items", self.items(часть, "Form"))
            elif часть.tag == "Attributes":
                сб.add("attributes", [self.attribute(a) for a in часть.children])
            elif часть.tag == "Commands":
                сб.add("formCommands", [self.command(c) for c in часть.children])
            elif часть.tag == "Parameters":
                сб.add("parameters", [self.parameter(p) for p in часть.children])
            elif часть.tag in SATELLITES and _is_satellite(часть):
                self.satellite_node(часть, сб)
            elif часть.tag == "Events":
                self.events(часть, "Form", сб)
            elif часть.tag == "CommandInterface":
                сб.specified.add("commandInterface")
                self.problem("Form.CommandInterface", "командный интерфейс формы не перекладывается")
            else:
                self.property(часть, сб, "Form")
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
                тип = _by_tag(a, "Type")
                слово = _by_tag(тип, "Type") if тип is not None else None
                return (слово.text or "").partition(":")[2].split(".")[0] if слово is not None else None
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
        вид = KINDS.get(x.tag)
        if вид is None:
            self.problem(where, f"вид элемента «{x.tag}» не перекладывается")
            return None
        класс, тип = вид
        if тип is None and x.tag == "Button":
            т = _by_tag(x, "Type")
            тип = т.text if т is not None else "CommandBarButton"
        return self.element(x, "items", класс, тип, x.tag, xsi=True)

    def satellite_node(self, x, owner):
        имя, тип = SATELLITES[x.tag]
        f = edt_model.feature(owner.cls, имя)
        if f is None:
            self.problem(x.tag, f"спутника нет у {owner.cls.rsplit('.', 1)[-1]}")
            return
        owner.add(имя, [self.element(x, имя, f.type.rsplit(".", 1)[-1], тип, x.tag, xsi=False)])

    def element(self, x, tag, класс, тип, вид, xsi):
        cls = FORM + класс
        where = f"{вид} «{x.attrs.get('name', '')}»"
        ext_name = EXT_INFO.get(вид)
        if вид == "Table" and self._data_path_root(x) in self.dynamic_lists:
            ext_name = "DynamicListTableExtInfo"
        сб = Assembly(tag, {"xsi:type": "form:" + класс} if xsi else {}, cls, ext_name)
        сб.add("name", [Node("name", text=x.attrs.get("name", ""))])
        сб.add("id", [Node("id", text=x.attrs.get("id", ""))])
        записанный = None
        f = edt_model.feature(cls, "type") if тип is not None else None
        if f is not None and not edt_model.is_default(f, тип, cls):
            записанный = тип
            сб.add("type", [Node("type", text=тип)])
        for c in x.children:
            if c.tag == "ChildItems":
                сб.add("items", self.items(c, where))
            elif c.tag in SATELLITES and _is_satellite(c):
                self.satellite_node(c, сб)
            elif c.tag == "Type" and вид == "Button":
                continue
            elif c.tag == "Events":
                self.events(c, класс, сб)
            else:
                self.property(c, сб, where)
        if сб.auto_edit:
            сб.parts = [пара for пара in сб.parts if пара[1].tag != "editMode"]
            сб.add("editMode", [Node("editMode", text="Auto")])
        self.specified_by_id[x.attrs.get("id", "")] = set(сб.specified)
        return сб.node(_key(класс if xsi else tag, записанный))

    @staticmethod
    def _data_path_root(x):
        путь = _by_tag(x, "DataPath")
        return (путь.text or "").split(".")[0] if путь is not None else None

    # --- свойства ---

    def property(self, свойство, сб, where):
        """Свойство выгрузки -> узлы в сборке `сб` (свойство вида — в `extInfo`)."""
        if свойство.tag == RAW:
            self.raw_property(свойство, сб)
            return
        if self.special(свойство, сб):
            return
        имя = feature_name(свойство.tag)
        f = edt_model.feature(сб.cls, имя)
        if f is not None:
            сб.specified.add(имя)
            сб.add(имя, self.form_value(свойство, f, сб.cls, f"{where}.{свойство.tag}"))
            return
        f = edt_model.feature(сб.ext_cls, имя) if сб.ext_cls is not None else None
        if f is not None:
            сб.specified.add("extInfo/" + имя)
            сб.add_ext(имя, self.form_value(свойство, f, сб.ext_cls, f"{where}.{свойство.tag}"))
            return
        сб.specified.add(имя)
        if not self._empty(свойство):
            self.problem(where, f"свойства «{свойство.tag}» нет у {сб.cls.rsplit('.', 1)[-1]}")

    @staticmethod
    def raw_property(свойство, сб):
        """Переходник обратной перекладки: узлы EDT — на своё место как были."""
        адрес = свойство.attrs.get("feature", "")
        узлы = [restore_raw(n) for n in свойство.children]
        if адрес == ALL:
            сб.all = True
        elif адрес == "extInfo":
            сб.raw_ext = узлы
        elif адрес.startswith("extInfo/"):
            сб.specified.add(адрес)
            if узлы:
                сб.add_ext(адрес[len("extInfo/"):], узлы)
        else:
            сб.specified.add(адрес)
            if узлы:
                сб.add(адрес, узлы)

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
            элемент = _by_tag(свойство, "Item")
            return [Node("source", text=элемент.text)] if элемент is not None and элемент.text else []
        тип = f.type.rsplit(".", 1)[-1]
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
        if тип == "FormChoiceListDesTimeValue":
            return self.choice_list(свойство, f.name, where)
        return self.value_nodes(свойство, f, cls, where)

    # --- значения оформления ---

    def color(self, свойство, name, where):
        текст = (свойство.text or "").strip()
        if текст in ("", "auto"):
            return []
        if текст.startswith("#") and len(текст) == 7:
            узел = Node(name, attrs={"xsi:type": "core:ColorDef"})
            for имя, часть in (("red", текст[1:3]), ("green", текст[3:5]), ("blue", текст[5:7])):
                if int(часть, 16):
                    узел.children.append(Node(имя, text=str(int(часть, 16))))
            return [узел]
        слово = ref_word(текст)
        if слово is None:
            self.problem(where, f"незнакомый цвет «{текст}»")
            return []
        return [Node(name, attrs={"xsi:type": "core:ColorRef"}, children=[Node("color", text=слово)])]

    def font(self, свойство, name, where):
        вид = свойство.attrs.get("kind")
        if вид == "AutoFont":
            узел = Node(name, attrs={"xsi:type": "core:AutoFont"})
        elif вид in ("StyleItem", "WindowsFont") and ref_word(свойство.attrs.get("ref")):
            узел = Node(name, attrs={"xsi:type": "core:FontRef"},
                        children=[Node("font", text=ref_word(свойство.attrs["ref"]))])
        else:
            self.problem(where, f"незнакомый шрифт вида «{вид}»")
            return []
        for имя in FONT_ATTRIBUTES:
            if имя in свойство.attrs:
                значение = свойство.attrs[имя]
                if имя == "height" and "." not in значение:
                    значение += ".0"
                узел.children.append(Node(имя, text=значение))
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
        for имя in ("startDate", "endDate"):
            часть = _by_tag(свойство, имя)
            if часть is not None and часть.text:
                узел.children.append(Node(имя, text=часть.text))
        return узел

    def choice_list(self, свойство, name, where):
        узлы = []
        for элемент in свойство.children:
            значение = _by_tag(элемент, "Value")
            if значение is None or значение.attrs.get("type") != "FormChoiceListDesTimeValue":
                self.problem(where, "незнакомый элемент списка выбора")
                continue
            узел = Node(name)
            представление = _by_tag(значение, "Presentation")
            if представление is not None:
                узел.children += [Node("presentation", children=[Node("key", text=item_part(i, "lang")),
                                                                 Node("value", text=item_part(i, "content"))])
                                  for i in представление.children if i.tag == "item"]
            внутри = _by_tag(значение, "Value")
            if внутри is not None:
                v = self.value(внутри, "value", where)
                if v is not None:
                    узел.children.append(v)
            узлы.append(узел)
        return узлы

    def events(self, events, класс, сб):
        """События элемента -> обработчики: в самом элементе или в `extInfo` вида."""
        for e in events.children:
            if e.tag != "Event":
                continue
            событие = e.attrs.get("name", "")
            узел = Node("handlers", children=[Node("event", text=событие), Node("name", text=e.text or "")])
            if класс in EXT_EVENTS:
                сам = событие not in EXT_EVENTS[класс]
            else:
                сам = событие in OWN_EVENTS.get(класс, ())
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
        if any(значение.tag == "Value" for значение in свойство.children):
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
                имя = "notDefaultUseAlwaysAttributes" if c.tag == "UseAlways" else "settingsSavedData"
                сб.specified.add(имя)
                сб.add(имя, [Node(имя, attrs={"xsi:type": "form:DataPath"}, children=[Node("segments", text=п.text)])
                             for п in c.children if п.text])
            elif c.tag == "Columns":
                сб.add("columns", [self.column(к, where) for к in c.children if к.tag == "Column"])
            elif c.tag == "Settings":
                self.settings(c, сб, where)
            else:
                self.property(c, сб, where)
        self.specified_by_id["attributes:" + имя_реквизита] = set(сб.specified)
        return сб.node(_key("attributes", ext_name))

    def settings(self, настройки, сб, where):
        if сб.ext_cls is None:
            self.problem(where, "настройки реквизита этого типа не перекладываются")
            return
        for часть in настройки.children:
            if часть.tag == "ListSettings":
                continue                                  # отдельным файлом ListSettings.dcss — площадка
            if часть.tag == RAW:
                self.raw_property(часть, сб)
                continue
            имя = ATTRIBUTE_SETTINGS.get(часть.tag) or feature_name(часть.tag)
            f = edt_model.feature(сб.ext_cls, имя)
            сб.specified.add("extInfo/" + имя)
            if f is None:
                if not self._empty(часть):
                    self.problem(where, f"настройки «{часть.tag}» нет у {сб.ext_name}")
                continue
            сб.add_ext(имя, self.form_value(часть, f, сб.ext_cls, f"{where}.{часть.tag}"))

    @staticmethod
    def _attribute_ext(a):
        """Класс `extInfo` реквизита — по типу (замер — все формы корпуса)."""
        тип = _by_tag(a, "Type")
        слова = [c.text or "" for c in тип.children] if тип is not None else []
        настройки = _by_tag(a, "Settings")
        if "cfg:DynamicList" in слова:
            return "DynamicListExtInfo"
        if any(с.endswith(":SpreadsheetDocument") for с in слова):
            return "SpreadsheetDocumentExtInfo"
        if "v8:ValueListType" in слова and настройки is not None:
            return "ValueListExtInfo"
        if any(с.endswith(":FlowchartContextType") for с in слова):
            return "GraphicalSchemeExtInfo"
        return None

    def column(self, к, where):
        ключ = f"columns:{where}.{к.attrs.get('name', '')}"
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
        self.specified_by_id[ключ] = set(сб.specified)
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

    def parameter(self, п):
        where = f"Parameter «{п.attrs.get('name', '')}»"
        сб = Assembly("parameters", {}, FORM + "FormParameter")
        сб.add("name", [Node("name", text=п.attrs.get("name", ""))])
        for c in п.children:
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
    группы = []
    for ребёнок in node.children:
        if группы and группы[-1][0] == ребёнок.tag:
            группы[-1][1].append(ребёнок)
        else:
            группы.append((ребёнок.tag, [ребёнок]))
    return группы


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
            стало = FormTranslation().form(as_parsed(designer))
            # объявления пространств имён корня текст вычисляет сам — их не сравнивать
            корень = Node(root.tag, attrs={k: v for k, v in root.attrs.items() if not k.startswith("xmlns:")},
                          children=root.children)
            return same(стало, корень)
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
                типы = _by_tag(a, "valueType")
                слово = _by_tag(типы, "types") if типы is not None else None
                expected = FORM_EXT_INFO.get((слово.text or "").split(".")[0]) if слово is not None else None
        дети = []
        for имя, узлы in _groups(root):
            if имя == "items":
                дети.append(Node("ChildItems", children=[self.item(n) for n in узлы]))
            elif имя == "attributes":
                дети.append(Node("Attributes", children=[self.attribute(n) for n in узлы]))
            elif имя == "formCommands":
                дети.append(Node("Commands", children=[self.command(n) for n in узлы]))
            elif имя == "parameters":
                дети.append(Node("Parameters", children=[self.parameter(n) for n in узлы]))
            elif имя == "autoCommandBar":
                дети.append(self.satellite(узлы[0], cls, имя))
            elif имя == "commandInterface":
                if not (len(узлы) == 1 and same(узлы[0], EMPTY_COMMAND_INTERFACE)):
                    дети.append(raw(имя, узлы))
            elif rich:
                дети += self.feature(cls, expected, имя, узлы)
            else:
                дети.append(raw(имя, узлы))
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
        тип = self._type(n, FORM + класс)
        if класс in ("Button", "Table"):              # вид в теге не различается: поле `type` — свойство
            тег = класс
        else:
            тег = KINDS_BACK.get((класс, тип))
        if тег is None:
            return raw("items", [n])                    # вид, которого выгрузка не пишет, — переходником
        return self.element(n, тег, класс, "items", тип)

    @staticmethod
    def _type(n, cls):
        т = _by_tag(n, "type")
        if т is not None:
            return т.text
        f = edt_model.feature(cls, "type")
        return edt_model.default_text(f) if f is not None else None

    def satellite(self, n, owner_cls, feature):
        f = edt_model.feature(owner_cls, feature)
        класс = f.type.rsplit(".", 1)[-1]
        return self.element(n, SATELLITES_BACK[feature], класс, feature, self._type(n, FORM + класс))

    def element(self, n, тег, класс, feature, тип):
        богатое = self._element(n, тег, класс, тип, feature, rich=True)
        if self._forward_element(богатое, тег, класс, feature, n):
            return богатое
        скелет = self._element(n, тег, класс, тип, feature, rich=False)
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
                тип = SATELLITES[тег][1]
                узел = вперёд.element(as_parsed(designer), feature, класс, тип, тег, xsi=False)
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False
        return узел is not None and not вперёд.problems and same(узел, n)

    def _element(self, n, тег, класс, тип, feature, rich):
        cls = FORM + класс
        if тег == "Table":
            путь = _by_tag(n, "dataPath")
            сегмент = _by_tag(путь, "segments") if путь is not None else None
            корень = (сегмент.text or "").split(".")[0] if сегмент is not None else None
            expected = "DynamicListTableExtInfo" if корень in self.forward.dynamic_lists else None
        else:
            expected = EXT_INFO.get(тег)
        attrs = {"name": self._name(n), "id": next((c.text for c in n.children if c.tag == "id"), "") or ""}
        дети, детей, спутники = [], [], []
        if тег == "Button" and тип != "CommandBarButton":
            дети.append(Node("Type", text=тип))
        for имя, узлы in _groups(n):
            if имя in ("name", "id", "type"):
                continue
            if имя == "items":
                детей += [self.item(c) for c in узлы]
            elif имя in SATELLITES_BACK and edt_model.feature(cls, имя) is not None \
                    and edt_model.feature(cls, имя).kind == "contains" and not edt_model.feature(cls, имя).many:
                спутники.append(self.satellite(узлы[0], cls, имя))
            elif rich:
                дети += self.feature(cls, expected, имя, узлы)
            elif имя == "dataPath" and self._plain_path(узлы):
                дети.append(Node("DataPath", text=_by_tag(узлы[0], "segments").text))
            else:
                дети.append(raw(имя, узлы))
        записанный = тип if _by_tag(n, "type") is not None else None
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

    def feature(self, cls, expected_ext, имя, узлы):
        """Свойство EDT -> свойства выгрузки (непонятное — переходником)."""
        if имя == "extInfo":
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
        f = edt_model.feature(cls, имя)
        if f is None:
            return [raw(имя, узлы)]
        if имя == "handlers":
            return [self.events(узлы)]
        return self.value(f, узлы, "")

    def events(self, узлы):
        события = []
        for h in узлы:
            поля = {c.tag: c.text for c in h.children}
            if set(поля) != {"event", "name"} or not plain(поля["event"]) or not plain(поля["name"] or "x"):
                return raw("handlers", узлы)
            события.append(Node("Event", attrs={"name": поля["event"]}, text=поля["name"]))
        return Node("Events", children=события)

    def value(self, f, узлы, адрес):
        """Узлы EDT свойства `f` -> свойства выгрузки."""
        тег = designer_tag(f.name)
        переходник = [raw(адрес + f.name, узлы)]
        один = узлы[0] if len(узлы) == 1 else None
        if f.type == LOCAL_STRING:
            items = []
            for n in узлы:
                поля = {c.tag: c for c in n.children}
                if set(поля) != {"key", "value"} or any(c.children or c.attrs for c in n.children) \
                        or not all(plain(c.text) for c in n.children):
                    return переходник
                items.append(Node("v8:item", children=[Node("v8:lang", text=поля["key"].text),
                                                       Node("v8:content", text=поля["value"].text)]))
            return [Node(тег, children=items)]
        if один is None and not f.many:
            return переходник
        if f.type == ADJUSTABLE:
            if один.attrs or any(c.tag != "common" or c.text != "true" for c in один.children):
                return переходник
            значение = "true" if один.children else "false"
            return [Node(тег, children=[Node("xr:Common", text=значение)])]
        if f.type.endswith("AbstractDataPath") and not f.many:
            if not self._plain_path(узлы):
                return переходник
            return [Node(тег, text=_by_tag(один, "segments").text)]
        if f.type == TYPE_DESCRIPTION:
            тип = self.type_description(один, тег)
            return [тип] if тип is not None else переходник
        if f.type == VALUE:
            значение = self.reverse_values.value(один, тег)
            if значение is None:
                return переходник
            return [Node(тег, text=значение.text,
                         attrs={("xsi:" + k): v for k, v in значение.attrs.items()})]
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
        тип = self.reverse_values.type_description(узел, тег)
        if тип is None:
            return None
        # прямая перекладка возьмёт из описания то же, что дал обратный ход;
        # пустые и пробельные тексты ей не пройти — переходником
        for c in тип.children:
            if c.text is not None and not plain(c.text):
                return None
        return Node(тег, children=[_v8(c) for c in тип.children])

    @staticmethod
    def color(n, тег):
        класс = n.attrs.get("xsi:type", "")
        if класс == "core:ColorRef" and len(n.children) == 1 and n.children[0].tag == "color":
            слово = ref_back(n.children[0].text)
            return [Node(тег, text=слово)] if слово else None
        if класс == "core:ColorDef" and all(c.tag in ("red", "green", "blue") and not c.children
                                            for c in n.children):
            части = {c.tag: int(c.text or "0") for c in n.children}
            if [c.tag for c in n.children] != [и for и in ("red", "green", "blue") if и in части]:
                return None
            if any(not 0 < v < 256 for v in части.values()):
                return None
            return [Node(тег, text="#" + "".join(f"{части.get(и, 0):02X}" for и in ("red", "green", "blue")))]
        return None

    @staticmethod
    def font(n, тег):
        класс = n.attrs.get("xsi:type", "")
        attrs = {}
        поля = list(n.children)
        if класс == "core:FontRef":
            if not поля or поля[0].tag != "font":
                return None
            ссылка = ref_back(поля[0].text)
            if ссылка is None or not ссылка.startswith(("style:", "sys:")):
                return None
            attrs["ref"] = ссылка
            поля = поля[1:]
        elif класс != "core:AutoFont":
            return None
        порядок = [c.tag for c in поля]
        if порядок != [и for и in FONT_ATTRIBUTES if и in порядок] or any(c.children for c in поля):
            return None
        for c in поля:
            текст = c.text or ""
            if c.tag == "height":
                if not текст.endswith(".0"):
                    return None
                текст = текст[:-2]
            attrs[c.tag] = текст
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
        поля = {c.tag: c.text for c in n.children}
        if [c.tag for c in n.children] not in (["style", "width"], ["style"], ["width"], []):
            return None
        attrs = {"width": поля["width"]} if "width" in поля else {}
        дети = [Node("v8ui:style", attrs={"xsi:type": "v8ui:ControlBorderType"}, text=поля["style"])] \
            if "style" in поля else []
        return [Node(тег, attrs=attrs, children=дети)]

    # --- умолчания ---

    def normalize(self, дети, n, cls, expected_ext, ключ):
        """Свойства, совпавшие с умолчанием платформы, не пишутся (прямая
        перекладка их допишет); отсутствующее в EDT, но имеющее умолчание —
        переходником без узлов: «задано, писать нечего»."""
        умолчания = DEFAULTS.get(ключ, {})
        if not умолчания:
            return дети
        ext = _by_tag(n, "extInfo")
        ext_ok = ext is not None and ext.attrs.get("xsi:type", "").partition(":")[2] == expected_ext
        for путь, текст in умолчания.items():
            if путь.startswith("extInfo/"):
                if not ext_ok:
                    continue
                узлы = [c for c in ext.children if c.tag == путь[len("extInfo/"):]]
            else:
                узлы = [c for c in n.children if c.tag == путь]
            if len(узлы) == 1 and default_value(узлы[0]) == текст:
                тег = designer_tag(путь.rpartition("/")[2])
                дети = [c for c in дети if not (c.tag == тег or (c.tag == RAW and c.attrs.get("feature") == путь))]
            elif not узлы:
                дети.append(raw(путь, []))
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

    def _forward_named(self, designer, n, вид):
        вперёд = FormTranslation()
        try:
            узел = getattr(вперёд, вид)(as_parsed(designer))
        except Exception:                               # noqa: BLE001 — не сошлось, значит скелет
            return False
        return not вперёд.problems and same(узел, n)

    def _attribute(self, n, expected, rich):
        cls = FORM + "FormAttribute"
        attrs = {"name": self._name(n), "id": next((c.text for c in n.children if c.tag == "id"), "") or ""}
        дети, настройки = [], []
        for имя, узлы in _groups(n):
            if имя in ("name", "id"):
                continue
            if имя == "valueType":
                тип = self.type_description(узлы[0], "Type") if len(узлы) == 1 else None
                дети.append(тип if тип is not None else raw(имя, узлы))
            elif имя == "main" and len(узлы) == 1 and узлы[0].text == "true":
                дети.append(Node("MainAttribute", text="true"))
            elif имя == "columns":
                дети.append(Node("Columns", children=[self.column(c, attrs["name"]) for c in узлы]))
            elif имя == "extInfo":
                класс = узлы[0].attrs.get("xsi:type", "").partition(":")[2]
                if not rich or len(узлы) != 1 or класс != expected:
                    дети.append(raw("extInfo", узлы))
                else:
                    настройки += self.feature(cls, expected, имя, узлы)
            elif rich:
                дети += self.feature(cls, expected, имя, узлы)
            else:
                дети.append(raw(имя, узлы))
        if expected is not None and _by_tag(n, "extInfo") is None:
            дети.append(raw("extInfo", []))
        if rich:
            дети = self.normalize(дети + настройки, n, cls, expected, _key("attributes", expected))
            настройки = [c for c in дети if c.tag == RAW and c.attrs.get("feature", "").startswith("extInfo/")
                         or c in настройки]
            дети = [c for c in дети if c not in настройки]
        else:
            дети.append(raw(ALL, []))
        if настройки:
            дети.append(Node("Settings", children=[self._setting(c) for c in настройки]))
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

    def _simple(self, n, тег, cls, ключ, rich):
        attrs = {"name": self._name(n)}
        номер = next((c.text for c in n.children if c.tag == "id"), None)
        if номер is not None:
            attrs["id"] = номер
        дети = []
        for имя, узлы in _groups(n):
            if имя in ("name", "id"):
                continue
            if имя == "valueType":
                тип = self.type_description(узлы[0], "Type") if len(узлы) == 1 else None
                дети.append(тип if тип is not None else raw(имя, узлы))
            elif имя == "action" and self._action(узлы) is not None:
                дети.append(Node("Action", text=self._action(узлы)))
            elif rich:
                дети += self.feature(cls, None, имя, узлы)
            else:
                дети.append(raw(имя, узлы))
        if rich:
            дети = self.normalize(дети, n, cls, None, ключ)
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
        имя = обработчик[0].children[0]
        return имя.text if имя.tag == "name" and plain(имя.text) else None


__all__ = ["FormTranslation", "ReverseForm", "PRIMITIVE_BACK", "QUALIFIERS_BACK", "FLAGS_BACK"]
