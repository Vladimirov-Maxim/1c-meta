"""Форма как понятие: назначение, главный реквизит, элементы, реквизиты,
команды — и правки над всем этим.

Здесь нет ни тегов, ни файлов, ни версии формата. Форма описана теми словами,
которыми её описывает разработчик в конфигураторе и в коде доработки формы:
«поле ввода», «группа формы», «родитель», «переместить перед», «путь к
данным», «обработчик». Во что это превращается
на диске — дело реализации формата (`infra/forms`), и у каждой версии
формата своя реализация. Домен, сценарии и разбор задания о версии не знают.

Что здесь замерено, а не придумано (выгрузка крупной типовой конфигурации,
11 042 формы):

* главный реквизит определяется назначением формы — у формы документа это
  «Объект» типа «ДокументОбъект», у формы списка — «Список» типа
  «ДинамическийСписок», у формы записи регистра — «Запись» типа «МенеджерЗаписи»;
* в форме объекта стандартные реквизиты привязываются английскими именами
  («Объект.Number» — 594 формы, «Объект.Номер» — 0), собственные — своими;
* имена элементов уникальны в пределах формы: 350 065 элементов, ноль
  повторов; спутники (контекстное меню, подсказка) живут в том же пространстве;
* видов элементов 29, девять покрывают 92,7 % корпуса.

Свойства элементов — `form_properties.py`: русское имя, английское имя,
вид значения, умолчание; снято со справочника проекта «Накидка».
"""

import re
from typing import NamedTuple

from .conventions import НЕЙТРАЛЬНЫЕ, КодФорм
from .form_dialect import ПЛАТФОРМА as ПЛАТФОРМА_ДИАЛЕКТ
from .form_dialect import CodeProcedure  # noqa: F401 — часть интерфейса модуля
from .form_events import EVENTS, kinds_with
from .form_properties import ENUMS, PROPERTIES
from .model import BooleanType, Finding, NumberType, PlatformType, Refuse, TypeRef, запись_типа
from .platform import STANDARD_ATTRIBUTES, STANDARD_ATTRIBUTES_RU

#: Имя, каким платформа принимает идентификаторы: буквы, цифры, подчёркивание,
#: не с цифры. Кириллица и латиница равноправны.
IDENTIFIER = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*$")


def is_identifier(text):
    return bool(text) and bool(IDENTIFIER.match(text))


# --- назначение формы ------------------------------------------------------

#: Назначение формы — ровно то, что предлагает мастер форм конфигуратора,
#: и от него зависит всё рождённое: главный реквизит, свойства корня формы
#: и слот «основная форма» в карточке хозяина.
#:
#: Поля: у каких видов хозяина такое назначение бывает; главный реквизит
#: (имя, грань типа хозяина — или платформенный тип); свойство хозяина,
#: которое получает ссылку на форму, когда она назначена основной.
ASSIGNMENTS = {
    "Документа": {"хозяева": ("Документ",), "главный": ("Объект", "Объект"),
                  "основная": "основнаяФормаОбъекта"},
    "Элемента": {"хозяева": ("Справочник",), "главный": ("Объект", "Объект"),
                 "основная": "основнаяФормаОбъекта"},
    "Группы": {"хозяева": ("Справочник",), "главный": ("Объект", "Объект"),
               "основная": "основнаяФормаГруппы"},
    "Списка": {"хозяева": ("Документ", "Справочник", "РегистрСведений",
                           "РегистрНакопления", "Перечисление"),
               "главный": ("Список", "ДинамическийСписок"),
               "основная": "основнаяФормаСписка"},
    "Выбора": {"хозяева": ("Документ", "Справочник", "Перечисление"),
               "главный": ("Список", "ДинамическийСписок"),
               "основная": "основнаяФормаВыбора"},
    "ВыбораГруппы": {"хозяева": ("Справочник",),
                     "главный": ("Список", "ДинамическийСписок"),
                     "основная": "основнаяФормаВыбораГруппы"},
    "Записи": {"хозяева": ("РегистрСведений",), "главный": ("Запись", "МенеджерЗаписи"),
               "основная": "основнаяФормаЗаписи"},
    "Обработки": {"хозяева": ("Обработка",), "главный": ("Объект", "Объект"),
                  "основная": "основнаяФорма"},
    "Отчета": {"хозяева": ("Отчет",), "главный": ("Отчет", "Объект"),
               "основная": "основнаяФорма"},
    "Произвольная": {"хозяева": None, "главный": None, "основная": None},
}

#: Назначение по стандартному имени формы — так его выводит мастер, когда
#: человек не назвал назначение сам. «Форма» у обработки и у отчёта — разные
#: назначения, поэтому имя одно, а ответ зависит от вида хозяина.
ASSIGNMENT_BY_NAME = {
    "ФормаДокумента": "Документа", "ФормаЭлемента": "Элемента", "ФормаГруппы": "Группы",
    "ФормаСписка": "Списка", "ФормаВыбора": "Выбора", "ФормаВыбораГруппы": "ВыбораГруппы",
    "ФормаЗаписи": "Записи",
}
ASSIGNMENT_BY_OWNER_KIND = {"Обработка": "Обработки", "Отчет": "Отчета"}

DYNAMIC_LIST = "ДинамическийСписок"
LIST_ASSIGNMENTS = ("Списка", "Выбора", "ВыбораГруппы")


def assignment_for(form_name, owner_kind, said=None):
    """Назначение формы: названное, иначе по имени формы, иначе по хозяину."""
    if said:
        if said not in ASSIGNMENTS:
            raise Refuse(f"не знаю назначения «{said}»; известны: "
                         + ", ".join(ASSIGNMENTS))
        return said
    if owner_kind is None:
        return "Произвольная"
    if form_name in ASSIGNMENT_BY_NAME:
        return ASSIGNMENT_BY_NAME[form_name]
    if form_name == "Форма" and owner_kind in ASSIGNMENT_BY_OWNER_KIND:
        return ASSIGNMENT_BY_OWNER_KIND[owner_kind]
    return "Произвольная"


# --- составляющие формы ----------------------------------------------------

class FormAttribute:
    """Реквизит формы: имя, тип, заголовок, колонки (у таблиц значений).

    `table` — имя реквизита-таблицы, чьей колонкой этот реквизит является
    (у колонки, заведённой кодом, это её путь). Главный реквизит от прочих
    отличается признаком: у него тип задан назначением, а не человеком.
    """

    def __init__(self, name, value_type, title=None, columns=(), main=False, table=None):
        self.name = name
        self.value_type = value_type
        self.title = title
        self.columns = list(columns)
        self.main = main
        self.table = table

    def __repr__(self):
        return f"FormAttribute({self.name!r}, {self.value_type!r})"


class FormCommand:
    """Команда формы: имя, заголовок, обработчик (по умолчанию — имя команды).

    Так именует и конфигуратор: у 48 259 команд из 54 139 обработчик зовётся
    как команда.
    """

    def __init__(self, name, title=None, action=None):
        self.name = name
        self.title = title
        self.action = action or name


#: Виды элементов, которые инструмент умеет заводить — в XML и кодом на обоих
#: языках; полный перечень видов платформы — ключи `PROPERTIES`.
#: `Кнопка` в командной панели и вне её — один вид, реализация решает сама.
ELEMENT_KINDS = ("ПолеВвода", "ПолеФлажка", "ПолеНадписи", "ПолеКартинки",
                 "ПолеПереключателя", "Надпись", "Картинка", "ГруппаФормы",
                 "Страницы", "Страница", "ГруппаКолонок", "КоманднаяПанель",
                 "ГруппаКнопок", "Кнопка", "ТаблицаФормы")

def is_ours(owner_name, form_name, приставка=None):
    """Своя ли это форма. Своя — когда объект или сама форма названы с
    приставкой доработок команды: форма с приставкой в чужом объекте — законный
    и нередкий приём. Без соглашения о приставке
    своё от типового не отличить, и правило «типовая — только кодом» не
    применяется: форма считается своей. `приставка` — строка или кортеж своих
    приставок."""
    if not приставка:
        return True
    return (owner_name or "").startswith(приставка) or (form_name or "").startswith(приставка)


#: Приставка процедур, которые подключает код (#std492): без неё
#: обработчик, назначенный кодом, проверка конфигурации считает
#: неиспользуемым.
HANDLER_PREFIX = "Подключаемый_"


def code_handler_name(handler):
    """Имя процедуры, которую подключает код формы, — с приставкой «Подключаемый_».

    Одно правило на всех, кто это имя называет: код формы, заготовку
    процедуры и показ задания: показ без приставки уводил бы к процедуре,
    которой в модуле не будет. Действие команды код назначает так же
    программно, поэтому правило и для него.
    """
    return handler if handler.startswith(HANDLER_PREFIX) else HANDLER_PREFIX + handler


