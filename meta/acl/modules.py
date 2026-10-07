"""Адрес модуля -> путь файла в выгрузке конфигуратора.

Замер по выгрузке крупной типовой конфигурации: все 22 742 модуля ложатся ровно в пять
шаблонов, исключений ноль —

    <Каталог>/<Имя>/Ext/<Файл модуля>                    собственные модули объекта
    <Каталог>/<Имя>/Forms/<Форма>/Ext/Form/Module.bsl    формы объекта (9 889)
    <Каталог>/<Имя>/Commands/<Команда>/Ext/CommandModule.bsl  команды объекта (995)
    CommonForms/<Форма>/Ext/Form/Module.bsl              общие формы (492)
    Ext/<Файл модуля>                                    модули конфигурации (4)

Имена видов — русские имена платформы, без каталогов выгрузки: так модуль
удобно называть одним именем и здесь, и в других инструментах, которые адресуют
модули по метаданным. В таблице только виды, у которых модули бывают.
"""

from ..domain.model import Refuse
from ..domain.modules import COMMAND_MARK, FORM_MARK, SINGLE_MODULE, ModuleAddress

#: Вид -> каталог выгрузки.
CONTAINERS = {
    "ОбщийМодуль": "CommonModules",
    "Справочник": "Catalogs",
    "Константа": "Constants",
    "Документ": "Documents",
    "РегистрСведений": "InformationRegisters",
    "РегистрНакопления": "AccumulationRegisters",
    "РегистрРасчета": "CalculationRegisters",
    "РегистрБухгалтерии": "AccountingRegisters",
    "Отчет": "Reports",
    "Обработка": "DataProcessors",
    "Перечисление": "Enums",
    "БизнесПроцесс": "BusinessProcesses",
    "Задача": "Tasks",
    "ПланВидовХарактеристик": "ChartsOfCharacteristicTypes",
    "ПланСчетов": "ChartsOfAccounts",
    "ПланВидовРасчета": "ChartsOfCalculationTypes",
    "ЖурналДокументов": "DocumentJournals",
    "ПланОбмена": "ExchangePlans",
    "КритерийОтбора": "FilterCriteria",
    "HTTPСервис": "HTTPServices",
    "WebСервис": "WebServices",
    "ХранилищеНастроек": "SettingsStorages",
    "ОбщаяФорма": "CommonForms",
    "ОбщаяКоманда": "CommonCommands",
}

#: Собственный модуль объекта -> файл в `Ext`.
OWN_FILES = {
    "МодульОбъекта": "ObjectModule.bsl",
    "МодульМенеджера": "ManagerModule.bsl",
    "МодульНабораЗаписей": "RecordSetModule.bsl",
    "МодульМенеджераЗначения": "ValueManagerModule.bsl",
    "Модуль": "Module.bsl",
    "МодульКоманды": "CommandModule.bsl",
}

#: Модуль конфигурации -> файл в корневом `Ext`.
CONFIGURATION_FILES = {
    "МодульСеанса": "SessionModule.bsl",
    "МодульУправляемогоПриложения": "ManagedApplicationModule.bsl",
    "МодульОбычногоПриложения": "OrdinaryApplicationModule.bsl",
    "МодульВнешнегоСоединения": "ExternalConnectionModule.bsl",
}

#: Обратное: файл собственного модуля -> слово адреса. Для подсказки
#: «у объекта есть такие модули».
OWN_BY_FILE = {файл: слово for слово, файл in OWN_FILES.items()}


def module_file(address):
    """`ModuleAddress` -> части относительного пути файла. Вид неизвестен — отказ."""
    if address.kind == "Конфигурация":
        return ("Ext", CONFIGURATION_FILES[address.module])
    container = CONTAINERS.get(address.kind)
    if container is None:
        raise Refuse(f"у вида «{address.kind}» модулей не бывает или вид не знаю; "
                     f"модули бывают у: {', '.join(CONTAINERS)}")
    if address.kind == "ОбщаяФорма":
        return (container, address.name, "Ext", "Form", "Module.bsl")
    if address.module == "Форма":
        return (container, address.name, "Forms", address.sub, "Ext", "Form", "Module.bsl")
    if address.module == "Команда":
        return (container, address.name, "Commands", address.sub, "Ext", "CommandModule.bsl")
    return (container, address.name, "Ext", OWN_FILES[address.module])


#: Обратное к `CONTAINERS`: каталог выгрузки -> вид.
KIND_BY_CONTAINER = {каталог: вид for вид, каталог in CONTAINERS.items()}
#: Обратное к `CONFIGURATION_FILES`.
CONFIGURATION_BY_FILE = {файл: слово for слово, файл in CONFIGURATION_FILES.items()}


def address_of_file(parts):
    """Части относительного пути файла -> `ModuleAddress`; вне пяти шаблонов — None.

    Обратное `module_file`: модуль, названный в задании путём, должен знать о
    себе то же, что модуль, названный адресом, — например, своё имя для
    переименования.
    """
    parts = tuple(parts)
    if len(parts) == 2 and parts[0] == "Ext" and parts[1] in CONFIGURATION_BY_FILE:
        return ModuleAddress("Конфигурация", "", CONFIGURATION_BY_FILE[parts[1]])
    if len(parts) < 4 or parts[0] not in KIND_BY_CONTAINER:
        return None
    kind, name = KIND_BY_CONTAINER[parts[0]], parts[1]
    if kind == "ОбщаяФорма":
        return ModuleAddress(kind, name, FORM_MARK) if parts[2:] == ("Ext", "Form", "Module.bsl") else None
    if len(parts) == 4 and parts[2] == "Ext" and parts[3] in OWN_BY_FILE:
        module = OWN_BY_FILE[parts[3]]
        if (kind in SINGLE_MODULE) != (module == SINGLE_MODULE.get(kind)):
            return None
        return ModuleAddress(kind, name, module)
    if len(parts) == 7 and parts[2] == "Forms" and parts[4:] == ("Ext", "Form", "Module.bsl"):
        return ModuleAddress(kind, name, FORM_MARK, parts[3])
    if len(parts) == 6 and parts[2] == "Commands" and parts[4:] == ("Ext", "CommandModule.bsl"):
        return ModuleAddress(kind, name, COMMAND_MARK, parts[3])
    return None


def object_folder(address):
    """Части пути каталога объекта — чтобы назвать, какие модули у него есть."""
    container = CONTAINERS.get(address.kind)
    return (container, address.name) if container else None
