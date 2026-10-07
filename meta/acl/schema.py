"""Схема видов: из каких свойств состоит карточка и в каком порядке.

Отделено от словаря (`vocabulary.py`) и от перекладки (`mapping.py`): словарь
отвечает на вопрос «как называется», схема — «что и в каком порядке пишется»,
перекладка — «как это собрать».

Числа в комментариях — замер по реальной выгрузке крупной типовой
конфигурации (корпусу); «у всех N карточек конфигурации» — у всех N в ней.
"""

from ..domain.kinds import (
    AttributeKind,
    DimensionKind,
    ResourceKind,
    TabularSectionKind,
)
from .vocabulary import (
    AUTO_USE_DONTUSE,
    BOOLEAN,
    BUTTON_REPRESENTATION,
    CATALOG_PRESENTATION,
    CHOICE_DATA_MODE,
    CHOICE_FOLDERS,
    CHOICE_MODE,
    CODE_SERIES,
    CODE_TYPE,
    COLOR,
    COMPARISON,
    EDIT_TYPE,
    EVENTS,
    FIELDS,
    FILL_CHECKING,
    GENERATED_TYPES,
    HIERARCHY_TYPE,
    INDEXING,
    ITEMS,
    LOCK_MODE,
    MAIN_SERVER_UNAVAILABLE,
    MULTILANG,
    NESTED,
    NUMBER_PERIODICITY,
    OBJECT_REFERENCE,
    ORDER_DIRECTION,
    PARAMETER_USE_MODE,
    POSTING,
    PREDEFINED_UPDATE,
    RECORDS_DELETION,
    RECORDS_WRITING,
    REGISTER_KIND,
    REGISTER_PERIODICITY,
    REGISTER_WRITE_MODE,
    RETURN_REUSE,
    SEARCH_MODE,
    SEQUENCE_FILLING,
    STRING_LENGTH,
    SUBORDINATION,
    TEXT,
    TYPE_REDUCTION,
    TYPED_VALUE,
    TYPES,
    USE_DONTUSE,
    USE_FOR,
    VALUE,
    VALUE_TYPE,
)

# --- схема видов ------------------------------------------------------------

class Field:
    #: «значение не задано» — отличается от «значение равно None»
    OMIT_NOTHING = object()

    def __init__(self, domain, tag, value_kind, always=False, prefix="",
                 dictionary=None, only_for=None, attrs=(), omit_when=OMIT_NOTHING):
        # Постоянные атрибуты узла: левый операнд отбора всегда несёт
        # `xsi:type="dcscor:Field"` — 6317 из 6318 в конфигурации.
        self.attrs = dict(attrs)
        # Значение, при котором свойство не пишется вовсе. `use` в настройках
        # платформа пишет только когда `false`: `true` у неё умолчание, и она
        # сама его вычищает — проверено кругом через базу.
        self.omit_when = omit_when
        self.domain = domain
        self.tag = tag
        self.value_kind = value_kind
        self.always = always  # писать тег даже при пустом значении
        # Приставка выгрузки: домен говорит «мой_Модуль.Метод», в файле стоит
        # «CommonModule.мой_Модуль.Метод». Знание про «CommonModule.» — здешнее.
        self.prefix = prefix
        # Значение само является словом выгрузки (перечисление).
        self.dictionary = dictionary
        # Свойство пишется только у перечисленных видов-хозяев: `Use` есть
        # у реквизита справочника (14 804 из 14 804) и отсутствует у документа
        # (0 из 12 744). Это факт формата, потому и живёт здесь.
        self.only_for = tuple(only_for or ())


class Satellite:
    """Файл рядом с карточкой: путь внутри каталога объекта и поле домена.

    `render` говорит, что файл не передаётся текстом, а собирается: у роли это
    `Ext/Rights.xml`, документ со своей структурой. Маркер строкой, а не
    функцией, чтобы схема осталась таблицей и не потянула за собой сборку —
    иначе `schema` и `mapping` начали бы импортировать друг друга.
    """

    def __init__(self, path, domain, render=None, fields=()):
        self.path = path
        self.domain = domain
        self.render = render
        # Какие ещё доменные поля уходят в этот файл. Нужно проверке
        # согласованности слоёв: без этого поля роли выглядели бы как забытые
        # схемой, хотя они не в свойствах карточки, а в файле прав.
        self.fields = tuple(fields)


class KindSchema:
    def __init__(self, element, container, registry_tag, fields, satellites=(),
                 generated=(), children=False, child_fields=(), wrapped=True,
                 named_children=(), inside=(), attrs=()):
        # Дети, записанные одним именем: так макет числится в карточке объекта.
        self.named_children = tuple(named_children)
        # Контейнеры внутри хозяина, куда ложится сущность: пункт отбора живёт
        # не прямо в варианте настроек, а в `settings/filter`. Заводятся, если
        # их ещё нет, — у свежей схемы настройки пусты.
        self.inside = tuple(inside)
        # Постоянные атрибуты самого узла: у пунктов настроек вид задаётся
        # `xsi:type`, а не тегом — теги у них у всех одинаковые (`item`).
        # Имя не `attrs`: так уже названы постоянные атрибуты **свойства**
        # (`Field.attrs`), и два разных смысла под одним именем в одном
        # модуле читаются как одно.
        self.node_attrs = tuple(attrs)
        # Карточная форма: у узла есть `uuid`, свойства лежат в `<Properties>`.
        # У схемы компоновки не так — там свойства прямые дети, а идентификатора
        # нет вовсе. Это факт формата, потому и живёт здесь, а не в домене.
        self.wrapped = wrapped
        self.element = element
        self.container = container
        self.registry_tag = registry_tag
        self.fields = list(fields)
        self.satellites = list(satellites)
        # Порождаемые типы: пары (приставка имени, категория). Платформа заводит
        # их сама при создании объекта в конфигураторе; при записи в выгрузку
        # их пишем мы, включая идентификаторы.
        self.generated = tuple(generated)
        # Раздел `<ChildObjects>` у прикладных объектов пишется всегда,
        # даже пустым; у плоских видов его нет вовсе.
        self.children = children
        # Поля, содержимое которых становится вложенными узлами.
        self.child_fields = tuple(child_fields)