#: Виды, у которых бывают дети, — включая те, что инструмент не заводит,
#: но в которые кладёт: автоматическая командная панель формы и таблицы
#: читается как «КоманднаяПанель», контекстное меню — как есть.
CONTAINER_KINDS = ("ГруппаФормы", "Страницы", "Страница", "КоманднаяПанель",
                   "ГруппаКнопок", "Подменю", "КонтекстноеМеню", "ГруппаКолонок",
                   "ТаблицаФормы")

#: Командная панель, с которой форма рождается: в неё кладут кнопки тем же
#: заданием, которым форму заводят. Имя — то, что пишет инструмент; у форм,
#: выгруженных конфигуратором на английском, она «FormCommandBar» (57 из 11 035).
FORM_COMMAND_BAR = "ФормаКоманднаяПанель"

#: Вместилища, с которыми рождается таблица формы: (суффикс имени, вид).
#: Без них кнопка в панель таблицы, заводимой тем же заданием, получала бы
#: «родителя нет» — как и кнопка в панель новой формы.
TABLE_CONTAINERS = (("КоманднаяПанель", "КоманднаяПанель"), ("КонтекстноеМеню", "КонтекстноеМеню"))

#: Виды, которым нужна привязка к данным.
BOUND_KINDS = ("ПолеВвода", "ПолеФлажка", "ПолеНадписи", "ТаблицаФормы")

#: Куда можно положить страницу — только в страницы.
REQUIRED_PARENT = {"Страница": ("Страницы",)}


class FormElement:
    """Элемент формы: вид, имя, привязка, где стоит, свойства, события, дети.

    `parent` — имя элемента-родителя, `None` — корень формы; `before`/`after` —
    имя соседа, перед которым или после которого встать; ни то ни другое —
    в конец родителя. В коде формы это `Элементы.Вставить(…, Родитель, Перед)`
    платформы или то же словами диалекта команды.

    `properties` — свойства платформы по русским именам (`form_properties`),
    значения — как в задании: булево, число, строка, русское слово
    перечисления. Проверяются `check_property`, переводятся реализацией.

    `events` — событие -> имя обработчика. `command` — у кнопки: имя команды
    формы или «Стандартная.Имя».
    """

    def __init__(self, kind, name, path=None, parent=None, before=None, after=None,
                 properties=None, events=None, command=None, children=(), column=None):
        if kind not in ELEMENT_KINDS:
            from .form_properties import PROPERTIES

            # Вид платформы, которого инструмент не заводит, — не опечатка:
            # отказ «не знаю вида» читался бы именно так.
            if kind in PROPERTIES:
                raise Refuse(f"вид «{kind}» в платформе есть, но заводить его инструмент не "
                             f"умеет — только показывает; заводит: " + ", ".join(ELEMENT_KINDS))
            raise Refuse(f"не знаю вида элемента «{kind}»; умею: "
                         + ", ".join(ELEMENT_KINDS))
        self.kind = kind
        self.name = name
        self.path = path
        #: у колонки таблицы — имя колонки внутри таблицы; путь достраивается
        #: от пути таблицы, когда тот разрешён (`bind_paths`)
        self.column = column
        #: вид не называли — подставлен умолчанием, и `bind_paths` вправе его
        #: уточнить: колонка динамического списка показывает, а не правит
        self.kind_defaulted = False
        self.parent = parent
        self.before = before
        self.after = after
        self.properties = dict(properties or {})
        self.events = dict(events or {})
        self.command = command
        self.children = list(children)
        for child in self.children:
            child.parent = name

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def title(self):
        return self.properties.get("Заголовок")

    def __repr__(self):
        return f"FormElement({self.kind!r}, {self.name!r}, path={self.path!r})"


class Form:
    """Новая форма целиком: чья, какая, с чего рождается.

    `owner` — пара (вид, имя) хозяина или `None` у общей формы;
    `assignment` — ключ `ASSIGNMENTS`; `default` — назначить основной.
    Содержимое (реквизиты, элементы, команды) приходит правками той же
    формы: рождение и наполнение — две операции над одним документом.
    """

    def __init__(self, name, owner=None, assignment=None, synonym=None,
                 default=False, title=None):
        self.name = name
        self.owner = tuple(owner) if owner else None
        self.assignment = assignment_for(name, self.owner_kind, assignment)
        self.synonym = synonym
        self.default = default
        self.title = title

    @property
    def owner_kind(self):
        return self.owner[0] if self.owner else None

    @property
    def owner_name(self):
        return self.owner[1] if self.owner else None

    @property
    def main_attribute(self):
        """Главный реквизит по назначению; `None` у произвольной формы."""
        described = ASSIGNMENTS[self.assignment]["главный"]
        if described is None:
            return None
        name, facet = described
        if facet == DYNAMIC_LIST:
            value_type = PlatformType(DYNAMIC_LIST)
        else:
            value_type = TypeRef(self.owner_kind, self.owner_name, facet)
        return FormAttribute(name, value_type, main=True)

    @property
    def default_slot(self):
        """Свойство хозяина, куда пишется ссылка на основную форму."""
        return ASSIGNMENTS[self.assignment]["основная"]


class ViewItem(NamedTuple):
    """Элемент прочитанной формы. Проверкам хватает пары «вид и родитель», а
    показу — нет: надо видеть, к чему элемент привязан и что на нём висит.
    Пара — первые два поля, и проверки, которым нужна только она, читают
    их как пару."""

    kind: str
    parent: str = None
    path: str = None
    command: str = None
    events: tuple = ()
    #: спутник — то, что платформа заводит сама: контекстное меню,
    #: расширенная подсказка, дополнения таблицы. Их на корпусе 262 218
    #: подсказок и 155 541 меню против 350 065 элементов, то есть в показе
    #: они и были бы большей частью вывода
    satellite: bool = False
    #: группировка подчинённых, если задана явно: «Горизонтальная»…
    layout: str = None


class FormView:
    """Что уже есть в форме — ответ порта чтения, словами домена.

    `elements` — имя -> `ViewItem`; `order` — имена в порядке документа,
    чтобы показать форму такой, какой её увидит человек; `attributes` — имя ->
    тип домена (или `None`, если тип не выражается); `commands` — имена;
    `events` — событие -> обработчик; `main` — имя главного реквизита.
    """

    def __init__(self, owner, name, elements=None, attributes=None, commands=(),
                 events=None, main=None, assignment="Произвольная", dynamic_lists=(),
                 order=(), commands_actions=None):
        self.owner = tuple(owner) if owner else None
        self.name = name
        self.elements = dict(elements or {})
        self.attributes = dict(attributes or {})
        self.commands = set(commands)
        self.events = dict(events or {})
        self.main = main
        self.assignment = assignment
        #: имена реквизитов формы, которые суть динамические списки. Отдельно
        #: от типов: от этого зависит и вид колонки (список показывают, а не
        #: правят), и состав рождённого у таблицы.
        self.dynamic_lists = set(dynamic_lists)
        #: имена элементов в порядке документа — для показа
        self.order = list(order) or list(self.elements)
        #: команда -> обработчик, если прочитан
        self.commands_actions = dict(commands_actions or {})
        #: имена процедур модуля формы; None — модуля нет или он не прочитан
        self.procedures = None

    @property
    def owner_kind(self):
        return self.owner[0] if self.owner else None

    @property
    def owner_name(self):
        return self.owner[1] if self.owner else None


class FormEdits:
    """Правки одной формы: что добавить и что убрать.

    `create` — `Form`, если форму надо сначала родить; иначе форма должна
    существовать. Порядок применения: удаления, реквизиты, команды,
    элементы (в порядке перечисления), события формы.
    """

    def __init__(self, owner, name, create=None, attributes=(), commands=(),
                 elements=(), events=None, remove_elements=(), remove_attributes=(),
                 remove_commands=(), as_code=False, code_module=None, code_procedure=None):
        self.owner = tuple(owner) if owner else None
        self.name = name
        self.create = create
        self.attributes = list(attributes)
        self.commands = list(commands)
        self.elements = list(elements)
        self.events = dict(events or {})
        self.remove_elements = list(remove_elements)
        self.remove_attributes = list(remove_attributes)
        self.remove_commands = list(remove_commands)
        self.as_code = as_code
        # Куда ляжет процедура кода формы: общий модуль и её имя. Без
        # модуля вызов выдаётся с заглушкой «<Модуль>», и модуль, его
        # контекст и свободное имя приходится искать самому.
        self.code_module = code_module
        self.code_procedure = code_procedure

    @property
    def code_procedure_name(self):
        """Имя процедуры кода формы: заданное или «<Форма>_ПриСозданииНаСервере»."""
        return self.code_procedure or f"{self.name}_ПриСозданииНаСервере"

    @property
    def code_module_name(self):
        """Имя общего модуля без «ОбщийМодуль.» — или `None`, если не задан."""
        if not self.code_module:
            return None
        return self.code_module.removeprefix("ОбщийМодуль.")

    @property
    def owner_kind(self):
        return self.owner[0] if self.owner else None

    @property
    def owner_name(self):
        return self.owner[1] if self.owner else None

    @property
    def address(self):
        owner = f"{self.owner_kind}.{self.owner_name}" if self.owner else "Общая"
        return f"{owner}.{self.name}"

    def all_elements(self):
        for element in self.elements:
            yield from element.walk()

    def is_empty(self):
        return not (self.attributes or self.commands or self.elements or self.events
                    or self.remove_elements or self.remove_attributes
                    or self.remove_commands or self.create)


