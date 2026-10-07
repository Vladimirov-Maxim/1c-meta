"""Физический формат файла выгрузки: что вернуть файлу задачи, чтобы он был
таким, каким его пишет конфигуратор.

Не проверка, а операция. Инструменты записи агентов не умеют писать BOM,
срезают хвостовые пробелы у любой записываемой строки и не доносят до файла
строку из одних пробельных символов; разовая правка не держится — следующая
перезапись теряет её снова. Поэтому нормализация идемпотентна и запускается
перед каждым показом кода и перед коммитом.

Что возвращается, по каждому файлу задачи:

1. BOM — файл выгрузки в UTF-8 с BOM;
2. переводы строк — принятые там, где лежит выгрузка (в репозитории — как у
   его файлов, у пары каталогов — как у эталона);
3. хвостовые пробелы — строкам, которые содержательно не менялись, окончание
   из базы: класс «строка заменена на себя же без хвоста»;
4. пустые строки внутри тел методов — табуляция по уровню вложенности:
   конфигуратор хранит в них отступ, и без него первая же выгрузка из базы
   даёт правки, которых никто не делал;
5. завершающий перевод строки — как в базе.

Строки, где пробельный символ уже есть, не переоформляются: их правка дала бы
косметическую правку чужого кода, а её проверка правок запрещает. Пустые
строки чужого кода — тоже: правится только добавленное задачей.
"""

from dataclasses import dataclass

from .edits import DEDENT, METHOD_END, METHOD_START

BOM = b"\xef\xbb\xbf"
EOLS = {"CRLF": "\r\n", "LF": "\n"}


@dataclass(frozen=True)
class FileText:
    """Файл как текст: BOM, строки без переводов, счёт переводов и последний."""

    bom: bool
    lines: tuple
    crlf: int
    lf: int
    final_eol: bool

    @property
    def eol_word(self):
        """Каких переводов больше — «CRLF» или «LF» (поровну — CRLF, как пишет
        конфигуратор); переводов нет — None."""
        if not self.crlf and not self.lf:
            return None
        return "LF" if self.lf > self.crlf else "CRLF"


def parse(data):
    """Байты -> `FileText`. Строки — как их считает git: по «\\n», «\\r» перед
    ним — часть перевода."""
    bom = data.startswith(BOM)
    text = (data[3:] if bom else data).decode("utf-8", "replace")
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    final = text.endswith("\n")
    if final:
        text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
    lines = tuple(строка[:-1] if строка.endswith("\r") else строка
                  for строка in text.split("\n")) if text else ()
    return FileText(bom, lines, crlf, lf, final)


def render(lines, eol, bom=True, final_eol=True):
    """Строки -> байты файла."""
    text = EOLS[eol].join(lines) + (EOLS[eol] if final_eol and lines else "")
    return (BOM if bom else b"") + text.encode("utf-8")


def indent_blank_lines(lines, only=None):
    """Пустым строкам внутри тел методов — отступ по уровню вложенности.

    Уровень — по СЛЕДУЮЩЕЙ непустой строке: её отступ, и шаг сверху, если
    она закрывает конструкцию (КонецЕсли, Иначе, КонецПроцедуры…) — пустая
    строка ещё принадлежит закрываемому блоку. Следующая строка надёжнее
    предыдущей: продолжение многострочного выражения сбивает счёт по
    предыдущей, но не по следующей. Только строки нулевой длины; `only` —
    номера строк (с единицы), которые можно трогать: у изменённого файла это
    добавленные задачей — пустые строки без отступа лежат в чужих модулях
    сотнями, и «починка» их была бы правкой сверх объёма задачи.
    """
    out = list(lines)
    in_body = False
    for i, line in enumerate(out):
        t = line.strip()
        if METHOD_START.match(t):
            in_body = True
            continue
        if METHOD_END.match(t):
            in_body = False
            continue
        if not in_body or line != "" or (only is not None and i + 1 not in only):
            continue
        j = i + 1
        while j < len(out) and not out[j].strip():
            j += 1
        if j >= len(out):
            continue
        следующая = out[j]
        отступ = следующая[:len(следующая) - len(следующая.lstrip(" \t"))]
        if DEDENT.match(следующая.strip()):
            отступ += "    " if отступ and "\t" not in отступ else "\t"
        if отступ:
            out[i] = отступ
    return out


def restore_trailing(lines, old_lines, pairs):
    """Строкам, которые совпадают с базой без хвостовых пробелов, — окончание
    из базы. `pairs` — (строка базы, строка новой версии), с единицы.
    -> (строки, сколько восстановлено)."""
    out = list(lines)
    restored = 0
    for o, n in pairs:
        if not (1 <= o <= len(old_lines) and 1 <= n <= len(out)):
            continue
        было, стало = old_lines[o - 1], out[n - 1]
        if было != стало and было.rstrip() == стало.rstrip():
            out[n - 1] = было
            restored += 1
    return out, restored


def normalized(data, old_data=None, pairs=(), added=None, eol=None, module=False):
    """Байты файла задачи -> (нормализованные байты, [что исправлено словами]).

    `old_data` — тот же файл в базе (None — файл новый); `pairs` — кандидаты
    «та же строка» (строка базы, строка новой версии); `added` — номера строк,
    добавленных задачей: только им ставится отступ пустых строк (у нового
    файла — всем); `eol` — «CRLF» или «LF», принятые там, где лежит выгрузка;
    None — свои переводы файла (большинства), их сверять не с чем;
    `module` — файл модуля: пустым строкам в методах нужен отступ.
    """
    cur = parse(data)
    lines = list(cur.lines)
    fixes = []
    if not cur.bom:
        fixes.append("BOM")
    цель = eol or cur.eol_word or "CRLF"
    if cur.crlf and cur.lf:
        fixes.append(f"смешанные переводы строк ({cur.crlf} CRLF / {cur.lf} LF)")
    elif cur.eol_word and cur.eol_word != цель:
        fixes.append(f"переводы строк {cur.eol_word} -> {цель}")
    final = cur.final_eol
    if old_data is not None:
        old = parse(old_data)
        lines, restored = restore_trailing(lines, old.lines, pairs)
        if restored:
            fixes.append(f"хвостовые пробелы: {restored} строк")
        if old.final_eol != cur.final_eol:
            final = old.final_eol
            fixes.append("вернуть завершающий перевод строки" if old.final_eol
                         else "снять завершающий перевод строки")
    if module:
        before = lines
        lines = indent_blank_lines(lines, None if old_data is None else set(added or ()))
        отступов = sum(1 for a, b in zip(before, lines, strict=True) if a != b)
        if отступов:
            fixes.append(f"отступ пустых строк: {отступов}")
    if not fixes:
        return data, []
    result = render(lines, цель, True, final)
    return (data, []) if result == data else (result, fixes)
