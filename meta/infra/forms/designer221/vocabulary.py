"""Словарь формата управляемой формы 2.21: порядок, рождённые значения, имена.

Всё здесь снято с реальной выгрузки крупной типовой конфигурации (11 042 формы,
350 065 элементов) и с эталона конфигуратора; всё относится к одной версии
формата. Другая версия — другой модуль рядом; домен и разбор нотации о нём
не узнают.

Что откуда:

* `ROOT_ORDER` — порядок детей корня `<Form>`: 47 тегов, 0 противоречий
  на всём корпусе;
* `ELEMENT_ORDER` — порядок детей каждого вида элемента, тоже без единого
  противоречия; хвост у всех один — спутники, `Events`, `ChildItems`;
* `BORN` — что конфигуратор пишет у только что созданного элемента: по эталону
  конфигуратора, у видов без эталона — по корпусу (рождённое — то, что есть
  у ≥ 95 % элементов вида, остальное ставит человек; значения — самые частые);
* `EVENTS` — имя события в выгрузке ↔ русское имя, каким конфигуратор
  заканчивает имя обработчика («КонтрагентПриИзменении» -> `OnChange`):
  18 519 обработчиков `OnChange`, из них 15 770 с хвостом «ПриИзменении»;
* `SATELLITES` — спутники элемента и их суффиксы: «РасширеннаяПодсказка»
  261 443 раза, «КонтекстноеМеню» 155 541.
"""

from ....acl.mapping import Node
from ....domain.forms import FORM_COMMAND_BAR

FORMAT_VERSION = "2.21"

#: Пространства имён корня `<Form>` — в порядке, в каком их пишет платформа:
#: пространство по умолчанию, дальше по алфавиту приставки.
NAMESPACES = (
    ("", "http://v8.1c.ru/8.3/xcf/logform"),
    ("app", "http://v8.1c.ru/8.2/managed-application/core"),
    ("cfg", "http://v8.1c.ru/8.1/data/enterprise/current-config"),
    ("dcscor", "http://v8.1c.ru/8.1/data-composition-system/core"),
    ("dcssch", "http://v8.1c.ru/8.1/data-composition-system/schema"),
    ("dcsset", "http://v8.1c.ru/8.1/data-composition-system/settings"),
    ("ent", "http://v8.1c.ru/8.1/data/enterprise"),
    ("lf", "http://v8.1c.ru/8.2/managed-application/logform"),
    ("pal", "http://v8.1c.ru/8.1/data/ui/colors/palette"),
    ("style", "http://v8.1c.ru/8.1/data/ui/style"),
    ("sys", "http://v8.1c.ru/8.1/data/ui/fonts/system"),
    ("v8", "http://v8.1c.ru/8.1/data/core"),
    ("v8ui", "http://v8.1c.ru/8.1/data/ui"),
    ("web", "http://v8.1c.ru/8.1/data/ui/colors/web"),
    ("win", "http://v8.1c.ru/8.1/data/ui/colors/windows"),
    ("xr", "http://v8.1c.ru/8.3/xcf/readable"),
    ("xs", "http://www.w3.org/2001/XMLSchema"),
    ("xsi", "http://www.w3.org/2001/XMLSchema-instance"),
)

#: Порядок детей корня формы.
ROOT_ORDER = (
    "Title", "Width", "Height", "WindowOpeningMode", "EnterKeyBehavior",
    "AutoSaveDataInSettings", "SaveDataInSettings", "SaveWindowSettings", "SettingsStorage",
    "AutoTitle", "AutoURL", "Group", "HorizontalSpacing", "VerticalSpacing",
    "ChildItemsWidth", "HorizontalAlign", "VerticalAlign", "AutoFillCheck", "Customizable",
    "Enabled", "CommandBarLocation", "VerticalScroll", "ScalingMode",
    "ConversationsRepresentation", "MobileDeviceCommandBarContent", "CommandSet", "Scale",
    "ShowTitle", "ChildrenAlign", "ShowCloseButton", "CollapseItemsByImportanceVariant",
    "ShowCommandBar", "ReportResult", "DetailsData", "ReportFormType", "VariantAppearance",
    "AutoShowState", "AutoTime", "CustomSettingsFolder", "UsePostingMode",
    "ReportResultViewMode", "RepostOnWrite", "UseForFoldersAndItems", "GroupList",
    "ViewModeApplicationOnSetReportResult", "AutoCommandBar", "Events", "ChildItems",
    "Attributes", "Commands", "Parameters", "CommandInterface",
)

#: Порядок детей реквизита формы и колонки таблицы значений.
ATTRIBUTE_ORDER = ("Title", "Type", "View", "Edit", "MainAttribute", "SavedData",
                   "FillCheck", "UseAlways", "Save", "FunctionalOptions", "Columns",
                   "Settings")
COLUMN_ORDER = ("Title", "Type", "View", "Edit", "FillCheck", "FunctionalOptions", "Column")

#: Порядок детей команды.
COMMAND_ORDER = ("Title", "ToolTip", "Shortcut", "Use", "Picture", "Action",
                 "FunctionalOptions", "Representation", "ModifiesSavedData", "CurrentRowUse",
                 "AssociatedTableElementId", "SelectedRowsUse")