# --- свойства -----------------------------------------------------------------

BOOLEAN_WORDS = {"Истина": True, "Ложь": False, "true": True, "false": False}


def property_of(kind, name):
    """Свойство вида по русскому или английскому имени: (русское, английское,
    вид значения, умолчание). `None` — у вида такого свойства нет."""
    table = PROPERTIES.get(kind, {})
    if name in table:
        return (name,) + table[name]
    for russian, described in table.items():
        if described[0] == name:
            return (russian,) + described
    return None


def check_property(kind, name, value):
    """Проверить и привести значение свойства. Возвращает (русское имя,
    английское имя, вид значения, приведённое значение) или поднимает отказ.

    Булево принимает и слова «Истина»/«Ложь»; перечисление — русское или
    английское слово из списка; число — число; строка — строку.
    Свойства со своей структурой (шрифт, цвет, картинка, сочетание клавиш)
    инструмент не выражает и говорит об этом, а не пишет наугад.
    """
    found = property_of(kind, name)
    if found is None:
        known = ", ".join(sorted(PROPERTIES.get(kind, {})))
        raise Refuse(f"у вида «{kind}» нет свойства «{name}»; есть: {known}")
    russian, english, value_kind, _ = found
    if value_kind in KIND_ITSELF:
        # Вид поля, группы и декорации — это и есть вид элемента, а не его
        # свойство: без этой ветки попытка «ПолеВвода со свойством Вид»
        # получала бы отказ про внутренний тег выгрузки.
        raise Refuse(f"«{russian}» у вида «{kind}» — это сам вид элемента: он задаётся ключом "
                     "«вид» элемента (ПолеВвода, ПолеФлажка, Надпись…), а не свойством")
    if value_kind in ("Булево", "БулевоНеопределено"):
        if isinstance(value, str) and value in BOOLEAN_WORDS:
            value = BOOLEAN_WORDS[value]
        if not isinstance(value, bool):
            raise Refuse(f"свойство «{russian}» булево, получено {value!r}")
        return russian, english, value_kind, value
    if value_kind == "Число":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise Refuse(f"свойство «{russian}» числовое, получено {value!r}")
        return russian, english, value_kind, value
    if value_kind == "Строка":
        if not isinstance(value, str):
            raise Refuse(f"свойство «{russian}» строковое, получено {value!r}")
        return russian, english, value_kind, value
    values = ENUMS.get(value_kind)
    if values is not None:
        if value in values:
            return russian, english, value_kind, value
        for ru, en in values.items():
            if en == value:
                return russian, english, value_kind, ru
        raise Refuse(f"у свойства «{russian}» не бывает значения {value!r}; "
                     f"допустимо: {', '.join(values)}")
    if value_kind == "Картинка":
        return russian, english, value_kind, _picture(russian, value)
    if value_kind == "СписокЗначений":
        return russian, english, value_kind, _value_list(russian, value)
    # Совет «правится в конфигураторе» для типовой формы противоречил бы
    # правилу: её правят только кодом.
    raise Refuse(f"свойство «{russian}» ({value_kind}) имеет собственную структуру "
                 "и заданием не выражается — у своей формы его ставят в конфигураторе, "
                 "у типовой дописывают его установку в код руками")


#: Типы реквизитов, которые показывает только своё поле.
DOCUMENT_FIELDS = {
    "ТабличныйДокумент": "ПолеТабличногоДокумента",
    "ТекстовыйДокумент": "ПолеТекстовогоДокумента",
    "ФорматированныйДокумент": "ПолеФорматированногоДокумента",
    "ГрафическаяСхема": "ПолеГрафическойСхемы",
    "ГеографическаяСхема": "ПолеГеографическойСхемы",
    "Диаграмма": "ПолеДиаграммы",
    "ДиаграммаГанта": "ПолеДиаграммыГанта",
    "Дендрограмма": "ПолеДендрограммы",
    "Планировщик": "ПолеПланировщика",
}

#: Свойство «Вид», которое и есть вид элемента: у поля, группы, декорации.
#: У кнопки «Вид» — настоящее свойство (обычная, гиперссылка, командной панели).
KIND_ITSELF = ("ВидПоляФормы", "ВидГруппыФормы", "ВидДекорацииФормы")


def expressible(value_kind):
    """Выражается ли значение свойства заданием на форму."""
    return (value_kind in ("Булево", "БулевоНеопределено", "Число", "Строка",
                           "Картинка", "СписокЗначений")
            or (value_kind in ENUMS and value_kind not in KIND_ITSELF))


#: Откуда бывает картинка: библиотека картинок конфигурации и стандартные
#: картинки платформы. Английские приставки выгрузки принимаются наравне с
#: русскими словами — их привычно копировать из готовой формы.
PICTURE_SOURCES = {"БиблиотекаКартинок": "БиблиотекаКартинок",
                   "СтандартнаяКартинка": "СтандартнаяКартинка",
                   "CommonPicture": "БиблиотекаКартинок",
                   "StdPicture": "СтандартнаяКартинка"}


def _picture(russian, value):
    """«БиблиотекаКартинок.ЗначокОшибки» -> ("БиблиотекаКартинок", "ЗначокОшибки").

    Встроенная в форму двоичная картинка (в выгрузке `Abs`) заданием не
    выражается: её 260 на корпус против 27 797 ссылок, и содержимое её —
    картинка, а не имя.
    """
    if not isinstance(value, str) or value.count(".") != 1:
        raise Refuse(f"свойство «{russian}» — картинка вида "
                     f"«БиблиотекаКартинок.Имя» или «СтандартнаяКартинка.Имя», "
                     f"получено {value!r}")
    источник, имя = value.split(".")
    if источник not in PICTURE_SOURCES or not имя:
        raise Refuse(f"у картинки «{value}» непонятный источник «{источник}»; "
                     f"бывает: {', '.join(sorted(set(PICTURE_SOURCES.values())))}")
    return PICTURE_SOURCES[источник], имя


def _value_list(russian, value):
    """Список выбора: [{значение, представление}] -> ((значение, представление), …).

    Значение бывает числом, строкой, булевым и значением перечисления
    («Перечисление.ОтражениеВУСН.Принимаются»); представление
    необязательно — платформа тогда покажет само значение.
    """
    if not isinstance(value, (list, tuple)) or not value:
        raise Refuse(f"свойство «{russian}» — непустой список элементов вида "
                     f"{{«значение»: …, «представление»: …}}, получено {value!r}")
    итог = []
    for item in value:
        if not isinstance(item, dict) or "значение" not in item:
            raise Refuse(f"в списке «{russian}» ожидался элемент со «значение», "
                         f"получено {item!r}")
        лишнее = set(item) - {"значение", "представление"}
        if лишнее:
            raise Refuse(f"в элементе списка «{russian}» лишние ключи: "
                         f"{', '.join(sorted(лишнее))}")
        знач = item["значение"]
        if isinstance(знач, str) and знач.startswith("Перечисление."):
            if знач.count(".") != 2:
                raise Refuse(f"значение перечисления пишется «Перечисление.Вид.Значение», "
                             f"получено {знач!r}")
        elif not isinstance(знач, (bool, int, float, str)):
            raise Refuse(f"значением списка «{russian}» бывает число, строка, булево "
                         f"или значение перечисления, получено {знач!r}")
        представление = item.get("представление")
        if представление is not None and not isinstance(представление, str):
            raise Refuse(f"представление в списке «{russian}» — строка, "
                         f"получено {представление!r}")
        итог.append((знач, представление))
    return tuple(итог)


# --- привязки ----------------------------------------------------------------

def _без_ё(text):
    return (text or "").replace("ё", "е").replace("Ё", "Е")


