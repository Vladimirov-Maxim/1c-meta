"""Язык ответов нормализации формата: что будет исправлено и что исправлено."""


def normalize_lines(result, apply_now, записать):
    """`записать` — как в этом канале применить: «повторите с --apply» или
    «вызовите normalize_apply с теми же параметрами»."""
    строки = [f"Нормализация формата: {result.source}",
              f"Текстовых файлов задачи: {len(result.files)}"]
    строки += [f"   {пояснение}" for пояснение in result.notes]
    for путь, что in result.fixes:
        строки.append(f"   [{'исправлено' if apply_now else 'к правке'}] {путь}: {'; '.join(что)}")
    строки.append("")
    if not result.fixes:
        строки.append(f"ФОРМАТ В НОРМЕ: проверено файлов {len(result.files)}, правок не требуется.")
    elif apply_now:
        строки.append(f"ИСПРАВЛЕНО: файлов {len(result.fixes)} из {len(result.files)}. "
                      "Повторный запуск обязан дать «ФОРМАТ В НОРМЕ» — операция идемпотентна.")
    else:
        строки.append(f"ТРЕБУЮТ ПРАВКИ: файлов {len(result.fixes)} из {len(result.files)}; на диск не "
                      f"записано ничего. Применить: {записать}.")
    return строки
