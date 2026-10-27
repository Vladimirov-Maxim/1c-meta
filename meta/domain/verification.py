"""Проверка правок задачи: правила домена и их находки.

Инструмент пишет выгрузку так, как конфигуратор, и ставит метки вставок сам.
Здесь — проверка того же самого постфактум, по правкам задачи: файлы и строки,
которые задача добавила, изменила или удалила относительно базы. Знание о
метках одно на запись и проверку — разбор из `edits`: что записал `code_apply`,
проверка принимает без находок по меткам.

Правила названы кодами — словами домена; уровень по умолчанию — свой у
каждого, команда меняет его профилем (`правила`). Какие файлы изменены и где
лежат роли, — знание площадки: правила получают его готовым.
"""

import difflib
import re
from collections import Counter

from .changes import changed_lines
from .edits import (
    DECLARATION,
    METHOD_END,
    code_part,
    declared_names,
    insertion_code,
    marker_kind,
    marker_ranges,
    outer_reason,
    replaced_code,
    revert_task,
    unclosed_markers,
)
from .form_events import unbound_handlers, unbound_message
from .model import Finding, Refuse, TypeRef

# --- коды правил ---------------------------------------------------------------

#: Новый объект метаданных без приставки команды — тот же код, что у записи:
#: правило одно, и уровень ему профиль задаёт один раз.
PREFIX = "МД-ПРЕФИКС"
INSERTION_YO = "ВСТАВКА-БУКВА-Ё"
INSERTION_WITHOUT_TYPE = "ВСТАВКА-БЕЗ-ТИПА"
INSERTION_WITHOUT_DATE = "ВСТАВКА-БЕЗ-ДАТЫ"
INSERTION_WITHOUT_TASK = "ВСТАВКА-БЕЗ-ЗАДАЧИ"
OUTSIDE_INSERTION = "ПРАВКА-ВНЕ-ВСТАВКИ"
IN_FOREIGN_INSERTION = "ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ"
NOT_CLOSED = "ВСТАВКА-НЕ-ЗАКРЫТА"
METHOD_NOT_AT_END = "ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ"
SERVICE_FILE = "ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ"
NO_BOM = "ФАЙЛ-БЕЗ-BOM"
EXTRA_BOM = "ФАЙЛ-ЛИШНИЙ-BOM"
TRANSLATIONS_MIXED = "ФАЙЛ-ПЕРЕВОДЫ-СМЕШАНЫ"
TRANSLATIONS_FOREIGN = "ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"
TAILS_TRIMMED = "ФАЙЛ-ХВОСТЫ-СРЕЗАНЫ"
WHITESPACE_ONLY = "ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ"
RIGHTS_IN_FOREIGN_ROLE = "ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ"
RIGHTS_NOT_GRANTED = "ПРАВА-НЕ-ВЫДАНЫ"
TYPE_SET_NARROWER = "СОСТАВ-ТИПОВ-УЖЕ"
WRAPPER_NEEDED = "ВСТАВКА-НУЖНА-ОБЁРТКА"
NOT_BOUND = "ФОРМА-ОБРАБОТЧИК-НЕ-ПРИВЯЗАН"

ERROR, WARNING = Finding.ERROR, Finding.WARNING

