"""Правка модуля вставками: язык меток и решения.

Единица работы разработчика — не объект метаданных, а размеченная вставка, и
почти всегда это фрагмент внутри тела метода: адресовать её можно только
номером строки. Оформление вставки — семнадцать правил, которые без
инструмента держатся на памяти разработчика и проверяются постфактум. Здесь
они не правила, а поведение функции: тип метки выводится из состава правки, а
не передаётся; дата, ИД задачи, автор, комментирование заменяемого кода,
отступы и пустые строки снаружи проставляются сами. Забыть нельзя.

Это домен: чистые функции над строками модуля. Файлов, BOM, переводов строк и
git здесь нет — какой модуль правится и где он лежит, решает площадка; создан
ли модуль текущей задачей, сообщает она же. Правка — объект `Edit`, пачка
получает строки модуля, а не прочитанный файл.
"""

import re
from dataclasses import dataclass

from .characters import described, guillemet_lines, invalid_characters, line_numbers
from .model import Refuse
from .modules import ModuleRef
from .modules import regions as module_regions


@dataclass(frozen=True)
class Signature:
    """Подпись вставки: чья задача, когда, кто. `tag` — метка команды перед
    автором («#TEAM»): соглашение команды, а не часть задания; `None` — без неё."""

    task: str
    date: str
    author: str
    tag: str = None


@dataclass(frozen=True)
class Edit:
    """Одна правка модуля.

    `line` — строка-якорь; `lines` — сколько строк заменяется (0 — чистая
    вставка перед якорем); `first_line`/`last_line` — ожидаемый текст обеих
    границ заменяемого блока, они играют роль `version` из LSP и защищают от
    промаха по устаревшему номеру; `code` — новый текст без меток (пустой —
    удаление). `carried` — текст не написан, а перенесён из модуля
    (переименование, перенос метода): проверки нового текста к нему не
    относятся — чужой символ в старой строке не повод отказать.
    """

    line: int
    lines: int = 0
    first_line: str = None
    last_line: str = None
    code: str = ""
    carried: bool = False


@dataclass(frozen=True)
class Decision:
    """Что сделано с правкой и почему — ответ человеку, а не лог.

    `insert` — чистая вставка перед строкой `first`; `block` — строки, которые
    встанут на место правки, а `at` — номер первой из них в новом тексте модуля:
    просмотр показывает, что будет записано, а не только решение, — пустые
    строки, отступы и деактивированные чужие метки видны до записи.
    """

    line: int
    first: int
    last: int
    marker: bool
    kind: str
    reason: str
    note: bool = False
    insert: bool = False
    block: tuple = ()
    at: int = 0
    #: Соседи блока в новом тексте — (строка выше, строка ниже), `None` — края
    #: модуля: по одним новым строкам не видно, встал ли разделитель рядом с
    #: чужой меткой.
    context: tuple = ()
    #: Отката: пустые строки-разделители, снятые вместе со вставкой, — номера
    #: по тексту до правки.
    dropped: tuple = ()
    #: Где правка — словами: в каком методе или в какой области (`place_of`).
    where: str = ""


@dataclass(frozen=True)
class ModuleJob:
    """Что сделать с одним модулем: правки, откат вставок задачи или
    переименование метода (`rename` — пара «старое имя, новое»)."""

    ref: ModuleRef
    edits: tuple = ()
    revert: bool = False
    rename: tuple = None


@dataclass(frozen=True)
class MethodMove:
    """Перенос метода между модулями: удаление в источнике и добавление в
    приёмнике перед строкой `line` — один акт."""

    source: ModuleRef
    method: str
    target: ModuleRef
    line: int


@dataclass(frozen=True)
class CodeJob:
    """Задание на код: подпись вставок, модули и, возможно, перенос метода.

    Атомарно по всему заданию: правка, разложенная по трём модулям, при
    частичном применении оставила бы код в состоянии, которого не планировал
    никто.
    """

    signature: Signature
    modules: tuple = ()
    move: MethodMove = None
    #: База сверки — ревизия до задачи (как у проверки правок): модуль, которого
    #: в ней нет, создан задачей. `None` — `HEAD`.
    base: str = None


#: Открывающая метка — первый комментарий строки вида `// {[+]…`. Того же языка
#: ещё три формы с меткой команды («#TEAM») в другом месте: `// {#TEAM [+]…`,
#: `// #TEAM{[+]…` и `// { [+]…`. Не узнай их разбор, такие вставки считались бы
#: кодом вне вставок, а их закрывающие метки оставались бы без пары и могли бы
#: сцепиться с чужой открывающей. Метка команды — любая: у каждой команды своя,
#: и разбор не должен знать, чья выгрузка. У форм
#: с пробелом или «#» после «{» знак правки обязателен: без него «{#…» и «{ …» —
#: обычные комментарии (правила обмена, `//{{MRG[`).
OPEN_MARK = re.compile(r"//\s*(?:#[^\s{]+\s*)?\{(?:\[|\s*(?:#\S+\s*)?\[[*+\-]\])")
#: Закрывающая — `// }…`, но не `//}}MRG[ <-> ]`: это след инструмента
#: сравнения-объединения (185 строк в 12 модулях корпуса), а не метка. Его
#: открывающая пара, `//{{MRG[`, меткой не считается, и без этого исключения
#: каждая такая «закрывающая» забирала бы со стека чужую открывающую — вставка
#: 27-515 вместо 27-72.
CLOSE_MARK = re.compile(r"//\s*\}(?!\}MRG)")
SIGN = re.compile(r"\[([*+\-])\]")
TASK_TOKEN = re.compile(r"#(\S+)")
MARKER_DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")

#: Длиннее этого чужую вставку снаружи не оборачиваем без вопроса: обёртка
#: деактивирует всё внутри, и 2300 строк за одну добавленную — не правка, а
#: авария. Число — порог внимания, а не свойство формата.
WRAP_LIMIT = 300
#: Столько заменяемых строк внутри чужой вставки ещё «одна-две строки» правила вложенности:
#: обёртка вкладывается в чужую, а не поглощает её. Чистая вставка (0 строк)
#: сюда попадает всегда — она ничего чужого не деактивирует.
NESTED_LIMIT = 2
#: Чужие метки без пары ближе этого к правке называются поимённо: рядом с
#: правкой непарная метка может сбить разбор, вдали — только шумит.
NOTE_REACH = 60
METHOD_START = re.compile(r"^(Процедура|Функция)\s", re.IGNORECASE)
METHOD_END = re.compile(r"^(КонецПроцедуры|КонецФункции)\b", re.IGNORECASE)

TYPE_CHANGED = ("*", "ИЗМЕНЕН")
TYPE_ADDED = ("+", "ДОБАВЛЕН")
TYPE_REMOVED = ("-", "УДАЛЕН")

DEDENT = re.compile(
    r"^(КонецЕсли|КонецЦикла|КонецПопытки|КонецПроцедуры|КонецФункции|Иначе|ИначеЕсли|Исключение)\b",
    re.IGNORECASE)
REGION = re.compile(r"^#(Область|КонецОбласти)\b", re.IGNORECASE)


def step_of(ind):
    """Шаг отступа в манере модуля: табуляция, а у модуля на пробелах — четыре."""
    return "\t" if ("\t" in ind or ind == "") else "    "


def place_level(lines, first, count, code):
    """Уровень вложенности места правки — отступ, на котором живёт новый код.

    Замена живёт на уровне первой заменяемой строки. Чистая вставка — на уровне
    якоря, но перед словом, закрывающим конструкцию (`КонецПроцедуры`,
    `КонецЕсли`, `Иначе`…), — на шаг глубже: код ложится внутрь неё. С
    отступом якоря всегда метки, код и пустые строки перед `КонецПроцедуры`
    ушли бы в нулевую колонку. Если новый код сам начинается словом
    продолжения (`ИначеЕсли` перед `ИначеЕсли`), уровень — якоря.
    """
    anchor = lines[first - 1] if first <= len(lines) else ""
    level = indent_of(anchor)
    if count == 0 and DEDENT.match(anchor.strip()):
        head = next((c for c in code if c.strip()), "")
        if not DEDENT.match(head.strip()):
            level += step_of(level)
    return level


def shifted(code, level):
    """Новый код мельче своего места — сдвинуть вправо целиком: (строки, сдвиг).

    Описание инструмента обещает, что отступы ставит он, и код приходит без
    отступа — без сдвига он лёг бы в нулевую колонку внутри процедуры. Глубже
    места — не трогаем: так бывает законно. Отступ из
    смеси табов и пробелов, не продолжающий уровень, — тоже: угадывать не из
    чего, остаётся предупреждение о потерянном табе.
    """
    body = [c for c in code if c.strip()]
    if not body:
        return code, ""
    head = indent_of(body[0])
    if len(head) >= len(level) or not level.startswith(head):
        return code, ""
    delta = level[len(head):]
    return [delta + c if c.strip() else c for c in code], delta


def shift_note(delta):
    if not delta:
        return ""
    if delta == "\t" * len(delta):
        return f"; код сдвинут вправо до уровня места правки (табуляций: {len(delta)})"
    return f"; код сдвинут вправо до уровня места правки (пробелов: {len(delta)})"


# --- разбор меток ------------------------------------------------------------


def marker_kind(line):
    """Метка распознаётся только как ПЕРВЫЙ комментарий строки.

    Два класса ложных срабатываний, которые видны на реальном модуле корпуса
    (69 открывающих меток против 59 закрывающих):

    1. Метка, ЗАКОММЕНТИРОВАННАЯ прежним внешним обёртыванием, выглядит как
       `//// {[` — поиск подстроки где угодно в строке счёл бы её новой вставкой.
       Здесь первый комментарий строки — `//`, а за ним идёт `//`, а не `{[`.
    2. Закрывающая метка вставки вокруг целого метода живёт хвостом на строке
       `КонецФункции // } Автор, дата` — её распознавать надо, поэтому закрывающую
       метку нельзя привязывать к началу строки, только к первому комментарию.
    """
    pos = line.find("//")
    if pos < 0:
        return None
    rest = line[pos:]
    if OPEN_MARK.match(rest):
        return "open"
    if CLOSE_MARK.match(rest):
        return "close"
    return None


def code_part(line):
    """Строка без метки: код до неё (`Функция Х() // {[+]…` -> `Функция Х()`),
    у строки из одной метки — пусто. Строка без метки — как есть."""
    if marker_kind(line) is None:
        return line
    return line[:line.find("//")].rstrip()


