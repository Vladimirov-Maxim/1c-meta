"""Факт задачи для сценариев плана изменений.

Что задача тронула, состав объектов до и после, методы модулей — от
источника правок (`ChangeSource`). Сценарии плана файлов не знают: где
карточка объекта, какой файл — модуль менеджера, как читается состав, —
говорит источник.
"""

from ..domain import plan as rules
from ..domain.changes import AFTER, BEFORE, MODIFIED
from ..domain.edits import declared_methods


def затронутые(source):
    """{(вид, имя): статусы файлов} — объекты, файлы которых тронула задача.
    Статус карточки — свой (новая, удалена); правка любого другого файла
    объекта — «изменён»."""
    out = {}
    for c in source.changes():
        объект = source.owner_of(c.path)
        if объект is None:
            continue
        статус = c.status if source.object_of(c.path) == объект else MODIFIED
        out.setdefault(объект, set()).add(статус)
    return out


def _методы(source, path, side):
    строки = source.lines(path, side)
    return None if строки is None else declared_methods(строки)


def _модуль(source, path):
    return rules.МодульФакта(path, _методы(source, path, AFTER), _методы(source, path, BEFORE) or {})


def факт_объекта(source, вид, имя, модули):
    """`ФактОбъекта`: состав до и после, модули {модуль: путь} — их методы."""
    return rules.ФактОбъекта(вид, имя, source.card_path(вид, имя),
                             source.composition(вид, имя, AFTER), source.composition(вид, имя, BEFORE),
                             {модуль: _модуль(source, путь) for модуль, путь in модули.items()})