#: Код -> (уровень по умолчанию, что правило требует). Перечень — для справки
#: и для профиля: код, которого здесь нет, профиль не выключит.
RULES = {
    PREFIX: (ERROR, "новый объект метаданных назван с приставкой команды"),
    INSERTION_YO: (ERROR, "тип вставки — ИЗМЕНЕН, ДОБАВЛЕН или УДАЛЕН без «Ё»: по этим словам вставки ищут"),
    INSERTION_WITHOUT_TYPE: (ERROR, "в открывающей метке назван тип вставки"),
    INSERTION_WITHOUT_DATE: (ERROR, "в открывающей метке дата дд.мм.гггг"),
    INSERTION_WITHOUT_TASK: (ERROR, "в открывающей метке ИД задачи — последним «#»"),
    OUTSIDE_INSERTION: (ERROR, "правка существующего кода — внутри вставки, и удалённое сохранено комментарием"),
    IN_FOREIGN_INSERTION: (WARNING, "правка внутри вставки другой задачи — своей вставкой поверх"),
    NOT_CLOSED: (ERROR, "открывающая метка, поставленная задачей, закрыта"),
    METHOD_NOT_AT_END: (ERROR, "вставка вокруг метода закрывается на строке КонецПроцедуры/КонецФункции"),
    SERVICE_FILE: (ERROR, "служебный файл выгрузки, который пересобирает платформа, в правки не входит"),
    NO_BOM: (ERROR, "текстовый файл выгрузки конфигуратора — UTF-8 с BOM"),
    EXTRA_BOM: (ERROR, "BOM у текстового файла — только там, где он принят: в проекте EDT его нет"),
    TRANSLATIONS_MIXED: (WARNING, "переводы строк внутри файла одни"),
    TRANSLATIONS_FOREIGN: (ERROR, "переводы строк — те, что приняты в репозитории"),
    TAILS_TRIMMED: (WARNING, "хвостовые пробелы строк эталона не срезаны"),
    WHITESPACE_ONLY: (ERROR, "строка не заменена на себя же с другими пробелами"),
    RIGHTS_IN_FOREIGN_ROLE: (ERROR, "права на новый объект выданы в своей роли, а не только в чужой"),
    RIGHTS_NOT_GRANTED: (ERROR, "новый объект входит в роль с включённым правом"),
    TYPE_SET_NARROWER: (WARNING, "у похожих составных членов задачи — один состав ссылочных типов"),
    WRAPPER_NEEDED: (WARNING, "правка, переписывающая больше половины чужой вставки, — обёрткой "
                                   "снаружи, а не вложенной вставкой"),
    NOT_BOUND: (WARNING, "новая процедура модуля формы с именем события привязана в описании "
                                 "формы"),
}


class FileFinding(Finding):
    """Находка проверки правок: где — файл от корня выгрузки и строка новой
    версии; у находки по объекту метаданных файла нет, объект назван в тексте."""

    def __init__(self, code, message, path=None, line=None, level=None):
        super().__init__(code, message, None, level or RULES[code][0])
        self.path = path
        self.line = line

    def __repr__(self):
        where = f"{self.path}:{self.line}" if self.line else (self.path or "")
        return f"[{self.code}] {where} {self.message}"


# --- приставка новых объектов ----------------------------------------------------


def prefix_findings(new_objects, conventions):
    """Новые объекты без приставки команды. `new_objects` — [(путь, вид, имя)]."""
    if not conventions.prefix:
        return []
    return [FileFinding(PREFIX, f"новый объект «{kind}.{name}» без приставки «{conventions.prefix}»",
                        path)
            for path, kind, name in new_objects if not conventions.is_own(name)]


# --- метки вставок ------------------------------------------------------------------

#: Разметка модуля, а не код: директивы областей вставками не оборачиваются.
#: Регистр не важен — так ищет и сам язык.
REGION_DIRECTIVE = re.compile(r"^\s*#(Область|КонецОбласти|Region|EndRegion)\b", re.IGNORECASE)
TYPE_WORD = re.compile(r"(ИЗМЕНЕН|ДОБАВЛЕН|УДАЛЕН)")
TYPE_WORD_YO = re.compile(r"(ИЗМЕНЁН|ДОБАВЛЁН|УДАЛЁН)")
DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
#: ИД задачи — последний «#» строки; терпимость: «#» со цифрой где угодно —
#: так бывает, когда за ИД дописано пояснение.
TASK_AT_END = re.compile(r"#\S+\s*$")
TASK_WITH_DIGIT = re.compile(r"#[A-Za-zА-Яа-яЁё0-9_-]+\d")