SCHEMA = {
    "ПодпискаНаСобытие": KindSchema(
        "EventSubscription", "EventSubscriptions", "EventSubscription", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("источник", "Source", TYPES),
            Field("событие", "Event", TEXT, dictionary=EVENTS),
            Field("обработчик", "Handler", TEXT, prefix="CommonModule."),
        ]),
    # Порядок и полнота свойств сняты с 4100 карточек: вариант порядка ровно
    # один, и все одиннадцать свойств пишутся всегда, включая флаги со значением
    # false — отсутствие флага и флаг «нет» для платформы не одно и то же.
    "ОбщийМодуль": KindSchema(
        "CommonModule", "CommonModules", "CommonModule", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("глобальный", "Global", BOOLEAN, always=True),
            Field("клиентУправляемоеПриложение", "ClientManagedApplication",
                  BOOLEAN, always=True),
            Field("сервер", "Server", BOOLEAN, always=True),
            Field("внешнееСоединение", "ExternalConnection", BOOLEAN, always=True),
            Field("клиентОбычноеПриложение", "ClientOrdinaryApplication",
                  BOOLEAN, always=True),
            Field("вызовСервера", "ServerCall", BOOLEAN, always=True),
            Field("привилегированный", "Privileged", BOOLEAN, always=True),
            Field("повторноеИспользование", "ReturnValuesReuse", TEXT, always=True,
                  dictionary=RETURN_REUSE),
        ],
        satellites=[Satellite("Ext/Module.bsl", "текст")]),
    # Реквизит — не карточка: он живёт узлом внутри чужого файла, поэтому ни
    # контейнера, ни записи в реестре у него нет. Порядок и полнота сняты
    # с 27 548 реквизитов справочников и документов: вариант порядка ровно один,
    # все свойства пишутся всегда, включая пустые.
    "Реквизит": KindSchema(
        "Attribute", None, None, [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("тип", "Type", VALUE_TYPE, always=True),
            Field("режимПароля", "PasswordMode", BOOLEAN, always=True),
            Field("формат", "Format", MULTILANG, always=True),
            Field("форматРедактирования", "EditFormat", MULTILANG, always=True),
            Field("подсказка", "ToolTip", MULTILANG, always=True),
            Field("выделятьОтрицательные", "MarkNegatives", BOOLEAN, always=True),
            Field("маска", "Mask", TEXT, always=True),
            Field("многострочный", "MultiLine", BOOLEAN, always=True),
            Field("расширенноеРедактирование", "ExtendedEdit", BOOLEAN, always=True),
            Field("минимальноеЗначение", "MinValue", VALUE, always=True),
            Field("максимальноеЗначение", "MaxValue", VALUE, always=True),
            Field("заполнятьИзДанныхЗаполнения", "FillFromFillingValue",
                  BOOLEAN, always=True,
                  only_for=AttributeKind.APPLIES_TO["заполнятьИзДанныхЗаполнения"]),
            Field("значениеЗаполнения", "FillValue", VALUE, always=True,
                  only_for=AttributeKind.APPLIES_TO["значениеЗаполнения"]),
            Field("проверкаЗаполнения", "FillChecking", TEXT, always=True,
                  dictionary=FILL_CHECKING),
            Field("выборГруппИЭлементов", "ChoiceFoldersAndItems", TEXT, always=True,
                  dictionary=CHOICE_FOLDERS),
            Field("связиПараметровВыбора", "ChoiceParameterLinks", NESTED, always=True),
            Field("параметрыВыбора", "ChoiceParameters", NESTED, always=True),
            Field("быстрыйВыбор", "QuickChoice", TEXT, always=True, dictionary=AUTO_USE_DONTUSE),
            Field("созданиеПриВводе", "CreateOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("формаВыбора", "ChoiceForm", TEXT, always=True),
            Field("связьПоТипу", "LinkByType", NESTED, always=True),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("использование", "Use", TEXT, always=True, dictionary=USE_FOR,
                  only_for=AttributeKind.APPLIES_TO["использование"]),
            Field("индексирование", "Indexing", TEXT, always=True,
                  dictionary=INDEXING,
                  only_for=AttributeKind.APPLIES_TO["индексирование"]),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE,
                  only_for=AttributeKind.APPLIES_TO["полнотекстовыйПоиск"]),
            Field("историяДанных", "DataHistory", TEXT, always=True, dictionary=USE_DONTUSE,
                  only_for=AttributeKind.APPLIES_TO["историяДанных"]),
        ]),
    # Справочник. Состав и порядок сняты с эталона, созданного конфигуратором
    # в пустой базе: у нового объекта 53 свойства, блока `StandardAttributes`
    # нет (он появляется, только когда стандартные реквизиты настраивают —
    # у 1182 справочников конфигурации он есть, у нетронутых двух нет).
    "Справочник": KindSchema(
        "Catalog", "Catalogs", "Catalog", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("иерархический", "Hierarchical", BOOLEAN, always=True),
            Field("видИерархии", "HierarchyType", TEXT, always=True,
                  dictionary=HIERARCHY_TYPE),
            Field("ограничиватьУровни", "LimitLevelCount", BOOLEAN, always=True),
            Field("количествоУровней", "LevelCount", TEXT, always=True),
            Field("группыСверху", "FoldersOnTop", BOOLEAN, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN, always=True),
            Field("владельцы", "Owners", ITEMS, always=True),
            Field("использованиеПодчинения", "SubordinationUse", TEXT, always=True,
                  dictionary=SUBORDINATION),
            Field("длинаКода", "CodeLength", TEXT, always=True),
            Field("длинаНаименования", "DescriptionLength", TEXT, always=True),
            Field("типКода", "CodeType", TEXT, always=True, dictionary=CODE_TYPE),
            Field("допустимаяДлинаКода", "CodeAllowedLength", TEXT, always=True,
                  dictionary=STRING_LENGTH),
            Field("серияКодов", "CodeSeries", TEXT, always=True,
                  dictionary=CODE_SERIES),
            Field("контрольУникальности", "CheckUnique", BOOLEAN, always=True),
            Field("автонумерация", "Autonumbering", BOOLEAN, always=True),
            Field("основноеПредставление", "DefaultPresentation", TEXT, always=True,
                  dictionary=CATALOG_PRESENTATION),
            Field("характеристики", "Characteristics", NESTED, always=True),
            Field("обновлениеПредопределённых", "PredefinedDataUpdate", TEXT,
                  always=True, dictionary=PREDEFINED_UPDATE),
            Field("способРедактирования", "EditType", TEXT, always=True,
                  dictionary=EDIT_TYPE),
            Field("быстрыйВыбор", "QuickChoice", BOOLEAN, always=True),
            Field("режимВыбора", "ChoiceMode", TEXT, always=True,
                  dictionary=CHOICE_MODE),
            Field("вводПоСтроке", "InputByString", FIELDS, always=True),
            Field("режимПоискаПриВводе", "SearchStringModeOnInputByString", TEXT,
                  always=True, dictionary=SEARCH_MODE),
            Field("полнотекстовыйПоискПриВводе", "FullTextSearchOnInputByString",
                  TEXT, always=True, dictionary=USE_DONTUSE),
            Field("режимПолученияДанныхВыбора", "ChoiceDataGetModeOnInputByString",
                  TEXT, always=True, dictionary=CHOICE_DATA_MODE),
            Field("основнаяФормаОбъекта", "DefaultObjectForm", TEXT, always=True),
            Field("основнаяФормаГруппы", "DefaultFolderForm", TEXT, always=True),
            Field("основнаяФормаСписка", "DefaultListForm", TEXT, always=True),
            Field("основнаяФормаВыбора", "DefaultChoiceForm", TEXT, always=True),
            Field("основнаяФормаВыбораГруппы", "DefaultFolderChoiceForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаОбъекта", "AuxiliaryObjectForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаГруппы", "AuxiliaryFolderForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаСписка", "AuxiliaryListForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаВыбора", "AuxiliaryChoiceForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаВыбораГруппы", "AuxiliaryFolderChoiceForm",
                  TEXT, always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("основание", "BasedOn", ITEMS, always=True),
            Field("поляБлокировкиДанных", "DataLockFields", FIELDS, always=True),
            Field("режимУправленияБлокировкой", "DataLockControlMode", TEXT,
                  always=True, dictionary=LOCK_MODE),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("представлениеОбъекта", "ObjectPresentation", MULTILANG,
                  always=True),
            Field("расширенноеПредставлениеОбъекта", "ExtendedObjectPresentation",
                  MULTILANG, always=True),
            Field("представлениеСписка", "ListPresentation", MULTILANG, always=True),
            Field("расширенноеПредставлениеСписка", "ExtendedListPresentation",
                  MULTILANG, always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
            Field("созданиеПриВводе", "CreateOnInput", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("историяДанных", "DataHistory", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяСразуПослеЗаписи", "UpdateDataHistoryImmediatelyAfterWrite",
                  BOOLEAN, always=True),
            Field("обработкаВерсийПослеЗаписи",
                  "ExecuteAfterWriteDataHistoryVersionProcessing", BOOLEAN,
                  always=True),
        ],
        generated=GENERATED_TYPES["Справочник"], children=True,
        child_fields=(("реквизиты", "Реквизит"),
                      ("табличныеЧасти", "ТабличнаяЧасть"))),
    # Перечисление. Состав снят с эталона конфигуратора: 15 свойств, детей нет.
    "Перечисление": KindSchema(
        "Enum", "Enums", "Enum", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN, always=True),
            Field("характеристики", "Characteristics", NESTED, always=True),
            Field("быстрыйВыбор", "QuickChoice", BOOLEAN, always=True),
            Field("режимВыбора", "ChoiceMode", TEXT, always=True,
                  dictionary=CHOICE_MODE),
            Field("основнаяФормаСписка", "DefaultListForm", TEXT, always=True),
            Field("основнаяФормаВыбора", "DefaultChoiceForm", TEXT, always=True),
            Field("дополнительнаяФормаСписка", "AuxiliaryListForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаВыбора", "AuxiliaryChoiceForm", TEXT,
                  always=True),
            Field("представлениеСписка", "ListPresentation", MULTILANG, always=True),
            Field("расширенноеПредставлениеСписка", "ExtendedListPresentation",
                  MULTILANG, always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
        ],
        generated=GENERATED_TYPES["Перечисление"], children=True,
        child_fields=(("значения", "ЗначениеПеречисления"),)),
    # Регистр сведений. 25 свойств; без измерений конфигуратор его не сохраняет,
    # загрузка принимает — в домене это предупреждение.
    "РегистрСведений": KindSchema(
        "InformationRegister", "InformationRegisters", "InformationRegister", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN, always=True),
            Field("способРедактирования", "EditType", TEXT, always=True,
                  dictionary=EDIT_TYPE),
            Field("основнаяФормаЗаписи", "DefaultRecordForm", TEXT, always=True),
            Field("основнаяФормаСписка", "DefaultListForm", TEXT, always=True),
            Field("дополнительнаяФормаЗаписи", "AuxiliaryRecordForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаСписка", "AuxiliaryListForm", TEXT,
                  always=True),
            Field("периодичность", "InformationRegisterPeriodicity", TEXT,
                  always=True, dictionary=REGISTER_PERIODICITY),
            Field("режимЗаписи", "WriteMode", TEXT, always=True,
                  dictionary=REGISTER_WRITE_MODE),
            Field("основнойОтборПоПериоду", "MainFilterOnPeriod", BOOLEAN,
                  always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("режимУправленияБлокировкой", "DataLockControlMode", TEXT,
                  always=True, dictionary=LOCK_MODE),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("итогиСрезПервых", "EnableTotalsSliceFirst", BOOLEAN, always=True),
            Field("итогиСрезПоследних", "EnableTotalsSliceLast", BOOLEAN,
                  always=True),
            Field("представлениеЗаписи", "RecordPresentation", MULTILANG,
                  always=True),
            Field("расширенноеПредставлениеЗаписи", "ExtendedRecordPresentation",
                  MULTILANG, always=True),
            Field("представлениеСписка", "ListPresentation", MULTILANG, always=True),
            Field("расширенноеПредставлениеСписка", "ExtendedListPresentation",
                  MULTILANG, always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
            Field("историяДанных", "DataHistory", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяСразуПослеЗаписи", "UpdateDataHistoryImmediatelyAfterWrite",
                  BOOLEAN, always=True),
            Field("обработкаВерсийПослеЗаписи",
                  "ExecuteAfterWriteDataHistoryVersionProcessing", BOOLEAN,
                  always=True),
        ],
        generated=GENERATED_TYPES["РегистрСведений"], children=True,
        child_fields=(("ресурсы", "Ресурс"), ("реквизиты", "Реквизит"),
                      ("измерения", "Измерение"))),
    # Документ. Состав снят с эталона конфигуратора: 45 свойств, блока
    # `StandardAttributes` у нового объекта нет — как у справочника.
    "Документ": KindSchema(
        "Document", "Documents", "Document", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN, always=True),
            Field("нумератор", "Numerator", TEXT, always=True),
            Field("типНомера", "NumberType", TEXT, always=True, dictionary=CODE_TYPE),
            Field("длинаНомера", "NumberLength", TEXT, always=True),
            Field("допустимаяДлинаНомера", "NumberAllowedLength", TEXT, always=True,
                  dictionary=STRING_LENGTH),
            Field("периодичностьНомера", "NumberPeriodicity", TEXT, always=True,
                  dictionary=NUMBER_PERIODICITY),
            Field("контрольУникальности", "CheckUnique", BOOLEAN, always=True),
            Field("автонумерация", "Autonumbering", BOOLEAN, always=True),
            Field("характеристики", "Characteristics", NESTED, always=True),
            Field("основание", "BasedOn", ITEMS, always=True),
            Field("вводПоСтроке", "InputByString", FIELDS, always=True),
            Field("созданиеПриВводе", "CreateOnInput", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("режимПоискаПриВводе", "SearchStringModeOnInputByString", TEXT,
                  always=True, dictionary=SEARCH_MODE),
            Field("полнотекстовыйПоискПриВводе", "FullTextSearchOnInputByString",
                  TEXT, always=True, dictionary=USE_DONTUSE),
            Field("режимПолученияДанныхВыбора", "ChoiceDataGetModeOnInputByString",
                  TEXT, always=True, dictionary=CHOICE_DATA_MODE),
            Field("основнаяФормаОбъекта", "DefaultObjectForm", TEXT, always=True),
            Field("основнаяФормаСписка", "DefaultListForm", TEXT, always=True),
            Field("основнаяФормаВыбора", "DefaultChoiceForm", TEXT, always=True),
            Field("дополнительнаяФормаОбъекта", "AuxiliaryObjectForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаСписка", "AuxiliaryListForm", TEXT,
                  always=True),
            Field("дополнительнаяФормаВыбора", "AuxiliaryChoiceForm", TEXT,
                  always=True),
            Field("проведение", "Posting", TEXT, always=True, dictionary=POSTING),
            Field("оперативноеПроведение", "RealTimePosting", TEXT, always=True,
                  dictionary=POSTING),
            Field("удалениеДвижений", "RegisterRecordsDeletion", TEXT, always=True,
                  dictionary=RECORDS_DELETION),
            Field("записьДвиженийПриПроведении", "RegisterRecordsWritingOnPost",
                  TEXT, always=True, dictionary=RECORDS_WRITING),
            Field("заполнениеПоследовательностей", "SequenceFilling", TEXT,
                  always=True, dictionary=SEQUENCE_FILLING),
            Field("движения", "RegisterRecords", ITEMS, always=True),
            Field("проведениеПривилегированно", "PostInPrivilegedMode", BOOLEAN,
                  always=True),
            Field("отменаПроведенияПривилегированно", "UnpostInPrivilegedMode",
                  BOOLEAN, always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("поляБлокировкиДанных", "DataLockFields", FIELDS, always=True),
            Field("режимУправленияБлокировкой", "DataLockControlMode", TEXT,
                  always=True, dictionary=LOCK_MODE),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("представлениеОбъекта", "ObjectPresentation", MULTILANG,
                  always=True),
            Field("расширенноеПредставлениеОбъекта", "ExtendedObjectPresentation",
                  MULTILANG, always=True),
            Field("представлениеСписка", "ListPresentation", MULTILANG, always=True),
            Field("расширенноеПредставлениеСписка", "ExtendedListPresentation",
                  MULTILANG, always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("историяДанных", "DataHistory", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяСразуПослеЗаписи", "UpdateDataHistoryImmediatelyAfterWrite",
                  BOOLEAN, always=True),
            Field("обработкаВерсийПослеЗаписи",
                  "ExecuteAfterWriteDataHistoryVersionProcessing", BOOLEAN,
                  always=True),
        ],
        generated=GENERATED_TYPES["Документ"], children=True,
        child_fields=(("реквизиты", "Реквизит"),
                      ("табличныеЧасти", "ТабличнаяЧасть"))),
    # Измерение регистра сведений. Тот же набор, что у реквизита, минус
    # «использование» (оно только у справочника) плюс четыре своих:
    # ведущее, основной отбор, запрет незаполненных и приведение типа.
    "Измерение": KindSchema(
        "Dimension", None, None, [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("тип", "Type", VALUE_TYPE, always=True),
            Field("режимПароля", "PasswordMode", BOOLEAN, always=True),
            Field("формат", "Format", MULTILANG, always=True),
            Field("форматРедактирования", "EditFormat", MULTILANG, always=True),
            Field("подсказка", "ToolTip", MULTILANG, always=True),
            Field("выделятьОтрицательные", "MarkNegatives", BOOLEAN, always=True),
            Field("маска", "Mask", TEXT, always=True),
            Field("многострочный", "MultiLine", BOOLEAN, always=True),
            Field("расширенноеРедактирование", "ExtendedEdit", BOOLEAN, always=True),
            Field("минимальноеЗначение", "MinValue", VALUE, always=True),
            Field("максимальноеЗначение", "MaxValue", VALUE, always=True),
            Field("заполнятьИзДанныхЗаполнения", "FillFromFillingValue",
                  BOOLEAN, always=True,
                  only_for=DimensionKind.APPLIES_TO["заполнятьИзДанныхЗаполнения"]),
            Field("значениеЗаполнения", "FillValue", VALUE, always=True,
                  only_for=DimensionKind.APPLIES_TO["значениеЗаполнения"]),
            Field("проверкаЗаполнения", "FillChecking", TEXT, always=True,
                  dictionary=FILL_CHECKING),
            Field("выборГруппИЭлементов", "ChoiceFoldersAndItems", TEXT, always=True,
                  dictionary=CHOICE_FOLDERS),
            Field("связиПараметровВыбора", "ChoiceParameterLinks", NESTED,
                  always=True),
            Field("параметрыВыбора", "ChoiceParameters", NESTED, always=True),
            Field("быстрыйВыбор", "QuickChoice", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("созданиеПриВводе", "CreateOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("формаВыбора", "ChoiceForm", TEXT, always=True),
            Field("связьПоТипу", "LinkByType", NESTED, always=True),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("ведущее", "Master", BOOLEAN, always=True,
                  only_for=DimensionKind.APPLIES_TO["ведущее"]),
            Field("основнойОтбор", "MainFilter", BOOLEAN, always=True,
                  only_for=DimensionKind.APPLIES_TO["основнойОтбор"]),
            Field("запретНезаполненных", "DenyIncompleteValues", BOOLEAN,
                  always=True),
            Field("индексирование", "Indexing", TEXT, always=True,
                  dictionary=INDEXING),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяДанных", "DataHistory", TEXT, always=True,
                  dictionary=USE_DONTUSE,
                  only_for=DimensionKind.APPLIES_TO["историяДанных"]),
            Field("приведениеТипа", "TypeReductionMode", TEXT, always=True,
                  dictionary=TYPE_REDUCTION,
                  only_for=DimensionKind.APPLIES_TO["приведениеТипа"]),
            # Использование в итогах — только у измерения регистра накопления;
            # в эталоне конфигуратора оно стоит последним, после поиска.
            Field("использованиеВИтогах", "UseInTotals", BOOLEAN, always=True,
                  only_for=DimensionKind.APPLIES_TO["использованиеВИтогах"]),
        ]),
    # Ресурс регистра сведений: тот же набор, что у измерения, минус четыре
    # измеренческих свойства (ведущее, основной отбор, запрет незаполненных,
    # приведение типа). Порядок один и тот же у всех 7216 ресурсов корпуса.
    "Ресурс": KindSchema(
        "Resource", None, None, [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("тип", "Type", VALUE_TYPE, always=True),
            Field("режимПароля", "PasswordMode", BOOLEAN, always=True),
            Field("формат", "Format", MULTILANG, always=True),
            Field("форматРедактирования", "EditFormat", MULTILANG, always=True),
            Field("подсказка", "ToolTip", MULTILANG, always=True),
            Field("выделятьОтрицательные", "MarkNegatives", BOOLEAN, always=True),
            Field("маска", "Mask", TEXT, always=True),
            Field("многострочный", "MultiLine", BOOLEAN, always=True),
            Field("расширенноеРедактирование", "ExtendedEdit", BOOLEAN, always=True),
            Field("минимальноеЗначение", "MinValue", VALUE, always=True),
            Field("максимальноеЗначение", "MaxValue", VALUE, always=True),
            Field("заполнятьИзДанныхЗаполнения", "FillFromFillingValue",
                  BOOLEAN, always=True,
                  only_for=ResourceKind.APPLIES_TO["заполнятьИзДанныхЗаполнения"]),
            Field("значениеЗаполнения", "FillValue", VALUE, always=True,
                  only_for=ResourceKind.APPLIES_TO["значениеЗаполнения"]),
            Field("проверкаЗаполнения", "FillChecking", TEXT, always=True,
                  dictionary=FILL_CHECKING),
            Field("выборГруппИЭлементов", "ChoiceFoldersAndItems", TEXT, always=True,
                  dictionary=CHOICE_FOLDERS),
            Field("связиПараметровВыбора", "ChoiceParameterLinks", NESTED,
                  always=True),
            Field("параметрыВыбора", "ChoiceParameters", NESTED, always=True),
            Field("быстрыйВыбор", "QuickChoice", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("созданиеПриВводе", "CreateOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("формаВыбора", "ChoiceForm", TEXT, always=True),
            Field("связьПоТипу", "LinkByType", NESTED, always=True),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("индексирование", "Indexing", TEXT, always=True,
                  dictionary=INDEXING,
                  only_for=ResourceKind.APPLIES_TO["индексирование"]),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяДанных", "DataHistory", TEXT, always=True,
                  dictionary=USE_DONTUSE,
                  only_for=ResourceKind.APPLIES_TO["историяДанных"]),
        ]),
    # Значение перечисления — самая простая вложенная сущность: четыре свойства
    # и никакого внутреннего блока.
    "ЗначениеПеречисления": KindSchema(
        "EnumValue", None, None, [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("цвет", "Color", TEXT, always=True, dictionary=COLOR),
        ]),
    # Табличная часть. Порождаемых типов два, и приставка у них зависит от вида
    # хозяина: справочник даёт `CatalogTabularSection`, документ —
    # `DocumentTabularSection` (снято по всем 3466 табличным частям корпуса).
    "ТабличнаяЧасть": KindSchema(
        "TabularSection", None, None, [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("подсказка", "ToolTip", MULTILANG, always=True),
            Field("проверкаЗаполнения", "FillChecking", TEXT, always=True,
                  dictionary=FILL_CHECKING),
            Field("использование", "Use", TEXT, always=True, dictionary=USE_FOR,
                  only_for=TabularSectionKind.WITH_USE),
            Field("длинаНомераСтроки", "LineNumberLength", TEXT, always=True,
                  only_for=TabularSectionKind.WITH_LINE_NUMBER),
        ],
        generated=(("{host}TabularSection", "TabularSection"),
                   ("{host}TabularSectionRow", "TabularSectionRow")),
        children=True, child_fields=(("реквизиты", "Реквизит"),)),
    # Роль. Карточка из трёх свойств — одинакова у всех 2709 ролей
    # конфигурации, без `InternalInfo` и без раздела детей. Всё содержательное
    # лежит в файле прав рядом.
    "Роль": KindSchema(
        "Role", "Roles", "Role", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
        ],
        satellites=[Satellite("Ext/Rights.xml", "права", render="права",
                              fields=("праваДляНовыхОбъектов",
                                      "праваРеквизитовПоУмолчанию",
                                      "независимыеПраваПодчинённых"))]),
    # Регламентное задание. Состав снят со всех 297 карточек конфигурации —
    # форма одна, исключений нет. Порождаемых типов и детей у него не бывает.
    "РегламентноеЗадание": KindSchema(
        "ScheduledJob", "ScheduledJobs", "ScheduledJob", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("обработчик", "MethodName", TEXT, always=True,
                  prefix="CommonModule."),
            Field("наименование", "Description", TEXT, always=True),
            Field("ключ", "Key", TEXT, always=True),
            Field("использование", "Use", BOOLEAN, always=True),
            Field("предопределённое", "Predefined", BOOLEAN, always=True),
            Field("количествоПовторов", "RestartCountOnFailure", TEXT, always=True),
            Field("интервалПовтора", "RestartIntervalOnFailure", TEXT, always=True),
        ]),
    # Общая команда. Состав снят со всех 705 карточек конфигурации — форма одна.
    # Порождаемых типов и детей у неё не бывает.
    "ОбщаяКоманда": KindSchema(
        "CommonCommand", "CommonCommands", "CommonCommand", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("группа", "Group", TEXT, always=True),
            Field("отображение", "Representation", TEXT, always=True,
                  dictionary=BUTTON_REPRESENTATION),
            Field("подсказка", "ToolTip", MULTILANG, always=True),
            Field("картинка", "Picture", NESTED, always=True),
            Field("сочетаниеКлавиш", "Shortcut", TEXT, always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("типПараметраКоманды", "CommandParameterType", TYPES, always=True),
            Field("режимИспользованияПараметра", "ParameterUseMode", TEXT,
                  always=True, dictionary=PARAMETER_USE_MODE),
            Field("изменяетДанные", "ModifiesData", BOOLEAN, always=True),
            Field("приНедоступностиГлавногоСервера", "OnMainServerUnavalableBehavior",
                  TEXT, always=True, dictionary=MAIN_SERVER_UNAVAILABLE),
        ]),
    # Набор данных схемы компоновки. Порядок снят с 852 наборов-запросов
    # конфигурации топологической сортировкой, без единого противоречия.
    # `field` сюда не входит: это дети набора, а не свойство.
    # Набор данных объявляет свой вид атрибутом: элемент `dataSet` абстрактный,
    # и `xsi:type` — то, чем платформа выбирает класс. Голых `<dataSet>`
    # в конфигурации нет ни одного из 1275: запрос 893, объект 273,
    # объединение 109. Без атрибута файл не загружается.
    #
    # Описан здесь только набор-запрос: его поля (`запрос`, `источникДанных`)
    # к остальным двум не подходят — у объекта вместо запроса `objectName`,
    # у объединения нет ни того ни другого, зато есть вложенные наборы.
    "НаборДанных": KindSchema(
        "dataSet", None, None, [
            Field("имя", "name", TEXT),
            Field("источникДанных", "dataSource", TEXT),
            Field("запрос", "query", TEXT),
            # Не универсальны: 145 и 16 наборов из 893. Пишутся, только если
            # заданы, — иначе мы дописывали бы то, чего платформа не пишет.
            Field("автозаполнениеПолей", "autoFillFields", BOOLEAN),
            Field("группировкаЗапроса", "useQueryGroupIfPossible", BOOLEAN),
        ], wrapped=False,
        attrs=(("xsi:type", "DataSetQuery"),)),
    # Параметр схемы компоновки. Порядок снят с 4726 параметров конфигурации.
    "Параметр": KindSchema(
        "parameter", None, None, [
            Field("имя", "name", TEXT),
            # Тип у заголовка и значения объявлен всегда: голых `title`
            # в конфигурации 0 из 25 886, голых `value` — 0 из 5812.
            # Форм две — `v8:LocalStringType` (многоязычная) и `xs:string`;
            # задание языка не называет, поэтому пишется простая строка,
            # которая в корпусе тоже есть (103 случая). У значения тип идёт
            # от того, что в нём лежит, — тем же механизмом, что у правого
            # операнда отбора.
            Field("заголовок", "title", TEXT, attrs={"xsi:type": "xs:string"}),
            # Тип параметра записан так же, как тип реквизита: значение
            # плюс квалификатор. Квалификаторов в схемах 5510 — значит это
            # `VALUE_TYPE`, а не голый перечень типов.
            Field("типЗначения", "valueType", VALUE_TYPE),
            # Оба пишутся всегда — этого требует сама платформа: параметру,
            # записанному без них, она дописывает оба в круге «записали →
            # загрузили → выгрузили». Корпус согласен — `useRestriction` есть
            # у всех параметров замеренной конфигурации.
            Field("значение", "value", TYPED_VALUE, always=True),
            Field("ограничениеИспользования", "useRestriction", BOOLEAN,
                  always=True),
            Field("выражение", "expression", TEXT),
            Field("списокЗначений", "valueListAllowed", BOOLEAN),
            Field("доступенКакПоле", "availableAsField", BOOLEAN),
            Field("запретНезаполненных", "denyIncompleteValues", BOOLEAN),
            Field("использование", "use", TEXT),
        ], wrapped=False),
    # Регистр накопления. Состав снят с эталона, записанного конфигуратором
    # (`мой_ЭталонРН`): четырнадцать свойств. У 172 карточек
    # конфигурации из 173 их пятнадцать — лишний `StandardAttributes`
    # появляется, когда стандартные реквизиты настроили руками; у только что
    # созданного его нет, как и у нового объекта любого другого вида.
    "РегистрНакопления": KindSchema(
        "AccumulationRegister", "AccumulationRegisters", "AccumulationRegister", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN,
                  always=True),
            Field("основнаяФормаСписка", "DefaultListForm", TEXT, always=True),
            Field("дополнительнаяФормаСписка", "AuxiliaryListForm", TEXT,
                  always=True),
            Field("видРегистра", "RegisterType", TEXT, always=True,
                  dictionary=REGISTER_KIND),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("режимУправленияБлокировкой", "DataLockControlMode", TEXT,
                  always=True, dictionary=LOCK_MODE),
            Field("полнотекстовыйПоиск", "FullTextSearch", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("разделениеИтогов", "EnableTotalsSplitting", BOOLEAN,
                  always=True),
            Field("представлениеСписка", "ListPresentation", MULTILANG,
                  always=True),
            Field("расширенноеПредставлениеСписка", "ExtendedListPresentation",
                  MULTILANG, always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
        ],
        generated=GENERATED_TYPES["РегистрНакопления"], children=True,
        # Порядок тот же, что в карточке: ресурс, реквизит, измерение —
        # так их пишет конфигуратор и так замерено по 173 карточкам.
        child_fields=(("ресурсы", "Ресурс"), ("реквизиты", "Реквизит"),
                      ("измерения", "Измерение"))),
    # Константа. Состав снят со всех 905 карточек — форма одна. Свойства
    # ввода те же, что у реквизита: константа хранит одно значение и
    # редактируется так же. Умолчания взяты по правилу «единственное значение
    # по корпусу — факт»: выбор групп и элементов `Элементы` у всех 905,
    # быстрый выбор `Авто` у всех 905, выделение отрицательных и расширенное
    # редактирование выключены у всех. Стандартные команды расходятся
    # (550 против 355) и потому спрашиваются.
    "Константа": KindSchema(
        "Constant", "Constants", "Constant", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("тип", "Type", VALUE_TYPE, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN,
                  always=True),
            Field("основнаяФорма", "DefaultForm", TEXT, always=True),
            Field("расширенноеПредставление", "ExtendedPresentation", MULTILANG,
                  always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
            Field("режимПароля", "PasswordMode", BOOLEAN, always=True),
            Field("формат", "Format", MULTILANG, always=True),
            Field("форматРедактирования", "EditFormat", MULTILANG, always=True),
            Field("подсказка", "ToolTip", MULTILANG, always=True),
            Field("выделятьОтрицательные", "MarkNegatives", BOOLEAN, always=True),
            Field("маска", "Mask", TEXT, always=True),
            Field("многострочный", "MultiLine", BOOLEAN, always=True),
            Field("расширенноеРедактирование", "ExtendedEdit", BOOLEAN,
                  always=True),
            Field("минимальноеЗначение", "MinValue", VALUE, always=True),
            Field("максимальноеЗначение", "MaxValue", VALUE, always=True),
            Field("проверкаЗаполнения", "FillChecking", TEXT, always=True,
                  dictionary=FILL_CHECKING),
            Field("выборГруппИЭлементов", "ChoiceFoldersAndItems", TEXT,
                  always=True, dictionary=CHOICE_FOLDERS),
            Field("связиПараметровВыбора", "ChoiceParameterLinks", NESTED,
                  always=True),
            Field("параметрыВыбора", "ChoiceParameters", NESTED, always=True),
            Field("быстрыйВыбор", "QuickChoice", TEXT, always=True,
                  dictionary=AUTO_USE_DONTUSE),
            Field("формаВыбора", "ChoiceForm", TEXT, always=True),
            Field("связьПоТипу", "LinkByType", NESTED, always=True),
            Field("историяВыбораПриВводе", "ChoiceHistoryOnInput", TEXT,
                  always=True, dictionary=AUTO_USE_DONTUSE),
            Field("режимУправленияБлокировкой", "DataLockControlMode", TEXT,
                  always=True, dictionary=LOCK_MODE),
            Field("историяДанных", "DataHistory", TEXT, always=True,
                  dictionary=USE_DONTUSE),
            Field("историяСразуПослеЗаписи",
                  "UpdateDataHistoryImmediatelyAfterWrite", BOOLEAN, always=True),
            Field("обработкаВерсийПослеЗаписи",
                  "ExecuteAfterWriteDataHistoryVersionProcessing", BOOLEAN,
                  always=True),
        ],
        generated=GENERATED_TYPES["Константа"]),
    # Определяемый тип. Четыре свойства у всех 552 карточек — самый простой
    # вид в конфигурации: имя, синоним, комментарий и собственно тип.
    "ОпределяемыйТип": KindSchema(
        "DefinedType", "DefinedTypes", "DefinedType", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("тип", "Type", VALUE_TYPE, always=True),
        ],
        generated=GENERATED_TYPES["ОпределяемыйТип"]),
    # Подсистема. Девять свойств у всех 1060 карточек; порождаемых типов
    # и внутреннего блока нет вовсе — единственный такой вид из заведённых.
    # Раздел детей пустой пишется всегда: 900 карточек из 1060 несут
    # `<ChildObjects/>`, остальные 160 — вложенные подсистемы, которых
    # инструмент не заводит.
    "Подсистема": KindSchema(
        "Subsystem", "Subsystems", "Subsystem", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("включатьВКомандныйИнтерфейс", "IncludeInCommandInterface",
                  BOOLEAN, always=True),
            Field("однаКоманда", "UseOneCommand", BOOLEAN, always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
            Field("картинка", "Picture", NESTED, always=True),
            Field("состав", "Content", ITEMS, always=True),
        ],
        children=True),
    # Обработка. Состав снят со всех 613 карточек конфигурации — форма одна,
    # без единого исключения: девять свойств и ровно в этом порядке. Ссылочные
    # поля (обе формы) у новой обработки пусты по построению: форм у неё ещё
    # нет, ссылаться не на что. Два флага в корпусе расходятся и потому
    # спрашиваются: стандартные команды включены у 441 из 613, справка
    # в содержании — у 161.
    "Обработка": KindSchema(
        "DataProcessor", "DataProcessors", "DataProcessor", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN,
                  always=True),
            Field("основнаяФорма", "DefaultForm", TEXT, always=True),
            Field("дополнительнаяФорма", "AuxiliaryForm", TEXT, always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents",
                  BOOLEAN, always=True),
            Field("расширенноеПредставление", "ExtendedPresentation", MULTILANG,
                  always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
        ],
        generated=GENERATED_TYPES["Обработка"], children=True,
        child_fields=(("реквизиты", "Реквизит"),
                      ("табличныеЧасти", "ТабличнаяЧасть"))),
    # Отчёт. Состав снят со всех 956 карточек конфигурации — форма одна.
    # Ссылочные поля (формы, хранилища, схема) у нового отчёта пусты
    # по построению: форм у него ещё нет, ссылаться не на что.
    "Отчет": KindSchema(
        "Report", "Reports", "Report", [
            Field("имя", "Name", TEXT),
            Field("синоним", "Synonym", MULTILANG, always=True),
            Field("комментарий", "Comment", TEXT, always=True),
            Field("стандартныеКоманды", "UseStandardCommands", BOOLEAN, always=True),
            Field("основнаяФорма", "DefaultForm", TEXT, always=True),
            Field("дополнительнаяФорма", "AuxiliaryForm", TEXT, always=True),
            # Обозначение объекта, а не текст: конфигуратор пишет
            # `Report.Имя.Template.Макет`, все 417 отчётов корпуса.
            # Текстом поле приняло бы дословно что дали — и русскую форму,
            # и английскую, обе молча.
            Field("основнаяСхема", "MainDataCompositionSchema",
                  OBJECT_REFERENCE, always=True),
            Field("основнаяФормаНастроек", "DefaultSettingsForm", TEXT, always=True),
            Field("дополнительнаяФормаНастроек", "AuxiliarySettingsForm", TEXT,
                  always=True),
            Field("основнаяФормаВарианта", "DefaultVariantForm", TEXT, always=True),
            Field("дополнительнаяФормаВарианта", "AuxiliaryVariantForm", TEXT,
                  always=True),
            Field("хранилищеВариантов", "VariantsStorage", TEXT, always=True),
            Field("хранилищеНастроек", "SettingsStorage", TEXT, always=True),
            Field("включатьСправкуВСодержание", "IncludeHelpInContents", BOOLEAN,
                  always=True),
            Field("расширенноеПредставление", "ExtendedPresentation", MULTILANG,
                  always=True),
            Field("пояснение", "Explanation", MULTILANG, always=True),
        ],
        satellites=(Satellite("Templates/{схема}.xml", "схема", render="макет",
                              fields=("синонимСхемы",)),
                    Satellite("Templates/{схема}/Ext/Template.xml", "схема",
                              render="схема")),
        generated=GENERATED_TYPES["Отчет"], children=True,
        named_children=(("схема", "Template"),),
        child_fields=(("реквизиты", "Реквизит"),
                      ("табличныеЧасти", "ТабличнаяЧасть"))),
    # Пункты настроек варианта. Тег у всех один — `item`, вид задаётся
    # `xsi:type`; поэтому и контейнер приходится называть отдельно.
    # Порядок свойств снят по 901 схеме: 6023 выбираемых поля, 2139 отборов,
    # 830 полей порядка, 1219 группировок — без единого противоречия.
    "ВыбираемоеПоле": KindSchema(
        "dcsset:item", None, None, [
            Field("использование", "dcsset:use", BOOLEAN, omit_when=True),
            Field("поле", "dcsset:field", TEXT),
            # А здесь тип не пишется, и это тоже замер: `dcsset:title`
            # у выбираемого поля голый во всех 484 случаях. Правило не общее
            # «в схеме всё с типом», а по элементу — потому и замерялось
            # поэлементно.
            Field("заголовок", "dcsset:title", TEXT),
        ],
        wrapped=False, inside=("dcsset:settings", "dcsset:selection"),
        attrs=(("xsi:type", "dcsset:SelectedItemField"),)),
    "Отбор": KindSchema(
        "dcsset:item", None, None, [
            Field("использование", "dcsset:use", BOOLEAN, omit_when=True),
            Field("левое", "dcsset:left", TEXT,
                  attrs={"xsi:type": "dcscor:Field"}),
            Field("видСравнения", "dcsset:comparisonType", TEXT,
                  dictionary=COMPARISON),
            Field("правое", "dcsset:right", TYPED_VALUE),
            Field("представление", "dcsset:presentation", TEXT,
                  attrs={"xsi:type": "xs:string"}),
        ],
        wrapped=False, inside=("dcsset:settings", "dcsset:filter"),
        attrs=(("xsi:type", "dcsset:FilterItemComparison"),)),
    "ПолеПорядка": KindSchema(
        "dcsset:item", None, None, [
            Field("использование", "dcsset:use", BOOLEAN, omit_when=True),
            Field("поле", "dcsset:field", TEXT),
            Field("направление", "dcsset:orderType", TEXT,
                  dictionary=ORDER_DIRECTION),
        ],
        wrapped=False, inside=("dcsset:settings", "dcsset:order"),
        attrs=(("xsi:type", "dcsset:OrderItemField"),)),
    "ГруппировкаСтруктуры": KindSchema(
        "dcsset:item", None, None, [
            Field("использование", "dcsset:use", BOOLEAN, omit_when=True),
            Field("имя", "dcsset:name", TEXT),
            # Порядок детей выведен топологической сортировкой по 2507
            # группировкам, без противоречий: use → name → groupItems →
            # filter → order → selection → … .
            #
            # А вот `order` и `selection` здесь НЕ пишутся, хотя есть у всех
            # 2507 группировок корпуса. Вывод «раз у всех — значит часть
            # формы записи» неверен, и опровергает его опыт: записанная
            # инструментом группировка из одного имени проходит круг «загрузили
            # → выгрузили» и возвращается от платформы без правок. Значит эти
            # разделы платформа заводит сама, когда вариант настроек начинают
            # править, — они признак настроенной группировки, а не свежесозданной.
            #
            # Правило общее: универсальное значение в корпусе — сильная улика,
            # но опыт с платформой сильнее. Корпус показывает, какими объекты
            # становятся, а не какими рождаются.
        ],
        wrapped=False, inside=("dcsset:settings",),
        attrs=(("xsi:type", "dcsset:StructureItemGroup"),)),
    # Вариант настроек. Нужен прежде всего для адресации: пункты настроек
    # лежат внутри него. Порядок снят с 1369 вариантов конфигурации.
    "ВариантНастроек": KindSchema(
        "settingsVariant", None, None, [
            Field("имя", "dcsset:name", TEXT),
            # Голых `presentation` в конфигурации 0 из 2080.
            Field("представление", "dcsset:presentation", TEXT,
                  attrs={"xsi:type": "xs:string"}),
        ], wrapped=False),
}
