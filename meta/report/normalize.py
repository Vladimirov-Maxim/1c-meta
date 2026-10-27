"""Язык ответов нормализации формата: что будет исправлено и что исправлено."""


def normalize_lines(result, apply_now, write):
    """`записать` — как в этом канале применить: «повторите с --apply» или
    «вызовите normalize_apply с теми же параметрами»."""
    lines = [f"Нормализация формата: {result.source}",
              f"Текстовых файлов задачи: {len(result.files)}"]
    lines += [f"   {explanation}" for explanation in result.notes]
    for path, what in result.fixes:
        lines.append(f"   [{'исправлено' if apply_now else 'к правке'}] {path}: {'; '.join(what)}")
    lines.append("")
    if not result.fixes:
        lines.append(f"ФОРМАТ В НОРМЕ: проверено файлов {len(result.files)}, правок не требуется.")
    elif apply_now:
        lines.append(f"ИСПРАВЛЕНО: файлов {len(result.fixes)} из {len(result.files)}. "
                      "Повторный запуск обязан дать «ФОРМАТ В НОРМЕ» — операция идемпотентна.")
    else:
        lines.append(f"ТРЕБУЮТ ПРАВКИ: файлов {len(result.fixes)} из {len(result.files)}; на диск не "
                      f"записано ничего. Применить: {write}.")
    return lines