def _significant(line):
    return bool(line.strip()) and not REGION_DIRECTIVE.match(line)


def _numbers(numbers, limit=5):
    shown = ", ".join(map(str, numbers[:limit]))
    return shown + ("…" if len(numbers) > limit else "")


def marker_findings(path, old, new, hunks, task=None):
    """Метки вставок в изменённом модуле: сама метка, правка вне вставок,
    правка внутри вставки другой задачи (`task` — ИД задачи; без него это
    правило не проверяется).

    Модуль, созданный задачей, сюда не попадает: внутри него меток нет вовсе.
    Пустые строки и директивы областей — вне правил: пустая строка снаружи
    вставки её отделяет, а директивы вставками не оборачиваются.
    """
    added, removed = changed_lines(hunks, old, new)
    added = [n for n in added if _significant(new[n - 1])]
    removed = [n for n in removed if _significant(old[n - 1])]
    found = []
    for n in added:
        line = new[n - 1]
        if marker_kind(line) != "open":
            continue
        marker = line.strip()
        if TYPE_WORD_YO.search(line):
            found.append(FileFinding(INSERTION_YO, "тип вставки написан через «Ё»; по словам ИЗМЕНЕН, "
                                                "ДОБАВЛЕН, УДАЛЕН вставки ищут по всей выгрузке", path, n))
        elif not TYPE_WORD.search(line):
            found.append(FileFinding(INSERTION_WITHOUT_TYPE, "в открывающей метке нет типа ИЗМЕНЕН/ДОБАВЛЕН/"
                                                       f"УДАЛЕН: {marker}", path, n))
        if not DATE.search(line):
            found.append(FileFinding(INSERTION_WITHOUT_DATE, f"в открывающей метке нет даты дд.мм.гггг: {marker}",
                                     path, n))
        if not TASK_AT_END.search(line) and not TASK_WITH_DIGIT.search(line):
            found.append(FileFinding(INSERTION_WITHOUT_TASK, "в открывающей метке нет ИД задачи (#<ИД>): "
                                                         f"{marker}", path, n))

    new_ranges = marker_ranges(new)
    old_ranges = marker_ranges(old)
    own_old = [r for r in old_ranges if task is None or r["task"] == task]

    outside = [n for n in added if not _inside(n, new_ranges)]
    erased = _erased(old, new, hunks, set(removed), set(added), old_ranges, own_old, new_ranges)
    # Удалённое из чужой вставки: строки, которые освободило правило выше (лежат
    # в прежней вставке), но которые не сохранены и своей вставкой. Без этого
    # чужая вставка, удалённая целиком, проходила молча: правило «в чужой
    # вставке» считает только добавленные строки.
    foreign_old = [r for r in old_ranges if task and r["task"] != task]
    from_foreign = [] if not foreign_old else [
        n for n in _erased(old, new, hunks, set(removed), set(added), own_old, own_old, new_ranges)
        if n not in erased and _inside(n, foreign_old) and not _inside(n, own_old)]
    if (outside or erased or from_foreign) and task and _matches_without_insertions(old, new, task):
        # выравнивание diff ошиблось, а не правка: сняв свои вставки, получаем базу
        outside, erased, from_foreign = [], [], []
    removed_whole = [r for r in foreign_old if r["start"] in from_foreign]
    if outside or erased or removed_whole:
        parts = []
        if outside:
            parts.append(f"добавленных вне вставок: {len(outside)} (стр. {_numbers(outside)})")
        if erased:
            parts.append(f"удалённых без комментария в своей вставке: {len(erased)} "
                         f"(стр. {_numbers(erased)} прежней версии)")
        for r in removed_whole:
            parts.append(f"удалена вставка другой задачи {r['task'] or 'без ИД'} (стр. {r['start']}–{r['end']} "
                         "прежней версии) без своей вставки УДАЛЕН")
        found.append(FileFinding(OUTSIDE_INSERTION, "; ".join(parts), path))
    unpreserved = set(erased) | set(from_foreign)
    from_foreign = [n for n in from_foreign if not _inside(n, removed_whole)]
    # Вложенная своя вставка, которая заменяет больше половины кода чужой, —
    # чужая вставка фактически переписана: по правилу записи это обёртка
    # снаружи (`needs_outer`). Заменённое — удалённые строки чужой вставки,
    # сохранённые своей вставкой.
    for r in foreign_old:
        # метка чужой вставки сохранена в своей — это и есть обёртка снаружи
        if r in removed_whole or r["start"] in removed:
            continue
        replaced_count = [n for n in removed if r["start"] < n < r["end"] and n not in unpreserved]
        group = _consecutive(replaced_count)
        if group and 2 * replaced_code(group, old) > insertion_code(old, r):
            found.append(FileFinding(
                WRAPPER_NEEDED, f"вставка другой задачи {r['task'] or 'без ИД'} (стр. {r['start']}–{r['end']} "
                               f"прежней версии): {outer_reason(group, r, old)} — оформить обёрткой снаружи, "
                               "а не вложенной вставкой", path))

    if task:
        foreign = []
        for n in added:
            around = [r for r in new_ranges if r["start"] <= n <= r["end"]]
            if around and not any(r["task"] == task for r in around):
                foreign.append((n, max(around, key=lambda r: r["start"])["task"]))
        if foreign or from_foreign:
            whose_one = (foreign[0][1] if foreign
                   else next(r["task"] for r in foreign_old if _inside(from_foreign[0], [r])))
            parts = []
            if foreign:
                parts.append(f"строк {len(foreign)} (стр. {_numbers([n for n, _ in foreign])})")
            if from_foreign:
                parts.append(f"удалено строк {len(from_foreign)} (стр. {_numbers(from_foreign)} прежней версии)")
            found.append(FileFinding(
                IN_FOREIGN_INSERTION, f"внутри вставки другой задачи ({whose_one or 'без ИД'}): " + "; ".join(parts)
                                 + " — нужна своя вставка поверх", path))
    return found


