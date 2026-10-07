"""Словарь выгрузки: таблицы соответствий «домен ↔ формат».

Здесь только данные — ни одной строчки логики. Таблицы пополняются с каждым
новым видом объекта, а перекладка при этом не меняется: ради этого они и
вынесены отдельно.

Каждая таблица снята с реальной выгрузки крупной типовой конфигурации, а не
придумана; числа наблюдений указаны рядом. Проверяются они не глазами:
побайтные сверки в `meta/tests`
пересобирают десятки тысяч настоящих карточек через эти же таблицы.
"""

# --- то, чем домен не обязан владеть ----------------------------------------

TEXT = "текст"           # <Name>значение</Name>


NESTED = "вложенное"   # <ChoiceParameters><app:item…> — своя структура


MULTILANG = "многоязычный"  # <Synonym><v8:item><v8:lang>ru…


TYPES = "типы"             # <Source><v8:Type>cfg:…


BOOLEAN = "логическое"  # <Server>true</Server>


VALUE_TYPE = "тип"      # <Type><v8:Type>xs:string</v8:Type><v8:StringQualifiers>…


VALUE = "значение"        # <MinValue xsi:nil="true"/> либо <FillValue xsi:type="xs:string"/>
FIELDS = "поля"           # <InputByString><xr:Field>…
#: Список обозначений объектов: владельцы справочника, основания документа,
#: его движения, состав подсистемы. Каждый элемент несёт
#: `xsi:type="xr:MDObjectRef"` и обозначение в написании выгрузки.
#:
#: Тип у элементов обязателен: с голым `<xr:Item>` три из четырёх мест
#: писались бы неверно — это видно на эталоне регистра накопления, на движениях
#: документа. Замер по корпусу: движения 4191, владельцы 86, основания 477,
#: состав подсистем 25 458 — тип у всех.
ITEMS = "элементы"        # <Owners><xr:Item xsi:type="xr:MDObjectRef">…


# Повторное использование возвращаемых значений: как называет разработчик →
# как записано в выгрузке. Третье значение платформы («на время вызова»)
# в конфигурации не встречается, но существует, поэтому в таблице есть.
RETURN_REUSE = {
    "НеИспользовать": "DontUse",
    "НаВремяВызова": "DuringRequest",
    "НаВремяСеанса": "DuringSession",
}


# Вид метаданных → корень обозначения типа. Снято с 639 подписок конфигурации.
# Версия формата выгрузки. Факт формата, а не подробность записи,
# поэтому живёт в словаре: её одинаково нужно знать и перекладке
# (файл прав роли), и сериализации.
FORMAT_VERSION = "2.21"


ROOTS = {
    "Справочник": "Catalog",
    "Документ": "Document",
    "ЖурналДокументов": "DocumentJournal",
    "Перечисление": "Enum",
    "Отчет": "Report",
    "Обработка": "DataProcessor",
    "Константа": "Constant",
    "ПланВидовХарактеристик": "ChartOfCharacteristicTypes",
    "ПланСчетов": "ChartOfAccounts",
    "ПланВидовРасчета": "ChartOfCalculationTypes",
    "ПланОбмена": "ExchangePlan",
    "БизнесПроцесс": "BusinessProcess",
    "Задача": "Task",
    "РегистрСведений": "InformationRegister",
    "РегистрНакопления": "AccumulationRegister",
    "РегистрБухгалтерии": "AccountingRegister",
    "РегистрРасчета": "CalculationRegister",
    "Последовательность": "Sequence",
    "Перерасчет": "Recalculation",
    # Определяемый тип грани не имеет: он сам раскрывается в набор типов.
    # Записывается как `cfg:DefinedType.Имя` — 95 подписок из 639.
    "ОпределяемыйТип": "DefinedType",
    # Ещё два вида без грани, встречаются в типах реквизитов: «любая ссылка»
    # (25 раз, имени не имеет) и характеристика плана видов характеристик
    # (306 раз, имя — сам план). Отдельного механизма не требуют: грань пуста,
    # имя ставится там же, где у определяемого типа.
    "ЛюбаяСсылка": "AnyIBRef",
    "Характеристика": "Characteristic",
    # Ещё три обозначения без грани, редкие, но настоящие: точка маршрута
    # бизнес-процесса (бывает и с именем, и без), построитель отчёта и набор
    # констант. Механизм тот же.
    "ТочкаМаршрутаБизнесПроцесса": "BusinessProcessRoutePointRef",
    "ПостроительОтчета": "ReportBuilder",
    "НаборКонстант": "ConstantsSet",
}


# Грань участия → хвост обозначения. Склейка ROOTS[вид] + FACETS[грань] покрывает
# все 26 обозначений, встреченных в конфигурации, без единого исключения.
FACETS = {
    "Объект": "Object",
    "Менеджер": "Manager",
    "НаборЗаписей": "RecordSet",
    "МенеджерЗначения": "ValueManager",
    # Грань менеджера записи: главный реквизит формы записи регистра
    # сведений (`cfg:InformationRegisterRecordManager.X`, 512 форм).
    "МенеджерЗаписи": "RecordManager",
    # Грань ссылки: так тип записывают реквизиты (`cfg:CatalogRef.Контрагенты`).
    # У подписок она не встречается — там объект, менеджер или набор записей.
    "Ссылка": "Ref",
}


