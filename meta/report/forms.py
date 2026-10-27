"""Форма словами задания: что разобрано из задания и что лежит в выгрузке."""

import difflib

from ..domain import forms as fm
from ..domain.model import type_record
from . import БЕЗ_КАНАЛА

#: Разделители в показе формы — чтобы дерево читалось, а не сливалось.
ВЕТКА = "   "


def describe_form(edits):
    """Что разобрано из задания: реквизиты, команды, дерево элементов, события.

    Обработчики у кода формы — тем именем, каким их назовёт код (с
    приставкой «Подключаемый_»): показ без неё уводил бы к процедуре, которой
    в модуле не будет.
    """
    lines = []
    пиши = lines.append
    handler_name = fm.code_handler_name if edits.as_code else (lambda handler: handler)
    for attribute in edits.attributes:
        where = f" (колонка «{attribute.table}»)" if attribute.table else ""
        пиши(f"   реквизит {attribute.name}: {type_record(attribute.value_type)}{where}"
             + (f" — {attribute.title}" if attribute.title else ""))
        for column in attribute.columns:
            пиши(f"      колонка {column.name}: {type_record(column.value_type)}")
    for command in edits.commands:
        action = handler_name(command.action) if command.action else command.action
        пиши(f"   команда {command.name} -> {action}"
             + (f" «{command.title}»" if command.title else ""))
    for event, handler in edits.events.items():
        пиши(f"   событие формы {event} -> {handler}")

    def tree(element, level):
        chunks = [element.kind, element.name]
        if element.path:
            chunks.append(f"[{element.path}]")
        if element.command:
            chunks.append(f"команда {element.command}")
        if element.before:
            chunks.append(f"перед «{element.before}»")
        if element.after:
            chunks.append(f"после «{element.after}»")
        if element.properties:
            chunks.append("{" + ", ".join(f"{k} = {v}" for k, v in element.properties.items()) + "}")
        if element.events:
            chunks.append(" ".join(f"@{e}={handler_name(h)}" for e, h in element.events.items()))
        пиши("   " + "   " * level + " ".join(chunks))
        for child in element.children:
            tree(child, level + 1)

    if edits.elements:
        пиши("   элементы:")
    for element in edits.elements:
        if element.parent:
            # Заголовок — на уровне корневых элементов: с отступом детей он
            # читался бы как ребёнок предыдущего элемента.
            пиши(f"   в «{element.parent}»:")
        tree(element, 1 if element.parent else 0)
    for name in edits.remove_elements:
        пиши(f"   убрать элемент {name}")
    for name in edits.remove_attributes:
        пиши(f"   убрать реквизит {name}")
    for name in edits.remove_commands:
        пиши(f"   убрать команду {name}")
    return lines


def shown_form(view, name, form_file, module_file, detailed=False, подсказки=БЕЗ_КАНАЛА,
               ветвь=None, своя=True):
    """Форма в выгрузке — деревом элементов, реквизитами и командами.

    Отвечает на вопрос «куда вставлять»: имя элемента, его вид, привязка,
    обработчики — то, чем оперирует задание. Иначе ответ добывался бы
    чтением `Form.xml`, а он бывает в сотню килобайт: у самой большой формы
    замеренной выгрузки 182 199 байт и 158 элементов.

    `ветвь` — имя элемента: показ только его ветки и пути к ней. У типовой
    формы дерево целиком — сотни строк, а место вставки ищут в одной группе.
    """
    lines = []
    пиши = lines.append
    процедуры = getattr(view, "procedures", None)

    def missing(handler):
        """Пометка обработчика, процедуры которого в модуле нет: после записи
        формы без задания на код ссылка ведёт в никуда, и показ об этом говорит."""
        if процедуры is None or not handler or handler in процедуры:
            return ""
        return " (процедуры в модуле нет)"

    хозяин = f"{view.owner_kind}.{view.owner_name}" if view.owner else "Общая"
    своя = "" if своя else "   ТИПОВАЯ: правится только кодом"
    пиши(f"Форма {хозяин}.{name}   (назначение {view.assignment}){своя}")
    пиши(f"   файл: {form_file}")
    if module_file:
        пиши(f"   модуль: {module_file}")
    if своя:
        # Дерево — из XML формы: что добавляет код, в нём не видно, и это
        # сказано — иначе соседа «после» выбирали бы без них.
        пиши("   элементы, которые добавляет код (модуль формы, код доработки), в дереве не "
             "видны — оно из XML формы")
    if ветвь is not None:
        return lines + _ветвь(view, ветвь, detailed, подсказки, missing)

    if view.attributes:
        пиши("\n   Реквизиты:")
        for attr_name, type_ in view.attributes.items():
            главный = "   (главный)" if attr_name == view.main else ""
            # Той же краткой записью, что принимает задание, — а не адресами
            # объектов Python у составного и не тегом `mxl:…`.
            пиши(f"{ВЕТКА * 2}{attr_name}: {type_record(type_) if type_ is not None else 'тип не задан'}{главный}")
    if view.commands:
        пиши("\n   Команды:")
        for команда in sorted(view.commands):
            handler = view.commands_actions.get(команда)
            пиши(f"{ВЕТКА * 2}{команда}"
                 + (f" -> {handler}" if handler and handler != команда else "")
                 + missing(handler))
    if view.events:
        пиши("\n   События формы:")
        for event, handler in view.events.items():
            пиши(f"{ВЕТКА * 2}{event} -> {handler}{missing(handler)}")
    пиши("\n   Элементы:")
    tree = _дерево(view, detailed)
    lines += tree.lines(None, 0, missing)
    if tree.спутников:
        # Спрятанное названо вслух: молча укоротить вывод — значит соврать
        # о составе формы.
        пиши(f"\n   Скрыто спутников (меню, подсказки, дополнения таблиц): "
             f"{tree.спутников}; показать — {подсказки.detailed}")
    return lines