def _matches_without_insertions(old, new, task):
    """Сняв вставки задачи (тем же откатом, что у правки), получаем базу — без
    учёта пустых строк и хвостовых пробелов: их судят свои правила.

    Построчное сопоставление diff ошибается, когда вставка начинается теми же
    строками, что стоят сразу за ней (разделители `|` в тексте запроса), и
    сдвинуть участок нельзя — к нему примыкает соседняя правка: тогда
    исходные строки за вставкой выглядят добавленными вне её. Структура
    вставок такой ошибки не знает: каждая правка учтена, если откат даёт базу."""
    try:
        without_insertions, _, _ = revert_task(new, task, old)
    except Refuse:
        return False

    def gist(lines):
        return [line.rstrip() for line in lines if line.strip()]
    return gist(without_insertions) == gist(old)


def _consecutive(numbers):
    """Номера строк -> группы подряд идущих, как их видит правило записи:
    [{"first", "last", "count"}]."""
    groups = []
    for n in sorted(numbers):
        if groups and groups[-1]["last"] == n - 1:
            groups[-1]["last"] = n
            groups[-1]["count"] += 1
        else:
            groups.append({"first": n, "last": n, "count": 1})
    return groups


def _indent(line):
    return line[:len(line) - len(line.lstrip())]


def _inside(n, ranges):
    return any(r["start"] <= n <= r["end"] for r in ranges)


def _commented_out(line):
    """Текст закомментированной строки без `//` и отступа; не комментарий — None."""
    s = line.strip()
    return s[2:].strip() if s.startswith("//") else None