#: Соответствие русских и английских имён стандартных реквизитов — те, что
#: бывают в привязках форм.
STANDARD_PAIRS = {
    "Ссылка": "Ref", "Код": "Code", "Наименование": "Description",
    "ПометкаУдаления": "DeletionMark", "Родитель": "Parent", "Владелец": "Owner",
    "ЭтоГруппа": "IsFolder", "Предопределенный": "Predefined",
    "ИмяПредопределенныхДанных": "PredefinedDataName", "НомерСтроки": "LineNumber",
    "Дата": "Date", "Номер": "Number", "Проведен": "Posted",
    "Период": "Period", "Регистратор": "Recorder", "Активность": "Active",
    "Порядок": "Order",
}


def standard_attribute_name(owner_kind, said):
    """«Номер» -> «Number», «Проведён»/«Проведен» -> «Posted». `None` — у этого
    вида такого стандартного реквизита нет."""
    russian = {_без_ё(r) for r in STANDARD_ATTRIBUTES_RU.get(owner_kind, ())}
    plain = _без_ё(said)
    if plain in russian and plain in STANDARD_PAIRS:
        english = STANDARD_PAIRS[plain]
        if english in STANDARD_ATTRIBUTES.get(owner_kind, ()):
            return english
    return None


def russian_standard_name(owner_kind, english):
    """Обратно: «Number» -> «Номер». `None` — не стандартный реквизит вида."""
    if english not in STANDARD_ATTRIBUTES.get(owner_kind, ()):
        return None
    for russian, name in STANDARD_PAIRS.items():
        if name == english:
            return russian
    return None


def resolve_path(said, owner_kind, main_name, assignment, form_attributes):
    """Привязка из задания -> привязка выгрузки.

    1. точечный путь — как есть, только стандартный реквизит хозяина после
       главного реквизита переводится («Объект.Номер» -> «Объект.Number»);
    2. имя реквизита формы — голым;
    3. у формы с главным реквизитом — «<главный>.<имя>» с тем же переводом;
    4. иначе — отказ: привязать не к чему.
    """
    if not said:
        raise Refuse("у элемента нет привязки")
    if "." in said:
        head, _, rest = said.partition(".")
        if main_name and head == main_name and "." not in rest and assignment not in LIST_ASSIGNMENTS:
            return f"{head}.{standard_attribute_name(owner_kind, rest) or rest}"
        return said
    if said in form_attributes or said == main_name:
        # Сам главный реквизит — законная привязка: к нему привязывают
        # таблицу динамического списка в форме списка.
        return said
    if main_name is None:
        raise Refuse(f"«{said}»: у формы нет главного реквизита, а реквизита формы "
                     "с таким именем нет — привязать не к чему")
    # И в форме объекта, и в форме списка стандартный реквизит пишется
    # английским именем: платформа при загрузке переписывает «Список.Дата» и
    # «Список.Номер» в `Список.Date` и `Список.Number`.
    return f"{main_name}.{standard_attribute_name(owner_kind, said) or said}"


def bind_paths(edits, view=None):
    """Привязки из задания -> привязки выгрузки.

    Главный реквизит и назначение — у рождаемой формы из неё самой, у
    существующей из прочитанного вида. Реквизиты формы — прочитанные плюс
    добавляемые этим же заданием. Колонка таблицы получает путь от пути
    таблицы, когда тот уже разрешён.
    """
    if edits.create is not None:
        main = edits.create.main_attribute
        main_name = main.name if main else None
        assignment = edits.create.assignment
        attributes = set()
    else:
        main_name = view.main if view else None
        assignment = view.assignment if view else "Произвольная"
        attributes = set(view.attributes) if view else set()
    attributes |= {a.name for a in edits.attributes if a.table is None}
    списки = set(view.dynamic_lists) if view else set()
    if edits.create is not None and assignment in LIST_ASSIGNMENTS and main_name:
        списки.add(main_name)
    for element in edits.all_elements():
        if element.kind not in BOUND_KINDS:
            continue
        if element.path:
            element.path = resolve_path(element.path, edits.owner_kind, main_name,
                                        assignment, attributes)
        по_списку = element.kind == "ТаблицаФормы" and element.path in списки
        for child in element.children:
            if child.column and not child.path and element.path:
                # Стандартное поле и в колонке пишется по-английски: у колонки
                # табличной части это «Объект.Статьи.LineNumber» (эталон),
                # у колонки списка — «Список.Date».
                поле = standard_attribute_name(edits.owner_kind, child.column) or child.column
                child.path = f"{element.path}.{поле}"
            # Динамический список показывают, а не правят: колонка у него —
            # поле-надписи (19 465 колонок корпуса против 1262 полей ввода).
            if по_списку and child.kind_defaulted:
                child.kind = "ПолеНадписи"


def _check_list_field(element, rest, known_paths, field, owner_kind):
    """Поле динамического списка — поле его запроса, а не реквизит объекта.

    У формы, которую заводит инструмент, запрос не задан («ManualQuery» ложь), и поля
    списка — это поля основной таблицы: собственные реквизиты плюс стандартные,
    причём русскими именами наравне с английскими («Список.Дата» 486 форм,
    «Список.Date» 439). У чужой формы запрос может быть и произвольным, и
    тогда полем бывает что угодно, — поэтому здесь предупреждение, а не
    ошибка: платформа такую колонку примет и покажет пустой.
    """
    if known_paths is None:
        return []
    first = rest.split(".")[0]
    known = set(known_paths) | {_без_ё(n) for n in STANDARD_ATTRIBUTES_RU.get(owner_kind, ())}
    if _без_ё(first) in {_без_ё(n) for n in known}:
        return []
    return [Finding("ФОРМА-ПОЛЕ-СПИСКА-НЕ-НАЙДЕНО",
                    f"«{element.name}» показывает поле «{element.path}», а такого поля "
                    "нет ни среди реквизитов хозяина, ни среди стандартных — "
                    "оно должно приходить из запроса списка", field, Finding.WARNING)]


def owner_attribute_names(owner_kind, owner_spec):
    """К чему можно привязаться в форме объекта: свои реквизиты, табличные
    части и стандартные реквизиты вида (по-английски)."""
    names = set(STANDARD_ATTRIBUTES.get(owner_kind, ()))
    for attribute in owner_spec.get("реквизиты") or ():
        names.add(attribute.get("имя"))
    for section in owner_spec.get("табличныеЧасти") or ():
        names.add(section.get("имя"))
    return names


def owner_attribute_type(owner_spec, path):
    """Тип реквизита хозяина по привязке «Объект.Имя» или «Объект.ТЧ.Имя».
    `None` — не нашли (стандартный реквизит или неизвестный)."""
    parts = path.split(".")
    if len(parts) == 2:
        for attribute in owner_spec.get("реквизиты") or ():
            if attribute.get("имя") == parts[1]:
                return attribute.get("тип")
    elif len(parts) == 3:
        for section in owner_spec.get("табличныеЧасти") or ():
            if section.get("имя") == parts[1]:
                for attribute in section.get("реквизиты") or ():
                    if attribute.get("имя") == parts[2]:
                        return attribute.get("тип")
    return None


def is_boolean(value_type):
    return isinstance(value_type, BooleanType)


# --- проверки --------------------------------------------------------------