#: Порядок детей элементов по видам.
ELEMENT_ORDER = {
    "Button": (
        "Type", "Visible", "UserVisible", "Representation", "DefaultButton", "SkipOnInput",
        "Enabled", "DefaultItem", "TitleHeight", "Width", "AutoMaxWidth", "MaxWidth", "Height",
        "HorizontalStretch", "AutoMaxHeight", "MaxHeight", "VerticalStretch",
        "GroupHorizontalAlign", "GroupVerticalAlign", "Check", "PlacementArea", "CommandName",
        "TextColor", "BackColor", "BorderColor", "Font", "Parameter", "DataPath", "Picture",
        "Title", "ToolTipRepresentation", "RepresentationInContextMenu", "Shape",
        "ShapeRepresentation", "PictureLocation", "LocationInCommandBar", "CommandUniqueness",
        "ButtonImportance", "ExtendedTooltip",
    ),
    "InputField": (
        "DataPath", "Visible", "UserVisible", "DefaultItem", "Enabled", "ReadOnly",
        "SkipOnInput", "Title", "TitleTextColor", "TitleFont", "TitleLocation", "TitleHeight",
        "ToolTip", "ToolTipRepresentation", "WarningOnEditRepresentation", "Shortcut",
        "HorizontalAlign", "GroupHorizontalAlign", "WarningOnEdit", "GroupVerticalAlign",
        "TitleBackColor", "VerticalAlign", "EditMode", "CellHyperlink", "FixingInTable",
        "AutoCellHeight", "ShowInHeader", "HeaderPicture", "HeaderHorizontalAlign",
        "ShowInFooter", "FooterDataPath", "FooterText", "FooterFont", "FooterHorizontalAlign",
        "MarkRequiredComplete", "FooterPicture", "FooterBackColor", "AutoEditMode",
        "CellHyperlinkRepresentation", "CellHyperlinkDisplayVariant", "Width", "AutoMaxWidth",
        "MaxWidth", "Height", "AutoMaxHeight", "MaxHeight", "HorizontalStretch",
        "VerticalStretch", "Wrap", "PasswordMode", "MultiLine", "ExtendedEdit",
        "DropListButton", "MarkNegatives", "ChoiceButton", "ChoiceButtonRepresentation",
        "ClearButton", "SpinButton", "OpenButton", "CreateButton", "Mask", "ListChoiceMode",
        "AllowInputEmptyMultipleValues", "ExtendedEditMultipleValues", "AutoChoiceIncomplete",
        "QuickChoice", "Format", "EditFormat", "ShowCheckBoxesInDropList",
        "ChoiceFoldersAndItems", "AutoMarkIncomplete", "ChooseType", "IncompleteChoiceMode",
        "TypeDomainEnabled", "MultipleValueDataPath", "AvailableTypes",
        "MultipleValuePresentDataPath", "TextEdit", "EditTextUpdate", "MinValue",
        "ChoiceButtonPicture", "ChoiceForm", "MaxValue", "ChoiceList", "ChoiceParameterLinks",
        "ChoiceParameters", "ChoiceListButton", "TextColor", "ChoiceListHeight",
        "DropListWidth", "BackColor", "BorderColor", "AutoShowOpenButtonMode",
        "AutoCorrectionOnTextInput", "Font", "HeightControlVariant", "AutoShowClearButtonMode",
        "SpecialTextInputMode", "InputHint", "TypeLink", "ChoiceHistoryOnInput",
        "SpellCheckingOnTextInput", "ContextMenu", "ExtendedTooltip", "Events",
    ),
    "UsualGroup": (
        "Visible", "UserVisible", "Enabled", "ReadOnly", "EnableContentChange", "Title",
        "TitleTextColor", "TitleFont", "ToolTip", "ToolTipRepresentation", "Width", "Height",
        "Shortcut", "HorizontalStretch", "VerticalStretch", "GroupHorizontalAlign",
        "GroupVerticalAlign", "Group", "ChildrenAlign", "HorizontalSpacing", "VerticalSpacing",
        "HorizontalAlign", "VerticalAlign", "Behavior", "CollapsedRepresentationTitle",
        "Collapsed", "ControlRepresentation", "Representation", "ShowLeftMargin", "United",
        "ChildItemsWidth", "Format", "ShowTitle", "BackColor", "CurrentRowUse", "ThroughAlign",
        "AssociatedTableElementId", "TitleDataPath", "ExtendedTooltip", "ChildItems",
    ),
    "LabelDecoration": (
        "Visible", "Enabled", "Width", "UserVisible", "AutoMaxWidth", "MaxWidth", "Height",
        "AutoMaxHeight", "MaxHeight", "HorizontalStretch", "VerticalStretch", "SkipOnInput",
        "TextColor", "Font", "Title", "ToolTip", "ToolTipRepresentation",
        "GroupHorizontalAlign", "GroupVerticalAlign", "Hyperlink", "HorizontalAlign",
        "VerticalAlign", "BackColor", "BorderColor", "Border", "TitleHeight", "Shortcut",
        "ContextMenu", "ExtendedTooltip", "Events",
    ),
    "LabelField": (
        "DataPath", "Visible", "UserVisible", "DefaultItem", "Enabled", "ReadOnly",
        "SkipOnInput", "Title", "TitleTextColor", "TitleFont", "TitleLocation", "TitleHeight",
        "ToolTip", "ToolTipRepresentation", "HorizontalAlign", "VerticalAlign",
        "GroupHorizontalAlign", "GroupVerticalAlign", "WarningOnEditRepresentation",
        "FooterText", "TitleBackColor", "EditMode", "FixingInTable", "CellHyperlink",
        "AutoCellHeight", "ShowInHeader", "HeaderHorizontalAlign", "FooterDataPath",
        "HeaderPicture", "ShowInFooter", "FooterHorizontalAlign", "AutoEditMode",
        "CellHyperlinkRepresentation", "CellHyperlinkDisplayVariant", "Width", "AutoMaxWidth",
        "MaxWidth", "Height", "AutoMaxHeight", "MaxHeight", "HorizontalStretch",
        "VerticalStretch", "MarkNegatives", "Format", "Hiperlink", "Border", "BorderColor",
        "PasswordMode", "TextColor", "BackColor", "Font", "ContextMenu", "ExtendedTooltip",
        "Events",
    ),
    "ButtonGroup": (
        "Visible", "EnableContentChange", "UserVisible", "Title", "ToolTip",
        "ToolTipRepresentation", "CommandSource", "GroupVerticalAlign", "Width",
        "HorizontalStretch", "GroupHorizontalAlign", "Representation", "ExtendedTooltip",
        "ChildItems",
    ),
    "Page": (
        "Visible", "UserVisible", "Enabled", "ReadOnly", "EnableContentChange", "Title",
        "TitleTextColor", "TitleFont", "ToolTip", "ToolTipRepresentation", "Width", "Height",
        "HorizontalStretch", "VerticalStretch", "Shortcut", "Picture", "GroupHorizontalAlign",
        "GroupVerticalAlign", "Group", "HorizontalSpacing", "VerticalSpacing",
        "HorizontalAlign", "ChildItemsWidth", "VerticalAlign", "ShowTitle", "Format",
        "BackColor", "ChildrenAlign", "TitleDataPath", "ScrollOnCompress", "ExtendedTooltip",
        "ChildItems",
    ),
    "CheckBoxField": (
        "DataPath", "Visible", "UserVisible", "DefaultItem", "Enabled", "ReadOnly",
        "SkipOnInput", "Title", "TitleTextColor", "TitleFont", "TitleLocation", "TitleHeight",
        "ToolTip", "ToolTipRepresentation", "WarningOnEditRepresentation", "Shortcut",
        "TitleBackColor", "HorizontalAlign", "VerticalAlign", "GroupHorizontalAlign",
        "EditMode", "FixingInTable", "ShowInHeader", "HeaderPicture", "CellHyperlink",
        "HeaderHorizontalAlign", "ShowInFooter", "AutoCellHeight", "FooterHorizontalAlign",
        "AutoEditMode", "GroupVerticalAlign", "CheckBoxType", "EditFormat", "ItemWidth",
        "CellHyperlinkRepresentation", "EqualItemsWidth", "ItemTitleHeight", "ThreeState",
        "WarningOnEdit", "BackColor", "CellHyperlinkDisplayVariant", "Font", "ContextMenu",
        "ExtendedTooltip", "Events",
    ),
    "Table": (
        "Representation", "Visible", "UserVisible", "TitleLocation", "CommandBarLocation",
        "Autofill", "Enabled", "TitleHeight", "ReadOnly", "SkipOnInput", "DefaultItem",
        "ChangeRowSet", "ChangeRowOrder", "Width", "AutoMaxWidth", "MaxWidth", "Height",
        "AutoMaxHeight", "MaxHeight", "HeightInTableRows", "HeightControlVariant",
        "AutoMaxRowsCount", "MaxRowsCount", "ChoiceMode", "MultipleChoice", "RowInputMode",
        "SelectionMode", "RowSelectionMode", "Header", "HeaderHeight", "Footer",
        "FooterHeight", "HorizontalScrollBar", "VerticalScrollBar", "HorizontalLinesBWA",
        "VerticalLinesBWA", "UseAlternationRowColorBWA", "AutoInsertNewRow",
        "AutoAddIncomplete", "AutoMarkIncomplete", "SearchOnInput", "InitialListView",
        "InitialTreeView", "HorizontalStretch", "VerticalStretch", "Output", "EnableStartDrag",
        "EnableDrag", "FileDragMode", "DataPath", "RowPictureDataPath", "RowsPicture",
        "BackColor", "BorderColor", "Font", "TextColor", "Title", "TitleTextColor",
        "TitleFont", "CommandSet", "ToolTip", "ToolTipRepresentation", "SearchStringLocation",
        "ViewStatusLocation", "SearchControlLocation", "CurrentRowUse", "RefreshRequest",
        "BehaviorOnHorizontalCompression", "GroupHorizontalAlign", "GroupVerticalAlign",
        "ShowCommandBar", "AutoRefresh", "AutoRefreshPeriod", "Period",
        "ChoiceFoldersAndItems", "RestoreCurrentRow", "TopLevelParent", "ShowRoot",
        "AllowRootChoice", "UpdateOnDataChange", "ViewMode", "UserSettingsGroup",
        "AllowGettingCurrentRowURL", "ComplexSettingsViewMode", "RowFilter",
        "SettingsNamedItemDetailedRepresentation", "ContextMenu", "AutoCommandBar",
        "ExtendedTooltip", "SearchStringAddition", "ViewStatusAddition",
        "SearchControlAddition", "Events", "ChildItems",
    ),
    "Popup": (
        "Visible", "EnableContentChange", "Enabled", "Title", "TitleTextColor", "TitleFont",
        "ToolTip", "HorizontalStretch", "ToolTipRepresentation", "Picture", "CommandSource",
        "Representation", "Shape", "Width", "BackColor", "GroupHorizontalAlign",
        "VerticalStretch", "ShapeRepresentation", "BorderColor", "Height", "ExtendedTooltip",
        "ChildItems",
    ),
    "PictureDecoration": (
        "Visible", "Width", "AutoMaxWidth", "MaxWidth", "Height", "AutoMaxHeight", "MaxHeight",
        "HorizontalStretch", "VerticalStretch", "SkipOnInput", "TextColor", "Font", "Enabled",
        "Shortcut", "Title", "ToolTip", "ToolTipRepresentation", "GroupHorizontalAlign",
        "GroupVerticalAlign", "Hyperlink", "PictureSize", "Zoomable", "ImageScale",
        "NonselectedPictureText", "Picture", "BorderColor", "EnableStartDrag", "EnableDrag",
        "Border", "FileDragMode", "PictureColor", "ContextMenu", "ExtendedTooltip", "Events",
    ),
    # Выведено топологической сортировкой по корпусу: 2025 полей картинки,
    # 1723 поля переключателя, ни одного противоречия в парах «раньше».
    "PictureField": (
        "DataPath", "Visible", "UserVisible", "ReadOnly", "SkipOnInput", "TitleHeight",
        "Enabled", "Title", "TitleTextColor", "TitleBackColor", "TitleLocation", "ToolTip",
        "ToolTipRepresentation", "GroupHorizontalAlign", "GroupVerticalAlign",
        "HorizontalAlign", "WarningOnEditRepresentation", "EditMode", "FixingInTable",
        "CellHyperlink", "AutoCellHeight", "ShowInHeader", "FooterDataPath", "Shortcut",
        "HeaderPicture", "HeaderHorizontalAlign", "ShowInFooter", "FooterHorizontalAlign",
        "AutoEditMode", "CellHyperlinkRepresentation", "CellHyperlinkDisplayVariant",
        "FooterText", "Width", "AutoMaxWidth", "MaxWidth", "Height", "AutoMaxHeight",
        "MaxHeight", "HorizontalStretch", "VerticalStretch", "PictureSize", "Zoomable",
        "Hyperlink", "NonselectedPictureText", "EnableDrag", "TextColor", "ImageScale",
        "ValuesPicture", "BorderColor", "Border", "Font", "FileDragMode", "PictureColor",
        "ContextMenu", "ExtendedTooltip", "Events"),
    "RadioButtonField": (
        "DataPath", "Visible", "ReadOnly", "DefaultItem", "SkipOnInput", "Title",
        "TitleTextColor", "TitleFont", "Enabled", "TitleLocation", "TitleHeight",
        "ToolTip", "ToolTipRepresentation", "EditMode", "VerticalAlign",
        "GroupVerticalAlign", "GroupHorizontalAlign", "WarningOnEditRepresentation",
        "Shortcut", "WarningOnEdit", "ShowInHeader", "HeaderHorizontalAlign",
        "ShowInFooter", "AutoEditMode", "FooterHorizontalAlign", "RadioButtonType",
        "ItemWidth", "ItemTitleHeight", "ItemHeight", "ColumnsCount", "EqualColumnsWidth",
        "ChoiceList", "Font", "TextColor", "ContextMenu", "ExtendedTooltip", "Events"),
    "ColumnGroup": (
        "Visible", "Enabled", "ReadOnly", "UserVisible", "EnableContentChange", "Title",
        "TitleFont", "ToolTip", "Width", "HorizontalStretch", "GroupHorizontalAlign",
        "ToolTipRepresentation", "GroupVerticalAlign", "Height", "VerticalStretch", "Group",
        "ShowTitle", "TitleBackColor", "ShowInHeader", "HeaderDataPath",
        "HeaderHorizontalAlign", "FixingInTable", "HeaderFormat", "HeaderPicture",
        "ExtendedTooltip", "ChildItems",
    ),
    "Pages": (
        "Visible", "ReadOnly", "EnableContentChange", "Enabled", "UserVisible", "Title",
        "TitleFont", "Shortcut", "TitleTextColor", "ToolTip", "Width", "Height",
        "ToolTipRepresentation", "HorizontalStretch", "VerticalStretch",
        "GroupHorizontalAlign", "GroupVerticalAlign", "PagesRepresentation", "CurrentRowUse",
        "ExtendedTooltip", "Events", "ChildItems",
    ),
    "CommandBar": (
        "Visible", "Enabled", "EnableContentChange", "Title", "ToolTip",
        "ToolTipRepresentation", "Width", "Height", "HorizontalStretch",
        "GroupHorizontalAlign", "VerticalStretch", "GroupVerticalAlign", "HorizontalLocation",
        "CommandSource", "ExtendedTooltip", "ChildItems",
    ),
}

