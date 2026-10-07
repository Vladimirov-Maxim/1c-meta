"""Раскладка выгрузки конфигуратора: что где лежит — для проверки правок.

Знание формата, а не домена: карточка объекта — `<Каталог>/<Имя>.xml`,
модуль — `.bsl`, служебный `ConfigDumpInfo.xml` пересобирает платформа, права
роли — `Roles/<Роль>/Ext/Rights.xml`, а объект в них назван словом вида
выгрузки (`Catalog.Имя`). У проекта EDT раскладка другая — другой модуль рядом.
"""

import re

#: Каталог выгрузки -> (вид по-русски, слово вида в Configuration.xml и в
#: правах ролей). Все каталоги объектов, кроме языков: язык — не доработка
#: команды, и приставки у него не бывает.
OBJECT_FOLDERS = {
    "AccountingRegisters": ("РегистрБухгалтерии", "AccountingRegister"),
    "AccumulationRegisters": ("РегистрНакопления", "AccumulationRegister"),
    "BusinessProcesses": ("БизнесПроцесс", "BusinessProcess"),
    "CalculationRegisters": ("РегистрРасчета", "CalculationRegister"),
    "Catalogs": ("Справочник", "Catalog"),
    "ChartsOfAccounts": ("ПланСчетов", "ChartOfAccounts"),
    "ChartsOfCalculationTypes": ("ПланВидовРасчета", "ChartOfCalculationTypes"),
    "ChartsOfCharacteristicTypes": ("ПланВидовХарактеристик", "ChartOfCharacteristicTypes"),
    "CommandGroups": ("ГруппаКоманд", "CommandGroup"),
    "CommonAttributes": ("ОбщийРеквизит", "CommonAttribute"),
    "CommonCommands": ("ОбщаяКоманда", "CommonCommand"),
    "CommonForms": ("ОбщаяФорма", "CommonForm"),
    "CommonModules": ("ОбщийМодуль", "CommonModule"),
    "CommonPictures": ("ОбщаяКартинка", "CommonPicture"),
    "CommonTemplates": ("ОбщийМакет", "CommonTemplate"),
    "Constants": ("Константа", "Constant"),
    "DataProcessors": ("Обработка", "DataProcessor"),
    "DefinedTypes": ("ОпределяемыйТип", "DefinedType"),
    "DocumentJournals": ("ЖурналДокументов", "DocumentJournal"),
    "DocumentNumerators": ("НумераторДокументов", "DocumentNumerator"),
    "Documents": ("Документ", "Document"),
    "Enums": ("Перечисление", "Enum"),
    "EventSubscriptions": ("ПодпискаНаСобытие", "EventSubscription"),
    "ExchangePlans": ("ПланОбмена", "ExchangePlan"),
    "ExternalDataSources": ("ВнешнийИсточникДанных", "ExternalDataSource"),
    "FilterCriteria": ("КритерийОтбора", "FilterCriterion"),
    "FunctionalOptions": ("ФункциональнаяОпция", "FunctionalOption"),
    "FunctionalOptionsParameters": ("ПараметрФункциональныхОпций", "FunctionalOptionsParameter"),
    "HTTPServices": ("HTTPСервис", "HTTPService"),
    "InformationRegisters": ("РегистрСведений", "InformationRegister"),
    "IntegrationServices": ("СервисИнтеграции", "IntegrationService"),
    "Reports": ("Отчет", "Report"),
    "Roles": ("Роль", "Role"),
    "ScheduledJobs": ("РегламентноеЗадание", "ScheduledJob"),
    "Sequences": ("Последовательность", "Sequence"),
    "SessionParameters": ("ПараметрСеанса", "SessionParameter"),
    "SettingsStorages": ("ХранилищеНастроек", "SettingsStorage"),
    "StyleItems": ("ЭлементСтиля", "StyleItem"),
    "Subsystems": ("Подсистема", "Subsystem"),
    "Tasks": ("Задача", "Task"),
    "WebServices": ("WebСервис", "WebService"),
    "WSReferences": ("WSСсылка", "WSReference"),
    "XDTOPackages": ("ПакетXDTO", "XDTOPackage"),
}

#: Вид по-русски -> каталог и слово вида в правах роли.
FOLDER_OF = {вид: каталог for каталог, (вид, _) in OBJECT_FOLDERS.items()}
RIGHTS_WORD = {вид: слово for _, (вид, слово) in OBJECT_FOLDERS.items()}

#: Карточка объекта верхнего уровня: `Catalogs/Имя.xml`.
CARD = re.compile(r"^([A-Za-z]+)/([^/]+)\.xml$")

#: Файлы, которые пересобирает платформа: в изменениях задачи их быть не должно.
SERVICE_FILES = ("ConfigDumpInfo.xml",)

#: Текстовые файлы выгрузки: у них проверяются BOM, переводы строк и пробелы.
TEXT_SUFFIXES = (".bsl", ".xml", ".txt", ".mdo")
MODULE_SUFFIX = ".bsl"

#: Права роли и объект в них: `<object><name>Catalog.Имя</name>…`.
RIGHTS_FOLDER = "Roles"
RIGHTS_FILE = re.compile(r"^Roles/([^/]+)/Ext/Rights\.xml$")


def object_of(path):
    """(вид, имя) карточки объекта верхнего уровня; иначе None."""
    found = CARD.match(path)
    if found is None or found.group(1) not in OBJECT_FOLDERS:
        return None
    return OBJECT_FOLDERS[found.group(1)][0], found.group(2)


def owner_of(path):
    """(вид, имя) объекта, которому принадлежит файл: карточка `Catalogs/Имя.xml`
    и всё внутри `Catalogs/Имя/` — модули, формы, макеты, права роли; иначе None."""
    части = path.split("/")
    if len(части) < 2 or части[0] not in OBJECT_FOLDERS:
        return None
    if len(части) == 2:
        return object_of(path)
    return OBJECT_FOLDERS[части[0]][0], части[1]


def card_path(вид, имя):
    """Путь карточки объекта от корня выгрузки; вид без каталога — None."""
    каталог = FOLDER_OF.get(вид)
    return f"{каталог}/{имя}.xml" if каталог else None


def is_service(path):
    return path.rsplit("/", 1)[-1] in SERVICE_FILES


def is_text(path):
    return path.lower().endswith(TEXT_SUFFIXES)


def is_module(path):
    return path.lower().endswith(MODULE_SUFFIX)


def rights_name(вид, имя):
    """Как объект назван в файле прав роли: `Catalog.Имя`."""
    return f"{RIGHTS_WORD[вид]}.{имя}"