def check(edits, view=None, owner_spec=None, configuration=None, соглашения=НЕЙТРАЛЬНЫЕ):
    """Инварианты правок формы. Возвращает находки; блокирующие — писать нельзя.

    `view` — что в форме уже есть (у новой формы — `None` или пустой вид);
    `owner_spec` — спецификация хозяина, если прочитана; без неё привязки
    к реквизитам объекта не проверяются, и об этом говорится предупреждением.
    `соглашения` — приставка команды: по ней своё отличается от типового;
    язык кода доработки формы — тоже оттуда.
    """
    findings = []
    kind = edits.owner_kind
    приставка = соглашения.приставка
    приставки = соглашения.приставки or None    # свои — и прежние, и тестовые
    код_форм = соглашения.код_форм
    if edits.owner and not is_ours(edits.owner_name, edits.name, приставки) and not edits.as_code:
        # Правило: типовые формы меняются только программно. Инструмент
        # видит XML типовой формы точно так же, как своей, и молча правил бы
        # её — поэтому правило проверяется здесь, а не оставляется на
        # внимательность человека.
        findings.append(Finding(
            "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ",
            f"«{edits.address}» — типовая форма: ни объект, ни форма не названы "
            f"с «{приставка}». В XML такая форма не правится: типовые формы "
            "меняются только программно. Добавьте в задание «код»: true — "
            "инструмент выдаст фрагмент кода доработки формы для вызова из "
            "ПриСозданииНаСервере", "форма"))
    if edits.as_code:
        findings.extend(_check_code_mode(edits, приставка, код_форм, приставки))
        findings.extend(_check_code_target(edits, configuration, приставка, код_форм, приставки))
    if edits.create is not None:
        findings.extend(_check_birth(edits.create, configuration))
    elif view is None:
        findings.append(Finding("ФОРМА-НЕТ", f"формы «{edits.address}» нет; чтобы завести, "
                                "укажите «создать»", "форма"))
        return findings
    existing_elements = dict(view.elements) if view else {}
    existing_attributes = dict(view.attributes) if view else {}
    existing_commands = set(view.commands) if view else set()
    main_name = (edits.create.main_attribute.name if edits.create and edits.create.main_attribute
                 else (view.main if view else None))
    assignment = edits.create.assignment if edits.create else (view.assignment if view else "Произвольная")

    for name in edits.remove_elements:
        if name not in existing_elements:
            findings.append(Finding("ФОРМА-УДАЛИТЬ-НЕТ", f"элемента «{name}» в форме нет",
                                    "удалить"))
    for name in edits.remove_attributes:
        if name not in existing_attributes:
            findings.append(Finding("ФОРМА-УДАЛИТЬ-НЕТ", f"реквизита «{name}» в форме нет",
                                    "удалитьРеквизиты"))
        elif name == main_name:
            findings.append(Finding("ФОРМА-ГЛАВНЫЙ-НЕ-УДАЛЯЕТСЯ",
                                    f"«{name}» — главный реквизит формы", "удалитьРеквизиты"))
    for name in edits.remove_commands:
        if name not in existing_commands:
            findings.append(Finding("ФОРМА-УДАЛИТЬ-НЕТ", f"команды «{name}» в форме нет",
                                    "удалитьКоманды"))
    elements_after = {n: v for n, v in existing_elements.items() if n not in edits.remove_elements}
    if edits.create is not None:
        elements_after.setdefault(FORM_COMMAND_BAR, ("КоманднаяПанель", None))
    attributes_after = {n: v for n, v in existing_attributes.items()
                        if n not in edits.remove_attributes}
    if edits.create is not None and main_name:
        attributes_after[main_name] = None
    commands_after = existing_commands - set(edits.remove_commands)

    for attribute in edits.attributes:
        if not is_identifier(attribute.name):
            findings.append(Finding("ФОРМА-РЕКВИЗИТ-ИМЯ", f"«{attribute.name}» — не имя",
                                    "реквизиты"))
        elif attribute.name in attributes_after and attribute.table is None:
            findings.append(Finding("ФОРМА-РЕКВИЗИТ-ЗАНЯТ",
                                    f"реквизит «{attribute.name}» в форме уже есть", "реквизиты"))
        if attribute.table and attribute.table not in attributes_after and not any(
                a.name == attribute.table for a in edits.attributes):
            findings.append(Finding("ФОРМА-КОЛОНКА-БЕЗ-ТАБЛИЦЫ",
                                    f"колонка «{attribute.name}» ждёт реквизит-таблицу "
                                    f"«{attribute.table}», а его нет", "реквизиты"))
        if attribute.table is None:
            attributes_after[attribute.name] = attribute.value_type
        # Табличный документ и прочие документы показываются только своим
        # полем, а его инструмент не заводит: без находки реквизит проходил
        # бы, и что показать его нечем, выяснялось бы на следующем шаге.
        тип = getattr(attribute.value_type, "name", None)
        поле = DOCUMENT_FIELDS.get(тип)
        if attribute.table is None and поле and поле not in ELEMENT_KINDS:
            findings.append(Finding(
                "ФОРМА-РЕКВИЗИТ-БЕЗ-ПОЛЯ",
                f"реквизит «{attribute.name}» типа {тип} показывается только элементом {поле}, "
                "а его инструмент не заводит ни в XML, ни кодом формы: без поля реквизит "
                "на форме не виден. Своей форме поле добавляют в конфигураторе, типовой — "
                "кодом в модуле формы (Элементы.Добавить) заданием на код", "реквизиты",
                Finding.WARNING))
    for command in edits.commands:
        if not is_identifier(command.name):
            findings.append(Finding("ФОРМА-КОМАНДА-ИМЯ", f"«{command.name}» — не имя", "команды"))
        elif command.name in commands_after:
            findings.append(Finding("ФОРМА-КОМАНДА-ЗАНЯТА",
                                    f"команда «{command.name}» в форме уже есть", "команды"))
        commands_after.add(command.name)

    known_paths = None
    if owner_spec is not None:
        known_paths = owner_attribute_names(kind, owner_spec)
    for element in edits.all_elements():
        findings.extend(_check_element(element, elements_after, attributes_after,
                                       commands_after, main_name, assignment, known_paths,
                                       kind))
        findings.extend(_check_column_name(element))
        findings.extend(_check_checkbox_type(element, attributes_after, main_name, owner_spec))
        elements_after[element.name] = (element.kind, element.parent)
        if element.kind == "ТаблицаФормы":
            for суффикс, вид in TABLE_CONTAINERS:
                elements_after.setdefault(element.name + суффикс, (вид, element.name))
    if owner_spec is None and edits.owner and any(
            e.path and e.path.startswith((main_name or "") + ".") for e in edits.all_elements()):
        findings.append(Finding("ФОРМА-ПРИВЯЗКИ-НЕ-ПРОВЕРЕНЫ",
                                "карточка хозяина не прочитана — привязки к его реквизитам "
                                "не проверялись", "элементы", Finding.WARNING))
    for handler in edits.events.values():
        if not is_identifier(handler):
            findings.append(Finding("ФОРМА-ОБРАБОТЧИК-ИМЯ", f"«{handler}» — не имя процедуры",
                                    "события"))
    return findings


def _bound_type(path, attributes, main_name, owner_spec):
    """Тип того, к чему привязано поле, — если его можно знать: реквизит
    формы или реквизит хозяина первым уровнем («Объект.Примечание»)."""
    head, _, rest = (path or "").partition(".")
    if not rest:
        return attributes.get(head)
    if head == main_name and owner_spec is not None and "." not in rest:
        for реквизит in owner_spec.get("реквизиты") or []:
            if реквизит.get("имя") == rest:
                return реквизит.get("тип")
    return None


def _check_checkbox_type(element, attributes, main_name, owner_spec):
    """Поле флажка редактирует Булево, Число — только при «ТриСостояния»
    (синтакс-помощник: «Расширение поля формы для поля флажка»). Без этой
    проверки флажок на строковом «Примечании» проходил бы с «замечаний нет»."""
    if element.kind != "ПолеФлажка" or not element.path:
        return []
    тип = _bound_type(element.path, attributes, main_name, owner_spec)
    if тип is None:
        return []
    части = тип if isinstance(тип, (list, tuple)) else [тип]
    if any(isinstance(часть, (BooleanType, NumberType)) for часть in части):
        return []
    return [Finding("ФОРМА-ФЛАЖОК-ТИП",
                    f"«{element.name}» (ПолеФлажка) привязан к «{element.path}» типа "
                    f"{запись_типа(тип)}, а флажок редактирует Булево (Число — при "
                    "«ТриСостояния»): нужен другой вид поля или реквизит Булево", "элементы")]


def _added_names(edits):
    """Имена, которые задание добавляет в форму: элементы, реквизиты, команды."""
    return ([e.name for e in edits.all_elements()]
            + [a.name for a in edits.attributes if a.table is None]
            + [c.name for c in edits.commands])


def _creates(вид, код_форм):
    """Как модуль заводит кодом элемент, реквизит или команду формы — имя первым
    аргументом: вызовами платформы и вызовами языка команды.

    Считается только заводящий вызов: имя в кавычках бывает и у
    «ОписаниеОповещения("мой_…")» (это имя процедуры), и у «Элементы.Найти»
    (это не то место, где элемент заводят). У элементов, реквизитов и команд
    формы имена — разные пространства: поле «Комментарий» и реквизит
    «Комментарий» живут рядом законно.
    """
    шаблоны = [ПЛАТФОРМА_ДИАЛЕКТ.заводящие[вид]]
    диалект = _язык(код_форм).диалект
    if диалект is not ПЛАТФОРМА_ДИАЛЕКТ and диалект.заводящие.get(вид):
        шаблоны.append(диалект.заводящие[вид])
    return "(?:" + "|".join(шаблоны) + ")"


def _added_by_code(edits, lines, where, advice, код_форм=None):
    """Имена задания, которые модуль уже заводит кодом в том же пространстве
    имён формы. Закомментированное не в счёт."""
    findings = []
    for вид, имена in (("элемент", [e.name for e in edits.all_elements()]),
                       ("реквизит", [a.name for a in edits.attributes if a.table is None]),
                       ("команда", [c.name for c in edits.commands])):
        for имя in имена:
            заводит = re.compile(_creates(вид, код_форм) + rf'\s*\(\s*"{re.escape(имя)}"')
            номер = next((n for n, строка in enumerate(lines or [], 1)
                          if not строка.lstrip().startswith("//") and заводит.search(строка)),
                         None)
            if номер:
                findings.append(Finding(
                    "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ",
                    f"{вид} «{имя}» уже заводится кодом {where} (строка {номер}) — второй с тем "
                    f"же именем форма не примет: {advice}", "код"))
    return findings