def _erased(old, new, hunks, removed, added, old_ranges, own_old, new_ranges):
    """Удалённые строки, не сохранённые комментарием, — номера прежней версии.

    Удалённая строка должна найтись закомментированной во вставке, которая
    накрывает её участок, — по копии на строку. Совпадение текста где-то ещё
    в модуле — не сохранение: так проходил бы физически удалённый вызов, если
    такой же комментарий стоит в другом методе.

    Строка внутри прежней вставки освобождена, как и раньше: правка в чужой
    вставке без своей — забота правила `ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ`. Но если
    участок накрыт вставкой, которую поставила сама задача (ИЗМЕНЕН поверх
    кода внутри старой вставки), освобождены только строки своих прежних
    вставок (`own_old`): задача назвала правку изменением — значит, прежнее
    сохранено в ней.

    Строка, которая в том же участке вернулась тем же текстом, не удалена:
    так git показывает файл, у которого сменились только переводы строк, —
    одним участком на весь файл. Вне своей вставки не удалена и строка,
    вернувшаяся с другими пробелами: это смена пробелов, её судит своё
    правило. Под своей ИЗМЕНЕН — удалена: прежний код, перенесённый с другим
    отступом, а не закомментированный, следа правки не оставляет."""
    margin = [Counter(text for text in map(_commented_out, new[r["start"] - 1:r["end"]]) if text)
             for r in new_ranges]
    erased = []
    for h in hunks:
        start = h.new_start
        end = h.new_start + h.new_count - 1 if h.new_count else h.new_start + 1
        # участок и вставка рядом с ним бывают разделены пустыми строками: diff
        # отдаёт удалённое отдельным участком перед пустой строкой над меткой
        while start > 1 and not new[start - 2].strip():
            start -= 1
        while end < len(new) and not new[end - 1].strip():
            end += 1
        nearby = [i for i, r in enumerate(new_ranges) if r["start"] <= end and r["end"] >= start]
        under_own = any(new_ranges[i]["start"] in added for i in nearby)
        is_free = own_old if under_own else old_ranges
        how = (lambda s: s) if under_own else str.strip
        returned = Counter(how(new[k - 1]) for k in range(h.new_start, h.new_start + h.new_count))
        for n in range(h.old_start, h.old_start + h.old_count):
            if n not in removed or _inside(n, is_free):
                continue
            if returned[how(old[n - 1])] > 0:
                returned[how(old[n - 1])] -= 1
                continue
            text = old[n - 1].strip()
            for i in nearby:
                if margin[i][text] > 0:
                    margin[i][text] -= 1
                    break
            else:
                erased.append(n)
    return erased


def unbound_findings(path, old, new, bindings):
    """Новые процедуры модуля формы, названные как событие формы или элемента,
    без привязки в описании формы: платформа их не вызовет. `привязки` —
    (привязанные процедуры, имена элементов, события формы)."""
    before = set(declared_names(old))
    new_items = [name for name in declared_names(new) if name not in before]
    lines = {name: n for n, name in ((n, m.group(1)) for n, m in
                                    ((n, DECLARATION.match(code_part(line))) for n, line in enumerate(new, 1))
                                    if m)}
    return [FileFinding(NOT_BOUND, unbound_message(name, whose), path, lines.get(name))
            for name, whose in unbound_handlers(new_items, *bindings)]


