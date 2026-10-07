"""Перекладка управляемой формы: `Form.xml` выгрузки -> `Form.form` проекта EDT.

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
  EDT. Таблица умолчаний снята с корпуса (`edt_form_defaults.py`).

Порядок свойств и умолчания EMF — метамодель (`edt_model`). Чего перекладка не
понимает, она называет (`problems`), а не теряет: запись с потерей — отказ.
"""

from . import edt_model
from .edt_card import MCORE, Translation, item_part
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

#: Свойство выгрузки -> имя свойства EDT там, где оно не «то же с маленькой буквы».
RENAMED = {"Events": "handlers", "Autofill": "autoFill", "Hiperlink": "hyperlink",
           "AdditionSource": "source", "CommandSet": "excludedCommands", "Customizable": "allowFormCustomize",
           "AutoURL": "autoUrl", "ModifiesSavedData": "modifiesStoredData", "RadioButtonType": "radioButtonsType",
           "HorizontalLocation": "horizontalAlign", "ChildItemsWidth": "slaveItemsWidth",
           "FillCheck": "fillChecking", "AutoShowState": "showState", "ReportFormType": "settingsForm",
           "DetailsData": "detailsInformation", "ReportResult": "reportResult",
           "CustomSettingsFolder": "userSettingsGroup", "EqualColumnsWidth": "equalElementsWidth",
           "EqualItemsWidth": "equalElementsWidth"}

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


def ref_word(text):
    """`style:ВажныйЦвет` -> `Style.ВажныйЦвет`; незнакомая приставка — None."""
    приставка, _, имя = (text or "").partition(":")
    return f"{REF_PREFIXES[приставка]}.{имя}" if приставка in REF_PREFIXES and имя else None


def feature_name(tag):
    return RENAMED.get(tag) or tag[:1].lower() + tag[1:]


def _by_tag(node, tag):
    return next((c for c in node.children if c.tag == tag), None)


def _is_satellite(node):
    return "name" in node.attrs and "id" in node.attrs


