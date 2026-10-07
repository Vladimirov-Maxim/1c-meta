"""Правки задачи: какие файлы изменены и какие строки в них.

Источник правок — git (рабочая копия или ревизия против базы) или пара
каталогов «эталон — копия» — знает площадка; сюда приходят его ответы:
состав файлов и участки различий. Здесь — что из них следует, без диска.

Строки нумеруются с единицы: так их называет `git diff`, так их видит
человек в редакторе, так их печатает показ кода.
"""

import difflib
from dataclasses import dataclass

#: Статусы файла задачи: новый, изменён, удалён. Переименование git
#: называет парой «удалён — новый» по новому пути: предмет проверок — новый.
ADDED, MODIFIED, DELETED = "A", "M", "D"

#: Стороны правки: версия до задачи (база) и после неё.
BEFORE, AFTER = "до", "после"


@dataclass(frozen=True)
class FileChange:
    """Файл задачи: статус (`ADDED`, `MODIFIED`, `DELETED`) и путь от корня
    выгрузки через «/»."""

    status: str
    path: str


@dataclass(frozen=True)
class Hunk:
    """Участок различий, как его называет `git diff -U0`: начало и число строк
    в старой версии и в новой. При нулевом числе начало — строка, после
    которой участок стоит (`-5,0` — вставка после пятой)."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int

    @property
    def old_lines(self):
        return range(self.old_start, self.old_start + self.old_count)

    @property
    def new_lines(self):
        return range(self.new_start, self.new_start + self.new_count)


def hunks_between(old, new):
    """Участки различий двух текстов — в том же виде, что у `git diff -U0`.

    Для пары каталогов, где git сравнивать не с чем: эталон обработки из
    вложения задачи против правленой копии.
    """
    matcher = difflib.SequenceMatcher(None, list(old), list(new), autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        out.append(Hunk(i1 + 1 if i2 > i1 else i1, i2 - i1, j1 + 1 if j2 > j1 else j1, j2 - j1))
    return out


def whole_file(new):
    """Новый файл: добавлена каждая его строка."""
    return [Hunk(0, 0, 1, len(new))] if new else []


def changed_lines(hunks, old, new):
    """(добавленные, удалённые) — номера строк новой и старой версии.

    Строка с тем же текстом на том же месте участка равного размера — не
    правка: так git показывает строку, у которой изменился только перевод
    строки в конце файла («\\ No newline at end of file»). Иначе такая строка,
    например «#КонецЕсли» в конце модуля, получала бы ложное «вне вставки».
    """
    added, removed = [], []
    for hunk in hunks:
        same = set()
        if hunk.old_count == hunk.new_count:
            for k in range(hunk.new_count):
                n, o = hunk.new_start + k, hunk.old_start + k
                if n <= len(new) and o <= len(old) and new[n - 1] == old[o - 1]:
                    same.add(k)
        added += [n for k, n in enumerate(hunk.new_lines) if k not in same and n <= len(new)]
        removed += [o for k, o in enumerate(hunk.old_lines) if k not in same and o <= len(old)]
    return added, removed


def pairs_by_position(hunks):
    """Пары (строка старой версии, строка новой) внутри участков равного
    размера — кандидаты в «та же строка, другие пробелы». Так их сопоставляет
    git: позиция в участке, а не содержимое."""
    pairs = []
    for hunk in hunks:
        if hunk.old_count == hunk.new_count and hunk.old_count:
            pairs += [(hunk.old_start + k, hunk.new_start + k) for k in range(hunk.old_count)]
    return pairs


def pairs_by_content(old, new):
    """Пары (строка старой версии, строка новой), совпадающие без хвостовых
    пробелов, — сопоставление по содержимому: у пары каталогов участков git
    нет, а срез хвостов не должен сдвигать сопоставление."""
    matcher = difflib.SequenceMatcher(None, [line.rstrip() for line in old],
                                      [line.rstrip() for line in new], autojunk=False)
    pairs = []
    for tag, i1, i2, j1, _ in matcher.get_opcodes():
        if tag == "equal":
            pairs += [(i1 + k + 1, j1 + k + 1) for k in range(i2 - i1)]
    return pairs