def structure_findings(path, new, added, task=None):
    """Вставки, поставленные задачей: открывающая метка без закрывающей и
    вставка вокруг метода, закрытая не на его конце. `added` — номера
    добавленных задачей строк новой версии.

    Метка над объявлением, чья пара закрывается раньше конца метода, — не
    вставка вокруг метода, а обёртка объявления (смена сигнатуры: старое
    объявление комментарием, новое, закрывающая метка сразу за ним): её
    закрывающая и должна стоять до тела."""
    added = set(added)
    found = []
    unclosed = set(unclosed_markers(new))
    ranges = marker_ranges(new)
    closed_at = {r["start"]: r["end"] for r in ranges}
    for n in sorted(unclosed & added):
        found.append(FileFinding(NOT_CLOSED, "открывающая метка вставки без закрывающей: вставка не закрыта",
                                 path, n))
    # Своя открывающая внутри чужой вставки, у которой закрывающая без даты:
    # разбор спаривает ту закрывающую с нашей открывающей, и незакрытой
    # выходит чужая метка — о ней молчат, она не наша. Пара, где открывающую
    # поставила задача, а закрывающую — нет, и есть наша незакрытая вставка.
    # Только метки своей задачи: чужую метку, перенесённую с хвоста объявления на
    # отдельную строку, задача тоже «добавила», но её пара — прежняя и законная.
    for r in ranges:
        if (task and r["task"] == task and r["start"] in added and r["end"] not in added
                and not r.get("implicit") and r["start"] not in unclosed):
            found.append(FileFinding(
                NOT_CLOSED, f"открывающая метка вставки без своей закрывающей: её закрыла метка на строке "
                            f"{r['end']}, которой задача не ставила, — вставка не закрыта", path, r["start"]))
    declarations = [(n, m.group(1)) for n, m in ((n, DECLARATION.match(code_part(line)))
                                              for n, line in enumerate(new, start=1)) if m]
    for decl, name in declarations:
        end = _method_end(new, decl)
        if end is None:
            continue
        k = decl - 1
        while k >= 1 and _header(new[k - 1]):
            k -= 1
        if (k >= 1 and marker_kind(new[k - 1]) == "open" and k in added and k not in unclosed
                and marker_kind(new[end - 1]) != "close" and not closed_at.get(k, end) < end):
            found.append(FileFinding(
                METHOD_NOT_AT_END, f"вставка вокруг метода {name} (метка на строке {k}): закрывающая "
                                   f"метка должна стоять на строке {new[end - 1].strip()}", path, end))
    return found


def _header(line):
    """Над объявлением метода — его часть: пустые строки, директивы, описание."""
    t = line.strip()
    return not t or t.startswith("&") or (t.startswith("//") and marker_kind(line) is None)


def _method_end(lines, decl):
    for n in range(decl + 1, len(lines) + 1):
        code = code_part(lines[n - 1]).strip()
        if METHOD_END.match(code):
            return n
        if DECLARATION.match(code):
            return None
    return None


# --- состав и формат файлов ------------------------------------------------------------


def service_findings(paths):
    """Служебные файлы выгрузки в правках. `paths` — пути, которые площадка
    назвала служебными: их пересобирает платформа, и в изменениях задачи их
    быть не должно."""
    return [FileFinding(SERVICE_FILE, f"{path.rsplit('/', 1)[-1]} в правках: его пересобирает "
                                        "платформа — верните файл к базе", path)
            for path in paths]


def eol_counts(data):
    """(CRLF, одиночных LF) в байтах файла."""
    crlf = data.count(b"\r\n")
    return crlf, data.count(b"\n") - crlf


def format_findings(path, data, accepted_eol=None, accepted_bom=True, why=None):
    """BOM и переводы строк файла. `accepted_eol` — «CRLF» или «LF», принятые
    в репозитории; `None` — сверять не с чем (git нормализует их сам или
    репозитория нет). `accepted_bom` — принят ли BOM: у выгрузки конфигуратора
    он обязателен, у проекта EDT его нет ни в одном файле. `why` — почему
    файлу нужны именно `accepted_eol` (так его кладёт git, так он лежит в
    базе); без него — «в репозитории приняты»."""
    found = []
    has_bom = data.startswith(b"\xef\xbb\xbf")
    if accepted_bom and not has_bom:
        found.append(FileFinding(NO_BOM, "файл без BOM: конфигуратор может прочитать его не в UTF-8",
                                 path))
    elif not accepted_bom and has_bom:
        found.append(FileFinding(EXTRA_BOM, f"лишний BOM: {path} — в репозитории файлы без BOM", path))
    crlf, lf = eol_counts(data)
    if crlf and lf:
        found.append(FileFinding(TRANSLATIONS_MIXED, f"смешанные переводы строк ({crlf} CRLF / {lf} LF)", path))
    elif accepted_eol is not None:
        is_own = "CRLF" if crlf else "LF" if lf else None
        if is_own is not None and is_own != accepted_eol:
            found.append(FileFinding(TRANSLATIONS_FOREIGN, f"переводы строк {is_own}, "
                                                     + (why or f"в репозитории приняты {accepted_eol}"),
                                     path))
    return found


