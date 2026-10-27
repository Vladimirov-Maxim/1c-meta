"""Расписание регламентного задания в проекте EDT — `ScheduledJobs/<Имя>/Schedule.schedule`.

Файл — один элемент `schedule:Schedule`: атрибуты в постоянном порядке
(обязательные — даты и время — всегда, повторы и день месяца — только
заданные), дети — дни недели, месяцы и расписания дня. Чтение и запись
обратимы: круг «прочитать → записать» по всем 209 расписаниям крупной
типовой конфигурации даёт те же байты.
"""

import re

from ..domain import schedule as домен

NAMESPACE = "http://g5.1c.ru/v8/dt/schedule"
ATTRIBUTE = re.compile(r'(\w+)="([^"]*)"')
WEEKDAYS_BACK = {v: k for k, v in домен.WEEKDAYS.items()}
MONTHS_BACK = {v: k for k, v in домен.MONTHS.items()}
ЧИСЛА = set(домен.ЧИСЛА)


def _атрибуты(пары, значения):
    out = []
    for поле, атрибут in пары:
        значение = значения.get(поле, домен.ALWAYS.get(поле))
        if значение is None:
            continue
        out.append(f'{атрибут}="{значение}"')
    return " ".join(out)


def render(расписание):
    """Расписание словами задания -> текст файла (переводы строк — LF)."""
    голова = f'<schedule:Schedule xmlns:schedule="{NAMESPACE}" {_атрибуты(домен.ATTRIBUTES, расписание)}'
    дети = ([f"  <weekDays>{домен.WEEKDAYS[x]}</weekDays>" for x in расписание.get("дниНедели") or ()]
            + [f"  <months>{домен.MONTHS[x]}</months>" for x in расписание.get("месяцы") or ()]
            + [f"  <dailySchedules {_атрибуты(домен.DAILY, день)}/>" for день in расписание.get("расписанияДня")
               or ()])
    строки = ['<?xml version="1.0" encoding="UTF-8"?>']
    if дети:
        строки += [голова + ">", *дети, "</schedule:Schedule>"]
    else:
        строки.append(голова + "/>")
    return "\n".join(строки) + "\n"


def parse(text):
    """Текст файла -> расписание словами задания (только заданное: обязательные
    атрибуты с пустыми значениями не называются)."""
    по_атрибуту = {атрибут: поле for поле, атрибут in домен.ATTRIBUTES}
    голова = re.search(r"<schedule:Schedule ([^>]*?)/?>", text)
    расписание = {}
    for атрибут, значение in ATTRIBUTE.findall(голова.group(1) if голова else ""):
        поле = по_атрибуту.get(атрибут)
        if поле is None:
            continue
        if поле in ЧИСЛА:
            расписание[поле] = int(значение)
        elif домен.ALWAYS.get(поле) != значение:
            расписание[поле] = значение
    дни = [WEEKDAYS_BACK[x] for x in re.findall(r"<weekDays>(\w+)</weekDays>", text)]
    месяцы = [MONTHS_BACK[x] for x in re.findall(r"<months>(\w+)</months>", text)]
    if дни:
        расписание["дниНедели"] = дни
    if месяцы:
        расписание["месяцы"] = месяцы
    дневные = []
    for атрибуты in re.findall(r"<dailySchedules ([^>]*?)/>", text):
        по_дню = {атрибут: поле for поле, атрибут in домен.DAILY}
        дневные.append({по_дню[a]: v for a, v in ATTRIBUTE.findall(атрибуты) if a in по_дню})
    if дневные:
        расписание["расписанияДня"] = дневные
    return расписание
