"""Правки формы -> код доработки формы методами платформы.

Язык по умолчанию: он есть в любой конфигурации и не требует ничьей
библиотеки. Тот же выход из того же описания, что XML своей формы и код
диалекта команды, — только слова платформы. Сверено с
синтакс-помощником 8.5.1:

- `Новый РеквизитФормы(<Имя>, <ОписаниеТипов>, <Путь>, <Заголовок>)` — колонка
  таблицы значений — реквизит с путём к таблице; все разом —
  `Форма.ИзменитьРеквизиты(<Массив>)`: операция ресурсоёмкая, платформа
  просит делать её пакетом;
- `Новый ОписаниеТипов(<Типы>, <КвалификаторыЧисла>, <КвалификаторыСтроки>,
  <КвалификаторыДаты>)` — квалификаторы именно в этом порядке;
- `Форма.Команды.Добавить(<Имя>)`, у команды `Заголовок` и `Действие`;
- `Форма.Элементы.Вставить(<Имя>, <Тип>, <Родитель>, <Элемент>)` — новый
  встаёт перед `<Элемент>`; без места — `Добавить(<Имя>, <Тип>, <Родитель>)`,
  в конец родителя;
- `УстановитьДействие(<Событие>, <Действие>)` — у поля, таблицы, группы и
  декорации.

Код пишется для процедуры общего модуля с параметром `Форма` (место и вызов
решает `domain.forms`); без отступов — их ставит тот, кто кладёт код в модуль.
"""

from ..domain import forms as fm
from ..domain import model as dm
from ..domain.model import Refuse
from .form_code import (
    BAR_KINDS,
    command_of,
    element_kinds,
    handler_name,
    parent_of,
    place_before,
    quote,
    reference_type,
    value_literal,
)

#: Переменные кода — те же в каждом фрагменте: дописанный в существующую
#: процедуру код просто переприсваивает их.
ELEMENT = "Элемент"
COMMAND = "Команда"
ATTRIBUTES = "ДобавляемыеРеквизиты"

#: Вид элемента домена -> (тип элемента платформы, его вид или `None`).
#: Вид кнопки ставится по родителю, у таблицы вида нет.
ELEMENT_TYPES = {
    "ПолеВвода": ("ПолеФормы", "ВидПоляФормы.ПолеВвода"),
    "ПолеФлажка": ("ПолеФормы", "ВидПоляФормы.ПолеФлажка"),
    "ПолеНадписи": ("ПолеФормы", "ВидПоляФормы.ПолеНадписи"),
    "ПолеКартинки": ("ПолеФормы", "ВидПоляФормы.ПолеКартинки"),
    "ПолеПереключателя": ("ПолеФормы", "ВидПоляФормы.ПолеПереключателя"),
    "Надпись": ("ДекорацияФормы", "ВидДекорацииФормы.Надпись"),
    "Картинка": ("ДекорацияФормы", "ВидДекорацииФормы.Картинка"),
    "ГруппаФормы": ("ГруппаФормы", "ВидГруппыФормы.ОбычнаяГруппа"),
    "Страницы": ("ГруппаФормы", "ВидГруппыФормы.Страницы"),
    "Страница": ("ГруппаФормы", "ВидГруппыФормы.Страница"),
    "ГруппаКолонок": ("ГруппаФормы", "ВидГруппыФормы.ГруппаКолонок"),
    "КоманднаяПанель": ("ГруппаФормы", "ВидГруппыФормы.КоманднаяПанель"),
    "ГруппаКнопок": ("ГруппаФормы", "ВидГруппыФормы.ГруппаКнопок"),
    "Кнопка": ("КнопкаФормы", None),
    "ТаблицаФормы": ("ТаблицаФормы", None),
}