def _check_code_target(edits, configuration, приставка=None, код_форм=None, приставки=None):
    """Куда ляжет процедура кода формы: модуль есть, серверный, свой, имя в
    нём свободно или занято процедурой, которую можно дополнить. Без модуля —
    совет, какой назвать."""
    findings = []
    if edits.code_procedure is not None and not is_identifier(edits.code_procedure):
        findings.append(Finding("ФОРМА-КОД-ИМЯ", f"«{edits.code_procedure}» — не имя процедуры",
                                "код"))
    # Элементы добавляет кодом и сам модуль формы: если «мой_ИтогоВыдано»
    # заводится в модуле формы, надпись с тем же именем без этой сверки прошла
    # бы с «замечаний нет» — а форма упала бы при открытии. Смотреть только
    # целевой модуль мало.
    строки_формы = (configuration.form_module_lines(edits.owner, edits.name)
                    if configuration is not None else None)
    if configuration is not None:
        findings.extend(_added_by_code(
            edits, строки_формы, "в модуле формы",
            "имя занято элементом, который модуль формы заводит сам, — новому нужно другое",
            код_форм))
    процедура = edits.code_procedure_name
    # Модуль формы уже зовёт процедуру с этим именем — доработка формы есть, и
    # новая процедура с новым вызовом её задвоили бы, а в режиме «код»: true
    # это прошло бы молча.
    вызов = existing_call(строки_формы, процедура)
    модуль = edits.code_module_name
    if модуль is None:
        свой = f"{приставка}{edits.owner_name}" if приставка and edits.owner_name else None
        есть = bool(свой) and configuration is not None and configuration.common_module_exists(свой)
        уже = есть and configuration.handler_arity(свой, процедура) is not None
        findings.append(Finding(
            "ФОРМА-КОД-БЕЗ-МОДУЛЯ",
            "общий модуль для процедуры не назван — вызов выдан с заглушкой «<Модуль>»"
            + (f"; у объекта есть свой модуль «{свой}»" if есть else "")
            + (f", и в нём уже есть процедура «{процедура}» — назовите модуль, и фрагмент "
               "дополнит её" if уже else "")
            + f". Укажите «код»: {{«модуль»: «ОбщийМодуль.{приставка or ''}…»}} — инструмент проверит модуль "
            "и имя процедуры и выдаст готовый вызов", "код", Finding.WARNING))
        if вызов:
            findings.append(_call_exists(вызов, процедура))
        return findings
    if not is_identifier(модуль):
        findings.append(Finding("ФОРМА-КОД-МОДУЛЬ", f"«{edits.code_module}» — не адрес общего "
                                f"модуля: «ОбщийМодуль.{приставка or ''}Имя»", "код"))
        return findings
    if configuration is None:
        return findings
    if not configuration.common_module_exists(модуль):
        findings.append(Finding("ФОРМА-КОД-МОДУЛЬ", f"общего модуля «{модуль}» в выгрузке нет",
                                "код"))
        return findings
    # Одного признака «Сервер» мало: клиент-серверный модуль и модуль вызова
    # сервера прошли бы с «замечаний нет», а в первом серверный код формы не
    # скомпилируется на клиенте, экспорт второго виден клиенту, а форму на
    # сервер не передать.
    флаги = configuration.common_module_flags(модуль)
    if флаги is not None and not флаги.get("сервер"):
        findings.append(Finding(
            "ФОРМА-КОД-МОДУЛЬ-НЕ-СЕРВЕР",
            f"«{модуль}» не серверный: процедуру зовут из ПриСозданииНаСервере, модулю "
            "нужен признак «Сервер»", "код"))
    elif флаги is not None and (флаги.get("клиентУправляемоеПриложение")
                                or флаги.get("глобальный")):
        findings.append(Finding(
            "ФОРМА-КОД-МОДУЛЬ-КЛИЕНТ",
            f"«{модуль}» компилируется и на клиенте: код доработки формы серверный "
            "(элементы и реквизиты формы добавляются только на сервере) — процедуре "
            "место в серверном модуле", "код"))
    elif флаги is not None and флаги.get("вызовСервера"):
        findings.append(Finding(
            "ФОРМА-КОД-МОДУЛЬ-ВЫЗОВ-СЕРВЕРА",
            f"«{модуль}» — модуль вызова сервера: его экспорт виден клиенту, а форму на "
            "сервер не передать — процедуре место в серверном модуле без вызова сервера",
            "код"))
    if приставка and not модуль.startswith(приставки or приставка):
        findings.append(Finding(
            "ФОРМА-КОД-МОДУЛЬ-ТИПОВОЙ",
            f"«{модуль}» — типовой модуль: реализация доработки живёт в своём модуле "
            f"«{приставка}…», в типовом остаётся вызов", "код",
            Finding.WARNING))
    # Совет «назовите иначе» вёл бы в ловушку: повтор той же доработки под
    # другим именем заводит второй элемент с тем же именем.
    # Процедура доработки, которую можно узнать, — не ошибка: новые
    # элементы дописываются в неё, и фрагмент выдаётся для этого места,
    # чтобы не дописывать её руками.
    строки_модуля = configuration.common_module_lines(модуль)
    арность = configuration.handler_arity(модуль, процедура)
    if арность is not None:
        if code_procedure(строки_модуля, процедура, код_форм, арность) is None:
            findings.append(Finding(
                "ФОРМА-КОД-ИМЯ-ЗАНЯТО",
                f"в «{модуль}» метод «{процедура}» уже есть, и процедуры доработки формы "
                f"в нём не узнать ({_признак_процедуры(код_форм)}) — если это та же "
                "доработка, она уже внесена: дополните ту процедуру заданием на код; другое "
                "имя («код»: {«модуль»: …, «процедура»: «…»}) — только для другой доработки",
                "код"))
    elif вызов:
        findings.append(_call_exists(вызов, процедура))
    elif edits.code_procedure:
        # Имя процедуры задано явно — это законный путь для другой доработки
        # той же формы, но и путь задвоить ту же в обход защиты от второго
        # вызова. Предупреждение, а не ошибка.
        обычная = f"{edits.name}_ПриСозданииНаСервере"
        прежний = existing_call(строки_формы, обычная) if обычная != процедура else None
        if прежний:
            findings.append(Finding(
                "ФОРМА-КОД-ВТОРАЯ-ДОРАБОТКА",
                f"модуль формы уже вызывает процедуру доработки «{прежний[1]}.{обычная}» "
                f"(строка {прежний[0]}) — «{процедура}» станет второй доработкой этой формы; "
                f"если это та же доработка, дополните ту: «код»: {{«модуль»: "
                f"«ОбщийМодуль.{прежний[1]}»}} без «процедура»", "код", Finding.WARNING))
    findings.extend(_added_by_code(
        edits, строки_модуля, f"в «{модуль}»",
        "это повтор доработки — элемент уже есть", код_форм))
    return findings


def _call_exists(вызов, процедура):
    строка, модуль = вызов
    return Finding(
        "ФОРМА-КОД-ВЫЗОВ-ЕСТЬ",
        f"модуль формы уже вызывает «{модуль}.{процедура}» (строка {строка}) — доработка формы "
        f"живёт в «{модуль}»: укажите «код»: {{«модуль»: «ОбщийМодуль.{модуль}»}}, и фрагмент "
        "дополнит её процедуру; второй вызов задвоил бы доработку", "код")


def _язык(код_форм):
    """Язык кода формы; без соглашений — методы платформы."""
    return код_форм if код_форм is not None else КодФорм()


def _признак_процедуры(код_форм):
    """По чему узнаётся процедура доработки формы — словами, для отказа."""
    язык = _язык(код_форм)
    return язык.диалект.признак_процедуры(язык.словарь)


def code_procedure(lines, name, код_форм=None, arity=None):
    """Процедура доработки формы `name` в строках модуля — или `None`:
    процедуры нет или дополнять её нечем узнать. Как её узнать, решает язык
    кода (`arity` — сколько параметров у метода, если известно)."""
    from .edits import method_range

    span = method_range(lines or [], name)
    if span is None:
        return None
    язык = _язык(код_форм)
    return язык.диалект.процедура(lines, span, arity, язык.словарь)