#: Вид элемента словами домена -> тег выгрузки.
XML_KIND = {
    "ПолеВвода": "InputField",
    "ПолеФлажка": "CheckBoxField",
    "ПолеНадписи": "LabelField",
    "ПолеКартинки": "PictureField",
    "ПолеПереключателя": "RadioButtonField",
    "Надпись": "LabelDecoration",
    "Картинка": "PictureDecoration",
    "ГруппаФормы": "UsualGroup",
    "Страницы": "Pages",
    "Страница": "Page",
    "КоманднаяПанель": "CommandBar",
    "ГруппаКнопок": "ButtonGroup",
    "ГруппаКолонок": "ColumnGroup",
    "Подменю": "Popup",
    "КонтекстноеМеню": "ContextMenu",
    "Кнопка": "Button",
    "ТаблицаФормы": "Table",
}
DOMAIN_KIND = {tag: kind for kind, tag in XML_KIND.items()}
#: Автоматическая командная панель формы и таблицы — для домена та же панель:
#: в неё кладут кнопки тем же словом.
DOMAIN_KIND["AutoCommandBar"] = "КоманднаяПанель"

#: Виды, которые инструмент читает, но не пишет: показ формы обязан называть
#: по-русски и то, чего не умеет заводить, — иначе в дереве элементов посреди
#: русских слов стоит английский тег и читается как ошибка. Слова взяты из
#: справочника свойств (`domain/form_properties.py`), а не придуманы здесь;
#: тест сверяет, что каждое из них там есть. Счёт по корпусу: полей
#: табличного документа 2166, HTML-документа 246, текстового 182.
DOMAIN_KIND.update({
    "SpreadSheetDocumentField": "ПолеТабличногоДокумента",
    "HTMLDocumentField": "ПолеHTMLДокумента",
    "TextDocumentField": "ПолеТекстовогоДокумента",
    "FormattedDocumentField": "ПолеФорматированногоДокумента",
    "ProgressBarField": "ПолеИндикатора",
    "GraphicalSchemaField": "ПолеГрафическойСхемы",
    "GeographicalSchemaField": "ПолеГеографическойСхемы",
    "DendrogramField": "ПолеДендрограммы",
    "ChartField": "ПолеДиаграммы",
    "GanttChartField": "ПолеДиаграммыГанта",
    "CalendarField": "ПолеКалендаря",
    "TrackBarField": "ПолеПолосыРегулирования",
    "PDFDocumentField": "ПолеPDFДокумента",
    "PlannerField": "ПолеПланировщика",
    "PeriodField": "ПолеПериода",
})