def marker_ranges(lines, problems=None):
    """Диапазоны вставок с ИД задачи. Номера строк — с единицы, границы включительно.

    Метки спариваются по порядку (стек), а ДАТА решает спор. Стек сам по себе
    ошибается ровно на незакрытой метке: она остаётся в стеке, и следующая же
    чужая закрывающая забирает её. Так вставка одной строки в общем модуле
    корпуса получила бы границы 1484–3814, и правка закомментировала бы
    2300 строк живого кода.

    Правило: если у верхней открывающей дата другая, а ГЛУБЖЕ в стеке есть
    открывающая с той же датой, что у закрывающей, — пара берётся с ней, а всё,
    что лежало выше, объявляется незакрытым. Если совпадения нет нигде — пара
    по порядку: вставку и открывают, и закрывают не всегда в один
    день (в корпусе 1350 пар с разными датами, не меньше 172 из них живые —
    у закрывающей тот же автор), и правило, требующее совпадения дат всегда,
    рвало бы их все и сыпало бы тысячами примечаний.

    Метки без даты (в корпусе 387 открывающих и 805 закрывающих из ~30 000) в
    споре не участвуют. Незакрытые и осиротевшие метки в разбор не идут, а не
    растягиваются до конца файла, и о каждой сказано в `problems`:
    дефект разметки — не наш, но молчать о нём значит рисковать той же аварией.
    В файле они остаются как есть — «не учтена» значит только это.

    Одно исключение: метка, открывающая метод
    — хвостом на его объявлении или отдельной строкой над ним (через описание
    и директиву), — которой нет своей пары, закрывается неявно на его
    `КонецПроцедуры`/`КонецФункции`: вставка и есть весь метод (`implicit` у
    диапазона). Так в корпусе 394 метода «[+] ДОБАВЛЕН» из 403 незакрытых с
    меткой хвостом и ещё 107 с меткой над методом: закрывающую просто не
    ставили. Закрывается при проходе, а не после: неявно закрытая уже не лежит
    в стеке, и чужая закрывающая ниже её не заберёт — иначе получались бы
    вставки 27-515 и 84-509 там, где методы кончаются на 72 и 129.

    «Своя пара» — та, с которой метка спарилась бы без неявного закрытия, если
    у закрывающей та же дата или она стоит сразу за концом метода: так
    устроены настоящие вставки из нескольких методов (и с метками у методов
    внутри) и метка над методом, закрытая следующей строкой другим днём. Пара
    с чужой датой через сотни строк — ложная: из 108 пар «метка метода —
    закрывающая дальше его конца» в корпусе 94 такие (у 80 дата другая, у 12
    её нет, 2 — строки `//}}MRG`).
    """
    kinds = [marker_kind(line) for line in lines]
    codes = [(line if kind is None else line[:line.find("//")]).strip()
             for line, kind in zip(lines, kinds, strict=True)]
    # Объявление метода -> строка его открывающей метки: хвостом на самом
    # объявлении или отдельной строкой над ним — через описание и директиву,
    # без пустых строк.
    heads, above = {}, None
    for i in range(1, len(lines) + 1):
        kind, code = kinds[i - 1], codes[i - 1]
        if DECLARATION.match(code):
            if kind == "open":
                heads[i] = i
            elif kind is None and above is not None:
                heads[i] = above
            above = None
        elif kind == "open" and not code:
            # «[-]» над живым методом по смыслу не бывает: удалённое — это
            # комментарии, и метод под такой меткой ей не принадлежит.
            знак = SIGN.search(lines[i - 1])
            above = i if знак and знак.group(1) in "+*" else None
        elif not (kind is None and code.startswith(("//", "&"))):
            above = None
    # С чем метка спарилась бы сама — проход без неявного закрытия.
    сама = {r["start"]: r["end"] for r in _pair_markers(lines, kinds, codes, heads, None, [])}

    def своя_пара(start, end):
        пара = сама.get(start)
        if пара is None or пара <= end:
            return False
        j = end + 1
        while j <= len(lines) and not lines[j - 1].strip():
            j += 1
        if пара == j:
            return True                  # закрыта сразу за концом метода
        дата = marker_date(lines[start - 1][lines[start - 1].find("//"):])
        return дата is not None and дата == marker_date(lines[пара - 1][lines[пара - 1].find("//"):])

    заметки = []
    ranges = _pair_markers(lines, kinds, codes, heads, своя_пара, заметки)
    # Метки внутри закрытого блока «[-]» — история: деактивированный код
    # несёт свои старые метки, а закрывающая часто стоит хвостом на
    # закомментированной строке («//КонецФункции // } …») и меткой не
    # считается. Называть такую «без пары» — шум.
    удалённые = [(r["start"], r["end"]) for r in ranges if r["sign"] == "-"]
    for заметка in заметки:
        номер = re.match(r"строка (\d+):", заметка)
        n = int(номер.group(1)) if номер else 0
        if problems is not None and not any(a < n < b for a, b in удалённые):
            problems.append(заметка)
    return ranges


def _pair_markers(lines, kinds, codes, heads, своя_пара, notes):
    """Проход по меткам: стек, спор по дате и — если задано `своя_пара` —
    неявное закрытие метки метода на его конце."""
    ranges, stack = [], []
    declared = None                   # метка, открывающая текущий метод
    for i, line in enumerate(lines, start=1):
        kind = kinds[i - 1]
        code = codes[i - 1]
        if kind == "open":
            mark = line[line.find("//"):]
            tokens = TASK_TOKEN.findall(mark)
            # последний #токен — ИД задачи; первый обычно метка команды («#TEAM»)
            m = SIGN.search(mark)
            sign = m.group(1) if m else ""
            stack.append((i, tokens[-1] if tokens else "", sign, marker_date(mark)))
        if DECLARATION.match(code):
            declared = heads.get(i)
        elif METHOD_END.match(code):
            if (своя_пара is not None and kind is None and declared is not None and stack
                    and stack[-1][0] == declared and not своя_пара(declared, i)):
                start, task, sign, _ = stack.pop()
                ranges.append({"start": start, "end": i, "task": task, "sign": sign,
                               "implicit": True})
            declared = None
        if kind == "open":
            continue
        if kind == "close" and not stack:
            notes.append(f"строка {i}: закрывающая метка без открывающей — в разборе не учтена")
        elif kind == "close":
            date = marker_date(line[line.find("//"):])
            j = len(stack) - 1
            if date is not None and stack[j][3] not in (None, date):
                # спор: верхняя открывающая датирована иначе — есть ли глубже
                # открывающая с датой закрывающей? Нет — остаёмся с верхней.
                deeper = [k for k in range(j - 1, -1, -1) if stack[k][3] == date]
                if deeper:
                    j = deeper[0]
            for start, task, _sign, odate in stack[j + 1:]:
                notes.append("строка {}: открывающая метка {} ({}) не закрыта — в разборе не учтена".format(start, task or "без ИД", odate or "без даты"))
            start, task, sign, _ = stack[j]
            del stack[j:]
            ranges.append({"start": start, "end": i, "task": task, "sign": sign})
    for start, task, _sign, odate in stack:
        notes.append("строка {}: открывающая метка {} ({}) не закрыта до конца модуля — в разборе не учтена".format(start, task or "без ИД", odate or "без даты"))
    return ranges


def unclosed_markers(lines):
    """Открывающие метки без своей закрывающей — номера строк, с единицы.

    Те же правила пары, что у `marker_ranges`, но без неявного закрытия метки
    метода на его конце: оно — терпимость к чужой истории (закрывающую там
    просто не ставили), а вставка, которую пишут сейчас, закрывается явно.
    """
    kinds = [marker_kind(line) for line in lines]
    codes = [(line if kind is None else line[:line.find("//")]).strip()
             for line, kind in zip(lines, kinds, strict=True)]
    paired = {r["start"] for r in _pair_markers(lines, kinds, codes, {}, None, [])}
    return [number for number, kind in enumerate(kinds, start=1)
            if kind == "open" and number not in paired]


def marker_date(text):
    """Дата в метке, `дд.мм.гггг`. `None` — даты нет."""
    m = MARKER_DATE.search(text)
    return m.group() if m else None


def uncomment(line):
    """Снять ОДИН уровень комментирования: `\\t//Код;` → `\\tКод;`, `\\t////c` → `\\t//c`.

    Ровно один уровень — потому что комментирование вставкой добавляет ровно один,
    и собственные комментарии заменяемого кода должны вернуться комментариями.
    """
    ind = indent_of(line)
    rest = line[len(ind):]
    return ind + rest[2:] if rest.startswith("//") else line


def covering(ranges, first, last):
    """Вставки, полностью охватывающие диапазон [first, last]."""
    return [r for r in ranges if r["start"] <= first and last <= r["end"]]


def innermost(items):
    return max(items, key=lambda r: r["start"]) if items else None


def indent_of(line):
    m = re.match(r"^([ \t]*)", line)
    return m.group(1) if m else ""


def comment_out(line, ind=""):
    """Комментирование: `//` на отступе БЛОКА (метки), исходный отступ строки — после.

    `\\t\\tКод;` внутри вставки с отступом `\\t` становится `\\t//\\tКод;`, а не
    `\\t\\t//Код;`. У строк на отступе метки обе формы совпадают; различаются
    они только у строк глубже метки, и там во вставках ИЗМЕНЕН корпуса `//` на
    отступе метки встречается в разы чаще, чем после полного отступа строки.
    `revert` симметричен: он снимает `//` сразу после ведущего отступа.
    """
    own = indent_of(line)
    if not own.startswith(ind):
        ind = own                     # строка мельче блока — комментируем по ней
    return ind + "//" + line[len(ind):]


def is_query_line(line):
    """Строка текста запроса внутри многострочного литерала."""
    return line.lstrip().startswith("|")


def indent_blank_lines(block):
    """Пустой строке внутри метода конфигуратор даёт табуляцию по уровню вложенности.

    Строка нулевой длины в выгрузке — расхождение с тем, что отдаст база: при первой
    же выгрузке все они изменятся. Инструмент правки не может перекладывать это на
    вызывающего — тот физически не передаст строку из одних пробельных символов.

    Уровень берётся по СЛЕДУЮЩЕЙ непустой строке блока: её отступ плюс шаг, если она
    закрывает конструкцию (тогда пустая строка ещё принадлежит закрываемому блоку).
    Строка между методами так получает пустой отступ и остаётся пустой — как и надо.
    """
    out = list(block)
    for i, line in enumerate(out):
        if line != "":
            continue
        j = i + 1
        while j < len(out) and out[j].strip() == "":
            j += 1
        if j >= len(out):
            continue
        ind = indent_of(out[j])
        if DEDENT.match(out[j].strip()):
            ind += "\t" if ("\t" in ind or ind == "") else "    "
        out[i] = ind
    return out


