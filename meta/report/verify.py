"""Язык ответов проверки правок: текст для человека и агента, JSON для хука.

Итог называет пропуски: «чисто» выдаётся только тогда, когда проверено всё.
Число без состава — не доказательство, поэтому при небольшом составе он
печатается целиком: «BOM на месте в трёх файлах» одинаково убедительно и при
трёх правильных файлах, и при трёх посторонних.
"""

#: Больше стольких файлов состав не печатается: такой объём для правок
#: задачи ненормален — похоже на перезалив выгрузки или обновление вендора.
COMPOSITION_WHOLE = 30

#: Больше стольких находок — сначала сводка по файлам, и у файла печатается не
#: больше `НА_ФАЙЛ`: чужой файл с сотнями находок не должен вытеснять из
#: ответа файлы задачи. Полный список — в JSON.
SUMMARY_FROM = 50
PER_FILE = 10


def _where(f):
    if f.path and f.line:
        return f"{f.path}:{f.line}"
    return f.path or ""


def _filter(result):
    parts = []
    if result.only:
        parts.append("правила " + ", ".join(result.only))
    if result.paths:
        parts.append("файлы " + ", ".join(result.paths))
    return "; ".join(parts)


def _line(f):
    where = _where(f)
    return f"   {f.level:14} [{f.code}] {where + ' — ' if where else ''}{f.message}"


def _findings(result):
    if len(result.findings) <= SUMMARY_FROM:
        return [_line(f) for f in result.findings]
    by_file = {}
    for f in result.findings:
        by_file.setdefault(f.path or "", []).append(f)
    lines = [f"   Находок {len(result.findings)} в {len(by_file)} файлах — сводка; у файла показано не "
              f"больше {PER_FILE}, все — в JSON; сузить — only, paths:"]
    for path, own in sorted(by_file.items(), key=lambda pt: (-len(pt[1]), pt[0])):
        error_count = len([f for f in own if f.blocking])
        lines.append(f"      {len(own):5}  (ошибок {error_count})  {path or 'без файла'}")
    lines.append("")
    for path, own in by_file.items():
        lines += [_line(f) for f in own[:PER_FILE]]
        if len(own) > PER_FILE:
            lines.append(f"   … ещё {len(own) - PER_FILE} в {path or 'находках без файла'}")
    return lines


def verify_lines(result):
    lines = [f"Проверка правок: {result.source}",
              f"Файлов задачи: {len(result.files)}" + (" (по отбору paths)" if result.paths else "")]
    if result.filtered:
        lines.insert(1, f"Фильтр: {_filter(result)} — остальное не проверялось")
    if len(result.files) <= COMPOSITION_WHOLE:
        lines += [f"   {c.status}  {c.path}" for c in result.files]
    else:
        lines.append("   состав не печатается: больше 30 файлов — похоже на перезалив выгрузки")
    lines += [f"   {explanation}" for explanation in result.notes]
    if result.findings:
        lines.append("")
        lines += _findings(result)
    if result.skipped:
        lines.append("")
        lines.append(f"Пропущено правил: {len(result.skipped)}")
        lines += [f"   - {what}: {why}" for what, why in result.skipped]
    lines.append("")
    error_count, warning_count = len(result.errors), len(result.warnings)
    if error_count:
        lines.append(f"НАРУШЕНИЙ: {error_count}, предупреждений: {warning_count}")
    elif warning_count:
        lines.append(f"ПРЕДУПРЕЖДЕНИЙ: {warning_count}; нарушений нет"
                      + (" — но не всё проверено, см. «Пропущено»" if result.skipped else ""))
    elif result.skipped:
        lines.append(f"НЕПОЛНЫЙ ПРОГОН: среди проверенного нарушений нет, но пропущено правил: "
                      f"{len(result.skipped)} — «чисто» это не означает")
    elif result.filtered:
        lines.append(f"ЧИСТО ПО ФИЛЬТРУ ({_filter(result)}): нарушений нет — остальное не проверялось")
    else:
        lines.append("ЧИСТО: нарушений нет, проверены все правила")
    return lines


def verify_json(result):
    """Находки одного вида для хука: `код` — правило словами домена, `уровень` —
    «ошибка» или «предупреждение», `файл` — от корня выгрузки, `строка` — в
    новой версии; у находки по объекту метаданных файла нет."""
    return {
        "источник": result.source,
        "находки": [{"код": f.code, "уровень": f.level, "файл": f.path, "строка": f.line,
                     "текст": f.message} for f in result.findings],
        "пропущено": [{"что": what, "почему": why} for what, why in result.skipped],
        "пояснения": list(result.notes),
        "фильтр": {"правила": list(result.only), "файлы": list(result.paths)},
    }
