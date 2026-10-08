"""Раскладка исходников: что где лежит — для проверки правок.

Знание формата, а не домена. Форматов два, и различаются они раскладкой и
физическим видом текста:

| | выгрузка конфигуратора | проект EDT |
|---|---|---|
| карточка объекта | `<Каталог>/<Имя>.xml` | `<Каталог>/<Имя>/<Имя>.mdo` |
| модуль | `<Каталог>/<Имя>/Ext/<Файл>.bsl` | `<Каталог>/<Имя>/<Файл>.bsl` |
| права роли | `Roles/<Роль>/Ext/Rights.xml` | `Roles/<Роль>/Rights.rights` |
| служебный файл | `ConfigDumpInfo.xml` — пересобирает платформа | нет |
| признак корня | `Configuration.xml` | `Configuration/Configuration.mdo` |
| текст | UTF-8 с BOM | UTF-8 без BOM, LF |

Текст EDT замерен по проекту крупной типовой конфигурации: 23 вида текстовых
файлов, по 300 каждого, — ни одного BOM и ни одного CRLF. Объект в правах роли
назван одинаково в обоих форматах — словом вида (`Catalog.Имя`).
"""

import os
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
#: Карточка объекта в проекте EDT: `Catalogs/Имя/Имя.mdo`.
EDT_CARD = re.compile(r"^([A-Za-z]+)/([^/]+)/\2\.mdo$")

#: Файлы, которые пересобирает платформа: в изменениях задачи их быть не должно.
SERVICE_FILES = ("ConfigDumpInfo.xml",)

#: Текстовые файлы выгрузки: у них проверяются BOM, переводы строк и пробелы.
TEXT_SUFFIXES = (".bsl", ".xml", ".txt", ".mdo")
MODULE_SUFFIX = ".bsl"

#: Права роли и объект в них: `<object><name>Catalog.Имя</name>…`.
RIGHTS_FOLDER = "Roles"
RIGHTS_FILE = re.compile(r"^Roles/([^/]+)/Ext/Rights\.xml$")
EDT_RIGHTS_FILE = re.compile(r"^Roles/([^/]+)/Rights\.rights$")
#: Текстовые файлы проекта EDT — все виды, которые в нём встречаются как XML
#: или код; картинки, архивы и `.bin` в них не входят.
EDT_TEXT_SUFFIXES = (".bsl", ".mdo", ".form", ".rights", ".dcs", ".dcss", ".dcssca", ".dcsat",
                     ".mxlx", ".cmi", ".cai", ".hpwa", ".xdto", ".schedule", ".htmldoc", ".scheme",
                     ".chart", ".xml", ".txt")


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


class Layout:
    """Раскладка одного формата: всё, что проверке правок нужно знать о том,
    где что лежит. Выгрузка конфигуратора — сам модуль (функции выше), EDT —
    своя раскладка; общий у них только словарь каталогов."""

    #: имя формата — для ответов
    name = "выгрузка конфигуратора"
    #: BOM в текстовых файлах формата
    bom = True
    #: каталог прав ролей и шаблон пути файла прав: группа 1 — имя роли
    rights_file = RIGHTS_FILE
    #: проект EDT
    edt = False

    def object_of(self, path):
        return object_of(path)

    def owner_of(self, path):
        return owner_of(path)

    def card_path(self, вид, имя):
        return card_path(вид, имя)

    def is_service(self, path):
        return is_service(path)

    def is_text(self, path):
        return is_text(path)

    def is_module(self, path):
        return is_module(path)

    def rights_path(self, роль):
        return f"{RIGHTS_FOLDER}/{роль}/Ext/Rights.xml"

    def rights_name(self, вид, имя):
        return rights_name(вид, имя)

    def is_configuration(self, root):
        """Корень — исходники этого формата."""
        return os.path.isfile(os.path.join(root, "Configuration.xml"))


class EdtLayout(Layout):
    """Проект EDT: объект — каталог с карточкой `<Имя>.mdo` внутри."""

    name = "проект EDT"
    bom = False
    rights_file = EDT_RIGHTS_FILE
    edt = True

    def object_of(self, path):
        found = EDT_CARD.match(path)
        if found is None or found.group(1) not in OBJECT_FOLDERS:
            return None
        return OBJECT_FOLDERS[found.group(1)][0], found.group(2)

    def owner_of(self, path):
        части = path.split("/")
        if len(части) < 3 or части[0] not in OBJECT_FOLDERS:
            return None
        return OBJECT_FOLDERS[части[0]][0], части[1]

    def card_path(self, вид, имя):
        каталог = FOLDER_OF.get(вид)
        return f"{каталог}/{имя}/{имя}.mdo" if каталог else None

    def is_service(self, path):
        return False

    def is_text(self, path):
        return path.lower().endswith(EDT_TEXT_SUFFIXES)

    def rights_path(self, роль):
        return f"{RIGHTS_FOLDER}/{роль}/Rights.rights"

    def is_configuration(self, root):
        return os.path.isfile(os.path.join(root, "Configuration", "Configuration.mdo"))


DESIGNER = Layout()
EDT = EdtLayout()
LAYOUTS = (DESIGNER, EDT)


def layout_of(root, default=DESIGNER):
    """Раскладка исходников по их корню: `Configuration.xml` — выгрузка
    конфигуратора, `Configuration/Configuration.mdo` — проект EDT. Ни того ни
    другого (обработка вне конфигурации, пустой каталог) — `default`."""
    for раскладка in LAYOUTS:
        if раскладка.is_configuration(root):
            return раскладка
    return default
