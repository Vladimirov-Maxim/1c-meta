"""Общее у языков кода доработки формы: литералы BSL, имена обработчиков,
ссылочные типы, вид кнопки и место элемента.

Язык выбирают соглашения команды (`domain.conventions.КодФорм`): методы
платформы (`platform_code`) или диалект команды из файла, который назвал
профиль (`domain.form_dialect`); диалект берёт отсюда те же помощники.
Описание формы одно — меняется только то, какими словами оно записано.
"""

from ..domain import forms as fm
from ..domain.form_properties import ENUMS
from ..domain.model import Refuse

#: Виды родителей, внутри которых кнопка — кнопка командной панели. Вид кнопки
#: код ставит явно: без него кнопка в панели выходит обычной.
BAR_KINDS = ("КоманднаяПанель", "ГруппаКнопок", "Подменю", "КонтекстноеМеню")

#: Приставка процедур, которые подключает код, — правило домена: им же называют
#: процедуры заготовка и показ задания.
HANDLER_PREFIX = fm.HANDLER_PREFIX
handler_name = fm.code_handler_name

#: Вид ссылочного типа домена -> корень его имени в коде: «СправочникСсылка.Имя».
REFERENCE_ROOTS = {
    "Справочник": "СправочникСсылка", "Документ": "ДокументСсылка",
    "Перечисление": "ПеречислениеСсылка", "ПланВидовХарактеристик": "ПланВидовХарактеристикСсылка",
    "ПланСчетов": "ПланСчетовСсылка", "ЗадачаСсылка": "ЗадачаСсылка",
    "ПланОбмена": "ПланОбменаСсылка",
}


def quote(text):
    """Строковый литерал BSL: кавычка внутри удваивается, перевод строки —
    продолжение литерала с «|». Без «|» многострочный заголовок дал бы
    невалидный BSL."""
    return '"{}"'.format(str(text).replace('"', '""').replace("\n", "\n|"))


def value_literal(kind, name, value):
    """Значение свойства -> литерал BSL по виду значения из словаря."""
    russian, _, value_kind, value = fm.check_property(kind, name, value)
    if value_kind in ("Булево", "БулевоНеопределено"):
        return "Истина" if value else "Ложь"
    if value_kind == "Число":
        return str(value)
    if value_kind == "Строка":
        return quote(value)
    if value_kind in ENUMS:
        # Перечисление платформы зовётся так же, как вид значения в словаре:
        # `ПоложениеЗаголовкаЭлементаФормы.Нет`, `ВидГруппыФормы.ОбычнаяГруппа`.
        return f"{value_kind}.{value}"
    raise Refuse(f"свойство «{russian}» кодом не выражается")


def reference_type(value_type):
    """`TypeRef` -> имя типа в коде: «СправочникСсылка.Контрагенты»."""
    root = REFERENCE_ROOTS.get(value_type.kind)
    if root is None:
        raise Refuse(f"не знаю, как назвать тип «{value_type}» в коде")
    return f"{root}.{value_type.name}"


def element_kinds(edits, view):
    """Вид каждого элемента — и того, что в форме уже есть, и того, что
    добавляет задание: по виду родителя ставится вид кнопки."""
    return dict({name: item.kind for name, item in (view.elements if view else {}).items()},
                **{e.name: e.kind for e in edits.all_elements()})


def place_before(element, view):
    """Перед каким элементом встаёт новый — или `None`, в конец родителя.

    У обоих языков есть только «перед», и «после» переводится в «перед» по
    прочитанной форме (`after_as_before`); элемента, после которого просили
    встать, в форме нет — отказ с советом, а не догадка.
    """
    if element.before:
        return element.before
    if not element.after:
        return None
    следующий, известен = fm.after_as_before(view, element.after)
    if not известен:
        raise Refuse(f"«{element.name}»: «после» в коде переводится в «перед» по прочитанной "
                     f"форме, а элемента «{element.after}» в ней нет — укажите «перед»")
    return следующий


def parent_of(element, view, parent=None):
    """Родитель нового элемента: названный, родитель по дереву задания или тот,
    где стоит сосед из «перед»/«после». Без соседа в расчёте элемент с одним
    «после» встал бы на верхний уровень формы, а не рядом с соседом.
    `None` — верхний уровень или родитель соседа не известен (соседа нет в
    прочитанной форме)."""
    if element.parent or parent:
        return element.parent or parent
    сосед = element.before or element.after
    if сосед and view is not None and сосед in view.elements:
        return view.elements[сосед].parent
    return None


def command_of(element):
    """Имя команды кнопки. Стандартную команду кодом не назначить — её ставит
    конфигуратор."""
    if element.command.startswith("Стандартная."):
        raise Refuse(f"кнопка «{element.name}»: стандартную команду кодом "
                     "не назначить — её ставит конфигуратор")
    return element.command