def render(edits, view=None):
    """Правки формы -> текст фрагмента: реквизиты, команды, элементы.

    `view` — что в форме уже есть: по нему «после» переводится в «перед» и
    узнаётся вид родителя кнопки. Проверки инвариантов уже прошли в домене —
    здесь только запись.
    """
    kinds = element_kinds(edits, view)
    lines = _attributes(edits) + _commands(edits)
    for element in edits.elements:
        lines += _element(element, kinds, view=view)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def type_description(value_type):
    """Тип домена (или список — составной) -> `Новый ОписаниеТипов(…)`."""
    composition = value_type if isinstance(value_type, list) else [value_type]
    if any(isinstance(type_, dm.AnyType) for type_ in composition):
        return "Новый ОписаниеТипов()"
    names, num, line, date = [], "", "", ""
    for type_ in composition:
        if isinstance(type_, dm.BooleanType):
            names.append("Булево")
        elif isinstance(type_, dm.StringType):
            names.append("Строка")
            if type_.length:
                line = (f"Новый КвалификаторыСтроки({type_.length}"
                          + (", ДопустимаяДлина.Фиксированная" if type_.fixed else "") + ")")
        elif isinstance(type_, dm.NumberType):
            # Без квалификаторов числа платформа числа хранить не даёт.
            names.append("Число")
            num = (f"Новый КвалификаторыЧисла({type_.digits}, {type_.fraction_digits}"
                     + (", ДопустимыйЗнак.Неотрицательный" if type_.nonnegative else "") + ")")
        elif isinstance(type_, dm.DateType):
            names.append("Дата")
            date = f"Новый КвалификаторыДаты(ЧастиДаты.{type_.parts})"
        elif isinstance(type_, dm.TypeRef):
            names.append(reference_type(type_))
        elif isinstance(type_, dm.PlatformType):
            names.append(type_.name)
        else:
            raise Refuse(f"не знаю, как записать тип «{type_}» в коде")
    arguments = [quote(",".join(names)), num, line, date]
    while not arguments[-1]:
        arguments.pop()
    return f"Новый ОписаниеТипов({', '.join(arguments)})"


def _attributes(edits):
    """Реквизиты и колонки таблиц — одним вызовом `ИзменитьРеквизиты`."""
    own = [a for a in edits.attributes if a.table is None]
    columns = [a for a in edits.attributes if a.table is not None]
    for attribute in own:
        columns += [fm.FormAttribute(c.name, c.value_type, c.title, table=attribute.name)
                    for c in attribute.columns]
    if not own and not columns:
        return []
    lines = [f"{ATTRIBUTES} = Новый Массив;"]
    for attribute in own + columns:
        arguments = [quote(attribute.name), type_description(attribute.value_type)]
        if attribute.table or attribute.title:
            arguments.append(quote(attribute.table) if attribute.table else "")
        if attribute.title:
            arguments.append(quote(attribute.title))
        lines.append(f"{ATTRIBUTES}.Добавить(Новый РеквизитФормы({', '.join(arguments)}));")
    return lines + [f"Форма.ИзменитьРеквизиты({ATTRIBUTES});", ""]


def _commands(edits):
    lines = []
    for command in edits.commands:
        lines.append(f"{COMMAND} = Форма.Команды.Добавить({quote(command.name)});")
        if command.title:
            lines.append(f"{COMMAND}.Заголовок = {quote(command.title)};")
        lines.append(f"{COMMAND}.Действие = {quote(handler_name(command.action))};")
        lines.append("")
    return lines


def _element(element, kinds, parent=None, view=None):
    """Один элемент и его дети — каждый своим блоком."""
    type_, kind = ELEMENT_TYPES[element.kind]
    parent_name = parent_of(element, view, parent)
    before_it = place_before(element, view)
    # Родителя не назвали и по форме его не узнать — тот, где стоит сосед:
    # «перед» без родителя вставлял бы на верхний уровень формы.
    destination = (f"Форма.Элементы.{parent_name}" if parent_name
            else f"Форма.Элементы.{before_it}.Родитель" if before_it else None)
    if before_it:
        creation = (f"{ELEMENT} = Форма.Элементы.Вставить({quote(element.name)}, "
                    f"Тип({quote(type_)}), {destination}, Форма.Элементы.{before_it});")
    else:
        creation = (f"{ELEMENT} = Форма.Элементы.Добавить({quote(element.name)}, Тип({quote(type_)})"
                    + (f", {destination}" if destination else "") + ");")
    lines = [creation]
    if kind:
        lines.append(f"{ELEMENT}.Вид = {kind};")
    if element.kind == "Кнопка" and kinds.get(parent_name) in BAR_KINDS:
        lines.append(f"{ELEMENT}.Вид = ВидКнопкиФормы.КнопкаКоманднойПанели;")
    if element.path:
        lines.append(f"{ELEMENT}.ПутьКДанным = {quote(element.path)};")
    if element.command:
        lines.append(f"{ELEMENT}.ИмяКоманды = {quote(command_of(element))};")
    for name, value in element.properties.items():
        lines.append(f"{ELEMENT}.{fm.property_of(element.kind, name)[0]} = "
                     f"{value_literal(element.kind, name, value)};")
    for event, handler in element.events.items():
        lines.append(f"{ELEMENT}.УстановитьДействие({quote(event)}, {quote(handler_name(handler))});")
    lines.append("")
    for child in element.children:
        lines += _element(child, kinds, element.name, view)
    return lines