#: Строка с хвостовыми пробелами — пробел или табуляция перед переводом строки.
TRAILING = re.compile(rb"[ \t]+\r?\n")


def trailing_findings(path, old_data, new_data):
    """Хвостовых пробелов меньше, чем в эталоне, — срез при записи или законная
    замена строк; счётчик грубее сопоставления, поэтому предупреждение, а
    точный ответ даёт нормализация."""
    old, new = len(TRAILING.findall(old_data)), len(TRAILING.findall(new_data))
    if new >= old:
        return []
    return [FileFinding(TAILS_TRIMMED, f"строк с хвостовыми пробелами меньше, чем в эталоне ({old} -> {new}): "
                                        "срез при записи или замена строк — точный ответ даст нормализация",
                        path)]


def cosmetic_findings(path, old, new, hunks):
    """Строка, заменённая на себя же с другими пробелами. В изменениях она
    выглядит правкой, к задаче отношения не имеет и при обновлении вендора даёт
    ложный конфликт. Пустые строки не в счёт: пустая строка вставки на месте
    пустой строки с отступом — следствие оформления, а не правка.

    Пара ищется внутри одного участка и по порядку строк (выравниванием без
    пробелов), а не общим пулом файла: иначе удалённый в одном месте тег
    `<field>` «находил пару» в добавленном с другим отступом совсем в другом
    месте, и вставка соседнего блока XML давала россыпь ложных находок.
    Строка, точная копия которой есть среди добавленных участка, не
    изменилась — она лишь сдвинулась.

    Не находка и перенос внутрь новой конструкции: прежняя строка сохранена в
    участке комментарием (своя ИЗМЕНЕН), или у строки сменился отступ, а
    участок меняет код и по существу — строка вошла в новый `Если`/`Попытка`
    или подзапрос, отступ — следствие. Смена одних хвостовых пробелов и
    отступ, сменившийся без смысловой правки рядом, — находка."""
    found = []
    for hunk in hunks:
        before = [old[o - 1] for o in hunk.old_lines if o <= len(old)]
        after_ = [(n, new[n - 1]) for n in hunk.new_lines if n <= len(new)]
        copies = Counter(text for _, text in after_)
        preserved = {_commented_out(text) for _, text in after_} - {None}
        gist_before = [re.sub(r"\s+", "", text) for text in before]
        gist_after = [re.sub(r"\s+", "", text) for _, text in after_]
        matcher = difflib.SequenceMatcher(None, gist_before, gist_after, autojunk=False)
        substantive = any(tag in ("insert", "replace") and any(gist_after[j] for j in range(j1, j2))
                          for tag, _, _, j1, j2 in matcher.get_opcodes())
        for tag, i1, i2, j1, _ in matcher.get_opcodes():
            if tag != "equal":
                continue
            for k in range(i2 - i1):
                text, (n, a) = before[i1 + k], after_[j1 + k]
                gist = gist_before[i1 + k]
                if not gist or a == text or copies[text] or text.strip() in preserved:
                    continue
                if substantive and _indent(a) != _indent(text):
                    continue
                shown = gist if len(gist) <= 60 else gist[:60] + "…"
                found.append(FileFinding(WHITESPACE_ONLY, f"строка отличается от прежней только пробелами: «{shown}»",
                                         path, n))
    return found


# --- права на новые объекты --------------------------------------------------------------