# Значения свойств-перечислений реквизита. Русские имена — как в конфигураторе;
# неизвестное значение перекладка не угадывает, а отвергает.
AUTO_USE_DONTUSE = {"Авто": "Auto", "Использовать": "Use", "НеИспользовать": "DontUse"}


USE_DONTUSE = {"Использовать": "Use", "НеИспользовать": "DontUse"}


FILL_CHECKING = {"НеПроверять": "DontCheck", "ВыдаватьОшибку": "ShowError"}


CHOICE_FOLDERS = {"Элементы": "Items", "Группы": "Folders",
               "ГруппыИЭлементы": "FoldersAndItems"}


USE_FOR = {"ДляЭлемента": "ForItem", "ДляГруппы": "ForFolder",
                 "ДляГруппыИЭлемента": "ForFolderAndItem"}


INDEXING = {"НеИндексировать": "DontIndex", "Индексировать": "Index",
                  "ИндексироватьСДопУпорядочиванием": "IndexWithAdditionalOrder"}


# Типы платформы без квалификаторов. Перечень снят по всем видам, у которых
# есть реквизиты: других в конфигурации не встречается.
PLATFORM_TYPES = {
    "ХранилищеЗначения": "v8:ValueStorage",
    "УникальныйИдентификатор": "v8:UUID",
    "СтандартныйПериод": "v8:StandardPeriod",
    "СписокЗначений": "v8:ValueListType",
    "ТаблицаЗначений": "v8:ValueTable",
    "ДеревоЗначений": "v8:ValueTree",
    "СтандартнаяДатаНачала": "v8:StandardBeginningDate",
}


# Типы из чужих пространств имён: пространство объявляется прямо на узле.
# Их ровно три на всю конфигурацию, и встречаются они только у реквизитов
# обработок и отчётов — там, где данные не хранятся в базе.
FOREIGN_NAMESPACES = {
    "КомпоновщикНастроек": ("dcsset",
                            "http://v8.1c.ru/8.1/data-composition-system/settings",
                            "SettingsComposer"),
    "ТабличныйДокумент": ("mxl", "http://v8.1c.ru/8.2/data/spreadsheet",
                          "SpreadsheetDocument"),
    "Диаграмма": ("d7p1", "http://v8.1c.ru/8.2/data/chart", "Chart"),
}


#: Обратная таблица (слово выгрузки -> слово показа): типы, которые в
#: выгрузке встречаются — у реквизитов форм, обработок,
#: отчётов, — а заданием не заводятся: показ называет их по-русски, как
#: платформа, а не тегом. Ключ — имя без приставки пространства: приставка
#: у одного и того же типа бывает разной (`d5p1:TextDocument`). Перечень —
#: по частоте в реквизитах форм корпуса (10 685 форм);
#: незнакомое печатается как записано.
READ_ONLY_TYPES_BACK = {
    "SpreadsheetDocument": "ТабличныйДокумент",
    "SettingsComposer": "КомпоновщикНастроек",
    "Chart": "Диаграмма",
    "FormattedString": "ФорматированнаяСтрока",
    "Color": "Цвет",
    "Font": "Шрифт",
    "Picture": "Картинка",
    "TypeDescription": "ОписаниеТипов",
    "TextDocument": "ТекстовыйДокумент",
    "FormattedDocument": "ФорматированныйДокумент",
    "FlowchartContextType": "ГрафическаяСхема",
    "PDFDocument": "PDFДокумент",
    "base64Binary": "ДвоичныеДанные",
    "Null": "Null",
    "ComparisonType": "ВидСравнения",
    "AccountType": "ВидСчета",
    "DataCompositionComparisonType": "ВидСравненияКомпоновкиДанных",
    "DataCompositionFieldPlacement": "РасположениеПоляКомпоновкиДанных",
    "DataCompositionGroupType": "ТипГруппировкиКомпоновкиДанных",
    "DataCompositionSortDirection": "НаправлениеСортировкиКомпоновкиДанных",
    "DataCompositionPeriodAdditionType": "ТипДополненияПериодаКомпоновкиДанных",
}


STRING_LENGTH = {"Переменная": "Variable", "Фиксированная": "Fixed"}


DATE_PARTS = {"Дата": "Date", "Время": "Time", "ДатаВремя": "DateTime"}


NUMBER_SIGN = {"Любой": "Any", "Неотрицательный": "Nonnegative"}


# Событие подписки: как называет разработчик → как записано в выгрузке.
EVENTS = {
    "ПередЗаписью": "BeforeWrite",
    "ПриЗаписи": "OnWrite",
    "ПередУдалением": "BeforeDelete",
    "ОбработкаЗаполнения": "Filling",
    "ОбработкаПроверкиЗаполнения": "FillCheckProcessing",
    "ОбработкаПроведения": "Posting",
    "ОбработкаУдаленияПроведения": "UndoPosting",
    "ПриКопировании": "OnCopy",
    "ПриУстановкеНовогоКода": "OnSetNewCode",
    "ПриУстановкеНовогоНомера": "OnSetNewNumber",
    "ПриПолученииДанныхОтГлавного": "OnReceiveDataFromMaster",
    "ПриПолученииДанныхОтПодчиненного": "OnReceiveDataFromSlave",
    "ПриОтправкеДанныхГлавному": "OnSendDataToMaster",
    "ПриОтправкеДанныхПодчиненному": "OnSendDataToSlave",
    "ПриОтправкеДанныхУзлаПодчиненному": "OnSendNodeDataToSlave",
    "ОбработкаПолученияФормы": "FormGetProcessing",
    "ОбработкаПолученияДанныхВыбора": "ChoiceDataGetProcessing",
    "ОбработкаПолученияПредставления": "PresentationGetProcessing",
    "ОбработкаПолученияПолейПредставления": "PresentationFieldsGetProcessing",
}