def split_parts(block):
    """Новый код по частям: директивы областей, целые методы, прочий код.

    Правило меток вставок: директивы `#Область`/`#КонецОбласти` вставками не
    оборачиваются; каждый новый метод — своя
    вставка, групповая обёртка на блок методов не допускается, даже если
    методы связаны по смыслу: при переносе на релиз вендора
    метод должен быть атомарно опознаваем. Прочий код подряд — одна вставка,
    пустые строки внутри него — его собственные.

    Над методом ему принадлежат описание и директивы компиляции
    (`&НаСервере`): считайся директива кодом вне метода, метод формы не
    распознавался бы целым, закрывающая метка уходила бы отдельной строкой, а
    области попадали бы внутрь меток. Пустая строка после накопленного
    описания тоже его — выбрасывать её значит молча менять переданный код.
    Пустые строки между частями — разделители, их ставит сборка.

    Части: ("область", [строка]), ("метод", строки), ("код", строки).
    Несбалансированный блок (метод не закрыт) — None.
    """
    parts, pending, depth = [], [], 0

    def code(строки):
        if parts and parts[-1][0] == "код":
            parts[-1][1].extend(строки)
        else:
            parts.append(("код", list(строки)))

    for line in block:
        t = line.strip()
        if depth > 0:
            parts[-1][1].append(line)
            if METHOD_START.match(t):
                depth += 1
            elif METHOD_END.match(t):
                depth -= 1
            continue
        if not t:
            if pending:
                pending.append(line)
            elif parts and parts[-1][0] == "код":
                parts[-1][1].append(line)
            continue
        if REGION.match(t):
            if pending:
                code(pending)
                pending = []
            parts.append(("область", [line]))
        elif t.startswith("//") or t.startswith("&"):
            pending.append(line)
        elif METHOD_START.match(t):
            parts.append(("метод", pending + [line]))
            pending, depth = [], 1
        else:
            code(pending + [line])
            pending = []
    if depth != 0:
        return None
    if pending:
        code(pending)
    for kind, строки in parts:
        while kind == "код" and строки and not строки[-1].strip():
            строки.pop()
    return parts


def is_whole_method(block):
    """Вставка охватывает РОВНО один целый метод (с описанием и директивами
    над ним) — тогда закрывающая метка ставится хвостом на строке КонецПроцедуры.
    Блок из нескольких частей сюда не подходит: он разбивается (см. split_parts).
    """
    parts = split_parts(block)
    return bool(parts) and len(parts) == 1 and parts[0][0] == "метод"


def indent_warning(new_block, ind):
    """Признаки потерянного таба в задании — предупреждение, не отказ.

    Задание пишется руками, и таб в нём теряется молча: последняя строка
    нового кода может прийти на таб мельче, пустая строка перед ней получит
    отступ по ней, и без предупреждения всё применилось бы без замечаний —
    расхождение поймала бы только построчная сверка с ручным эталоном. Два
    дешёвых признака:
    первая и последняя непустые строки нового кода на разных отступах (блок
    начинается и кончается на одном уровне почти всегда) и первая строка мельче
    якоря (глубже — норма: так вставляют перед `КонецЕсли`). Оба бывают
    законными, поэтому это предупреждение в решении, а не отказ.
    """
    body = [b for b in new_block if b.strip()]
    if not body:
        return ""
    head, tail = len(indent_of(body[0])), len(indent_of(body[-1]))
    notes = []
    if head != tail:
        notes.append(f"первая и последняя строки нового кода на разных отступах ({head} и {tail})")
    if head < len(ind):
        notes.append(f"первая строка нового кода мельче якоря ({head} против {len(ind)})")
    return "; ВНИМАНИЕ: " + "; ".join(notes) + " — не потерян ли таб в задании" if notes else ""


def separate(block, lines, first, last, ind, count):
    """Пустая строка СНАРУЖИ вставки — она отделяет правку от соседнего чужого кода,
    чтобы граница была видна при чтении вендорского модуля.

    Ставится только там, где её нет: соседняя пустая строка уже выполняет эту роль,
    а вторая подряд была бы лишним расхождением с новой поставкой вендора. И не
    рядом с меткой, стоящей отдельной строкой: строка метки сама граница, а
    пустая строка между нашей меткой и меткой чужой вставки внутри неё только
    раздвигала бы чужой блок.
    """
    out = list(block)
    before = lines[first - 2] if first >= 2 else None
    # при чистой вставке (last == first, строка-якорь не заменяется) соседом снизу
    # оказывается сама строка-якорь: она сдвинется вниз, а не исчезнет
    tail_index = last if count > 0 else first - 1
    after = lines[tail_index] if tail_index < len(lines) else None
    if before is not None and before.strip() and not bare_marker(before):
        out.insert(0, ind)
    if after is not None and after.strip() and not bare_marker(after):
        out.append(ind)
    return out


def bare_marker(line):
    """Строка — метка вставки отдельной строкой, без кода перед ней."""
    return marker_kind(line) is not None and not code_part(line).strip()


def open_marker(kind, ind, date, author, task, tag=None):
    """Открывающая метка; `tag` — метка команды перед автором, если она у команды есть."""
    sign, word = kind
    кто = f"{tag} {author}" if tag else author
    return f"{ind}// {{[{sign}](фрагмент {word}), {date}, {кто} #{task}"


def close_marker(ind, author, date):
    return f"{ind}// }} {author}, {date}"


def build_insertion(kind, ind, old_block, new_block, meta):
    """Тело вставки по шаблонам ИЗМЕНЕН, ДОБАВЛЕН и УДАЛЕН.

    ИЗМЕНЕН: закомментированный старый код, пустая строка, новый код — пустые строки
    внутри вставки не декоративны, они разделяют смысловые блоки.
    ДОБАВЛЕН и УДАЛЕН внутренних границ не имеют, код идёт вплотную к меткам.
    """
    out = [open_marker(kind, ind, meta["date"], meta["author"], meta["task"], meta.get("tag"))]
    # Пустые строки по краям нового кода — привычка набора (перевод строки в
    # конце `code`), а не код: внутри меток они только раздвигают вставку.
    new_block = list(new_block)
    while new_block and not new_block[0].strip():
        new_block.pop(0)
    while new_block and not new_block[-1].strip():
        new_block.pop()
    whole = kind != TYPE_REMOVED and new_block and is_whole_method(new_block)

    if kind == TYPE_CHANGED:
        out.append(ind)
        out.extend(comment_out(строка, ind) for строка in old_block)
        out.append(ind)
        out.extend(new_block)
        if not whole:
            out.append(ind)
    elif kind == TYPE_ADDED:
        out.extend(new_block)
    else:
        out.extend(comment_out(строка, ind) for строка in old_block)

    # Закрывающая метка вставки вокруг ЦЕЛОГО метода ставится на строке КонецПроцедуры
    # через пробел, а не отдельной строкой.
    # Поэтому у ИЗМЕНЕН за целым методом нет пустой строки: метка цеплялась бы
    # к ней, и под КонецФункции появлялось бы « // } Автор, дата».
    if whole:
        out[-1] = out[-1] + f" // }} {meta['author']}, {meta['date']}"
    else:
        out.append(close_marker(ind, meta["author"], meta["date"]))
    return out


def checked(edit, lines):
    """Правка -> её место и новый код, после проверки якоря.

    Словарь: `first`/`last` — заменяемые строки (у чистой вставки обе — якорь),
    `count` — сколько заменяется, `block` — новый код строками, `edit` — сама правка.
    """
    first = edit.line
    count = edit.lines
    last = first + count - 1 if count > 0 else first
    code = edit.code

    if count < 0 or first < 1 or (count > 0 and last > len(lines)) or (count == 0 and first > len(lines) + 1):
        raise Refuse(f"строка {first}: выход за границы модуля (в модуле {len(lines)} строк)")
    заглушка = placeholder(code)
    if заглушка:
        raise Refuse(f"строка {first}: в коде заглушка «{заглушка}» — подставьте настоящее имя")
    # Проверяется только написанный код: закомментированный и перенесённый
    # чужой — как был.
    символы = [] if edit.carried else invalid_characters(code)
    if символы:
        raise Refuse(f"строка {first}: в коде символы, которые bsl-ls считает ошибкой "
                     "(InvalidCharacterInFile, стандарт «Тексты модулей» #std456) — "
                     + described(символы, "строка кода"))
    ёлочки = [] if edit.carried else guillemet_lines(code)
    if ёлочки:
        raise Refuse(f"строка {first}: в коде кавычки-ёлочки ({line_numbers(ёлочки)} кода) — "
                     "в коде — и в комментариях, и в текстах сообщений — кавычки прямые, "
                     "внутри строкового литерала — удвоенные (\"\")")
    плоский = None if edit.carried else flat_method(code.split("\n") if code else [])
    if плоский:
        имя, номер = плоский
        raise Refuse(f"строка {first}: тело метода «{имя}» без отступа (строка {номер} кода) — "
                     "инструмент сдвигает блок целиком до уровня места правки, а отступы "
                     "внутри кода не ставит: передайте тело метода с табуляцией")
    повтор = duplicate_region(lines, first, last, count, code.split("\n") if code else [])
    if повтор:
        raise Refuse(повтор)

    # Код встаёт на уровень своего места и сдвигается туда целиком, если пришёл
    # мельче; пустые строки переданного кода получают отступ здесь, а не остаются
    # на совести вызывающего: он их физически не наберёт (строка из одних
    # пробельных символов не доходит до инструмента правки агента)
    raw = code.split("\n") if code else []
    level = place_level(lines, first, count, raw)
    raw, delta = shifted(raw, level)
    new_block = indent_blank_lines(raw) if raw else []

    # границы заменяемого блока — роль version из LSP
    if count > 0:
        for field, num in (("first_line", first), ("last_line", last)):
            expected = getattr(edit, field)
            if expected is None:
                raise Refuse(f"строка {first}: не задано поле «{field}» — якорь без проверки не принимается")
            actual = lines[num - 1]
            if actual.rstrip() != expected.rstrip():
                raise Refuse(mismatch(num, expected, actual, lines))
    else:
        # У чистой вставки заменяемых границ нет, но переданный текст — тот же
        # якорь: молча его не сверять значит промахнуться так же, как без него.
        actual = lines[first - 1] if first <= len(lines) else ""
        for field in ("first_line", "last_line"):
            expected = getattr(edit, field)
            if expected is not None and actual.rstrip() != expected.rstrip():
                raise Refuse(mismatch(first, expected, actual, lines,
                                      f" — при вставке «{field}» сверяется со строкой-якорем"))
    if not new_block and count == 0:
        raise Refuse(f"строка {first}: правка пуста — нечего ни добавить, ни удалить")
    if count == 0:
        разрыв = directive_split(lines, first)
        if разрыв:
            raise Refuse(разрыв)
    return {"edit": edit, "first": first, "last": last, "count": count, "block": new_block,
            "level": level, "shift": delta}


#: Строки тела, которым нулевая колонка законна: инструкции препроцессора,
#: комментарии (закомментированное конфигуратором), продолжение литерала.
FLAT_ALLOWED = ("#", "//", "|")


