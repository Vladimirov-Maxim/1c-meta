"""Ответ на задание на код: подпись, решения по модулям, что будет записано.

Текст решений устойчив: по нему сверяются фикстуры тех, кто разбирает ответ.
Сверх того просмотр показывает сам текст, который встанет на место правки, с
номерами строк нового модуля: иначе пустые строки, отступы, деактивированные
чужие метки и расширение диапазона до всей чужой вставки были бы видны только
после записи.
"""

from ..domain.edits import DECLARATION
from . import NO_CHANNEL

#: Блок длиннее этого показывается началом и концом.
SHOW_WHOLE = 40
SHOW_START, SHOW_END = 20, 10


def place(d):
    """Где правка — словами, а не «строки 613-613» у вставки перед строкой.

    И в каком методе или области: текст якоря «#КонецОбласти» в модуле не
    один, и без этого вставка в конец чужой области прошла бы без слова о
    том, куда ляжет.
    """
    if d.insert:
        where = f"перед строкой {d.first}"
    elif d.line and d.line != d.first:
        where = f"строка {d.line} → обёртка строк {d.first}-{d.last}"
    else:
        where = f"строка {d.first}" if d.first == d.last else f"строки {d.first}-{d.last}"
    return f"{where} ({d.where})" if d.where else where


def neighbours(d, lines, pairs, end):
    """Блок со строкой-соседом сверху и снизу: «·» вместо «│».

    Решение о разделителе рядом с чужой меткой иначе было бы видно только в
    файле после записи; у отката соседи показываются тоже — шапка их обещает.
    """
    above, below = d.context if len(d.context) == 2 else (None, None)
    if above is not None:
        lines.append(f"        {d.at - 1:>6} ·{visibly(above)}")
    for number, text in pairs:
        lines.append(f"        {number if number else '':>6} │{visibly(text)}")
    if below is not None:
        lines.append(f"        {end + 1:>6} ·{visibly(below)}")
    return lines


def visibly(text):
    """Пустая строка с отступом — знаками: «→» на табуляцию, «␣» на пробел.

    Табуляция, которую инструмент ставит в пустые строки тела, иначе
    выглядела бы в показе пустой строкой, и проверять её пришлось бы по
    байтам. В строке с кодом отступ и так виден.
    """
    if text and not text.strip():
        return text.replace("\t", "→").replace(" ", "␣")
    return text


def shown(d, apply_now, whole=False, detailed="подробный показ"):
    """Текст блока правки с номерами строк нового модуля; длинный — краями,
    `целиком` — весь. У записи текст — только при `целиком`: без него ответ
    записи даёт одни номера, и записанное пришлось бы сверять чтением файла."""
    if d.kind == "откат":
        if apply_now and not whole:
            return []
        # Разделители — в счёте той же вставки: итоговой строкой отдельно от
        # неё «снимается 7» не сошлось бы с ушедшими 8.
        separators = ""
        if d.dropped:
            separators = (f" и пустая строка-разделитель {d.dropped[0]}" if len(d.dropped) == 1
                           else " и пустые строки-разделители "
                           + ", ".join(map(str, d.dropped)))
        lines = [f"      снимаются строки {d.first}-{d.last} ({d.last - d.first + 1})"
                  f"{separators}; на их место "
                  + ("— ничего, на стыке:" if not d.block else
                     f"вернётся строк: {len(d.block)} — "
                     + (f"строка {d.at}" if len(d.block) == 1
                        else f"строки {d.at}-{d.at + len(d.block) - 1}")
                     + " нового текста:")]
        return neighbours(d, lines, list(enumerate(d.block, d.at)), d.at + len(d.block) - 1)
    if not d.block:
        return [] if apply_now or d.insert else [
            f"      будет удалено строк: {d.last - d.first + 1}"]
    end = d.at + len(d.block) - 1
    if apply_now and not whole:
        return [f"      записано — строки {d.at}-{end}"]
    lines = [f"      записано — строки {d.at}-{end}:" if apply_now
              else f"      будет записано — строки {d.at}-{end} нового текста:"]
    pairs = list(enumerate(d.block, d.at))
    if len(pairs) > SHOW_WHOLE and not whole:
        # Объявления методов из середины видны всегда: иначе при переименовании
        # строка с новым именем пряталась бы в свёрнутом.
        middle = pairs[SHOW_START:-SHOW_END]
        visible = [pair for pair in middle if DECLARATION.match(pair[1])]
        hidden = len(middle) - len(visible)
        pairs = (pairs[:SHOW_START]
                + [(None, f"… ещё строк: {hidden}; целиком — {detailed} …")]
                + visible + ([(None, "…")] if visible else [])
                + pairs[-SHOW_END:])
    return neighbours(d, lines, pairs, end)


def code_lines(result, apply_now=False, hints=NO_CHANNEL, whole=False):
    lines = []
    emit = lines.append
    caption = result.signature
    # у чистого отката даты и автора нет — иначе шапка напечатала бы «дата , автор »
    emit(f"Задача: {caption.task}" + (f", дата {caption.date}, автор {caption.author}"
                                      if caption.date or caption.author else ""))
    emit(f"Модулей в задании: {len(result.per_module)}")
    # Две системы номеров в одном ответе выглядят одинаково, поэтому шапка
    # говорит, какие номера по какому тексту. «Разметку модуля» она называет —
    # иначе её номера сверяли бы по новому тексту, — но только когда разметка
    # в ответе есть: иначе отправляла бы искать раздел, которого нет.
    markup = any(d.note for _, decisions in result.per_module for d in decisions)
    emit("Номера строк в решениях" + (" и в «разметке модуля»" if markup else "")
         + " — по тексту до правки; " + ("в «записано» — нового текста." if apply_now
                                         else "в показе — нового текста."))
    if not apply_now:
        emit("В показе «│» — что будет записано, «·» — соседние строки, для ориентира; "
             "«→» — табуляция в пустой строке.")
    elif whole:
        emit("В показе «│» — что записано, «·» — соседние строки, для ориентира; "
             "«→» — табуляция в пустой строке.")
    for remark in getattr(result, "notes", ()):
        emit(f"Примечание: {remark}")
    for ref, decisions in result.per_module:
        emit("")
        fmt = (getattr(result, "formats", None) or {}).get(str(ref))
        emit(f"  {ref} (правок: {len([d for d in decisions if not d.note])}"
             + (f"; файл {fmt}" + ("" if " — " in fmt else " — так и останется") if fmt else "")
             + ")")
        for d in decisions:
            if d.note:
                # Дефекты чужой разметки (незакрытые, осиротевшие метки) — рядом
                # с решениями: правку они не останавливают, но авария разметки
                # случается именно тогда, когда о такой метке молчат.
                emit(f"    разметка модуля: {d.reason}")
                continue
            mark = d.kind if d.marker else (d.kind or "без меток")
            emit(f"    {place(d)}: {mark} — {d.reason}")
            lines.extend(shown(d, apply_now, whole, hints.detailed))
    emit("")
    if apply_now:
        emit(f"Записано модулей: {len(result.written)}.")
        # Записанное — путями: модуль, которого в задании не было, виден сразу.
        for path in result.written:
            emit(f"   {path}")
    else:
        emit(f"Показ без записи. Для записи {hints.write}.")
    return lines