# Вид метаданных → каталог выгрузки, где лежат его карточки. Множественное число
# нерегулярно (ПланСчетов → ChartsOfAccounts), поэтому таблица, а не правило.
# Перерасчёта здесь нет намеренно: своего каталога у него нет, он лежит внутри
# регистра расчёта.
FOLDERS = {
    "Справочник": "Catalogs",
    "Документ": "Documents",
    "ЖурналДокументов": "DocumentJournals",
    "Перечисление": "Enums",
    "Отчет": "Reports",
    "Обработка": "DataProcessors",
    "Константа": "Constants",
    "ПланВидовХарактеристик": "ChartsOfCharacteristicTypes",
    "ПланСчетов": "ChartsOfAccounts",
    "ПланВидовРасчета": "ChartsOfCalculationTypes",
    "ПланОбмена": "ExchangePlans",
    "БизнесПроцесс": "BusinessProcesses",
    "Задача": "Tasks",
    "РегистрСведений": "InformationRegisters",
    "РегистрНакопления": "AccumulationRegisters",
    "РегистрБухгалтерии": "AccountingRegisters",
    "РегистрРасчета": "CalculationRegisters",
    "Последовательность": "Sequences",
    "ОпределяемыйТип": "DefinedTypes",
}


# Порядок групп в `<ChildObjects>` файла Configuration.xml. Снят с реальной
# выгрузки: там все 43 группы лежат сплошняком, ни одна не разорвана, —
# то есть это порядок, которым их пишет сам конфигуратор, а не чьё-то мнение.
# Нужен ровно для одного случая: объект заводится первым в своём виде, группы
# в файле ещё нет, и её надо поставить на положенное место, а не в конец.
GROUP_ORDER = (
    "Language", "Subsystem", "StyleItem", "CommonPicture",
    "SessionParameter", "Role", "CommonTemplate", "FilterCriterion",
    "CommonModule", "CommonAttribute", "ExchangePlan", "XDTOPackage",
    "WebService", "HTTPService", "WSReference", "EventSubscription",
    "ScheduledJob", "SettingsStorage", "FunctionalOption", "FunctionalOptionsParameter",
    "DefinedType", "CommonCommand", "CommandGroup", "Constant",
    "CommonForm", "Catalog", "Document", "DocumentNumerator",
    "Sequence", "DocumentJournal", "Enum", "Report",
    "DataProcessor", "InformationRegister", "AccumulationRegister",
    "ChartOfCharacteristicTypes", "ChartOfAccounts", "AccountingRegister",
    "ChartOfCalculationTypes", "BusinessProcess", "Task", "ExternalDataSource",
    "IntegrationService",
)


ROOTS_BACK = {v: k for k, v in ROOTS.items()}


#: Вложенные шаги обозначения объекта, когда оно стоит значением свойства:
#: основная схема отчёта записана как `Report.Имя.Template.Макет` — все 417
#: отчётов конфигурации в этой форме, других нет. Шаги нужны отдельно от
#: `SCHEMA`, потому что макет своим объектом не заводится, а в обозначении
#: участвует.
NESTED_ROOTS = {
    "Макет": "Template",
    "Форма": "Form",
    "Реквизит": "Attribute",
    "ТабличнаяЧасть": "TabularSection",
    "Команда": "Command",
}


#: Сущности, в которых стоят ссылки, но своим видом инструмент их не заводит:
#: слово адреса -> теги выгрузки. Нужны отказу в удалении — назвать место
#: ссылки, а не одного держателя. Слова — имена синтакс-помощника:
#: «ОбъектМетаданных: Графа», «ОбъектМетаданных: РеквизитАдресации»; в схеме
#: компоновки — поле набора данных, вычисляемое поле и элемент объединения:
#: `Элементы` у набора-объединения — тоже наборы данных, только тег у них
#: `item`, а не `dataSet`. Остальные слова дают `SCHEMA` и `NESTED_ROOTS`.
#: Замер мест ссылок по выгрузке: графы журналов — 2392, реквизиты адресации —
#: 21; в 925 схемах — поля наборов 1702, вычисляемые поля 14 (параметров 6379,
#: их слово — из `SCHEMA`).
MEMBER_TAGS = {
    "Графа": ("Column",),
    "РеквизитАдресации": ("AddressingAttribute",),
    "Поле": ("field",),
    "ВычисляемоеПоле": ("calculatedField",),
    "НаборДанных": ("item",),
}


FACETS_BACK =sorted(((v, k) for k, v in FACETS.items()), key=lambda p: -len(p[0]))


EVENTS_BACK = {v: k for k, v in EVENTS.items()}


# Порядок свойств реквизита одинаков у всех тринадцати видов-хозяев, кроме
# одного: у плана видов характеристик «использование» стоит после
# индексирования. Отклонение единственное, поэтому таблица перестановок,
# а не отдельный порядок на каждый вид.
REORDER = {"ПланВидовХарактеристик": ("использование", "полнотекстовыйПоиск")}