#: Спутники — не элементы справочника свойств, поэтому имена им даны по их
#: платформенному назначению: с «--подробно» они видны, и английский тег там
#: читался бы так же плохо.
DOMAIN_KIND.update({
    "ExtendedTooltip": "РасширеннаяПодсказка",
    "SearchStringAddition": "ДополнениеСтрокаПоиска",
    "ViewStatusAddition": "ДополнениеСостояниеПросмотра",
    "SearchControlAddition": "ДополнениеУправлениеПоиском",
})

#: Английское имя свойства платформы -> тег выгрузки, где они расходятся.
#: Снято сравнением справочника свойств с тегами корпуса: платформа зовёт
#: положение в группе `HorizontalAlignInGroup`, а файл — `GroupHorizontalAlign`.
#: Чего здесь нет — пишется тегом, равным английскому имени.
TAG_BY_PLATFORM_NAME = {
    "HorizontalAlignInGroup": "GroupHorizontalAlign",
    "VerticalAlignInGroup": "GroupVerticalAlign",
    "UseAlternationRowColor": "UseAlternationRowColorBWA",
    "HorizontalLines": "HorizontalLinesBWA",
    "VerticalLines": "VerticalLinesBWA",
    "AutoShowClearButton": "AutoShowClearButtonMode",
    "AutoShowOpenButton": "AutoShowOpenButtonMode",
}

#: Свойства, которые платформа в выгрузку не пишет вовсе (в корпусе тега нет
#: ни у одного из 350 065 элементов). Задать их нельзя — отказ, а не тег наугад.
NOT_IN_DUMP = ("DisplayImportance", "OnMainServerUnavalableBehavior")

#: Свойства-строки, которые платформа пишет многоязычно (`<v8:item>`):
#: `Title` 165 291 из 165 356, `ToolTip` 54 964 из 54 964, остальные — все.
MULTILANG_TAGS = ("Title", "ToolTip", "Format", "EditFormat", "InputHint", "FooterText",
                  "WarningOnEdit", "CollapsedRepresentationTitle", "NonselectedPictureText")

#: Свойства со своей структурой в файле — булевым или строкой не пишутся.
#: `UserVisible` — `{Common, Value}` у 4808 элементов; списки, наборы команд,
#: картинки, рамки. Отказ, а не текст наугад.
STRUCTURED_TAGS = ("UserVisible", "ChoiceList", "ChoiceParameterLinks", "ChoiceParameters",
                   "CommandSet", "Border", "Picture", "HeaderPicture", "RowsPicture",
                   "ValuesPicture", "ChoiceButtonPicture", "TypeLink", "AdditionSource",
                   "Period", "Parameter", "RowFilter", "TopLevelParent", "Font",
                   "TitleFont", "FooterFont")