class _дерево:
    """Элементы формы по родителям — без спутников, если не просили.

    Спутник (меню, подсказка, дополнение таблицы) прячется, только когда
    внутри него нет настоящих элементов: автоматическая панель формы —
    спутник, но кнопки в ней — настоящие элементы, и спрятать её значило бы
    спрятать их.
    """

    def __init__(self, view, detailed, root=None):
        self.view = view
        все_дети = {}
        for name in view.order:
            все_дети.setdefault(view.elements[name].parent, []).append(name)

        def со_своими(name):
            return any(not view.elements[child].satellite or со_своими(child)
                       for child in все_дети.get(name, ()))

        self.children = {}
        self.спутников = 0
        for name in view.order:
            element = view.elements[name]
            if root is not None and root not in _путь(view, name)[:-1]:
                continue
            if element.satellite and not detailed and not со_своими(name):
                self.спутников += 1
                continue
            self.children.setdefault(element.parent, []).append(name)

    def line(self, name, level, missing):
        element = self.view.elements[name]
        kind = element.kind + (f", {element.layout}" if element.layout else "")
        chunks = [f"{name} ({kind})"]
        if element.path:
            chunks.append(f"[{element.path}]")
        if element.command:
            chunks.append(f"-> {element.command}")
        chunks += [f"@{event}={handler}{missing(handler)}"
                  for event, handler in element.events]
        return ВЕТКА * (level + 2) + " ".join(chunks)

    def lines(self, parent, level, missing):
        output = []
        for name in self.children.get(parent, ()):
            output.append(self.line(name, level, missing))
            output += self.lines(name, level + 1, missing)
        return output


def _путь(view, name):
    """Имена от корня формы до элемента включительно."""
    path = []
    while name is not None:
        path.append(name)
        name = view.elements[name].parent
    return path[::-1]


def _ветвь(view, name, detailed, подсказки, missing):
    """Одна ветка дерева: путь к элементу, он сам и всё, что внутри."""
    if name not in view.elements:
        similar = difflib.get_close_matches(name, list(view.elements), n=5, cutoff=0.6)
        return [f"\n   элемента «{name}» на форме нет"
                + (f"; похожие: {', '.join(similar)}" if similar else "")
                + f" — дерево целиком: без {подсказки.ветвь}"]
    tree = _дерево(view, detailed, root=name)
    lines = [f"\n   Ветка «{name}»: {' › '.join(_путь(view, name))}",
              f"   реквизиты, команды и события формы и остальные ветки — без {подсказки.ветвь}",
              "\n   Элементы:", tree.line(name, 0, missing)]
    lines += tree.lines(name, 1, missing)
    if tree.спутников:
        lines.append(f"\n   Скрыто спутников в ветке: {tree.спутников}; показать — "
                      f"{подсказки.detailed}")
    return lines


def element_properties(kind):
    """Свойства элемента формы — для ключа «свойства» в задании на формы.

    Без неё их узнавали бы только отказом: справка по полям знает виды
    объектов, а не элементы. Вид, которого инструмент не заводит, показывается
    тоже — с пометкой.
    """
    from ..domain.form_properties import ENUMS, PROPERTIES
    from ..domain.forms import ELEMENT_KINDS, KIND_ITSELF, expressible

    props = PROPERTIES.get(kind)
    if props is None:
        return None
    # У вида, которого инструмент не заводит, свойства — справка о платформе,
    # а не «для задания»: в задание такой элемент не поставить.
    lines = [f"{kind} — элемент формы. "
              + ("Свойства для «свойства» в задании на формы, русскими именами платформы:\n"
                 if kind in ELEMENT_KINDS else
                 "Инструмент его показывает, но не заводит — в задание такой элемент не "
                 "поставить; свойства ниже — справка о платформе:\n")]
    if kind in ("Кнопка", "ГруппаКнопок"):
        # Куда кладут кнопку, сказано здесь же — иначе панель формы искали бы
        # по README.
        from ..domain.forms import FORM_COMMAND_BAR, TABLE_CONTAINERS

        панель_таблицы = next(suffix for suffix, вид_ in TABLE_CONTAINERS if вид_ == "КоманднаяПанель")
        lines.append(f"   Куда: «родитель» — «{FORM_COMMAND_BAR}» (командная панель формы, у новой "
                      f"формы — тем же заданием), «<Таблица>{панель_таблицы}» (панель таблицы) или "
                      "имя своей группы кнопок; без родителя — в корень формы.\n")
    for name, (_, type_, default) in props.items():
        # Невыразимое помечено: цвет и шрифт стоят в справке наравне с
        # остальными, а задание их отвергает.
        if type_ in KIND_ITSELF:
            lines.append(f"   {name:34} — сам вид элемента, задаётся ключом «вид»")
            continue
        values = ENUMS.get(type_)
        what = f"{type_}: {', '.join(values)}" if values else (type_ or "")
        if default:
            what += f"; по умолчанию {default}"
        if not expressible(type_):
            what += " — заданием не выражается"
        lines.append(f"   {name:34} {what}")
    # События — здесь же: иначе допустимые узнавали бы только отказом, а в
    # отказе — общий список событий всех видов.
    from ..domain.form_events import EVENTS

    if kind in EVENTS:
        lines.append("\nСобытия (ключ «обработчики»): "
                      + (", ".join(EVENTS[kind]) if EVENTS[kind] else "у этого вида событий нет"))
    return lines