def flat_method(code):
    """Метод в новом коде, тело которого не глубже объявления: (имя, номер
    первой такой строки кода) или None.

    Метод телом в нулевой колонке сдвигается до места правки целиком, но тело
    так и остаётся вровень с объявлением, а пустые строки получают табуляцию
    через раз. Угадывать структуру тела инструмент не берётся — отказ.
    """
    метод = None
    for number, line in enumerate(code, start=1):
        объявлен = DECLARATION.match(line)
        if метод is None:
            if объявлен:
                метод = (объявлен.group(1), indent_of(line), [])
            continue
        if METHOD_END.match(line.strip()):
            имя, отступ, тело = метод
            if тело and all(len(indent_of(s)) <= len(отступ) for _, s in тело):
                return имя, тело[0][0]
            метод = None
            continue
        if line.strip() and not line.strip().startswith(FLAT_ALLOWED):
            метод[2].append((number, line))
    return None


def duplicate_region(lines, first, last, count, code):
    """Область нового кода, которая на этом уровне модуля уже есть, — текст
    отказа или None.

    Повтор метода получает отказ, и повтор области — тоже: иначе вторая
    «#Область ОбработчикиСобытийЭлементовШапкиФормы» легла бы рядом с первой
    (bsl-ls: DuplicateRegion).
    Сравниваются соседи по уровню: области внутри той же области модуля.
    """
    новые, глубина = [], 0
    for line in code:
        слово = line.strip()
        if слово.startswith("#Область"):
            if глубина == 0:
                новые.append(слово[len("#Область"):].strip())
            глубина += 1
        elif слово.startswith("#КонецОбласти") and глубина:
            глубина -= 1
    if not новые:
        return None
    области = module_regions(lines)

    def самая_вложенная(объемлющие):
        return max(объемлющие, key=lambda о: о[1]) if объемлющие else None

    # Вставка перед строкой `first` лежит внутри области, если та началась
    # раньше и кончается не раньше якоря (перед её #КонецОбласти — ещё в ней);
    # замена — если область охватывает заменяемые строки.
    место = самая_вложенная([о for о in области if о[1] < first and (
        last <= о[2] if count == 0 else last < о[2])])
    for имя, начало, конец in области:
        родитель = самая_вложенная([о for о in области if о[1] < начало and конец < о[2]])
        if имя in новые and родитель == место:
            return (f"строка {first}: область «{имя}» здесь уже есть (строки {начало}-{конец}) "
                    f"— новый код кладите в неё: якорем её #КонецОбласти (строка {конец})")
    return None


def mismatch(number, expected, actual, lines, why=""):
    """Отказ по якорю: что ожидалось, что в файле и где ожидаемое сейчас.

    Отступ в «…» не виден: строка, расходящаяся одними табуляциями, читалась
    бы как совпавшая, а «такой строки в модуле нет» — как неправда; строка из
    одной табуляции печаталась бы пустыми кавычками (Read печатает табуляцию и
    после номера строки, и ведущие табуляции легко сбить). Такое расхождение
    называется словами. Сверку
    отступа оно не отменяет: одинаковые «КонецЕсли;» разной вложенности
    различает только он.
    """
    if expected.strip() and expected.strip() == actual.strip():
        return (f"строка {number}: текст совпал, отступ — нет: ожидалось "
                f"{indent_words(expected)}, в файле {indent_words(actual)}{why}; отступ "
                "сверяется — им различаются одинаковые строки разной вложенности")
    return (f"строка {number}: ожидалось {shown_line(expected)}, фактически "
            f"{shown_line(actual)}{why}" + where_now(lines, expected, number))


def shown_line(text):
    """Строка для отказа: «текст» — или «пустая строка (1 табуляция)»."""
    if text.strip():
        return f"«{text.rstrip()}»"
    return "пустая строка" + (f" ({indent_words(text)})" if text else "")


def indent_words(text):
    """Ведущие пробельные символы словами: «2 табуляции», «без отступа»."""
    head = text[:len(text) - len(text.lstrip())]
    if not head:
        return "без отступа"
    части = []
    for count, forms in ((head.count("\t"), ("табуляция", "табуляции", "табуляций")),
                         (head.count(" "), ("пробел", "пробела", "пробелов"))):
        if count:
            части.append(f"{count} {plural(count, *forms)}")
    return " и ".join(части) or "отступ из других пробельных символов"


def plural(n, one, few, many):
    """Слово при числе: 1 табуляция, 2 табуляции, 5 табуляций."""
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def where_now(lines, expected, near):
    """Где ожидаемый текст сейчас — приписка к отказу по устаревшему якорю.

    Отказ, который говорит, что номер не тот, но не говорит, где нужная
    строка, заставляет искать её заново. Ближайшая к названному номеру;
    одинаковых строк бывает много — сказано, сколько.
    """
    цель = expected.rstrip()
    if not цель.strip():
        return ""
    найдено = [n for n, line in enumerate(lines, start=1) if line.rstrip() == цель]
    if not найдено:
        # Тот же текст с другим отступом — почти всегда сбитые табуляции, а
        # не пропавшая строка.
        похожие = [n for n, line in enumerate(lines, start=1) if line.strip() == цель.strip()]
        if похожие:
            ближайшая = min(похожие, key=lambda n: abs(n - near))
            return (f"; с таким отступом строки в модуле нет, с другим — на {ближайшая} "
                    f"({indent_words(lines[ближайшая - 1])}, а ожидалось "
                    f"{indent_words(expected)})")
        return "; такой строки в модуле сейчас нет"
    ближайшая = min(найдено, key=lambda n: abs(n - near))
    ещё = f" (таких строк в модуле {len(найдено)}, это ближайшая)" if len(найдено) > 1 else ""
    return f"; такая строка сейчас на {ближайшая}{ещё} — номер устарел?"

PLACEHOLDER = re.compile(r"<[А-Яа-яЁё][\wА-Яа-яЁё]*>")


def placeholder(code):
    """Заглушка вида «<Модуль>» вне строкового литерала — или None.

    Подсказка инструмента к коду доработки формы пишет вызов с заглушкой
    модуля, и такой код не должен проходить просмотр без замечаний. В строке
    «…признак <Согласовать>…» это текст, а не код.
    """
    for line in (code or "").split("\n"):
        for m in PLACEHOLDER.finditer(line):
            if line[:m.start()].count('"') % 2 == 0:
                return m.group()
    return None


def crossing(ranges, item):
    """Вставка, границу которой правка пересекает: начало снаружи, конец внутри
    или наоборот. Обёртка по такой правке закомментировала бы одну метку вставки
    и оставила другую — разметка рвётся, и поймать это потом нечем."""
    if item["count"] == 0:
        return None
    first, last = item["first"], item["last"]
    for r in ranges:
        if first < r["start"] <= last < r["end"] or r["start"] < first <= r["end"] < last:
            return r
    return None


def place(item, ranges, task):
    """Где правка: («своя», вставка), («чужая», самая внутренняя) или (None, None).

    Чистая вставка встаёт ПЕРЕД якорем, и якорь на открывающей метке чужой
    вставки означает «перед вставкой», а не «внутри неё»: код физически ложится
    выше метки. Считайся диапазон включительно с обеих сторон, такая правка
    деактивировала бы чужую вставку целиком — тот же класс аварии.
    """
    first, last = item["first"], item["last"]
    encl = ([r for r in ranges if r["start"] < first <= r["end"]] if item["count"] == 0
            else covering(ranges, first, last))
    own = [r for r in encl if r["task"] == task]
    if own:
        return "own", innermost(own)
    foreign = innermost(encl)
    return ("foreign", foreign) if foreign else (None, None)


def touches_marks(item, foreign):
    """Правка заменяет строку с меткой чужой вставки — её открывающую (в том числе
    хвостом на объявлении метода: `Функция Х() // {[+]…`) или закрывающую."""
    return item["count"] > 0 and (item["first"] == foreign["start"] or item["last"] == foreign["end"])


def needs_outer(group, foreign):
    """Правило меток вставок делит правку внутри чужой вставки надвое,
    и решает то, остаётся ли деактивированный чужой код под нашей меткой:

    - правится одна-две строки — обёртка ВКЛАДЫВАЕТСЯ в чужую: своя метка внутри
      чужого блока, чужой блок живёт;
    - правится больше, деактивируются несколько фрагментов вставки или правка
      задевает её метку — обёртка СНАРУЖИ, прежняя вставка уходит под нашу метку.

    Обёртка «снаружи всегда» деактивировала бы десятки строк живого кода ради
    двух. Чистая вставка (0 строк) ничего чужого не деактивирует и вкладывается
    всегда.
    """
    replacing = [g for g in group if g["count"] > 0]
    return (len(replacing) > 1
            or any(g["count"] > NESTED_LIMIT for g in replacing)
            or any(touches_marks(g, foreign) for g in replacing))


def outer_reason(group, foreign):
    """Почему обёртка снаружи — критерием правила, а не числом строк молча."""
    replacing = [g for g in group if g["count"] > 0]
    if any(touches_marks(g, foreign) for g in replacing):
        return "правка задевает строку с меткой этой вставки"
    if len(replacing) > 1:
        return f"правок внутри неё {len(replacing)} — несколько фрагментов"
    return f"заменяемых строк {replacing[0]['count']}, вложить можно не больше {NESTED_LIMIT}"


def live_lines(lines, first, last, ranges):
    """Что из строк first..last не исполняется: (номера мёртвых строк, хвосты).

    Следом за деактивированной копией идёт только живой код. Вложенные чужие
    вставки раскрываются — их метки и деактивированный ими код в новую версию
    не идут, история остаётся в копии. Повторяй их как есть, чужая метка после
    переименования встречалась бы в модуле трижды живой и трижды
    закомментированной.

    По каждой вставке внутри (и по самой обёрнутой): метки — мёртвые, у
    хвостовой метки остаётся код перед ней (`хвосты`); рамка из пустых строк у
    меток — мёртвая; деактивированный вставкой код — по шаблону метки:
    у ИЗМЕНЕН — первый сплошной блок закомментированных строк (ровно его
    восстанавливает откат), у УДАЛЕН — всё содержимое. Выбрасываются только
    комментарии и пустые строки — живой код не теряется ни при каком разборе.
    """
    dead, tails = set(), {}
    for r in ranges:
        if not (first <= r["start"] and r["end"] <= last):
            continue
        for n in (r["start"], r["end"]):
            code = code_part(lines[n - 1])
            if code.strip():
                tails[n] = code
            else:
                dead.add(n)
        if r["sign"] == "-":
            # Только комментарии и пустые: у правильной УДАЛЕН другого внутри
            # нет, а неявно закрытая «[-]» над живым методом иначе потеряла
            # бы в новой версии весь его исполняемый код.
            dead.update(n for n in range(r["start"] + 1, r["end"])
                        if not lines[n - 1].strip() or lines[n - 1].lstrip().startswith("//"))
            continue
        # Рамка — только у метки отдельной строкой. Метка хвостом стоит на
        # коде (объявление, КонецФункции), и пустые строки рядом — тело метода:
        # их снятие срезало бы тело и давало бы «косметические правки» чужого
        # кода. У
        # неявно закрытой метки над методом за ней идут описание и директива
        # метода, а не деактивированный код: они живые.
        k = r["start"] + 1
        if r["start"] not in tails and not r.get("implicit"):
            while k < r["end"] and not lines[k - 1].strip():
                dead.add(k)
                k += 1
            if r["sign"] == "*":
                while (k < r["end"] and lines[k - 1].lstrip().startswith("//")
                       and marker_kind(lines[k - 1]) is None):
                    dead.add(k)
                    k += 1
                while k < r["end"] and not lines[k - 1].strip():
                    dead.add(k)
                    k += 1
        if r["end"] not in tails:
            k = r["end"] - 1
            while k > r["start"] and not lines[k - 1].strip():
                dead.add(k)
                k -= 1
    return dead, tails