#: Дополнения таблицы — спутники с содержимым: источник (сама таблица и вид
#: дополнения) и собственные контекстное меню с подсказкой. Пустые теги
#: платформа при загрузке и выгрузке дописывает до этого состава.
ADDITION_TYPES = {
    "SearchStringAddition": "SearchStringRepresentation",
    "ViewStatusAddition": "ViewStatusRepresentation",
    "SearchControlAddition": "SearchControl",
}

#: Атрибуты заголовка по виду элемента: у надписи заголовок несёт признак
#: форматирования — `formatted="false"`.
TITLE_ATTRS = {"LabelDecoration": {"formatted": "false"},
               # у всех 4197 заголовков картинок-декораций корпуса
               "PictureDecoration": {"formatted": "false"}}

#: Спутники элемента: тег -> суффикс имени. Имя спутника — имя элемента
#: плюс суффикс, так у 261 443 подсказок из 262 218.
SATELLITES = {
    "ContextMenu": "КонтекстноеМеню",
    "ExtendedTooltip": "РасширеннаяПодсказка",
    "AutoCommandBar": "КоманднаяПанель",
    "SearchStringAddition": "СтрокаПоиска",
    "ViewStatusAddition": "СостояниеПросмотра",
    "SearchControlAddition": "УправлениеПоиском",
}

#: Период таблицы динамического списка — структура, а не текст: платформа
#: пишет её у всех 3373 таблиц корпуса одинаково, пустым произвольным
#: периодом.
PERIOD_NODE = Node("Period", children=[
    Node("v8:variant", attrs={"xsi:type": "v8:StandardPeriodVariant"}, text="Custom"),
    Node("v8:startDate", text="0001-01-01T00:00:00"),
    Node("v8:endDate", text="0001-01-01T00:00:00"),
])