def code_addition(text, procedure, код_форм=None):
    """Код формы -> то, что дописывается в существующую процедуру; как —
    решает язык кода."""
    язык = _язык(код_форм)
    строки = text.rstrip("\n").split("\n")
    return "\n".join(язык.диалект.дополнение(строки, procedure, язык.словарь)) + "\n"


def existing_call(lines, procedure):
    """Вызов процедуры доработки в модуле формы: (строка, модуль) или `None`.
    Закомментированный не в счёт."""
    if not procedure:
        return None
    вызов = re.compile(rf"([\wА-Яа-яЁё]+)\s*\.\s*{re.escape(procedure)}\s*\(")
    for number, line in enumerate(lines or [], 1):
        if line.lstrip().startswith("//"):
            continue
        found = вызов.search(line.split("//")[0])
        if found:
            return number, found.group(1)
    return None


class CodePlace(NamedTuple):
    """Куда ложится часть кода формы: вставкой перед строкой `line` модуля
    `module` (адрес задания на код), чей текст — `anchor`. `what` —
    «процедура», «дополнение» (код в существующую процедуру; `variable` — имя,
    которое язык кода держит в процедуре, у кода платформы `None`; `where` —
    куда ложится дополнение, словами языка), «вызов» или «вызов есть»
    (вставлять не нужно)."""

    what: str
    module: str
    line: int
    anchor: str
    variable: str = None
    where: str = None


def form_module_address(address):
    """Адрес формы в заданиях на формы -> адрес её модуля в задании на код."""
    части = address.split(".")
    if части[0] == "Общая" and len(части) == 2:
        return "ОбщаяФорма." + части[1]
    if len(части) == 3:
        return f"{части[0]}.{части[1]}.Форма.{части[2]}"
    return address


def code_anchors(edits, module_lines, form_lines, код_форм=None):
    """Куда ложатся процедура доработки формы и её вызов: (места, пояснения).

    Одни слова «в область, где у модуля лежит программный интерфейс» и «в
    конце ПриСозданииНаСервере» якорей не дают: строки пришлось бы искать
    самому. Места — данными, а не только словами: по ним канал собирает
    готовое задание на код, и двадцать строк процедуры не переносятся руками.
    `None` у строк — модуль не прочитан, о нём ничего не говорится.
    """
    from .edits import method_range
    from .modules import top_regions

    places, notes = [], []
    модуль = edits.code_module_name
    имя = edits.code_procedure_name
    # Процедура доработки уже есть — новые элементы дописываются в неё, а не
    # второй процедурой.
    готовая = (code_procedure(module_lines, имя, код_форм) if модуль and module_lines
               else None)
    if готовая:
        диалект = _язык(код_форм).диалект
        places.append(CodePlace("дополнение", f"ОбщийМодуль.{модуль}", готовая.insert_line,
                                module_lines[готовая.insert_line - 1], готовая.variable,
                                диалект.место_дополнения(готовая)))
        перед = диалект.якорь_дополнения(готовая)
        notes.append(f"процедура «{имя}» в «{модуль}» уже есть (строки {готовая.start}-"
                     f"{готовая.end}) — фрагмент дополняет её: вставкой перед строкой "
                     f"{готовая.insert_line} ({перед}, lines = 0)")
    elif модуль and module_lines is not None:
        область = next((о for о in top_regions(module_lines) if о[0] == "ПрограммныйИнтерфейс"),
                       None)
        if область:
            places.append(CodePlace("процедура", f"ОбщийМодуль.{модуль}", область[2],
                                    module_lines[область[2] - 1]))
            notes.append(f"процедура — вставкой перед строкой {область[2]} модуля «{модуль}» "
                         "(#КонецОбласти области «ПрограммныйИнтерфейс», lines = 0)")
        else:
            notes.append(f"в «{модуль}» нет области «ПрограммныйИнтерфейс» — положите процедуру "
                         "рядом с его экспортными методами")
    if form_lines is not None:
        вызов = existing_call(form_lines, имя)
        метод = method_range(form_lines, "ПриСозданииНаСервере")
        if готовая and вызов and вызов[1] == модуль:
            places.append(CodePlace("вызов есть", form_module_address(edits.address), вызов[0],
                                    form_lines[вызов[0] - 1]))
            notes.append(f"вызов в модуле формы уже есть (строка {вызов[0]}) — второй не нужен")
        elif метод:
            places.append(CodePlace("вызов", form_module_address(edits.address), метод[1],
                                    form_lines[метод[1] - 1]))
            notes.append(f"вызов — вставкой перед строкой {метод[1]} модуля формы (КонецПроцедуры "
                         "у ПриСозданииНаСервере, lines = 0)")
        else:
            notes.append("у формы нет ПриСозданииНаСервере — обработчик события формы "
                         "заводится заданием на код, тоже с метками")
    return places, notes


def placement_notes(edits, view, код_форм=None):
    """Как «после» легло в код формы — словами.

    У кода формы есть только «перед», и «после «Комментарий»» в коде
    становится вставкой перед следующим элементом; без объяснения это
    выглядит ошибкой.
    """
    диалект = _язык(код_форм).диалект
    notes = []
    for element in edits.all_elements():
        if not element.after:
            continue
        следующий, известен = after_as_before(view, element.after)
        if not известен:
            continue
        if следующий:
            # И чем это грозит: код теперь зависит от элемента, которого в
            # задании не было.
            в_коде = диалект.перемещение(следующий)
            notes.append(f"«{element.name}» после «{element.after}»: у кода формы есть только "
                         f"«перед», поэтому в коде {в_коде} — перед "
                         f"следующим за «{element.after}» элементом. Сосед взят по форме в "
                         "выгрузке: элементы, добавленные кодом раньше, в расчёт не входят; "
                         f"уберёт или переименует вендор «{следующий}» — код бросит "
                         "исключение при открытии формы")
        else:
            notes.append(f"«{element.name}» после «{element.after}»: «{element.after}» — "
                         "последний в группе, элемент встанет в её конец сам, перемещать незачем")
    return notes


def after_as_before(view, name):
    """(сосед после элемента `name` в том же родителе, известен ли элемент).

    У кода формы есть только «перед» (`Элементы.Вставить` и его подобия в
    других языках кода), а соседа после элемента инструмент видит в
    прочитанной форме — «после» переводится в «перед». Элемент последний
    в родителе — соседа нет, и перемещать незачем: добавленный встаёт в конец
    родителя сам.
    """
    if view is None or name not in view.elements:
        return None, False
    parent = view.elements[name].parent
    found = False
    for other in view.order:
        if other == name:
            found = True
            continue
        item = view.elements.get(other)
        if found and item is not None and not item.satellite and item.parent == parent:
            return other, True
    return None, True


def _check_code_mode(edits, приставка=None, код_форм=None, приставки=None):
    """Чего программная доработка формы не умеет по устройству платформы."""
    findings = []
    if edits.create is not None:
        findings.append(Finding("ФОРМА-КОД-НЕ-СОЗДАЁТ",
                                "кодом форму не создать — она объект метаданных; "
                                "«код» и «создать» вместе не бывают", "код"))
    if edits.events:
        findings.append(Finding(
            "ФОРМА-КОД-БЕЗ-СОБЫТИЙ",
            "события самой формы кодом не назначаются: это свойства формы, "
            "а не элементов. Обработчик типовой формы вызывается вставкой "
            "в её модуль или подпиской", "события"))
    if edits.remove_elements or edits.remove_attributes or edits.remove_commands:
        findings.append(Finding(
            "ФОРМА-КОД-БЕЗ-УДАЛЕНИЯ",
            "удалить элемент типовой формы кодом нельзя — типовой элемент прячут "
            "свойством «Видимость»", "удалить"))
    # Правило: всё, что добавляется в типовой объект, — с приставкой.
    # Без неё элемент неотличим от вендорского и следующий релиз заведёт
    # такой же — «замечаний нет» на это отвечать нельзя.
    # Ошибка, а не предупреждение: приставка обязательна, и у
    # метаданных то же правило (МД-ПРЕФИКС) — ошибка; предупреждение
    # принималось бы через «accepted».
    if not is_ours(edits.owner_name, edits.name, приставки or приставка):
        чужие = [имя for имя in _added_names(edits) if not имя.startswith(приставки or приставка)]
        if чужие:
            findings.append(Finding(
                "ФОРМА-БЕЗ-ПРИСТАВКИ",
                f"в типовую форму добавляется без приставки «{приставка}»: {', '.join(чужие)} — "
                "всё добавляемое в типовые объекты называется с ней, иначе его не отличить "
                "от вендорского", "имя"))
    # Чего язык кода не выражает из описания — говорит сам язык.
    язык = _язык(код_форм)
    findings.extend(язык.диалект.находки(edits, язык.словарь))
    return findings


