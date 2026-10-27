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
NUMBERS = set(домен.NUMBERS)


def _атрибуты(пары, values):
    out = []
    for field, атрибут in пары:
        value = values.get(field, домен.ALWAYS.get(field))
        if value is None:
            continue
        out.append(f'{атрибут}="{value}"')
    return " ".join(out)


def render(schedule):
    """Расписание словами задания -> текст файла (переводы строк — LF)."""
    голова = f'<schedule:Schedule xmlns:schedule="{NAMESPACE}" {_атрибуты(домен.ATTRIBUTES, schedule)}'
    дети = ([f"  <weekDays>{домен.WEEKDAYS[x]}</weekDays>" for x in schedule.get("дниНедели") or ()]
            + [f"  <months>{домен.MONTHS[x]}</months>" for x in schedule.get("месяцы") or ()]
            + [f"  <dailySchedules {_атрибуты(домен.DAILY, day)}/>" for day in schedule.get("расписанияДня")
               or ()])
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    if дети:
        lines += [голова + ">", *дети, "</schedule:Schedule>"]
    else:
        lines.append(голова + "/>")
    return "\n".join(lines) + "\n"


def parse(text):
    """Текст файла -> расписание словами задания (только заданное: обязательные
    атрибуты с пустыми значениями не называются)."""
    по_атрибуту = {атрибут: field for field, атрибут in домен.ATTRIBUTES}
    голова = re.search(r"<schedule:Schedule ([^>]*?)/?>", text)
    schedule = {}
    for атрибут, value in ATTRIBUTE.findall(голова.group(1) if голова else ""):
        field = по_атрибуту.get(атрибут)
        if field is None:
            continue
        if field in NUMBERS:
            schedule[field] = int(value)
        elif домен.ALWAYS.get(field) != value:
            schedule[field] = value
    days = [WEEKDAYS_BACK[x] for x in re.findall(r"<weekDays>(\w+)</weekDays>", text)]
    месяцы = [MONTHS_BACK[x] for x in re.findall(r"<months>(\w+)</months>", text)]
    if days:
        schedule["дниНедели"] = days
    if месяцы:
        schedule["месяцы"] = месяцы
    дневные = []
    for атрибуты in re.findall(r"<dailySchedules ([^>]*?)/>", text):
        по_дню = {атрибут: field for field, атрибут in домен.DAILY}
        дневные.append({по_дню[a]: v for a, v in ATTRIBUTE.findall(атрибуты) if a in по_дню})
    if дневные:
        schedule["расписанияДня"] = дневные
    return schedule