#: Что рождается у элемента каждого вида: (тег, значение) в порядке появления
#: среди свойств; спутники перечислены отдельно. Значение словарём — атрибуты
#: вместо текста (`<RowFilter xsi:nil="true"/>`).
#:
#: **Снято с эталона конфигуратора**, а не с корпуса: форма `мой_Эталон`
#: документа `мой_ПробаНепроводимый` в проверочной пустой конфигурации — мастер
#: плюс по элементу каждого вида, добавленному руками без настройки. Корпус для
#: этого не годится: там формы прожили годы правок, и «что настроили» от
#: «что родилось» по нему не отличить. С эталоном корпус расходится в пяти
#: местах: у флажка нет `TitleLocation`, у группы нет ни `Group`, ни
#: `Behavior`, ни `Representation`, ни `ShowTitle`, у страниц нет
#: `PagesRepresentation`, у страницы нет `Group` и `ScrollOnCompress`,
#: у таблицы нет `RowSelectionMode` и `UseAlternationRowColorBWA`.
BORN = {
    # Поле ввода вне таблицы: только признак расширенного редактирования.
    # `EditMode` мастер пишет своим полям, а добавленному руками — нет
    # (эталон: «Номер» от мастера с ним, «Комментарий1» руками без него).
    "InputField": {
        "properties": (("ExtendedEditMultipleValues", "true"),),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    "InputField/в таблице": {
        "properties": (("EditMode", "EnterOnInput"), ("AutoEditMode", "true"),
                       ("ExtendedEditMultipleValues", "true")),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    "LabelField": {
        "properties": (),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    # Поле-надпись в таблице: режим редактирования есть, автоматического нет
    # (эталон, колонка «НомерСтроки» табличной части).
    "LabelField/в таблице": {
        "properties": (("EditMode", "EnterOnInput"),),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    "CheckBoxField": {
        "properties": (),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    "CheckBoxField/в таблице": {
        "properties": (("EditMode", "EnterOnInput"), ("AutoEditMode", "true")),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    "LabelDecoration": {
        "properties": (),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    "UsualGroup": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
    "Page": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
    "Pages": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
    # Таблица табличной части и таблица значений формы рождаются одинаково —
    # это видно на эталоне, где есть обе.
    "Table": {
        "properties": (("Representation", "List"), ("AutoInsertNewRow", "true"),
                       ("EnableStartDrag", "true"), ("EnableDrag", "true"),
                       ("ShowCommandBar", "auto"), ("RowFilter", {"xsi:nil": "true"})),
        "satellites": ("ContextMenu", "AutoCommandBar", "ExtendedTooltip",
                       "SearchStringAddition", "ViewStatusAddition", "SearchControlAddition"),
    },
    # Таблица динамического списка. Эталона конфигуратора для формы списка
    # нет, и судит платформа: эти десять свойств стоят у всех 3373 таблиц
    # динамических списков корпуса, и круг через платформу (запись — загрузка
    # — выгрузка) возвращает их нетронутыми, а лишний `RowFilter` убирает.
    "Table/динамический список": {
        # `RowFilter` здесь нет намеренно: платформа его убирает — отбор строк
        # бывает у таблицы данных, а не у списка, который сам себе запрос.
        "properties": (("AutoRefresh", "false"), ("AutoRefreshPeriod", "60"),
                       ("Period", PERIOD_NODE), ("ChoiceFoldersAndItems", "Items"),
                       ("RestoreCurrentRow", "false"),
                       ("TopLevelParent", {"xsi:nil": "true"}),
                       ("ShowRoot", "true"), ("AllowRootChoice", "false"),
                       ("UpdateOnDataChange", "Auto"),
                       ("AllowGettingCurrentRowURL", "true")),
        "satellites": ("ContextMenu", "AutoCommandBar", "ExtendedTooltip",
                       "SearchStringAddition", "ViewStatusAddition", "SearchControlAddition"),
    },
    # Поле картинки: спутники как у любого поля (у всех 2025 корпуса). Свойств
    # с долей 95 % и выше нет — `КартинкаЗначений` 87 %, `ПоложениеЗаголовка`
    # 84 %, их ставит человек. Эталона конфигуратора на этот вид нет: значения —
    # по корпусу.
    "PictureField": {
        "properties": (),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    # Поле переключателя: `RadioButtonType` стоит у всех 1723 полей корпуса,
    # у 1162 со значением `Auto` — рождённое. `ChoiceList` (95,2 %) рождённым
    # НЕ считаем: это не рождение, а бесполезность переключателя без списка,
    # пустой список конфигуратор не пишет. Значения тоже по корпусу.
    "RadioButtonField": {
        "properties": (("RadioButtonType", "Auto"),),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    # Картинка-декорация — как надпись-декорация (эталон): два спутника и
    # ничего больше. Заголовок рождённым не считаем, он есть у 57,7 %; зато у
    # всех 4197, где он есть, стоит `formatted="false"` — это в `TITLE_ATTRS`.
    "PictureDecoration": {
        "properties": (),
        "satellites": ("ContextMenu", "ExtendedTooltip"),
    },
    # Группа колонок — контейнер, и спутник у неё один: `ExtendedTooltip` у
    # всех 5490, контекстного меню нет ни у одной. Заголовок пишется от имени
    # (91 %), а подсказка — нет (34,8 %): в этом группа колонок расходится с
    # группами формы, где на эталоне `ToolTip` — дословная копия `Title`.
    "ColumnGroup": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
    "Button": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
    "CommandBar": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
    "ButtonGroup": {
        "properties": (),
        "satellites": ("ExtendedTooltip",),
    },
}

# Таблица дерева значений. Рождается как таблица данных, но без отбора строк:
# круг через платформу убирает `RowFilter` — отбор бывает у плоского набора
# строк, а у дерева и у динамического списка его нет. `Representation`
# платформа оставляет `List`: иерархию даёт источник данных, а не свойство
# таблицы.
BORN["Table/дерево"] = {
    "properties": tuple((tag, value) for tag, value in BORN["Table"]["properties"]
                        if tag != "RowFilter"),
    "satellites": BORN["Table"]["satellites"],
}

#: Теги-картинки и приставка ссылки. В выгрузке картинка — узел `Ref`
#: с `LoadTransparent` (27 797 случаев против 260 встроенных двоичных `Abs`,
#: которые заданием не выражаются). Приставок две: картинка конфигурации
#: `CommonPicture` (17 575) и стандартная картинка платформы `StdPicture`
#: (10 221).
PICTURE_TAGS = ("Picture", "ValuesPicture", "HeaderPicture")
PICTURE_PREFIX = {"БиблиотекаКартинок": "CommonPicture",
                  "СтандартнаяКартинка": "StdPicture"}

#: Виды, которым конфигуратор пишет подсказку тем же текстом, что и заголовок:
#: у группы, страниц, страницы и командной панели эталона `ToolTip` дословно
#: повторяет `Title`.
TOOLTIP_AS_TITLE = ("UsualGroup", "Pages", "Page", "CommandBar", "ButtonGroup")

#: Виды, которым заголовок пишется от имени, а подсказка — нет. Группа колонок
#: единственная: заголовок у 91 % из 5490, подсказка у 34,8 % — если бы она
#: рождалась копией заголовка, доли совпали бы, как у групп формы.
TITLE_AS_NAME = ("ColumnGroup",)

#: Свойства, которые пишутся у элемента по словам нотации. Ключ — слово
#: нотации, значение — (тег, значение или функция от сказанного).
OPTION_TAGS = {
    "горизонтально": ("Group", "Horizontal"),
    "заголовок": ("ShowTitle", "true"),
    "рамка": ("Representation", "NormalSeparation"),
    "свернуть": ("Behavior", "Collapsible"),
    "закладки": ("PagesRepresentation", "TabsOnTop"),
    "ширина": ("Width", None),
    "высота": ("Height", None),
    "просмотр": ("ReadOnly", "true"),
    "безПодписи": ("TitleLocation", "None"),
    "подписьСверху": ("TitleLocation", "Top"),
    "многострочное": ("MultiLine", "true"),
    "гиперссылка": ("Hyperlink", "true"),
    "растянуть": ("HorizontalStretch", "true"),
}

#: Свойства корня, которые рождаются с формой, по назначению. Порядок —
#: по `ROOT_ORDER`, здесь только состав и значения.
#:
#: По эталону конфигуратора: у новой формы документа в корне
#: только три свойства проведения — ни `WindowOpeningMode`, ни `Group`
#: конфигуратор не пишет, хотя в корпусе они есть у 11 024 и 11 014 форм
#: из 11 042. Объяснение простое: это значения по умолчанию, а корпусные
#: формы настраивали руками (у форм документов `DontBlock` 666 из 680,
#: у форм элемента `LockOwner` 541 из 754 — разнобой, а не рождение).
#:
#: `UseForFoldersAndItems` оставлен: у форм элемента он стоит у всех 754,
#: у форм группы — `Folders` у всех 108; такого единогласия у настраиваемых
#: свойств не бывает. Эталоном не подтверждён — эталона формы справочника нет.
ROOT_BORN = {
    "Документа": (("AutoTime", "CurrentOrLast"), ("UsePostingMode", "Auto"),
                  ("RepostOnWrite", "true")),
    "Элемента": (("UseForFoldersAndItems", "Items"),),
    "Группы": (("UseForFoldersAndItems", "Folders"),),
    "Списка": (),
    "Выбора": (),
    "ВыбораГруппы": (),
    "Записи": (),
    "Обработки": (),
    "Отчета": (),
    "Произвольная": (),
}

#: Имя автоматической командной панели формы. «ФормаКоманднаяПанель» —
#: 10 978 форм, «FormCommandBar» — 57: зависит от языка конфигуратора.
#: Значение — из домена: проверка формы кладёт в эту панель кнопки ещё до
#: того, как форма родилась, и имя у них одно.
AUTO_COMMAND_BAR = FORM_COMMAND_BAR

#: Главный реквизит по назначению: что пишется сверх имени и типа.
#: `UseAlways Объект.RegisterRecords` у формы документа — 643 из 680.
MAIN_ATTRIBUTE_BORN = {
    "Документа": (("SavedData", "true"), ("UseAlways", ("Объект.RegisterRecords",))),
    "Элемента": (("SavedData", "true"),),
    "Группы": (("SavedData", "true"),),
    "Записи": (("SavedData", "true"),),
    "Обработки": (),
    "Отчета": (),
    "Списка": (("Settings", "DynamicList"),),
    "Выбора": (("Settings", "DynamicList"),),
    "ВыбораГруппы": (("Settings", "DynamicList"),),
}

#: Грани типов выгрузки для главного реквизита.
MAIN_TYPE_FACET = {"Объект": "Object", "МенеджерЗаписи": "RecordManager"}

#: События формы: русское имя -> имя в выгрузке. Снято по 9947 `OnCreateAtServer`
#: и далее по убыванию.
FORM_EVENTS = {
    "ПриСозданииНаСервере": "OnCreateAtServer",
    "ПриОткрытии": "OnOpen",
    "ОбработкаОповещения": "NotificationProcessing",
    "ПередЗакрытием": "BeforeClose",
    "ПриЗакрытии": "OnClose",
    "ПриЧтенииНаСервере": "OnReadAtServer",
    "ПослеЗаписиНаСервере": "AfterWriteAtServer",
    "ПослеЗаписи": "AfterWrite",
    "ПередЗаписьюНаСервере": "BeforeWriteAtServer",
    "ОбработкаПроверкиЗаполненияНаСервере": "FillCheckProcessingAtServer",
    "ПередЗаписью": "BeforeWrite",
    "ОбработкаВыбора": "ChoiceProcessing",
    "ПриПовторномОткрытии": "OnReopen",
    "ПриИзмененииНаСервере": "OnChangeAtServer",
    # Дальше — редкие, но в корпусе есть: без них показ печатал бы английское
    # имя выгрузки («OnWriteAtServer»). Русское имя — по обработчикам корпуса:
    # у события формы обработчик по умолчанию зовётся им.
    "ПриЗагрузкеДанныхИзНастроекНаСервере": "OnLoadDataFromSettingsAtServer",            # 248
    "ПриЗагрузкеПользовательскихНастроекНаСервере": "OnLoadUserSettingsAtServer",        # 194
    "ПриСохраненииПользовательскихНастроекНаСервере": "OnSaveUserSettingsAtServer",      # 194
    "ОбработкаНавигационнойСсылки": "URLProcessing",                                     # 110
    "ПередЗагрузкойДанныхИзНастроекНаСервере": "BeforeLoadDataFromSettingsAtServer",     # 108
    "ПриЗагрузкеВариантаНаСервере": "OnLoadVariantAtServer",                             # 86
    "ПриЗаписиНаСервере": "OnWriteAtServer",                                             # 73
    "ПриСохраненииВариантаНаСервере": "OnSaveVariantAtServer",                           # 43
    "ПриОбновленииСоставаПользовательскихНастроекНаСервере": "OnUpdateUserSettingSetAtServer",
    "ВнешнееСобытие": "ExternalEvent",
    "ПриСохраненииДанныхВНастройкахНаСервере": "OnSaveDataInSettingsAtServer",
    "ПередЗагрузкойВариантаНаСервере": "BeforeLoadVariantAtServer",
    "ПередЗагрузкойПользовательскихНастроекНаСервере": "BeforeLoadUserSettingsAtServer",
    "ОбработкаЗаписиНового": "NewWriteProcessing",
    "ОбработкаПолученияНавигационнойСсылки": "URLGetProcessing",
    "ОбработкаПерехода": "NavigationProcessing",
    "ОбработкаПолученияСпискаНавигационныхСсылок": "URLListGetProcessing",
    "ПриИзмененииДоступностиОсновногоСервера": "OnMainServerAvailabilityChange",
}

FORM_EVENTS_BACK = {english: russian for russian, english in FORM_EVENTS.items()}

#: События элементов: русское имя -> имя в выгрузке. Хвосты имён обработчиков
#: по корпусу: «ПриИзменении» 15 770, «Нажатие» 4522, «НачалоВыбора» 3929…
ELEMENT_EVENTS = {
    "ПриИзменении": "OnChange",
    "Нажатие": "Click",
    "НачалоВыбора": "StartChoice",
    "ОбработкаНавигационнойСсылки": "URLProcessing",
    "ПриАктивизацииСтроки": "OnActivateRow",
    "Очистка": "Clearing",
    "Выбор": "Selection",
    "ОбработкаВыбора": "ChoiceProcessing",
    "АвтоПодбор": "AutoComplete",
    "ПередНачаломДобавления": "BeforeAddRow",
    "ПередУдалением": "BeforeDeleteRow",
    "ПриНачалеРедактирования": "OnStartEdit",
    "ПередНачаломИзменения": "BeforeRowChange",
    "ОкончаниеВводаТекста": "TextEditEnd",
    "Открытие": "Opening",
    "ПриОкончанииРедактирования": "OnEditEnd",
    "ПослеУдаления": "AfterDeleteRow",
    "Создание": "Creating",
    "ПриСменеСтраницы": "OnCurrentPageChange",
    "Регулирование": "Tuning",
    "Перетаскивание": "Drag",
    "ИзменениеТекстаРедактирования": "EditTextChange",
    "ПроверкаПеретаскивания": "DragCheck",
    "ПриАктивизацииЯчейки": "OnActivateCell",
    "ПриПолученииДанныхНаСервере": "OnGetDataAtServer",
    # Редкие, по хвостам имён обработчиков корпуса.
    # «OnActivate» не взят: хвосты «ПриАктивизацииОбласти» 38 и «ПриАктивизации»
    # 26 — по корпусу не решить, а статьи в синтакс-помощнике нет.
    "ПередЗагрузкойПользовательскихНастроекНаСервере": "BeforeLoadUserSettingsAtServer",  # 703
    "ПриОбновленииСоставаПользовательскихНастроекНаСервере": "OnUpdateUserSettingSetAtServer",
    "ПриЗагрузкеПользовательскихНастроекНаСервере": "OnLoadUserSettingsAtServer",
    "ПриСохраненииПользовательскихНастроекНаСервере": "OnSaveUserSettingsAtServer",
    "ВыборЗначения": "ValueChoice",
    "ОбработкаРасшифровки": "DetailProcessing",
    "ПередОкончаниемРедактирования": "BeforeEditEnd",
    "ПриНажатии": "OnClick",
    "ОбработкаДополнительнойРасшифровки": "AdditionalDetailProcessing",
    "ПередРазворачиванием": "BeforeExpand",
    "НачалоПеретаскивания": "DragStart",
    "ПриАктивизацииПоля": "OnActivateField",
    "ПередСворачиванием": "BeforeCollapse",
    "ПриИзмененииСодержимогоОбласти": "OnChangeAreaContent",
    "НачалоВыбораИзСписка": "StartListChoice",
    "ОкончаниеПеретаскивания": "DragEnd",
    "ОбработкаЗапросаОбновления": "RefreshRequestProcessing",
    "ДокументСформирован": "DocumentComplete",
    "ПриАктивизацииДаты": "OnActivateDate",
    "ОбработкаЗаписиНового": "NewWriteProcessing",
    "ПередСозданием": "BeforeCreate",
    "ПриСменеТекущегоПериодаОтображения": "OnCurrentRepresentationPeriodChange",
    "ПередНачаломРедактирования": "BeforeStartEdit",
    "ОбработкаФормированияКоманд": "CommandGenerateProcessing",
    "ПередНачаломБыстрогоРедактирования": "BeforeStartQuickEdit",
    "ПриВыводеПериода": "OnPeriodOutput",
    "ПриОкончанииРедактированияИнтервала": "OnIntervalEditEnd",
    "ОткрытиеМножественногоЗначения": "MultipleValueOpening",
    "ПередПечатью": "BeforePrint",
    "ПередСтартом": "BeforeStart",
    "ПриСменеТекущегоРодителя": "OnCurrentParentChange",
    "УдалениеМножественныхЗначений": "MultipleValuesDelete",
    "ОбработкаНавигационнойСсылкиМножественногоЗначения": "MultipleValueURLProcessing",
    # «BeforeDelete» (1 в корпусе, планировщик) по-русски тоже «ПередУдалением»,
    # как «BeforeDeleteRow» таблицы: словарь записи их бы не различил — не взят.
    # Есть у видов по синтакс-помощнику (domain/form_events), в корпусе не
    # встречаются; имена в выгрузке — английские имена синтакс-помощника, как у
    # всех событий выше.
    "ДобавлениеМножественныхЗначений": "MultipleValuesAdd",
    "ПриИзмененииСоставаВыделенныхСтрок": "OnSelectedRowsSetChange",
    "ПриНаведении": "OnHover",
    "ОбработкаПолученияНавигационнойСсылки": "URLGetProcessing",
    "ОбработкаПолученияСпискаНавигационныхСсылок": "URLListGetProcessing",
}

ELEMENT_EVENTS_BACK = {english: russian for russian, english in ELEMENT_EVENTS.items()}

#: Сигнатуры обработчиков для заготовок модуля: (где, событие) -> (директива,
#: параметры). Сняты с 10 239 модулей форм: по имени обработчика из Form.xml
#: найдено объявление процедуры, взято самое частое. Где — «форма», «элемент»,
#: «таблица», «надпись» (у надписи «Нажатие» без стандартной обработки —
#: 7551 против 1930 у полей-надписей).
HANDLER_SIGNATURES = {
    ("форма", "ПриСозданииНаСервере"): ("&НаСервере", "Отказ, СтандартнаяОбработка"),   # 9916
    ("форма", "ПриОткрытии"): ("&НаКлиенте", "Отказ"),                                      # 4748
    ("форма", "ОбработкаОповещения"): ("&НаКлиенте", "ИмяСобытия, Параметр, Источник"),     # 4155
    ("форма", "ПередЗакрытием"): ("&НаКлиенте", "Отказ, ЗавершениеРаботы, ТекстПредупреждения, СтандартнаяОбработка"),   # 2893
    ("форма", "ПриЗакрытии"): ("&НаКлиенте", "ЗавершениеРаботы"),                           # 2251
    ("форма", "ПриЧтенииНаСервере"): ("&НаСервере", "ТекущийОбъект"),                       # 1385
    ("форма", "ПослеЗаписиНаСервере"): ("&НаСервере", "ТекущийОбъект, ПараметрыЗаписи"),    # 1273
    ("форма", "ПослеЗаписи"): ("&НаКлиенте", "ПараметрыЗаписи"),                             # 1041
    ("форма", "ПередЗаписьюНаСервере"): ("&НаСервере", "Отказ, ТекущийОбъект, ПараметрыЗаписи"),   # 783
    ("форма", "ОбработкаПроверкиЗаполненияНаСервере"): ("&НаСервере", "Отказ, ПроверяемыеРеквизиты"),   # 660
    ("форма", "ПередЗаписью"): ("&НаКлиенте", "Отказ, ПараметрыЗаписи"),                    # 487
    ("форма", "ОбработкаВыбора"): ("&НаКлиенте", "ВыбранноеЗначение, ИсточникВыбора"),      # 466
    ("элемент", "ПриИзменении"): ("&НаКлиенте", "Элемент"),                                  # 23758
    ("элемент", "Нажатие"): ("&НаКлиенте", "Элемент, СтандартнаяОбработка"),                # 1930 у полей
    ("надпись", "Нажатие"): ("&НаКлиенте", "Элемент"),                                       # 7551
    ("элемент", "НачалоВыбора"): ("&НаКлиенте", "Элемент, ДанныеВыбора, СтандартнаяОбработка"),   # 4592
    ("элемент", "ОбработкаНавигационнойСсылки"): ("&НаКлиенте", "Элемент, НавигационнаяСсылкаФорматированнойСтроки, СтандартнаяОбработка"),   # 3527
    ("элемент", "Очистка"): ("&НаКлиенте", "Элемент, СтандартнаяОбработка"),                # 2143
    ("элемент", "ОбработкаВыбора"): ("&НаКлиенте", "Элемент, ВыбранноеЗначение, СтандартнаяОбработка"),   # 1658
    ("элемент", "АвтоПодбор"): ("&НаКлиенте", "Элемент, Текст, ДанныеВыбора, ПараметрыПолученияДанных, Ожидание, СтандартнаяОбработка"),   # 1426
    ("элемент", "ОкончаниеВводаТекста"): ("&НаКлиенте", "Элемент, Текст, ДанныеВыбора, ПараметрыПолученияДанных, СтандартнаяОбработка"),   # 692
    ("элемент", "Открытие"): ("&НаКлиенте", "Элемент, СтандартнаяОбработка"),               # 711
    ("элемент", "Создание"): ("&НаКлиенте", "Элемент, СтандартнаяОбработка"),               # 253
    ("элемент", "ПриСменеСтраницы"): ("&НаКлиенте", "Элемент, ТекущаяСтраница"),            # 186
    ("таблица", "ПриАктивизацииСтроки"): ("&НаКлиенте", "Элемент"),                          # 2322
    ("таблица", "Выбор"): ("&НаКлиенте", "Элемент, ВыбраннаяСтрока, Поле, СтандартнаяОбработка"),   # 2030
    ("таблица", "ПриИзменении"): ("&НаКлиенте", "Элемент"),                                  # 1441
    ("таблица", "ПередНачаломДобавления"): ("&НаКлиенте", "Элемент, Отказ, Копирование, Родитель, Группа, Параметр"),   # 679
    ("таблица", "ПередУдалением"): ("&НаКлиенте", "Элемент, Отказ"),                         # 990
    ("таблица", "ПриНачалеРедактирования"): ("&НаКлиенте", "Элемент, НоваяСтрока, Копирование"),   # 894
    ("таблица", "ПередНачаломИзменения"): ("&НаКлиенте", "Элемент, Отказ"),                  # 849
    ("таблица", "ПриОкончанииРедактирования"): ("&НаКлиенте", "Элемент, НоваяСтрока, ОтменаРедактирования"),   # 559
    ("таблица", "ПослеУдаления"): ("&НаКлиенте", "Элемент"),                                 # 448
    ("таблица", "ОбработкаВыбора"): ("&НаКлиенте", "Элемент, ВыбранноеЗначение, СтандартнаяОбработка"),   # 210
    ("таблица", "ПриАктивизацииЯчейки"): ("&НаКлиенте", "Элемент"),                          # 125
}