def _check_birth(form, configuration):
    findings = []
    hosts = ASSIGNMENTS[form.assignment]["хозяева"]
    if hosts is not None and form.owner_kind not in hosts:
        findings.append(Finding("ФОРМА-НАЗНАЧЕНИЕ-НЕ-ДЛЯ-ВИДА",
                                f"назначение «{form.assignment}» не бывает у вида "
                                f"«{form.owner_kind}»; бывает у: {', '.join(hosts)}", "создать"))
    if not is_identifier(form.name):
        findings.append(Finding("ФОРМА-ИМЯ", f"«{form.name}» — не имя формы", "форма"))
    if form.owner and configuration is not None:
        if configuration.object_exists(form.owner_kind, form.owner_name) is False:
            findings.append(Finding("ФОРМА-ХОЗЯИН-НЕТ",
                                    f"объекта «{form.owner_kind}.{form.owner_name}» нет", "форма"))
    return findings


def _check_column_name(element):
    """Имя колонки с именем таблицы впереди — имя элемента выйдет двойным.

    «имя» колонки — поле в строке таблицы, а имя элемента инструмент собирает
    сам: таблица плюс колонка. Полное имя элемента, переданное вместо поля,
    без этой находки молча дало бы «мой_Строкимой_СтрокиСтатья».
    Предупреждение, а не отказ: поле таблицы может и правда начинаться с её
    имени.
    """
    таблица = element.parent
    if not element.column or not таблица or not element.column.startswith(таблица) \
            or element.column == таблица:
        return []
    поле = element.column[len(таблица):]
    return [Finding("ФОРМА-КОЛОНКА-ИМЯ",
                    f"колонка «{element.column}» таблицы «{таблица}»: «имя» колонки — поле "
                    f"строки (здесь, видимо, «{поле}»), имя элемента инструмент собирает сам — "
                    f"выйдет «{element.name}»", "элементы", Finding.WARNING)]


def _check_element(element, elements, attributes, commands, main_name, assignment,
                   known_paths, owner_kind=None):
    findings = []
    field = "элементы"
    if not is_identifier(element.name):
        findings.append(Finding("ФОРМА-ЭЛЕМЕНТ-ИМЯ", f"«{element.name}» — не имя элемента", field))
    elif element.name in elements:
        findings.append(Finding("ФОРМА-ЭЛЕМЕНТ-ЗАНЯТ",
                                f"элемент «{element.name}» в форме уже есть", field))
    if element.parent is not None and element.parent not in elements:
        findings.append(Finding("ФОРМА-РОДИТЕЛЬ-НЕТ",
                                f"у «{element.name}» родитель «{element.parent}», "
                                "а такого элемента в форме нет", field))
    elif element.parent is not None:
        parent_kind = elements[element.parent][0]
        if parent_kind not in CONTAINER_KINDS and parent_kind is not None:
            findings.append(Finding("ФОРМА-РОДИТЕЛЬ-НЕ-КОНТЕЙНЕР",
                                    f"«{element.parent}» ({parent_kind}) не вмещает детей", field))
    required = REQUIRED_PARENT.get(element.kind)
    if required is not None:
        parent_kind = elements.get(element.parent, (None, None))[0] if element.parent else None
        if parent_kind not in required:
            findings.append(Finding("ФОРМА-МЕСТО-НЕ-ТОГО-ВИДА",
                                    f"«{element.name}» ({element.kind}) кладут только в: "
                                    + ", ".join(required), field))
    for anchor in (element.before, element.after):
        if anchor is not None and anchor not in elements:
            findings.append(Finding("ФОРМА-СОСЕД-НЕТ",
                                    f"«{element.name}» просят поставить рядом с «{anchor}», "
                                    "а такого элемента нет", field))
        elif anchor is not None and elements[anchor][1] != element.parent:
            # где сосед на самом деле — чтобы исправить задание, а не искать
            findings.append(Finding("ФОРМА-СОСЕД-В-ДРУГОМ-МЕСТЕ",
                                    f"«{anchor}» лежит не в «{element.parent or 'корне'}», "
                                    f"куда ставят «{element.name}», а в «{elements[anchor][1] or 'корне'}»"
                                    " — укажите этот «родитель»", field))
    if element.before and element.after:
        findings.append(Finding("ФОРМА-ПЕРЕД-И-ПОСЛЕ",
                                f"у «{element.name}» указаны и «перед», и «после»", field))
    if element.kind in BOUND_KINDS:
        if not element.path:
            findings.append(Finding("ФОРМА-БЕЗ-ПРИВЯЗКИ",
                                    f"«{element.name}» ({element.kind}) без привязки", field))
        else:
            findings.extend(_check_path(element, attributes, main_name, known_paths, field,
                                        assignment, owner_kind))
    if element.kind == "Кнопка":
        if not element.command:
            findings.append(Finding("ФОРМА-КНОПКА-БЕЗ-КОМАНДЫ",
                                    f"кнопка «{element.name}» без команды", field))
        elif not element.command.startswith("Стандартная.") and element.command not in commands:
            findings.append(Finding("ФОРМА-КНОПКА-БЕЗ-КОМАНДЫ",
                                    f"кнопка «{element.name}» ссылается на команду "
                                    f"«{element.command}», которой в форме нет", field))
    for name, value in element.properties.items():
        try:
            check_property(element.kind, name, value)
        except Refuse as отказ:
            findings.append(Finding("ФОРМА-СВОЙСТВО", f"«{element.name}»: {отказ}", field))
    for handler in element.events.values():
        if not is_identifier(handler):
            findings.append(Finding("ФОРМА-ОБРАБОТЧИК-ИМЯ",
                                    f"«{element.name}»: «{handler}» — не имя процедуры", field))
    findings.extend(_check_events(element, field))
    return findings


def _check_events(element, field):
    """События элемента — из тех, что у его вида бывают (`form_events`).

    Иначе неизвестное имя всплывало бы позже, отказом записи без кода и по
    одному, а событие чужого вида проходило бы вовсе.
    """
    допустимые = EVENTS.get(element.kind)
    if допустимые is None:
        return []
    findings = []
    for событие in element.events:
        if событие in допустимые:
            continue
        у_кого = kinds_with(событие)
        перечень = ", ".join(допустимые) if допустимые else "нет ни одного"
        findings.append(Finding(
            "ФОРМА-СОБЫТИЕ-НЕ-ДЛЯ-ВИДА" if у_кого else "ФОРМА-СОБЫТИЕ-НЕИЗВЕСТНО",
            f"«{element.name}» ({element.kind}): "
            + (f"«{событие}» — событие вида {', '.join(у_кого[:3])}, а не этого"
               if у_кого else f"события «{событие}» у элементов формы нет")
            + f"; у {element.kind} событий: {перечень}", field))
    return findings


def _check_path(element, attributes, main_name, known_paths, field,
                assignment="Произвольная", owner_kind=None):
    head, _, rest = element.path.partition(".")
    if head == main_name and rest and assignment in LIST_ASSIGNMENTS:
        return _check_list_field(element, rest, known_paths, field, owner_kind)
    if not rest:
        if head not in attributes:
            return [Finding("ФОРМА-ПРИВЯЗКА-НЕТ-РЕКВИЗИТА",
                            f"«{element.name}» привязан к «{head}», а реквизита формы "
                            "с таким именем нет", field)]
        # Реквизит-документ показывается своим полем, а не полем ввода:
        # ПолеВвода, привязанное к табличному документу, без этой проверки
        # прошло бы молча.
        тип = getattr(attributes.get(head), "name", None)
        нужен = DOCUMENT_FIELDS.get(тип)
        if нужен and element.kind != нужен:
            return [Finding("ФОРМА-ПОЛЕ-НЕ-ДЛЯ-ТИПА",
                            f"«{element.name}» ({element.kind}) привязан к «{head}» типа {тип}, "
                            f"а такой реквизит показывается элементом {нужен}"
                            + ("" if нужен in ELEMENT_KINDS else " — его инструмент не заводит"),
                            field)]
        return []
    if head != main_name:
        # колонка таблицы значений формы или чужой путь — проверяем только голову
        if head not in attributes:
            return [Finding("ФОРМА-ПРИВЯЗКА-НЕТ-РЕКВИЗИТА",
                            f"«{element.name}» привязан к «{element.path}», а реквизита формы "
                            f"«{head}» нет", field)]
        return []
    if known_paths is None:
        return []
    first = rest.split(".")[0]
    if first not in known_paths:
        return [Finding("ФОРМА-ПРИВЯЗКА-НЕТ-РЕКВИЗИТА",
                        f"«{element.name}» привязан к «{element.path}», а реквизита "
                        f"«{first}» у хозяина нет", field)]
    return []
