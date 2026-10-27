"""Язык ответов плана изменений: сверка текстом и JSON, план по факту — JSON.

Расхождение называет объект и что именно разошлось; у расхождения по модулю —
файл и строка объявления. Итог — «СОВПАДАЕТ» только без расхождений;
предупреждения его не отменяют, но называются числом.
"""

from ..jobs.plan import план_в_json


def _где(f):
    if f.path and f.line:
        return f"{f.path}:{f.line}"
    return f.path or ""


def plan_check_lines(result):
    lines = [f"Сверка плана изменений: {result.source}",
              f"Объектов в плане: {len(result.plan.objects)}, тронуто задачей: {len(result.touched)}"]
    lines += [f"   {пояснение}" for пояснение in result.notes]
    if result.findings:
        lines.append("")
        for f in result.findings:
            where = _где(f)
            lines.append(f"   {f.level:14} [{f.code}] {f.message}" + (f"   ({where})" if where else ""))
    lines.append("")
    ошибок, предупреждений = len(result.errors), len(result.warnings)
    if ошибок:
        lines.append(f"РАСХОЖДЕНИЙ: {ошибок}, предупреждений: {предупреждений}")
    else:
        lines.append("СОВПАДАЕТ" + (f" (предупреждений: {предупреждений})" if предупреждений else ""))
    return lines


def plan_check_json(result):
    """Находки того же вида, что у проверки правок, и `объект` — «Вид.Имя»."""
    return {
        "источник": result.source,
        "находки": [{"код": f.code, "уровень": f.level, "объект": f.obj, "файл": f.path,
                     "строка": f.line, "текст": f.message} for f in result.findings],
        "пропущено": [],
        "пояснения": list(result.notes),
    }


def plan_emit_json(result):
    """План по факту — тот же формат, что принимает сверка."""
    return план_в_json(result.plan)
