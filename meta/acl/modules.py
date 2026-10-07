"""Адрес модуля -> путь файла: в выгрузке конфигуратора и в проекте EDT.

Замер по выгрузке крупной типовой конфигурации: все 22 742 модуля ложатся ровно в пять
шаблонов, исключений ноль —

    <Каталог>/<Имя>/Ext/<Файл модуля>                    собственные модули объекта
    <Каталог>/<Имя>/Forms/<Форма>/Ext/Form/Module.bsl    формы объекта (9 889)
    <Каталог>/<Имя>/Commands/<Команда>/Ext/CommandModule.bsl  команды объекта (995)
    CommonForms/<Форма>/Ext/Form/Module.bsl              общие формы (492)
    Ext/<Файл модуля>                                    модули конфигурации (4)

Проект EDT той же конфигурации раскладывает их так же, но без `Ext` (замер:
21 802 модуля, исключений ноль) —

    <Каталог>/<Имя>/<Файл модуля>                        собственные модули объекта
    <Каталог>/<Имя>/Forms/<Форма>/Module.bsl             формы объекта (9 905)
    <Каталог>/<Имя>/Commands/<Команда>/CommandModule.bsl команды объекта
    CommonForms/<Форма>/Module.bsl                       общие формы
    Configuration/<Файл модуля>                          модули конфигурации (4)

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


class ModuleLayout:
    """Где лежат файлы модулей в одном формате исходников.

    Форматы различаются только тем, что стоит между каталогом объекта и
    файлом модуля: у выгрузки — `Ext` (и `Ext/Form` у формы), у EDT — ничего,
    а модули конфигурации у выгрузки в корневом `Ext`, у EDT — в `Configuration`.
    """

    def __init__(self, name, own, form, configuration):
        self.name = name
        #: между каталогом объекта и файлом собственного модуля (и команды)
        self.own = tuple(own)
        #: хвост пути модуля формы после каталога формы
        self.form = tuple(form)
        #: каталог модулей конфигурации
        self.configuration = configuration

    def module_file(self, address):
        """`ModuleAddress` -> части относительного пути файла. Вид неизвестен — отказ."""
        if address.kind == "Конфигурация":
            return (self.configuration, CONFIGURATION_FILES[address.module])
        container = CONTAINERS.get(address.kind)
        if container is None:
            raise Refuse(f"у вида «{address.kind}» модулей не бывает или вид не знаю; "
                         f"модули бывают у: {', '.join(CONTAINERS)}")
        if address.kind == "ОбщаяФорма":
            return (container, address.name, *self.form)
        if address.module == "Форма":
            return (container, address.name, "Forms", address.sub, *self.form)
        if address.module == "Команда":
            return (container, address.name, "Commands", address.sub, *self.own, "CommandModule.bsl")
        return (container, address.name, *self.own, OWN_FILES[address.module])

    def address_of_file(self, parts):
        """Части относительного пути файла -> `ModuleAddress`; вне шаблонов — None.

        Обратное `module_file`: модуль, названный в задании путём, должен знать о
        себе то же, что модуль, названный адресом, — например, своё имя для
        переименования.
        """
        parts = tuple(parts)
        own, form = self.own, self.form
        if len(parts) == 2 and parts[0] == self.configuration and parts[1] in CONFIGURATION_BY_FILE:
            return ModuleAddress("Конфигурация", "", CONFIGURATION_BY_FILE[parts[1]])
        if len(parts) < 3 or parts[0] not in KIND_BY_CONTAINER:
            return None
        kind, name = KIND_BY_CONTAINER[parts[0]], parts[1]
        if kind == "ОбщаяФорма":
            return ModuleAddress(kind, name, FORM_MARK) if parts[2:] == form else None
        if len(parts) == 3 + len(own) and parts[2:-1] == own and parts[-1] in OWN_BY_FILE:
            module = OWN_BY_FILE[parts[-1]]
            if (kind in SINGLE_MODULE) != (module == SINGLE_MODULE.get(kind)):
                return None
            return ModuleAddress(kind, name, module)
        if len(parts) == 4 + len(form) and parts[2] == "Forms" and parts[4:] == form:
            return ModuleAddress(kind, name, FORM_MARK, parts[3])
        if len(parts) == 5 + len(own) and parts[2] == "Commands"                 and parts[4:] == (*own, "CommandModule.bsl"):
            return ModuleAddress(kind, name, COMMAND_MARK, parts[3])
        return None

    def own_folder(self, address):
        """Части пути каталога, где лежат собственные модули объекта."""
        folder = object_folder(address)
        return None if folder is None else (*folder, *self.own)


#: Выгрузка конфигуратора.
DESIGNER = ModuleLayout("выгрузка конфигуратора", ("Ext",), ("Ext", "Form", "Module.bsl"), "Ext")
#: Проект EDT.
EDT = ModuleLayout("проект EDT", (), ("Module.bsl",), "Configuration")

#: Обратное к `CONTAINERS`: каталог выгрузки -> вид.
KIND_BY_CONTAINER = {каталог: вид for вид, каталог in CONTAINERS.items()}
#: Обратное к `CONFIGURATION_FILES`.
CONFIGURATION_BY_FILE = {файл: слово for слово, файл in CONFIGURATION_FILES.items()}

#: Выгрузка конфигуратора — раскладка по умолчанию.
module_file = DESIGNER.module_file
address_of_file = DESIGNER.address_of_file


def object_folder(address):
    """Части пути каталога объекта — чтобы назвать, какие модули у него есть."""
    container = CONTAINERS.get(address.kind)
    return (container, address.name) if container else None