class FormTranslation(Translation):
    """Форма выгрузки (узел `Form`) -> корень формы EDT (`form:Form`)."""

    def form(self, root):
        #: id элемента -> свойства, которые выгрузка задала явно (для снятия умолчаний)
        self.specified_by_id = {}
        внешние = set()
        self.specified = внешние
        узел = Node("form:Form")
        cls = FORM + "Form"
        собрано, ext = [], Node("extInfo")
        основной = self._main_type(root)
        ext_cls = FORM + FORM_EXT_INFO[основной] if основной in FORM_EXT_INFO else None
        for часть in root.children:
            if часть.tag == "ChildItems":
                собрано += [(edt_model.position(cls, "items"), n) for n in self.items(часть, "Form")]
            elif часть.tag == "Attributes":
                собрано += [(edt_model.position(cls, "attributes"), self.attribute(a))
                            for a in часть.children]
            elif часть.tag == "Commands":
                собрано += [(edt_model.position(cls, "formCommands"), self.command(c))
                            for c in часть.children]
            elif часть.tag == "Parameters":
                собрано += [(edt_model.position(cls, "parameters"), self.parameter(p))
                            for p in часть.children]
            elif часть.tag in SATELLITES:
                собрано += self.satellite_node(часть, cls)
            elif часть.tag == "Events":
                собрано += self.events(часть, "Form", cls, None, None)
            elif часть.tag == "CommandInterface":
                self.specified.add("commandInterface")
                self.problem("Form.CommandInterface", "командный интерфейс формы не перекладывается")
            else:
                собрано += self.property(часть, cls, "Form", ext, ext_cls)
        if "commandInterface" not in self.specified:
            собрано.append((edt_model.position(cls, "commandInterface"),
                            Node("commandInterface", children=[Node("navigationPanel"), Node("commandBar")])))
        self.specified_by_id["Form"] = set(self.specified)
        собрано += self.defaults("Form|", cls, собрано, ext, ext_cls, self.specified)
        if ext_cls is not None:
            ext.attrs["xsi:type"] = "form:" + ext_cls.rsplit(".", 1)[-1]
            ext.children = [n for _, n in sorted(ext.children, key=lambda пара: пара[0])]
            собрано.append((edt_model.position(cls, "extInfo"), ext))
        собрано.sort(key=lambda пара: пара[0])
        узел.children = [n for _, n in собрано]
        return узел

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
        return [n for n in (self.item(ребёнок, where) for ребёнок in child_items.children) if n is not None]

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

    def satellite_node(self, x, owner_cls):
        имя, тип = SATELLITES[x.tag]
        f = edt_model.feature(owner_cls, имя)
        if f is None:
            self.problem(x.tag, f"спутника нет у {owner_cls.rsplit('.', 1)[-1]}")
            return []
        класс = f.type.rsplit(".", 1)[-1]
        return [(edt_model.position(owner_cls, имя), self.element(x, имя, класс, тип, x.tag, xsi=False))]

    def element(self, x, tag, класс, тип, вид, xsi):
        внешние, флаг = getattr(self, "specified", set()), getattr(self, "auto_edit", False)
        try:
            return self._element(x, tag, класс, тип, вид, xsi)
        finally:
            self.specified, self.auto_edit = внешние, флаг

    def _element(self, x, tag, класс, тип, вид, xsi):
        cls = FORM + класс
        where = f"{вид} «{x.attrs.get('name', '')}»"
        узел = Node(tag, attrs={"xsi:type": "form:" + класс} if xsi else {})
        ext_name = EXT_INFO.get(вид)
        if вид == "Table" and self._dynamic_list_table(x):
            ext_name = "DynamicListTableExtInfo"
        ext_cls = FORM + ext_name if ext_name else None
        ext = Node("extInfo")
        self.specified = set()
        self.auto_edit = False
        собрано = [(edt_model.position(cls, "name"), Node("name", text=x.attrs.get("name", ""))),
                   (edt_model.position(cls, "id"), Node("id", text=x.attrs.get("id", "")))]
        записанный = None
        if тип is not None and edt_model.feature(cls, "type") is not None:
            f = edt_model.feature(cls, "type")
            if not edt_model.is_default(f, тип, cls):
                записанный = тип
                собрано.append((edt_model.position(cls, "type"), Node("type", text=тип)))
        for c in x.children:
            if c.tag == "ChildItems":
                собрано += [(edt_model.position(cls, "items"), n) for n in self.items(c, where)]
            elif c.tag in SATELLITES and _is_satellite(c):
                собрано += self.satellite_node(c, cls)
            elif c.tag == "Type" and вид == "Button":
                continue
            elif c.tag == "Events":
                собрано += self.events(c, класс, cls, ext, ext_cls)
            else:
                собрано += self.property(c, cls, where, ext, ext_cls)
        if self.auto_edit:
            собрано = [пара for пара in собрано if пара[1].tag != "editMode"]
            собрано.append((edt_model.position(cls, "editMode"), Node("editMode", text="Auto")))
        ключ = f"{класс if xsi else tag}|{записанный or ''}"
        self.specified_by_id[x.attrs.get("id", "")] = set(self.specified)
        собрано += self.defaults(ключ, cls, собрано, ext, ext_cls, self.specified)
        if ext_cls is not None:
            ext.attrs["xsi:type"] = "form:" + ext_name
            ext.children = [n for _, n in sorted(ext.children, key=lambda пара: пара[0])]
            собрано.append((edt_model.position(cls, "extInfo"), ext))
        собрано.sort(key=lambda пара: пара[0])
        узел.children = [n for _, n in собрано]
        return узел

    def _dynamic_list_table(self, x):
        return x.attrs.get("name") is not None and _by_tag(x, "UpdateOnDataChange") is not None

    # --- свойства ---

    def property(self, свойство, cls, where, ext=None, ext_cls=None):
        """Свойство выгрузки -> [(место, узел)] у элемента; свойство вида — в `ext`."""
        особое = self.special(свойство, cls)
        if особое is not None:
            return особое
        имя = feature_name(свойство.tag)
        f = edt_model.feature(cls, имя)
        if hasattr(self, "specified"):
            self.specified.add(имя)
        if f is not None:
            место = edt_model.position(cls, имя)
            return [(место, n) for n in self.form_value(свойство, f, cls, f"{where}.{свойство.tag}")]
        if ext_cls is not None:
            f = edt_model.feature(ext_cls, имя)
            if f is not None:
                место = edt_model.position(ext_cls, имя)
                ext.children += [(место, n) for n in self.form_value(свойство, f, ext_cls,
                                                                       f"{where}.{свойство.tag}")]
                return []
        if not self._empty(свойство):
            self.problem(where, f"свойства «{свойство.tag}» нет у {cls.rsplit('.', 1)[-1]}")
        return []

    def special(self, свойство, cls):
        """Свойства, которые ложатся в EDT не по имени. None — не особое."""
        if свойство.tag == "AutoEditMode":
            # режим «автоматически» — в выгрузке флагом при режиме, в EDT — значением режима
            self.specified.add("editMode")
            if свойство.text == "true":
                self.auto_edit = True
            return []
        if свойство.tag == "ShowCommandBar" and свойство.text == "auto" and cls == FORM + "Table":
            self.specified.add("showCommandBar")
            return [(edt_model.position(cls, "showCommandBarNeedDereferenced"),
                     Node("showCommandBarNeedDereferenced", text="true"))]
        return None

    def form_value(self, свойство, f, cls, where):
        """Значение свойства выгрузки -> узлы EDT."""
        if f.name == "handlers":
            return [Node("handlers", children=[Node("event", text=e.attrs.get("name", "")),
                                               Node("name", text=e.text or "")])
                    for e in свойство.children if e.tag == "Event"]
        if f.type == ADJUSTABLE:
            return [self.adjustable(свойство, f.name)]
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
            return self.border(свойство, f.name, where)
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
        for атрибут, имя in (("faceName", "faceName"), ("height", "height"), ("bold", "bold"),
                             ("italic", "italic"), ("underline", "underline"), ("strikeout", "strikeout"),
                             ("scale", "scale")):
            if атрибут in свойство.attrs:
                значение = свойство.attrs[атрибут]
                if атрибут == "height" and "." not in значение:
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

    def border(self, свойство, name, where):
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

    def events(self, events, класс, cls, ext, ext_cls):
        """События элемента -> обработчики: в самом элементе или в `extInfo` вида."""
        собрано = []
        for e in events.children:
            if e.tag != "Event":
                continue
            событие = e.attrs.get("name", "")
            узел = Node("handlers", children=[Node("event", text=событие), Node("name", text=e.text or "")])
            if класс in EXT_EVENTS:
                сам = событие not in EXT_EVENTS[класс]
            else:
                сам = событие in OWN_EVENTS.get(класс, ())
            if not сам and (ext_cls is None or edt_model.feature(ext_cls, "handlers") is None):
                сам = True
            if сам:
                собрано.append((edt_model.position(cls, "handlers"), узел))
            else:
                ext.children.append((edt_model.position(ext_cls, "handlers"), узел))
        return собрано

    def adjustable(self, свойство, name):
        узел = Node(name)
        общий = _by_tag(свойство, "Common")
        текст = общий.text if общий is not None else "false"
        if текст == "true":
            узел.children.append(Node("common", text="true"))
        for значение in свойство.children:
            if значение.tag == "Value":
                self.problem(name, "значение по ролям не перекладывается")
        return узел

    # --- умолчания платформы ---

    def defaults(self, ключ, cls, собрано, ext, ext_cls, specified=()):
        """Умолчания платформы, которые EDT пишет явно, — там, где выгрузка
        свойства не задала."""
        есть = {n.tag for _, n in собрано}
        есть_ext = {n.tag for _, n in ext.children}
        добавлено = []
        for путь, текст in DEFAULTS.get(ключ, {}).items():
            if путь.startswith("extInfo/"):
                имя = путь[len("extInfo/"):]
                if ext_cls is None or имя in есть_ext or имя in specified:
                    continue
                f = edt_model.feature(ext_cls, имя)
                if f is not None:
                    ext.children.append((edt_model.position(ext_cls, имя), self.default_node(f, текст)))
            elif путь not in есть and путь not in specified:
                f = edt_model.feature(cls, путь)
                if f is not None:
                    добавлено.append((edt_model.position(cls, путь), self.default_node(f, текст)))
        return добавлено

    @staticmethod
    def default_node(f, текст):
        """Значение из таблицы умолчаний -> узел: текст простого свойства,
        `@класс|поле=значение;…` — плоский объект."""
        if not текст.startswith("@"):
            return Node(f.name, text=текст)
        класс, _, поля = текст[1:].partition("|")
        узел = Node(f.name, attrs={"xsi:type": класс} if класс else {})
        for пара in filter(None, поля.split(";")):
            имя, _, значение = пара.partition("=")
            узел.children.append(Node(имя, text=значение))
        return узел

    # --- реквизиты, команды, параметры ---

    def attribute(self, a):
        cls = FORM + "FormAttribute"
        where = f"Attribute «{a.attrs.get('name', '')}»"
        внешние, self.specified = self.specified, set()
        собрано = [(edt_model.position(cls, "name"), Node("name", text=a.attrs.get("name", ""))),
                   (edt_model.position(cls, "id"), Node("id", text=a.attrs.get("id", "")))]
        for c in a.children:
            if c.tag == "Type":
                собрано.append((edt_model.position(cls, "valueType"),
                                self.type_description(c, "valueType", where)))
            elif c.tag == "MainAttribute":
                if c.text == "true":
                    собрано.append((edt_model.position(cls, "main"), Node("main", text="true")))
            elif c.tag == "SavedData":
                if c.text == "true":
                    собрано.append((edt_model.position(cls, "savedData"), Node("savedData", text="true")))
            elif c.tag in ("UseAlways", "Save"):
                имя = "notDefaultUseAlwaysAttributes" if c.tag == "UseAlways" else "settingsSavedData"
                self.specified.add(имя)
                собрано += [(edt_model.position(cls, имя),
                             Node(имя, attrs={"xsi:type": "form:DataPath"},
                                  children=[Node("segments", text=п.text)]))
                            for п in c.children if п.text]
            elif c.tag == "Columns":
                собрано += [(edt_model.position(cls, "columns"), self.column(к, where))
                            for к in c.children if к.tag == "Column"]
            elif c.tag == "Settings":
                continue
            else:
                собрано += self.property(c, cls, where)
        ext, ext_name = Node("extInfo"), self._attribute_ext(a)
        ext_cls = FORM + ext_name if ext_name else None
        настройки = _by_tag(a, "Settings")
        if настройки is not None:
            if ext_cls is None:
                self.problem(where, "настройки реквизита этого типа не перекладываются")
            else:
                for часть in настройки.children:
                    if часть.tag == "ListSettings":
                        continue                          # отдельным файлом ListSettings.dcss — площадка
                    имя = ATTRIBUTE_SETTINGS.get(часть.tag) or feature_name(часть.tag)
                    f = edt_model.feature(ext_cls, имя)
                    self.specified.add("extInfo/" + имя)
                    if f is None:
                        if not self._empty(часть):
                            self.problem(where, f"настройки «{часть.tag}» нет у {ext_name}")
                        continue
                    ext.children += [(edt_model.position(ext_cls, имя), n)
                                     for n in self.form_value(часть, f, ext_cls, f"{where}.{часть.tag}")]
        self.specified_by_id["attributes:" + a.attrs.get("name", "")] = set(self.specified)
        ключ = f"attributes|{ext_name or ''}"
        собрано += self.defaults(ключ, cls, собрано, ext, ext_cls,
                                 {з[len("extInfo/"):] for з in self.specified if з.startswith("extInfo/")}
                                 | self.specified)
        if ext_cls is not None:
            ext.attrs["xsi:type"] = "form:" + ext_name
            ext.children = [n for _, n in sorted(ext.children, key=lambda пара: пара[0])]
            собрано.append((edt_model.position(cls, "extInfo"), ext))
        self.specified = внешние
        собрано.sort(key=lambda пара: пара[0])
        return Node("attributes", children=[n for _, n in собрано])

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
        cls = FORM + "FormAttributeColumn"
        внешние, self.specified = self.specified, set()
        ключ_столбца = "columns:" + where + "." + к.attrs.get("name", "")
        where = f"{where}.Column «{к.attrs.get('name', '')}»"
        собрано = [(edt_model.position(cls, "name"), Node("name", text=к.attrs.get("name", ""))),
                   (edt_model.position(cls, "id"), Node("id", text=к.attrs.get("id", "")))]
        for c in к.children:
            if c.tag == "Type":
                собрано.append((edt_model.position(cls, "valueType"),
                                self.type_description(c, "valueType", where)))
            else:
                собрано += self.property(c, cls, where)
        self.specified_by_id[ключ_столбца] = set(self.specified)
        собрано += self.defaults("columns|", cls, собрано, Node("extInfo"), None, self.specified)
        self.specified = внешние
        собрано.sort(key=lambda пара: пара[0])
        return Node("columns", children=[n for _, n in собрано])

    def command(self, к):
        cls = FORM + "FormCommand"
        where = f"Command «{к.attrs.get('name', '')}»"
        внешние, self.specified = self.specified, set()
        собрано = [(edt_model.position(cls, "name"), Node("name", text=к.attrs.get("name", ""))),
                   (edt_model.position(cls, "id"), Node("id", text=к.attrs.get("id", "")))]
        for c in к.children:
            if c.tag == "Action":
                собрано.append((edt_model.position(cls, "action"),
                                Node("action", attrs={"xsi:type": "form:FormCommandHandlerContainer"},
                                     children=[Node("handler", children=[Node("name", text=c.text or "")])])))
            else:
                собрано += self.property(c, cls, where)
        self.specified_by_id["formCommands:" + к.attrs.get("name", "")] = set(self.specified)
        собрано += self.defaults("formCommands|", cls, собрано, Node("extInfo"), None, self.specified)
        self.specified = внешние
        собрано.sort(key=lambda пара: пара[0])
        return Node("formCommands", children=[n for _, n in собрано])

    def parameter(self, п):
        cls = FORM + "FormParameter"
        where = f"Parameter «{п.attrs.get('name', '')}»"
        собрано = [(edt_model.position(cls, "name"), Node("name", text=п.attrs.get("name", "")))]
        for c in п.children:
            if c.tag == "Type":
                собрано.append((edt_model.position(cls, "valueType"),
                                self.type_description(c, "valueType", where)))
            else:
                собрано += self.property(c, cls, where)
        собрано.sort(key=lambda пара: пара[0])
        return Node("parameters", children=[n for _, n in собрано])


__all__ = ["FormTranslation", "item_part", "MCORE"]