# Порядок квалификаторов внутри узла `<Type>`. Значим только у составного типа,
# где их бывает несколько; отклонений от этой последовательности в конфигурации
# нет ни одного (15 узлов с двумя и тремя квалификаторами).
QUALIFIER_ORDER = ("v8:NumberQualifiers", "v8:StringQualifiers",
                          "v8:DateQualifiers")

# --- прикладные объекты -----------------------------------------------------

# Порождаемые типы: платформа заводит их для каждого прикладного объекта.
# Набор и порядок сняты с конфигурации — по одному варианту на вид, без исключений
# (1184 справочника, 1809 регистров сведений, 1627 перечислений).
# Идентификаторы к ним инструмент порождает сам: на пустой базе платформа
# принимает их без изменений.
GENERATED_TYPES = {
    # Отчёт: объект и менеджер. Табличные части добавляют свои —
    # их пишет сам вид «ТабличнаяЧасть».
    "Отчет": (("ReportObject", "Object"), ("ReportManager", "Manager")),
    # У обработки те же две грани, что у отчёта: объект и менеджер.
    # Замерено по 613 карточкам — иных наборов нет, а различия между
    # ними дают только табличные части, которые добавляются сами.
    "Обработка": (("DataProcessorObject", "Object"),
                  ("DataProcessorManager", "Manager")),
    # Константа. Три грани у всех 905 карточек, иных наборов нет.
    "Константа": (("ConstantManager", "Manager"),
                  ("ConstantValueManager", "ValueManager"),
                  ("ConstantValueKey", "ValueKey")),
    # Определяемый тип. Одна грань у всех 552 карточек.
    "ОпределяемыйТип": (("DefinedType", "DefinedType"),),
    # Регистр накопления. Шесть граней у всех 173 карточек.
    "РегистрНакопления": (
        ("AccumulationRegisterRecord", "Record"),
        ("AccumulationRegisterManager", "Manager"),
        ("AccumulationRegisterSelection", "Selection"),
        ("AccumulationRegisterList", "List"),
        ("AccumulationRegisterRecordSet", "RecordSet"),
        ("AccumulationRegisterRecordKey", "RecordKey")),
    "Справочник": (("CatalogObject", "Object"), ("CatalogRef", "Ref"),
                   ("CatalogSelection", "Selection"), ("CatalogList", "List"),
                   ("CatalogManager", "Manager")),
    "Документ": (("DocumentObject", "Object"), ("DocumentRef", "Ref"),
                 ("DocumentSelection", "Selection"), ("DocumentList", "List"),
                 ("DocumentManager", "Manager")),
    "РегистрСведений": (
        ("InformationRegisterRecord", "Record"),
        ("InformationRegisterManager", "Manager"),
        ("InformationRegisterSelection", "Selection"),
        ("InformationRegisterList", "List"),
        ("InformationRegisterRecordSet", "RecordSet"),
        ("InformationRegisterRecordKey", "RecordKey"),
        ("InformationRegisterRecordManager", "RecordManager")),
    "Перечисление": (("EnumRef", "Ref"), ("EnumManager", "Manager"),
                     ("EnumList", "List")),
}

# Значения свойств прикладных объектов. Как и остальные словари — снято
# с конфигурации; значения, которых там нет, платформа знает, но инструмент
# их не выдумывает: неизвестное имя перекладка отвергает.
HIERARCHY_TYPE = {"ГруппыИЭлементы": "HierarchyFoldersAndItems",
                  "Элементы": "HierarchyOfItems"}
SUBORDINATION = {"Элементам": "ToItems"}
CODE_TYPE = {"Строка": "String", "Число": "Number"}
CODE_SERIES = {"ВесьСправочник": "WholeCatalog",
               "ВПределахПодчинения": "WithinSubordination",
               "ВПределахПодчиненияВладельцу": "WithinOwnerSubordination"}
CATALOG_PRESENTATION = {"ВВидеНаименования": "AsDescription", "ВВидеКода": "AsCode"}
PREDEFINED_UPDATE = {"Авто": "Auto", "ОбновлятьАвтоматически": "AutoUpdate",
                     "НеОбновлятьАвтоматически": "DontAutoUpdate"}
EDIT_TYPE = {"ВДиалоге": "InDialog", "ВСписке": "InList",
             "ОбоимиСпособами": "BothWays"}
CHOICE_MODE = {"ОбоимиСпособами": "BothWays", "БыстрыйВыбор": "QuickChoice",
               "ИзФормы": "FromForm"}
SEARCH_MODE = {"Начало": "Begin", "ЛюбаяЧасть": "AnyPart"}
CHOICE_DATA_MODE = {"Непосредственно": "Directly"}
LOCK_MODE = {"Управляемый": "Managed", "Автоматический": "Automatic"}
# Периодичность регистра сведений. Замерено по 1809 регистрам конфигурации:
# Nonperiodical 1438, Day 114, Second 91, RecorderPosition 78, Month 57,
# Year 21, Quarter 10.
#
# Значения пишутся без приставки `Per`: `PerDay`, `PerMonth` и подобных в
# выгрузке нет ни одного, и платформа отвергает загрузку словами «Неверное
# значение перечисления - PerDay». Непериодический регистр — умолчание, им
# создают чаще всего, поэтому ошибку в остальных значениях ловит только круг
# через платформу, а не корпусные сверки.
#: Вид регистра накопления. По корпусу они расходятся ровно пополам —
#: обороты 89, остатки 84, — и это не мелочь: перепутать значит
#: спроектировать другой регистр. Поэтому поле обязательное, хотя
#: у конфигуратора умолчание есть (остатки).
REGISTER_KIND = {"Остатки": "Balance", "Обороты": "Turnovers"}