def rebuild(lines, first, last, group, ranges):
    """Новая версия чужой вставки (строки first..last) со всеми правками группы.

    Обёртка снаружи деактивирует вставку целиком, и всё, что в ней было живым,
    обязано вернуться следом — с правкой, но целиком: верни она одну правку,
    замена 3 строк из 15 оставила бы живыми только новые строки, а 12 ушли бы
    в комментарий — и модуль при этом компилировался бы. Возвращается
    исполняемый код (см. `live_lines`), строки — дословно.
    """
    dead, tails = live_lines(lines, first, last, ranges)
    by_line = {g["first"]: g for g in group}
    out, n = [], first
    while n <= last:
        g = by_line.get(n)
        if g is not None:
            out.extend(g["block"])
            if g["count"] > 0:
                n = g["last"] + 1
                continue
        if n not in dead:
            # Строка — дословно, с хвостовыми пробелами: срезанные, они дали бы
            # в diff «ту же строку без пробела» — косметическую правку чужого
            # кода, на которой проверка правок останавливает запись.
            # Дословная копия в diff не видна вовсе.
            out.append(tails.get(n, lines[n - 1]))
        n += 1
    return out


def outer_wrapper(group, foreign, lines, ranges, meta):
    """Одна обёртка снаружи чужой вставки на все правки, попавшие в неё."""
    f_first, f_last = foreign["start"], foreign["end"]
    # Обёртка снаружи деактивирует чужую вставку целиком — прежде чем это
    # делать молча, два признака, что вставка не та, за которую себя выдаёт:
    # она длиннее порога или внутри неё есть ещё открывающие метки.
    # Любой из них — стоп и вопрос человеку, а не автоматическая обёртка.
    # Исключение одно, и спаренность в нём доказана структурой: вставка —
    # ровно целый метод (у части вендорских модулей метка стоит хвостом на
    # объявлении и на КонецФункции), а вложенные в него вставки спарены
    # внутри. Так устроены почти все методы одного модуля корпуса, и без
    # исключения переименование любого из них упиралось бы в отказ.
    size = f_last - f_first + 1
    inner_opens = [n for n in range(f_first + 1, f_last)
                   if marker_kind(lines[n - 1]) == "open"]
    if inner_opens and is_whole_method(rebuild(lines, f_first, f_last, [], ranges)):
        paired = {r["start"] for r in ranges if f_first < r["start"] and r["end"] < f_last}
        if all(n in paired for n in inner_opens):
            inner_opens = []
    if size > WRAP_LIMIT or inner_opens:
        why = (f"длина {size} строк при пороге {WRAP_LIMIT}" if size > WRAP_LIMIT
               else "внутри неё ещё открывающие метки на строках {}".format(", ".join(str(n) for n in inner_opens[:5])))
        raise Refuse(
            "строка {}: правка попадает в чужую вставку {} (строки {}-{}), и обёртка "
            "снаружи деактивировала бы её целиком; {}. Либо это не та вставка "
            "(незакрытая метка выше?), либо объём не для автоматической обёртки — "
            "оформите вручную".format(group[0]["first"], foreign["task"] or "без ИД", f_first, f_last, why))
    new_version = rebuild(lines, f_first, f_last, group, ranges)
    ind = indent_of(lines[f_first - 1])
    wrapped = lines[f_first - 1:f_last]
    task = foreign["task"] or "без ИД"
    if any(s.strip() for s in new_version):
        kind = TYPE_CHANGED
        block = build_insertion(TYPE_CHANGED, ind, wrapped, new_version, meta)
        # «Повторён» — только если повторять было что: когда правка заменила
        # всё живое, такая фраза заставляла бы искать задвоенный старый код.
        dead, _ = live_lines(lines, f_first, f_last, ranges)
        замена = {n for g in group for n in range(g["first"], g["last"] + 1) if g["count"]}
        осталось = [n for n in range(f_first, f_last + 1)
                    if n not in dead and n not in замена and lines[n - 1].strip()]
        what = ("её живой код повторён следом с правкой" if осталось
                else "живой код в ней весь заменён правкой — следом только новый код")
    else:
        kind = TYPE_REMOVED
        block = build_insertion(TYPE_REMOVED, ind, wrapped, [], meta)
        what = "живого кода в ней не остаётся"
    # пустые строки снаружи — как у любой вставки: без них граница правки
    # сливалась бы с соседним кодом
    block = separate(block, lines, f_first, f_last, ind, f_last - f_first + 1)
    shifts = "".join(shift_note(g["shift"]) for g in group[:1] if g["shift"])
    return {"line": group[0]["first"], "first": f_first, "last": f_last, "marker": True,
            "kind": kind[1],
            "reason": f"правка попала во вставку {task}: {outer_reason(group, foreign)} — обёртка "
                      f"снаружи, вставка деактивирована целиком, {what}" + shifts,
            "replace": (f_first, f_last), "insert": False, "block": block}


def plain(item, reason):
    """Правка без меток: модуль создан задачей или правка внутри своей вставки."""
    return {"line": item["first"], "first": item["first"], "last": item["last"], "marker": False,
            "reason": reason + shift_note(item["shift"]), "kind": None,
            "replace": (item["first"], item["last"]),
            "insert": item["count"] == 0, "block": item["block"]}


def marked(item, lines, meta, nested_in=None):
    """Обычная вставка — вне вставок или вложенная в чужую."""
    first, last, count, new_block = item["first"], item["last"], item["count"], item["block"]
    old_block = lines[first - 1:last] if count > 0 else []
    anchor = lines[first - 1] if first <= len(lines) else (lines[-1] if lines else "")
    # Метка — на уровне места правки (`place_level`): у строки-ЯКОРЯ, а не у
    # предыдущей, — новый код встаёт на её место (якорь с одним табом,
    # предыдущая с двумя — метка несёт один). Перед словом,
    # закрывающим конструкцию, — на шаг глубже.
    ind = item["level"]

    # тип выводится из состава правки, а не передаётся
    if new_block and old_block:
        kind = TYPE_CHANGED
    elif new_block:
        kind = TYPE_ADDED
    else:
        kind = TYPE_REMOVED

    # Текст запроса — те же метки, но комментарием BSL без «|»:
    # метка с фигурными скобками, попавшая в текст запроса, разбирается
    # компоновщиком как расширение {ВЫБРАТЬ}/{ГДЕ}.
    in_query = is_query_line(anchor) or (old_block and any(is_query_line(строка) for строка in old_block))

    # Несколько частей разом — каждый метод и каждый кусок прочего кода в своей
    # вставке, директивы областей без меток, между частями пустая строка.
    parts = split_parts(new_block) if kind == TYPE_ADDED else None
    regions = bool(parts) and any(p[0] == "область" for p in parts)
    if parts and (len(parts) > 1 or regions):
        block = []
        for part_kind, part in parts:
            if block:
                block.append(ind)
            if part_kind == "область":
                block.extend(part)
            else:
                block.extend(build_insertion(kind, ind, [], part, meta))
    else:
        block = build_insertion(kind, ind, old_block, new_block, meta)

    block = separate(block, lines, first, last, ind, count)
    if nested_in:
        чья = nested_in["task"] or "без ИД"
        заменяемое = ("деактивирована только заменяемая строка" if count == 1
                      else "деактивированы только заменяемые строки")
        reason = (f"вложенная метка внутри чужой вставки {чья} (правка в 1-2 строки: чужие метки "
                  f"на месте, {заменяемое})" if count > 0 else
                  f"вложенная метка внутри чужой вставки {чья} (чистая вставка ничего чужого не "
                  "деактивирует)")
    elif in_query:
        reason = "текст запроса, метки комментарием BSL без «|»"
    else:
        # Речь о том, что чужих вставок вокруг нет и метки — по шаблону.
        # Слова «обычная разметка» — часть ответа: по ним сверяются
        # фикстуры тех, кто разбирает ответ.
        reason = "вне чужих вставок — обычная разметка: метки по шаблону"
    if regions:
        reason += "; директивы областей без меток, каждый метод — своей вставкой"
    return {"line": first, "first": first, "last": last, "marker": True, "kind": kind[1],
            "reason": reason + shift_note(item["shift"]) + indent_warning(new_block, ind),
            "replace": (first, last), "insert": count == 0, "block": block}


DECLARATION = re.compile(r"^\s*(?:Асинх\s+)?(?:Процедура|Функция)\s+([^\s(]+)", re.IGNORECASE)


def repeated(item, lines, ranges, task):
    """Правка уже внесена — текст отказа или None.

    Повтор задания после записи (оборванный ответ, таймаут) молча задвоил бы
    вставку, а метод — объявил бы второй раз, и модуль перестал бы
    компилироваться; bsl-ls повторного объявления не ловит. Признаков два:
    новый метод с именем, уже объявленным в модуле
    (правка не заменяет сам этот метод), и чистая вставка, вплотную к которой
    уже стоит вставка этой же задачи с тем же кодом.
    """
    for kind, part in split_parts(item["block"]) or ():
        if kind != "метод":
            continue
        name = next((m.group(1) for m in map(DECLARATION.match, part) if m), None)
        span = method_range(lines, name) if name else None
        if span and not (item["count"] > 0 and item["first"] <= span[0] and span[1] <= item["last"]):
            return (f"строка {item['first']}: метод «{name}» в модуле уже объявлен (строка "
                    f"{span[0]}) — повтор задания после записи объявил бы его второй раз; "
                    "чтобы изменить метод, замените его строки (lines > 0)")
    new = [s.strip() for s in item["block"] if s.strip()]
    if item["count"] or not new:
        return None
    first = item["first"]
    for r in ranges:
        if r["task"] != task or not (r["start"] in (first, first + 1) or r["end"] in (first - 1, first - 2)):
            continue
        content = [(code_part(lines[n - 1]) if n in (r["start"], r["end"]) else lines[n - 1]).strip()
                   for n in range(r["start"], r["end"] + 1)]
        if [s for s in content if s] == new:
            return (f"строка {first}: у якоря уже стоит вставка задачи {task} с тем же кодом "
                    f"(строки {r['start']}-{r['end']}) — правка, похоже, уже внесена, и повтор "
                    "задания задвоил бы её")
    return None


