"""Факт задачи для сценариев плана изменений.

Что задача тронула, состав объектов до и после, методы модулей — от
источника правок (`ChangeSource`). Сценарии плана файлов не знают: где
карточка объекта, какой файл — модуль менеджера, как читается состав, —
говорит источник.
"""

from ..domain import plan as rules
from ..domain.changes import AFTER, BEFORE, MODIFIED
from ..domain.edits import declared_methods


def touched(source):
    """{(вид, имя): статусы файлов} — объекты, файлы которых тронула задача.
    Статус карточки — свой (новая, удалена); правка любого другого файла
    объекта — «изменён»."""
    out = {}
    for c in source.changes():
        obj = source.owner_of(c.path)
        if obj is None:
            continue
        status = c.status if source.object_of(c.path) == obj else MODIFIED
        out.setdefault(obj, set()).add(status)
    return out


def _methods(source, path, side):
    lines = source.lines(path, side)
    return None if lines is None else declared_methods(lines)


def _module(source, path):
    return rules.FactModule(path, _methods(source, path, AFTER), _methods(source, path, BEFORE) or {})


def object_fact(source, kind, name, modules):
    """`ObjectFact`: состав до и после, модули {модуль: путь} — их методы."""
    return rules.ObjectFact(kind, name, source.card_path(kind, name),
                             source.composition(kind, name, AFTER), source.composition(kind, name, BEFORE),
                             {module: _module(source, path) for module, path in modules.items()})