REGISTER_PERIODICITY = {"Непериодический": "Nonperiodical",
                        "ВПределахСекунды": "Second",
                        "ВПределахДня": "Day",
                        "ВПределахМесяца": "Month",
                        "ВПределахКвартала": "Quarter",
                        "ВПределахГода": "Year",
                        "ПоПозицииРегистратора": "RecorderPosition"}
REGISTER_WRITE_MODE = {"Независимо": "Independent",
                       "ПодчинениеРегистратору": "RecorderSubordinate"}

# Значения свойств документа. Как обычно — снято с 634 документов конфигурации;
# значения платформы, которых там нет, не выдумываются.
NUMBER_PERIODICITY = {"Непериодический": "Nonperiodical", "ВПределахГода": "Year",
                      "ВПределахДня": "Day"}
POSTING = {"Разрешить": "Allow", "Запретить": "Deny"}
RECORDS_DELETION = {"УдалятьАвтоматическиПриОтмене": "AutoDeleteOnUnpost",
                    "НеУдалятьАвтоматически": "AutoDeleteOff",
                    "УдалятьАвтоматически": "AutoDelete"}
RECORDS_WRITING = {"ЗаписыватьВыбранные": "WriteSelected",
                   "ЗаписыватьМодифицированные": "WriteModified"}
SEQUENCE_FILLING = {"ЗаполнятьАвтоматически": "AutoFill",
                    "НеЗаполнятьАвтоматически": "AutoFillOff"}

# Приведение типа у измерения: что делать с данными, не влезающими в новый тип.
TYPE_REDUCTION = {"ПреобразовыватьЗначения": "TransformValues",
                  "УдалятьДанные": "DeleteData"}

# Цвет значения перечисления. В конфигурации он у всех 11 629 значений один
# и тот же — платформа пишет «auto», пока цвет не назначили руками.
COLOR = {"Авто": "auto"}

# Порядок групп внутри `<ChildObjects>` карточки объекта. Ключ — каталог
# выгрузки: таблица покрывает и виды, которых домен не знает вовсе.
#
# Таблиц три, потому что вопрос «в каком порядке идут дети» задаётся трём
# разным сущностям: карточке объекта (`CARD_ORDER`), документу целиком
# (`DOCUMENT_ORDER` — схема компоновки) и контейнеру внутри документа
# (`CONTAINER_ORDER` — разделы настроек). Ключи у них из разных словарей —
# каталог, корень документа, тег элемента — и в одном словаре различались
# только тем, что искать полагалось в известном порядке.
#
# Не соглашение и не большинство, а требование платформы: карточка, записанная
# с переставленными группами, после загрузки в базу и обратной выгрузки
# возвращается в этот порядок. Свод по 7179 карточкам корпуса даёт его без
# единого противоречия — наблюдаемые «разные варианты» оказываются
# подмножествами одного общего порядка, а не разбросом.
#
# Порядок разный у разных видов, и это не описка: у документа формы идут между
# реквизитами и табличными частями, у справочника — после них; у регистра
# бухгалтерии измерения впереди ресурсов, у регистра сведений — наоборот.
CARD_ORDER = {
    "AccountingRegisters": ("Dimension", "Resource", "Attribute", "Form"),   # карточек 7
    "AccumulationRegisters": ("Resource", "Attribute", "Dimension", "Form", "Command", "Template"),   # карточек 173
    "BusinessProcesses": ("Attribute", "TabularSection", "Form"),   # карточек 10
    "Catalogs": ("Attribute", "TabularSection", "Form", "Template", "Command"),   # карточек 1150
    "ChartsOfAccounts": ("Attribute", "AccountingFlag", "ExtDimensionAccountingFlag", "Form", "Template", "Command"),   # карточек 7
    "ChartsOfCalculationTypes": ("Attribute", "TabularSection", "Form"),   # карточек 3
    "ChartsOfCharacteristicTypes": ("Attribute", "TabularSection", "Form", "Template"),   # карточек 22
    "DataProcessors": ("Attribute", "TabularSection", "Form", "Template", "Command"),   # карточек 571
    "DocumentJournals": ("Column", "Form", "Template", "Command"),   # карточек 46
    "Documents": ("Attribute", "Form", "TabularSection", "Template", "Command"),   # карточек 633
    "Enums": ("EnumValue", "Template", "Form"),   # карточек 1625
    "ExchangePlans": ("Attribute", "TabularSection", "Form", "Template", "Command"),   # карточек 38
    "ExternalDataSources": ("Table", "Cube"),   # карточек 6
    "FilterCriteria": ("Form",),   # карточек 1
    "HTTPServices": ("URLTemplate",),   # карточек 22
    # Читается как описка — ресурсы и реквизиты впереди измерений, — но
    # это замер: 1809 карточек, 12 различных соседств, ни одного против
    # этого порядка. «Resource → Attribute» встречается 507 раз,
    # «Attribute → Dimension» 620; обратных нет вовсе.
    "InformationRegisters": ("Resource", "Attribute", "Dimension", "Form", "Template", "Command"),   # карточек 1809
    "IntegrationServices": ("IntegrationServiceChannel",),   # карточек 1
    "Reports": ("Attribute", "TabularSection", "Form", "Template", "Command"),   # карточек 956
    "Sequences": ("Dimension",),   # карточек 6
    "SettingsStorages": ("Form",),   # карточек 5
    "Subsystems": ("Subsystem",),   # карточек 65
    "Tasks": ("Attribute", "TabularSection", "Form", "Template", "AddressingAttribute", "Command"),   # карточек 2
    "WebServices": ("Operation",),   # карточек 25
}