def classify_all(items, lines, ranges, meta):
    """Решения по всем правкам модуля: правки внутри одной чужой вставки
    решаются вместе — обёртка снаружи на них одна."""
    for item in items:
        отказ = repeated(item, lines, ranges, meta["task"])
        if отказ:
            raise Refuse(отказ)
    if meta["new_module"]:
        return [plain(i, "модуль создан текущей задачей — внутри разметки нет") for i in items]
    if not meta.get("markers", True):
        return [plain(i, "метки вставок выключены профилем — правка на месте, без вставки")
                for i in items]
    slots, groups = [], {}            # решения в порядке правок задания
    for item in items:
        cut = crossing(ranges, item)
        if cut is not None:
            raise Refuse(
                "строки {}-{}: правка пересекает границу вставки {} (строки {}-{}) — сузьте "
                "её внутрь вставки или расширьте на всю вставку вместе с метками".format(
                    item["first"], item["last"], cut["task"] or "без ИД", cut["start"], cut["end"]))
        where, r = place(item, ranges, meta["task"])
        if where == "own":
            slots.append(plain(item, "правка внутри своей вставки {} — новой обёртки нет, "
                                     "дата прежняя".format(meta["task"])))
        elif where == "foreign":
            if r["start"] not in groups:
                groups[r["start"]] = (r, [])
                slots.append(r["start"])
            groups[r["start"]][1].append(item)
        else:
            slots.append(marked(item, lines, meta))
    decisions = []
    for slot in slots:
        if isinstance(slot, dict):
            decisions.append(slot)
            continue
        foreign, group = groups[slot]
        if needs_outer(group, foreign):
            decisions.append(outer_wrapper(group, foreign, lines, ranges, meta))
        else:
            decisions.extend(marked(item, lines, meta, nested_in=foreign) for item in group)
    return decisions


def revert_task(lines, task, base=None):
    """Снять вставки указанной задачи, вернув код в состояние до неё.

    `base` — строки модуля в базовой версии (HEAD) или None: по ней сверяются
    пустые строки на стыках (см. `settle`).

    Правило меток вставок: снятие собственной вставки ТОЙ ЖЕ задачи — физическое удаление
    вместе с метками, обёртка УДАЛЕН не заводится. Закомментированного следа не
    остаётся: блок появился и исчез внутри одной задачи, историю хранит git.

    По типу метки:
      [+] ДОБАВЛЕН — удаляется весь блок, восстанавливать нечего;
      [-] УДАЛЕН   — закомментированный код возвращается в строй;
      [*] ИЗМЕНЕН  — возвращается закомментированный старый код, новый удаляется.
                     Сюда же попадает внешняя обёртка: деактивированная чужая
                     вставка восстанавливается целиком со своими метками.

    Вложенные вставки задачи снимаются от внутренних к внешним — иначе номера
    строк внешней уехали бы после снятия внутренней.

    Область, которую завела задача, снимается вместе со своими вставками:
    директивы областей меток не несут, и иначе откат оставлял бы
    её пустой — «#Область …», пустые строки, «#КонецОбласти». Чья она,
    говорит базовая версия: в HEAD такой
    области нет. Без базовой версии область остаётся, а примечание о ней
    возвращается третьим значением.
    """
    out = list(lines)
    decisions = []
    mine = [r for r in marker_ranges(out) if r["task"] == task]
    if not mine:
        return out, decisions, []
    заведённые, notes = task_regions(out, mine, base)
    for имя, начало, конец in заведённые:
        внутри = [r for r in mine if начало < r["start"] and r["end"] < конец]
        mine = [r for r in mine if r not in внутри]
        mine.append({"start": начало, "end": конец, "sign": "+", "task": task, "region": имя,
                     "inner": [(r["start"], r["end"]) for r in внутри]})
    # (начало, конец) восстановленного — после всех откатов — и чьё это решение:
    # снятый разделитель называется у своей вставки, с номером по тексту до
    # правки: при одной итоговой строке «снято: 3» счёт по вставкам не
    # сходился бы — «снимается 7», а ушло 8.
    junctions = []

    for r in sorted(mine, key=lambda x: -x["start"]):
        start, end, sign = r["start"], r["end"], r["sign"]
        body = out[start:end - 1]           # без обеих строк-меток

        if sign == "+":
            restored = []
        elif sign == "-":
            restored = [uncomment(строка) for строка in body if строка.strip()]
        else:
            # ИЗМЕНЕН: старый код — первый непрерывный блок закомментированных строк
            restored, seen = [], False
            for line in body:
                if not line.strip():
                    if seen:
                        break               # пустая строка после старого кода — граница
                    continue
                if indent_of(line) and line.lstrip().startswith("//") or line.lstrip().startswith("//"):
                    restored.append(uncomment(line))
                    seen = True
                elif seen:
                    break
                else:
                    break                   # первым идёт не комментарий — структура чужая
            if not restored:
                raise Refuse(f"вставка на строках {start}-{end} помечена ИЗМЕНЕН, но закомментированного "
                             "кода в ней нет — структура не распознана, откат не выполняется")

        # Строка с закрывающей меткой удаляется ЦЕЛИКОМ, даже когда метка стоит на ней
        # хвостом (`КонецПроцедуры // } ...`): такая форма бывает только у вставки вокруг
        # целого метода, и сам `КонецПроцедуры` там — наш код, а не чужой.
        # Сохрани откат эту строку — в модуле остался бы висячий `КонецПроцедуры`, и
        # такой модуль не компилируется.
        out[start - 1:end] = restored

        # Стык снятой вставки — место, где у соседей могли остаться пустые
        # строки-разделители (`separate`). Номера стыков, найденных раньше (они
        # ниже), сдвигаются на разницу длин; попавшие внутрь снятого — пропадают.
        delta = len(restored) - (end - start + 1)
        junctions = [(p + delta, q + delta, k) for p, q, k in junctions if p >= end]
        junctions.append((start - 1, start - 1 + len(restored), len(decisions)))

        dropped = []
        if base is None:
            # Без базовой версии разделители от пустых строк, бывших в модуле
            # до вставки, не отличить. Схлопываем пару подряд в одну — иначе
            # цикл «вставить-откатить» копил бы их.
            pos = start - 1 + len(restored)
            if 0 < pos < len(out) and not out[pos - 1].strip() and not out[pos].strip():
                del out[pos]
                dropped.append(end + 1)

        decisions.append({"start": start, "end": end, "sign": sign, "restored": len(restored),
                          "lines": list(restored), "dropped": dropped,
                          "region": r.get("region"), "inner": r.get("inner") or []})

    if base is not None:
        # кандидат -> (чьё решение, номер строки по тексту до правки)
        candidates = {}
        for p, q, k in junctions:
            if p >= 1 and not out[p - 1].strip():
                candidates[p - 1] = (k, decisions[k]["start"] - 1)
            if q < len(out) and not out[q].strip():
                candidates[q] = (k, decisions[k]["end"] + 1)
        out, failed, drop = settle(out, set(candidates), base)
        for index in sorted(drop):
            k, original = candidates[index]
            decisions[k]["dropped"].append(original)
        # Сверено или нет — у каждой вставки своё: иначе одно несверенное окно
        # объявляло бы несверенными все стыки модуля, и по diff пришлось бы
        # проверять места, которые совпали с HEAD побайтно.
        несверенные = {candidates[index][0] for index in failed}
        for k, d in enumerate(decisions):
            d["settled"] = k not in несверенные
    return out, decisions, notes


def task_regions(lines, mine, base):
    """Области, которые завела задача: ([(имя, «#Область», «#КонецОбласти»)],
    примечания).

    Своя — если внутри неё только вставки задачи [+] и пустые строки, а в
    базовой версии таких заголовков меньше, чем в модуле. Без базовой версии
    чья область, не сказать: она остаётся, о ней — примечание.
    """
    добавленные = [r for r in mine if r["sign"] == "+"]
    кандидаты = []
    for имя, начало, конец in module_regions(lines):
        внутри = [r for r in mine if начало < r["start"] and r["end"] < конец]
        if not внутри or any(r not in добавленные for r in внутри):
            continue
        покрыто = {n for r in внутри for n in range(r["start"], r["end"] + 1)}
        if all(n in покрыто or not lines[n - 1].strip() for n in range(начало + 1, конец)):
            кандидаты.append((имя, начало, конец))
    if not кандидаты:
        return [], []
    if base is None:
        return [], [f"область «{имя}» (строки {начало}-{конец}) после отката останется "
                    "пустой — если её завела задача, удалите её: базовой версии модуля нет, "
                    "чья область, не сверить" for имя, начало, конец in кандидаты]

    def заголовки(строки):
        счёт = {}
        for строка in строки:
            if строка.strip().startswith("#Область"):
                счёт[строка.strip()] = счёт.get(строка.strip(), 0) + 1
        return счёт

    в_базе, в_модуле = заголовки(base), заголовки(lines)
    return [о for о in кандидаты
            if в_модуле.get(lines[о[1] - 1].strip(), 0) > в_базе.get(lines[о[1] - 1].strip(), 0)], []


#: Строк контекста по краям окна, в котором стык сверяется с базовой версией.
SETTLE_CONTEXT = 5


def settle(out, candidates, base):
    """Пустые строки на стыках снятых вставок — как в базовой версии модуля.

    Не сними откат разделители, которые запись ставит снаружи вставки, модуль
    не вернулся бы к исходному (например, +2 строки после отката вложенной
    метки). Отличить разделитель от пустой строки,
    бывшей в модуле, по тексту нельзя — а по базовой версии (HEAD) можно:
    git и есть история, которую откат обещает восстановить.

    Соседние кандидаты собираются в окно с контекстом; окно ищется в базе по
    первой строке-не-кандидату и совмещается: строки-не-кандидаты — одна в
    одну, кандидат — остаётся (если совпал) или выбрасывается. Решение
    принимается, только если оно единственно на всех совпавших местах. Иначе
    (в базе это место другое: чужие правки, задача уже закоммичена) окно не
    трогается. Возвращает (строки, кандидаты несверенных окон, номера снятых).
    """
    if not candidates:
        return out, set(), set()
    order = sorted(candidates)
    clusters = []
    for c in order:
        if clusters and c - clusters[-1][-1] <= 2 * SETTLE_CONTEXT:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    where = {}
    for x, line in enumerate(base):
        where.setdefault(line, []).append(x)
    drop, failed = set(), set()
    for cluster in clusters:
        a = max(0, cluster[0] - SETTLE_CONTEXT)
        b = min(len(out), cluster[-1] + SETTLE_CONTEXT + 1)
        anchor = next((k for k in range(a, b) if k not in candidates), None)
        if anchor is None or anchor > cluster[0]:
            failed.update(cluster)
            continue
        answers = {align(out, anchor, b, base, x, candidates) for x in where.get(out[anchor], [])}
        answers.discard(None)
        if len(answers) != 1:
            failed.update(cluster)
            continue
        drop |= answers.pop()
    return [line for k, line in enumerate(out) if k not in drop], failed, drop