#: Виды, которым права выдаются в ролях. У остальных (общий модуль,
#: перечисление, подписка, регламентное задание, определяемый тип) роль прав
#: не даёт, и проверять нечего.
KINDS_WITH_RIGHTS = ("Справочник", "Документ", "ЖурналДокументов", "РегистрСведений",
                     "РегистрНакопления", "РегистрБухгалтерии", "РегистрРасчета",
                     "ПланВидовХарактеристик", "ПланСчетов", "ПланВидовРасчета", "ПланОбмена",
                     "БизнесПроцесс", "Задача", "Константа", "Отчет", "Обработка", "ОбщаяКоманда",
                     "ОбщаяФорма", "Подсистема", "ПараметрСеанса", "КритерийОтбора",
                     "Последовательность", "ОбщийРеквизит")


def rights_findings(objects, roles, conventions):
    """Права на новые объекты. `objects` — [(вид, имя)] новых объектов тех видов,
    которым права выдаются в ролях; `roles` — {(вид, имя): [(роль, включено ли
    право)]}. Своя роль — с приставкой команды; без приставки «своё» не
    отличить, и проверяется только то, что право выдано хоть в какой-то роли."""
    found = []
    for kind, name in objects:
        with_right = [role for role, included in roles.get((kind, name), ()) if included]
        own = [role for role in with_right if conventions.is_own(role) is not False]
        if own:
            continue
        obj = f"{kind}.{name}"
        if with_right:
            found.append(FileFinding(
                RIGHTS_IN_FOREIGN_ROLE, f"{obj} — права выданы только в ролях без приставки "
                                    f"«{conventions.prefix}» ({', '.join(with_right)}): чужие роли не "
                                    "правят — нужна своя роль"))
        else:
            found.append(FileFinding(
                RIGHTS_NOT_GRANTED, f"{obj} — новый объект не входит ни в одну "
                                 + ("свою " if conventions.prefix else "")
                                 + "роль с включённым правом: заведите атомарные роли (atomic_roles) "
                                   "или дайте право в роли того же вида"))
    return found


# --- составные типы новых членов ---------------------------------------------------------

#: Насколько составы могут различаться, чтобы считаться похожими: на один-два
#: типа. Больше — это уже разные по смыслу члены, а не недосмотр.
CLOSE_COMPOSITIONS = 2


def type_set_findings(members):
    """Похожие составные члены задачи с разным составом ссылочных типов.

    `members` — [(путь карточки, «Вид.Имя.Член», типы домена)] — члены, которых
    до задачи не было. Член с двумя и больше ссылками, чей состав — собственное
    подмножество состава другого и отличается на один-два типа, почти всегда
    хранит значения того же происхождения: запись значения недостающего типа
    упадёт. Например: измерение регистра держит пять видов документов, а
    соседнее измерение и регистр фактов — шесть. Сужение бывает и сознательным, поэтому
    это предупреждение: решает человек.
    """
    composite = []
    for path, who, types in members:
        references = {str(tk) for tk in (types if isinstance(types, (list, tuple)) else [types])
                  if isinstance(tk, TypeRef) and tk.facet == "Ссылка" and tk.name and not tk.is_set}
        if len(references) >= 2:
            composite.append((path, who, references))
    found = []
    for path, aa, types_a in composite:
        for _, bb, types_b in composite:
            if aa == bb or not types_a < types_b or len(types_b - types_a) > CLOSE_COMPOSITIONS:
                continue
            found.append(FileFinding(
                TYPE_SET_NARROWER, f"«{aa}» — состав типов уже, чем у «{bb}»: нет "
                                  f"{', '.join(sorted(types_b - types_a))}. Если значения одного происхождения "
                                  "пишутся в оба, запись недостающего типа упадёт — сверьте с кодом, который "
                                  f"пишет «{aa.rsplit('.', 1)[-1]}»", path))
    return found