# Права ролей: русское имя -> имя в файле прав.
#
# Не выписаны по памяти, а сняты со статьи «Глобальный контекст.ПравоДоступа»
# синтакс-помощника — это единственный источник, где обе стороны названы рядом.
# Таблица покрывает все 69 прав, встречающихся в 2709 ролях замеренной
# конфигурации; одно право из статьи там не встречается.
#
# `Automation` — единственный ключ латиницей, и это не описка: платформа так
# и называет право по-русски.
RIGHTS = {
    "АктивныеПользователи": "ActiveUsers",
    "Администрирование": "Administration",
    "РежимВсеФункции": "AllFunctionsMode",
    "КлиентСистемыАналитики": "AnalyticsSystemClient",
    "Automation": "Automation",
    "РегистрацияИнформационнойБазыСистемыВзаимодействия": "CollaborationSystemInfoBaseRegistration",
    "АдминистрированиеРасширенийКонфигурации": "ConfigurationExtensionsAdministration",
    "АдминистрированиеДанных": "DataAdministration",
    "Удаление": "Delete",
    "Редактирование": "Edit",
    "РедактированиеКомментарияВерсииИсторииДанных": "EditDataHistoryVersionComment",
    "ЖурналРегистрации": "EventLog",
    "МонопольныйРежим": "ExclusiveMode",
    "ЗавершениеМонопольногоРежимаПриНачалеСеанса": "ExclusiveModeTerminationAtSessionStart",
    "Выполнение": "Execute",
    "ВнешнееСоединение": "ExternalConnection",
    "Получение": "Get",
    "ВводПоСтроке": "InputByString",
    "Добавление": "Insert",
    "ИнтерактивнаяАктивация": "InteractiveActivate",
    "ИнтерактивноеИзменениеПроведенных": "InteractiveChangeOfPosted",
    "ИнтерактивноеСнятиеПометкиУдаления": "InteractiveClearDeletionMark",
    "ИнтерактивноеСнятиеПометкиУдаленияПредопределенныхДанных": "InteractiveClearDeletionMarkPredefinedData",
    "ИнтерактивноеУдаление": "InteractiveDelete",
    "ИнтерактивноеУдалениеПомеченных": "InteractiveDeleteMarked",
    "ИнтерактивноеУдалениеПомеченныхПредопределенныхДанных": "InteractiveDeleteMarkedPredefinedData",
    "ИнтерактивноеУдалениеПредопределенныхДанных": "InteractiveDeletePredefinedData",
    "ИнтерактивноеВыполнение": "InteractiveExecute",
    "ИнтерактивноеДобавление": "InteractiveInsert",
    "ИнтерактивноеОткрытиеВнешнихОбработок": "InteractiveOpenExtDataProcessors",
    "ИнтерактивноеОткрытиеВнешнихОтчетов": "InteractiveOpenExtReports",
    "ИнтерактивноеПроведение": "InteractivePosting",
    "ИнтерактивноеПроведениеНеОперативное": "InteractivePostingRegular",
    "ИнтерактивнаяПометкаУдаления": "InteractiveSetDeletionMark",
    "ИнтерактивнаяПометкаУдаленияПредопределенныхДанных": "InteractiveSetDeletionMarkPredefinedData",
    "ИнтерактивныйСтарт": "InteractiveStart",
    "ИнтерактивнаяОтменаПроведения": "InteractiveUndoPosting",
    "РежимОсновногоОкнаВстроенноеРабочееМесто": "MainWindowModeEmbeddedWorkplace",
    "РежимОсновногоОкнаПолноэкранноеРабочееМесто": "MainWindowModeFullscreenWorkplace",
    "РежимОсновногоОкнаКиоск": "MainWindowModeKiosk",
    "РежимОсновногоОкнаОбычный": "MainWindowModeNormal",
    "РежимОсновногоОкнаРабочееМесто": "MainWindowModeWorkplace",
    "МобильныйКлиент": "MobileClient",
    "Вывод": "Output",
    "Проведение": "Posting",
    "Чтение": "Read",
    "ЧтениеИсторииДанных": "ReadDataHistory",
    "ЧтениеИсторииДанныхОтсутствующихДанных": "ReadDataHistoryOfMissingData",
    "СохранениеДанныхПользователя": "SaveUserData",
    "ИзменениеАутентификацииОССеанса": "SessionOSAuthenticationChange",
    "ИзменениеСтандартнойАутентификацииСеанса": "SessionStandardAuthenticationChange",
    "Установка": "Set",
    "ИзменениеСтандартнойАутентификации": "StandardAuthenticationChange",
    "Старт": "Start",
    "ПереходНаВерсиюИсторииДанных": "SwitchToDataHistoryVersion",
    "РежимТехническогоСпециалиста": "TechnicalSpecialistMode",
    "ТолстыйКлиент": "ThickClient",
    "ТонкийКлиент": "ThinClient",
    "УправлениеИтогами": "TotalsControl",
    "ОтменаПроведения": "UndoPosting",
    "Изменение": "Update",
    "ОбновлениеКонфигурацииБазыДанных": "UpdateDataBaseConfiguration",
    "ИзменениеИсторииДанных": "UpdateDataHistory",
    "ИзменениеИсторииДанныхОтсутствующихДанных": "UpdateDataHistoryOfMissingData",
    "ИзменениеНастроекИсторииДанных": "UpdateDataHistorySettings",
    "ИзменениеКомментарияВерсииИсторииДанных": "UpdateDataHistoryVersionComment",
    "Использование": "Use",
    "Просмотр": "View",
    "ПросмотрИсторииДанных": "ViewDataHistory",
    "ВебКлиент": "WebClient",
}