def align(out, j0, j1, base, i0, candidates):
    """Совместить out[j0:j1] с base от i0: множество выброшенных кандидатов или None.

    Строки-не-кандидаты обязаны совпасть одна в одну; кандидат совпавший может
    остаться, любой — выпасть. Два пути к одному месту базы дают один и тот же
    текст (выпала одна из двух одинаковых пустых строк) — берётся любой; разные
    места базы в конце окна — неоднозначность, None.
    """
    reach = {i0: frozenset()}
    for j in range(j0, j1):
        nxt = {}
        for i, dropped in reach.items():
            if i < len(base) and base[i] == out[j]:
                nxt.setdefault(i + 1, dropped)
            if j in candidates:
                nxt.setdefault(i, dropped | {j})
        if not nxt:
            return None
        reach = nxt
    return next(iter(reach.values())) if len(reach) == 1 else None


def method_spans(lines):
    """Методы модуля: [(имя, начало шапки, объявление, конец)], номера с единицы.

    Шапка — строки вплотную над объявлением: директива компиляции, описание,
    открывающая метка вставки вокруг метода. Пустая строка и закрывающая
    метка чужой вставки шапку обрывают.
    """
    spans, current = [], None
    for number, line in enumerate(lines, start=1):
        m = DECLARATION.match(line)
        if current is None and m:
            head = number
            while head > 1:
                above = lines[head - 2].strip()
                if not above.startswith(("&", "//")) or CLOSE_MARK.match(above):
                    break
                head -= 1
            current = (m.group(1), head, number)
            continue
        if current is not None and METHOD_END.match(line.strip()):
            spans.append(current + (number,))
            current = None
    return spans


#: Сколько строк смотреть от объявления до закрывающей скобки параметров.
DECLARATION_SPAN = 30
EXPORT_AFTER_PARAMETERS = re.compile(r"\)\s*Экспорт\b", re.IGNORECASE)


def declared_methods(lines):
    """Объявленные методы модуля: {имя: (экспортный ли, строка объявления)} —
    в порядке модуля, номера с единицы.

    Тем же разбором объявления, что у правки вставками (`DECLARATION`): что
    записал инструмент, проверка читает тем же пониманием. «Экспорт» стоит за
    скобкой параметров, а параметры бывают на нескольких строках — поэтому
    смотрится текст от объявления до скобки, без меток вставок.
    """
    методы = {}
    for номер, строка in enumerate(lines, start=1):
        найдено = DECLARATION.match(строка)
        if найдено is None or найдено.group(1) in методы:
            continue
        хвост = " ".join(code_part(lines[n])
                         for n in range(номер - 1, min(len(lines), номер - 1 + DECLARATION_SPAN)))
        скобка = хвост.find(")")
        экспорт = скобка >= 0 and EXPORT_AFTER_PARAMETERS.match(хвост, скобка) is not None
        методы[найдено.group(1)] = (экспорт, номер)
    return методы


def place_of(lines, number, insert):
    """Где в модуле строка `number` — словами: в каком методе, в какой области.

    Текст якоря сверяется, но «#КонецОбласти» и «КонецПроцедуры» в модуле не
    одни: вставка в конец чужой области прошла бы с «замечаний нет», и куда
    она ляжет, ответ бы не сказал.
    """
    methods = method_spans(lines)
    for name, head, start, end in methods:
        if not head <= number <= end:
            continue
        if insert and number == head:
            return f"перед методом «{name}»"
        if number < start:
            return f"в описании метода «{name}»"
        if number == start:
            return (f"перед объявлением метода «{name}», под его описанием" if insert
                    else f"объявление метода «{name}»")
        if insert and number == end:
            return f"в конце метода «{name}»"
        return f"в методе «{name}»"
    области = [о for о in module_regions(lines) if о[1] <= number <= о[2]]
    if not области:
        return "вне областей"
    имя, начало, конец = области[-1]                    # самая вложенная
    if number == начало:
        return f"перед областью «{имя}»" if insert else f"начало области «{имя}»"
    if insert and number == конец:
        return f"в конце области «{имя}»"
    раньше = [m[0] for m in methods if начало < m[3] < number]
    return f"в области «{имя}»" + (f", после метода «{раньше[-1]}»" if раньше else "")


def directive_split(lines, number):
    """Вставка перед объявлением метода, над которым стоит директива, — текст
    отказа или None.

    Код встал бы между «&НаКлиенте» и «Процедура …»: директива досталась бы
    вставленному коду, а метод остался бы без неё. Законного кода в этом
    месте не бывает — описание метода стоит над директивой, а не под ней.
    """
    if number < 2 or number > len(lines) or not DECLARATION.match(lines[number - 1]):
        return None
    above = lines[number - 2].strip()
    if not above.startswith("&"):
        return None
    head = next((h for name, h, start, _ in method_spans(lines) if start == number), number - 1)
    return (f"строка {number}: вставка встала бы между директивой «{above}» (строка "
            f"{number - 1}) и объявлением метода — директива досталась бы вставленному коду. "
            f"Перед методом вставляют якорем первую строку его шапки: строка {head} "
            f"«{lines[head - 1].strip()}»")


def method_range(lines, name):
    """Границы метода по имени: от строки объявления до КонецПроцедуры/КонецФункции."""
    start = None
    for i, line in enumerate(lines, start=1):
        t = line.strip()
        if start is None and METHOD_START.match(t):
            m = re.match(r"^(?:Процедура|Функция)\s+([^\s(]+)", t, re.IGNORECASE)
            if m and m.group(1).lower() == name.lower():
                start = i
            continue
        if start is not None and METHOD_END.match(t):
            return start, i
    return None


def rename_edits(lines, old_name, new_name, own=()):
    """Правки для переименования метода внутри модуля: объявление и обращения.

    Каждая затронутая строка — отдельная правка ИЗМЕНЕН со своей меткой: правило
    «одна логическая правка — одна вставка» тут работает против нас, но переименование
    в чужом модуле и должно быть дорогим, иначе след теряется.

    Обращение через точку переименовывается, только если перед точкой — сам этот
    модуль (`own`: имя общего модуля, `ЭтотОбъект`…): `ДругойМодульПовтИсп.Х()`
    в модуле, где объявлен свой `Х`, — вызов чужого метода, и переименовывать
    его вместе со своим нельзя. Такие места возвращаются
    вторым значением — их перечень печатается рядом с решениями.

    Метка на строке не переименовывается, но код перед ней — да: в части
    вендорских модулей открывающая метка часто стоит хвостом на объявлении
    (`Функция Х() // {[+]…`), и считай разбор строку целиком меткой, объявление
    молча осталось бы со старым именем, а вызовы получили бы новое. Новая строка
    идёт без хвостовой метки: такая строка открывает чужую вставку, правка в
    ней оборачивает вставку снаружи, и метка остаётся в деактивированной копии.

    Обращения из ДРУГИХ модулей этот инструмент не ищет и не правит: полный
    поиск вызовов по выгрузке ему недоступен, а инструмент, обещающий найти все
    вызовы и не находящий их, хуже отсутствующего.
    """
    word = re.compile(rf"(?<![\wА-Яа-яЁё_]){re.escape(old_name)}(?![\wА-Яа-яЁё_])", re.IGNORECASE)
    qualifier = re.compile(r"([\wА-Яа-яЁё_]+)\s*\.\s*$")
    own_lower = {o.lower() for o in own}
    edits, foreign = [], []
    for i, line in enumerate(lines, start=1):
        code = code_part(line)
        if not word.search(code):
            continue
        out, pos = [], 0
        for m in word.finditer(code):
            before = code[:m.start()]
            if before.rstrip().endswith("."):
                q = qualifier.search(before)
                if q is None or q.group(1).lower() not in own_lower:
                    foreign.append((i, (q.group(1) if q else "…") + "." + m.group()))
                    continue
            out.append(code[pos:m.start()] + new_name)
            pos = m.end()
        if not out:
            continue
        out.append(code[pos:])
        edits.append(Edit(line=i, lines=1, first_line=line, last_line=line, code="".join(out),
                          carried=True))
    return edits, foreign


def all_refusals(отказы):
    """Отказы по правкам одного модуля — одним текстом, каждый своей строкой."""
    if len(отказы) == 1:
        return отказы[0]
    return f"правок с отказом: {len(отказы)}:\n" + "\n".join(
        f"    {номер}) {текст}" for номер, текст in enumerate(отказы, 1))