# Порядок прав внутри `<object>` файла прав. Канонический: платформа
# переставляет права в него при загрузке, а свод по 9984 блокам прав из 500
# ролей даёт его топологической сортировкой без единого цикла — все
# последовательности корпуса в него укладываются.
#
# Порядок из статьи синтакс-помощника не годится: в блоке истории данных он
# другой (`ViewDataHistory` там раньше, а в файле — позже). Права, которые
# в корпусе не встречаются, дописываются в конец в порядке статьи.
RIGHTS_ORDER = (
    "Read", "Insert", "Update", "Delete", "Use", "Get", "Set", "Administration",
    "DataAdministration", "UpdateDataBaseConfiguration", "ExclusiveMode",
    "ActiveUsers", "EventLog", "ThinClient", "WebClient", "ThickClient",
    "ExternalConnection", "Automation", "TechnicalSpecialistMode",
    "CollaborationSystemInfoBaseRegistration", "MainWindowModeNormal",
    "MainWindowModeWorkplace", "MainWindowModeEmbeddedWorkplace",
    "MainWindowModeFullscreenWorkplace", "MainWindowModeKiosk",
    "AnalyticsSystemClient", "SaveUserData", "ConfigurationExtensionsAdministration",
    "Output", "Posting", "UndoPosting", "View", "InteractiveInsert", "Edit",
    "TotalsControl", "InteractiveDelete", "InteractiveSetDeletionMark",
    "InteractiveClearDeletionMark", "InteractiveDeleteMarked", "InteractivePosting",
    "InteractivePostingRegular", "InteractiveUndoPosting",
    "InteractiveChangeOfPosted", "InputByString", "ReadDataHistory",
    "ReadDataHistoryOfMissingData", "UpdateDataHistory",
    "UpdateDataHistoryOfMissingData", "UpdateDataHistorySettings",
    "UpdateDataHistoryVersionComment", "ViewDataHistory",
    "EditDataHistoryVersionComment", "SwitchToDataHistoryVersion",
    "InteractiveActivate", "Start", "InteractiveStart",
)

# Виды, на которые права вообще выдаются. Снято по всем 2709 ролям: три
# миллиона записей, 27 корней. Общего модуля среди них нет ни разу — и это
# не мелочь: право на общий модуль подвешивает загрузку конфигурации намертво,
# платформа не сообщает об ошибке, а уходит в бесконечный цикл.
RIGHTS_HOSTS = frozenset({
    "Document", "Catalog", "InformationRegister", "DataProcessor",
    "AccumulationRegister", "Report", "ExternalDataSource", "ExchangePlan",
    "BusinessProcess", "ChartOfCharacteristicTypes", "DocumentJournal",
    "Constant", "AccountingRegister", "ChartOfAccounts", "CommonCommand",
    "ChartOfCalculationTypes", "Subsystem", "Configuration", "CommonForm",
    "Task", "SessionParameter", "WebService", "HTTPService", "FilterCriterion",
    "Sequence", "CommonAttribute", "IntegrationService",
})

# Отображение кнопки — системное перечисление `ОтображениеКнопки`
# (ButtonRepresentation) синтакс-помощника; статья прямо называет его свойством
# общей команды. Режим использования параметра — `РежимИспользованияПараметраКоманды`
# (CommandParameterUseMode) оттуда же. Не по памяти: русские имена значений
# нигде в выгрузке не встречаются, в файлах только английские.
BUTTON_REPRESENTATION = {"Авто": "Auto", "Картинка": "Picture",
                         "КартинкаИТекст": "PictureAndText", "Текст": "Text"}
PARAMETER_USE_MODE = {"Одиночный": "Single", "Множественный": "Multiple"}

# Поведение при недоступности главного сервера. В корпусе одно значение
# на все 705 общих команд — второе там не встречается, и инструмент его не
# выдумывает.
MAIN_SERVER_UNAVAILABLE = {"Авто": "Auto"}

# Порядок детей внутри документа целиком. Ключ — корень документа, а не
# каталог выгрузки: схема компоновки живёт в макете и своего каталога не имеет.
# Снято по 901 схеме корпуса той же топологической сортировкой, что
# и порядок групп в карточке, — без единого противоречия.
DOCUMENT_ORDER = {
    "DataCompositionSchema": (
        "dataSource", "dataSet", "dataSetLink", "calculatedField", "totalField",
        "parameter", "nestedSchema", "template", "fieldTemplate",
        "groupTemplate", "groupHeaderTemplate", "totalFieldsTemplate",
        "settingsVariant"),
}

# Пространства имён схемы компоновки данных. Набор один и тот же на всех
# 901 схеме корпуса — ни одного исключения, поэтому таблица, а не догадка.
SCHEMA_NAMESPACES = (
    ("", "http://v8.1c.ru/8.1/data-composition-system/schema"),
    ("dcscom", "http://v8.1c.ru/8.1/data-composition-system/common"),
    ("dcscor", "http://v8.1c.ru/8.1/data-composition-system/core"),
    ("dcsset", "http://v8.1c.ru/8.1/data-composition-system/settings"),
    ("v8", "http://v8.1c.ru/8.1/data/core"),
    ("v8ui", "http://v8.1c.ru/8.1/data/ui"),
    ("xs", "http://www.w3.org/2001/XMLSchema"),
    ("xsi", "http://www.w3.org/2001/XMLSchema-instance"),
)

# `<dcsset:settings>` несёт ещё пять объявлений — тоже у всех 901 схемы.
SETTINGS_NAMESPACES = (
    ("pal", "http://v8.1c.ru/8.1/data/ui/colors/palette"),
    ("style", "http://v8.1c.ru/8.1/data/ui/style"),
    ("sys", "http://v8.1c.ru/8.1/data/ui/fonts/system"),
    ("web", "http://v8.1c.ru/8.1/data/ui/colors/web"),
    ("win", "http://v8.1c.ru/8.1/data/ui/colors/windows"),
)

# Порядок внутри настроек варианта и внутри каждого контейнера настроек.
# Снято по 901 схеме: у самих настроек порядок разделов, у контейнеров —
# пункты первыми, служебные хвосты после. Ключ — имя элемента без префикса.
# Вариант настроек: имя, представление, настройки — 1369 вариантов, одна форма.
CONTAINER_ORDER = {
    "settingsVariant": ("name", "presentation", "settings"),
    "settings": (
        "userFields", "selection", "filter", "dataParameters", "order",
        "conditionalAppearance", "outputParameters", "item",
        "additionalProperties", "itemsViewMode", "userSettingID",
        "itemsUserSettingID"),
}
for _контейнер in ("selection", "filter", "order", "conditionalAppearance",
                   "dataParameters", "outputParameters", "appearance",
                   "groupItems", "userFields"):
    CONTAINER_ORDER[_контейнер] = ("item", "viewMode", "userSettingID",
                                   "userSettingPresentation")
del _контейнер

# Виды, чьё русское имя служит обозначением в языке запросов. Замерено по
# 926 схемам компоновки реальной выгрузки: «Справочник.» встречается в 515,
# «Перечисление.» в 429, «РегистрСведений.» в 387, «Документ.» в 230.
# Остальные виды, которые заводит инструмент (отчёт, роль, общий модуль,
# подписка, регламентное задание, общая команда), источником запроса не бывают.
QUERY_DESIGNATION = ("Справочник", "Документ", "Перечисление", "РегистрСведений")

# Направление сортировки в настройках компоновки.
ORDER_DIRECTION = {"Возрастание": "Asc", "Убывание": "Desc"}

# Значение, у которого платформа объявляет тип: правый операнд отбора несёт
# `xsi:type` по тому, что в нём лежит. Замерено на 6318 отборах: строка,
# число, булево, поле, список значений и «значение времени разработки».
TYPED_VALUE = "значениеСТипом"

#: Значение-обозначение объекта метаданных: основная схема отчёта и прочие
#: ссылки на объекты из свойств. Задание пишет по-русски, в файл идёт форма
#: платформы.
OBJECT_REFERENCE = "обозначениеОбъекта"

XSI_BY_PYTHON = {bool: "xs:boolean", int: "xs:decimal", float: "xs:decimal",
                 str: "xs:string"}

# Вид сравнения в отборе компоновки. Обе половины замерены по реальной выгрузке:
# английские значения — 9991 отбор в 1472 файлах (19 различных), русские имена —
# 11 703 употребления `ВидСравненияКомпоновкиДанных.*` в модулях (20 различных).
# Пары — перевод имя в имя; в XML нет только `NotLike`, в модулях он есть.
COMPARISON = {
    "Равно": "Equal",                   "НеРавно": "NotEqual",
    "Больше": "Greater",                "БольшеИлиРавно": "GreaterOrEqual",
    "Меньше": "Less",                   "МеньшеИлиРавно": "LessOrEqual",
    "ВСписке": "InList",                "НеВСписке": "NotInList",
    "ВИерархии": "InHierarchy",         "НеВИерархии": "NotInHierarchy",
    "ВСпискеПоИерархии": "InListByHierarchy",
    "НеВСпискеПоИерархии": "NotInListByHierarchy",
    "Содержит": "Contains",             "НеСодержит": "NotContains",
    "НачинаетсяС": "BeginsWith",        "НеНачинаетсяС": "NotBeginsWith",
    "Подобно": "Like",                  "НеПодобно": "NotLike",
    "Заполнено": "Filled",              "НеЗаполнено": "NotFilled",
}