def apply_all(lines, edits, meta):
    lines = list(lines)
    problems = []
    ranges = marker_ranges(lines, problems)
    # Отказы по правкам — все разом: отказ по первой правке прятал бы вторую
    # проблему того же модуля (устаревший якорь, повтор метода) до следующего
    # вызова.
    items, отказы = [], []
    for edit in edits:
        try:
            item = checked(edit, lines)
        except Refuse as отказ:
            отказы.append(str(отказ))
            continue
        повтор = repeated(item, lines, ranges, meta["task"])
        if повтор:
            отказы.append(повтор)
        items.append(item)
    if отказы:
        raise Refuse(all_refusals(отказы))

    # правило LSP: диапазоны правок не пересекаются, иначе часть документа
    # правилась бы дважды и результат зависел бы от порядка
    spans = sorted((i["first"], i["last"]) for i in items)
    for k in range(1, len(spans)):
        if spans[k][0] <= spans[k - 1][1]:
            raise Refuse(f"правки пересекаются: строки {spans[k - 1][0]}-{spans[k - 1][1]} и {spans[k][0]}-{spans[k][1]}")

    # По порядку строк, как у отката: в порядке задания решения шли бы
    # вразнобой с откатом той же правки.
    decisions = sorted(classify_all(items, lines, ranges, meta), key=lambda d: d["first"])
    for d in decisions:
        d["where"] = place_of(lines, d["line"], bool(d.get("insert")))
    # Дефекты чужой разметки (незакрытые, осиротевшие метки) печатаются
    # примечаниями рядом с решениями: правку они не останавливают, но авария
    # из `marker_ranges` случается именно тогда, когда о такой метке никто не
    # сказал. Целиком — те, что рядом с правками; далёкие сводятся в одну
    # строку: двенадцать строк о чужой разметке в каждом ответе — шум, за
    # которым теряется решение.
    near, far = [], []
    for p in problems:
        m = re.match(r"строка (\d+):", p)
        n = int(m.group(1)) if m else 0
        # Влиять на решение метка без пары может только в свою сторону:
        # закрывающая — на правки выше неё (её вставка кончалась бы на ней),
        # открывающая — на правки ниже. Иначе закрывающая на конце соседней
        # функции над правками называлась бы «сверьте решение» в каждом ответе,
        # хотя на решения не влияет.
        закрывающая = "закрывающая метка без открывающей" in p
        if any((n - NOTE_REACH <= i["first"] <= n) if закрывающая
               else (n <= i["last"] <= n + NOTE_REACH) for i in items):
            near.append(p)
        else:
            far.append(n)
    if far:
        # Номера — чтобы сводку можно было проверить: без них «ещё меток: 3»
        # пришлось бы искать самому. Что значит «в разборе не учтены» и почему
        # далёкие не важны, сводка говорит сама: без пояснения её легко понять
        # неверно.
        shown = ", ".join(str(n) for n in far[:10]) + (", …" if len(far) > 10 else "")
        near.append(f"ещё меток без пары: {len(far)} ({'строка' if len(far) == 1 else 'строки'} "
                    f"{shown}) — на решения не влияют: дальше {NOTE_REACH} строк от правок "
                    "или по другую сторону от них (закрывающая — ниже правок, открывающая — "
                    "выше); в разборе не учтены")
    # Неявно закрытая метка объявления — допущение, на котором стоит решение:
    # оно названо, когда правка внутри такого метода. Соседние методы на
    # решение не влияют, и четыре строки о них рядом с одной правкой были бы
    # шумом.
    for r in ranges:
        if r.get("implicit") and any(r["start"] <= i["first"] <= r["end"] for i in items):
            near.append(f"строка {r['start']}: метка {r['task'] or 'без ИД'} на объявлении метода "
                        f"без закрывающей — вставкой считается весь метод, строки "
                        f"{r['start']}-{r['end']}")
    decisions.extend({"line": 0, "first": 0, "last": 0, "marker": False, "kind": None,
                      "reason": p, "note": True} for p in near)

    # обёртка снаружи занимает всю чужую вставку — с соседней правкой она
    # пересечься не должна, и это проверяется уже по решениям
    spans = sorted(((d["replace"][0], d["replace"][1], d) for d in decisions
                    if not d.get("note")), key=lambda x: x[0])
    for i in range(1, len(spans)):
        if spans[i][0] <= spans[i - 1][1]:
            raise Refuse(f"правки пересекаются: строки {spans[i - 1][0]}-{spans[i - 1][1]} и {spans[i][0]}-{spans[i][1]}")

    # применяем СНИЗУ ВВЕРХ: ранняя правка иначе сдвинула бы номера для поздних
    for start, end, d in sorted(spans, key=lambda x: -x[0]):
        if not d["block"]:
            lines[start - 1:end] = []                 # физическое удаление
        elif d["insert"]:
            # ЧИСТАЯ вставка: код встаёт ПЕРЕД строкой-якорем, якорь сдвигается вниз.
            # Признак берётся из состава правки (`lines` == 0), а не из типа метки:
            # на пути «без маркера» (модуль создан задачей, правка внутри своей
            # вставки) типа нет, и условие по типу молча ЗАМЕНИЛО бы якорь —
            # например, `#КонецОбласти` нового модуля.
            lines[start - 1:start - 1] = d["block"]
        else:
            lines[start - 1:end] = d["block"]

    # где блок каждой правки оказался в новом тексте — для показа
    offset = 0
    for start, end, d in spans:
        d["at"] = start + offset
        if not d["block"]:
            offset -= end - start + 1
        elif d["insert"]:
            offset += len(d["block"])
        else:
            offset += len(d["block"]) - (end - start + 1)
    # и кто стоит вокруг него — строкой выше и строкой ниже
    for _, _, d in spans:
        после = d["at"] - 1 + len(d["block"] or ())
        d["context"] = (lines[d["at"] - 2] if d["at"] >= 2 else None,
                        lines[после] if после < len(lines) else None)

    return lines, decisions


# --- вход домена ---------------------------------------------------------------


def _decision(d):
    return Decision(d["line"], d["first"], d["last"], d["marker"], d.get("kind"),
                    d["reason"], bool(d.get("note")), bool(d.get("insert")),
                    tuple(d.get("block") or ()), d.get("at", 0), tuple(d.get("context") or ()),
                    where=d.get("where", ""))


def edit_module(lines, edits, signature, new_module, notes=(), markers=True):
    """Строки модуля и правки -> (новые строки, решения). Отказ — `Refuse`.

    `new_module` — модуль создан текущей задачей: внутри него разметки нет
    вовсе, и это знает площадка, а не домен. `notes` —
    примечания, добытые до правок (что переименование оставило нетронутым).
    `markers` — ставит ли команда метки вставок: нет — правка на месте.
    """
    if not edits:
        raise Refuse("в задании нет ни одной правки")
    meta = {"task": signature.task, "date": signature.date, "author": signature.author,
            "tag": signature.tag, "new_module": new_module, "markers": markers}
    new_lines, decisions = apply_all(lines, edits, meta)
    return new_lines, ([_decision(d) for d in decisions]
                       + [Decision(0, 0, 0, False, None, n, True) for n in notes])


def revert(lines, task, base=None):
    """Снять вставки задачи: (новые строки, решения). `base` — строки модуля в
    базовой версии (HEAD), по ним сверяются пустые строки на стыках."""
    new_lines, reverted, notes = revert_task(lines, task, base)
    edge = {None: "; пустые строки на стыке не сверены — базовой версии модуля нет, проверьте diff",
            True: "; пустые строки на стыке — как в базовой версии",
            False: "; пустые строки на стыке не сверены — в базовой версии это место другое, "
                   "проверьте diff"}
    # Восстановленный текст — в решении: по одним счётчикам не видно до
    # записи, что вернётся на место.
    def разделители(номера):
        if not номера:
            return ""
        return (f", снята пустая строка-разделитель {номера[0]}" if len(номера) == 1
                else ", сняты пустые строки-разделители " + ", ".join(map(str, sorted(номера))))

    def что_снято(d):
        if d.get("region"):
            вставки = ", ".join(f"{a}-{b}" for a, b in d["inner"])
            return (f"снята область «{d['region']}» со вставками задачи {task} (строки "
                    f"{вставки}) — её завела задача: в базовой версии её нет")
        return f"снята вставка [{d['sign'] or '?'}] задачи {task}"

    # по порядку строк: снимаются снизу вверх, а читать снизу вверх
    # непривычно
    reverted = sorted(reverted, key=lambda d: d["start"])
    # Где восстановленное окажется в новом тексте: показ отката нумерует
    # строки так же, как показ правки. Сдвиг — от снятого выше и
    # от снятых выше разделителей.
    сдвиг, снятые = 0, sorted(n for d in reverted for n in d["dropped"])
    decisions = []
    for d in reverted:
        выше = sum(1 for n in снятые if n < d["start"])
        at = d["start"] + сдвиг - выше
        # соседи восстановленного в новом тексте; у пустого — строки стыка
        после = at - 1 + len(d["lines"])
        context = (new_lines[at - 2] if at >= 2 else None,
                   new_lines[после] if после < len(new_lines) else None)
        decisions.append(Decision(
            d["start"], d["start"], d["end"], False, "откат",
            "{}, восстановлено строк: {}{}{}".format(
                что_снято(d), d["restored"], разделители(d["dropped"]), edge[d.get("settled")]),
            block=tuple(d["lines"]), at=at, context=context,
            dropped=tuple(sorted(d["dropped"]))))
        сдвиг += d["restored"] - (d["end"] - d["start"] + 1)
    if not reverted:
        decisions.append(Decision(0, 0, 0, False, None, f"вставок задачи {task} в модуле нет", True))
    decisions.extend(Decision(0, 0, 0, False, None, n, True) for n in notes)
    return new_lines, decisions


def date_note(date, today):
    """Дата меток не сегодняшняя — примечание или None.

    В метку ставится дата правки, а дату задания, кроме как с сегодняшней,
    сверить не с чем: без примечания вчерашняя дата принималась бы без слова.
    Отказом это не сделать:
    задание, начатое вчера, законно доносят сегодня, — решает тот, кто его
    составил.
    `today` — «дд.мм.гггг» от площадки (у домена часов нет), `None` — не знаем.
    """
    if not date or not today or date == today:
        return None
    return (f"дата меток {date} — не сегодняшняя ({today}): в метке ставится дата "
            "правки; если дата задана намеренно, примечание не мешает записи")


def rename(lines, old_name, new_name, own=()):
    """Переименование метода, объявленного в модуле: (правки, примечания).

    `own` — слова, которые перед точкой означают сам этот модуль (см.
    `modules.own_qualifiers`). Метода в модуле нет — отказ: обращения к методу
    другого модуля — обычные правки, а не переименование.
    """
    span = method_range(lines, old_name)
    занят = method_range(lines, new_name)
    if span is None and занят is not None:
        # Повтор задания после записи: «не объявлен» читалось бы как ошибка в
        # имени, хотя переименование уже внесено.
        raise Refuse(f"метод «{old_name}» в модуле не объявлен, а «{new_name}» объявлен "
                     f"(строка {занят[0]}) — переименование уже внесено?")
    if span is None:
        raise Refuse(f"метод «{old_name}» в модуле не объявлен — переименовывается метод "
                     "своего модуля; обращения к методу другого модуля правятся обычными правками")
    if занят is not None:
        raise Refuse(f"метод «{new_name}» в модуле уже есть (строка {занят[0]}) — "
                     "переименование объявило бы его второй раз")
    edits, foreign = rename_edits(lines, old_name, new_name, own)
    notes = []
    if foreign:
        shown = ", ".join(f"строка {n} «{text}»" for n, text in foreign[:10])
        more = f" и ещё {len(foreign) - 10}" if len(foreign) > 10 else ""
        notes.append("обращения через точку к другим модулям и объектам не переименованы — "
                     f"это не этот метод: {shown}{more}")
    declaration = ""
    for n in range(span[0], min(span[1], span[0] + 20) + 1):
        declaration += " " + code_part(lines[n - 1])
        if ")" in declaration:
            break
    if re.search(r"\)\s*Экспорт\b", declaration, re.IGNORECASE):
        notes.append(f"метод «{old_name}» экспортный — обращения из других модулей инструмент "
                     "не ищет и не правит: найдите их и переименуйте отдельными правками")
    return edits, notes
