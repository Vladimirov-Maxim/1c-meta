"""Расписание регламентного задания в проекте EDT — `ScheduledJobs/<Имя>/Schedule.schedule`.

Файл — один элемент `schedule:Schedule`: атрибуты в постоянном порядке
(обязательные — даты и время — всегда, повторы и день месяца — только
заданные), дети — дни недели, месяцы и расписания дня. Чтение и запись
обратимы: круг «прочитать → записать» по всем 209 расписаниям крупной
типовой конфигурации даёт те же байты.
"""

import re

from ..domain import schedule as domain_value

NAMESPACE = "http://g5.1c.ru/v8/dt/schedule"
ATTRIBUTE = re.compile(r'(\w+)="([^"]*)"')
WEEKDAYS_BACK = {v: k for k, v in domain_value.WEEKDAYS.items()}
MONTHS_BACK = {v: k for k, v in domain_value.MONTHS.items()}
NUMBERS = set(domain_value.NUMBERS)


def _xml_attrs(pairs, values):
    out = []
    for field, xml_attr in pairs:
        value = values.get(field, domain_value.ALWAYS.get(field))
        if value is None:
            continue
        out.append(f'{xml_attr}="{value}"')
    return " ".join(out)


def render(schedule):
    """Расписание словами задания -> текст файла (переводы строк — LF)."""
    head = f'<schedule:Schedule xmlns:schedule="{NAMESPACE}" {_xml_attrs(domain_value.ATTRIBUTES, schedule)}'
    children = ([f"  <weekDays>{domain_value.WEEKDAYS[x]}</weekDays>" for x in schedule.get("дниНедели") or ()]
            + [f"  <months>{domain_value.MONTHS[x]}</months>" for x in schedule.get("месяцы") or ()]
            + [f"  <dailySchedules {_xml_attrs(domain_value.DAILY, day)}/>" for day in schedule.get("расписанияДня")
               or ()])
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    if children:
        lines += [head + ">", *children, "</schedule:Schedule>"]
    else:
        lines.append(head + "/>")
    return "\n".join(lines) + "\n"


def parse(text):
    """Текст файла -> расписание словами задания (только заданное: обязательные
    атрибуты с пустыми значениями не называются)."""
    by_attribute = {xml_attr: field for field, xml_attr in domain_value.ATTRIBUTES}
    head = re.search(r"<schedule:Schedule ([^>]*?)/?>", text)
    schedule = {}
    for xml_attr, value in ATTRIBUTE.findall(head.group(1) if head else ""):
        field = by_attribute.get(xml_attr)
        if field is None:
            continue
        if field in NUMBERS:
            schedule[field] = int(value)
        elif domain_value.ALWAYS.get(field) != value:
            schedule[field] = value
    days = [WEEKDAYS_BACK[x] for x in re.findall(r"<weekDays>(\w+)</weekDays>", text)]
    months = [MONTHS_BACK[x] for x in re.findall(r"<months>(\w+)</months>", text)]
    if days:
        schedule["дниНедели"] = days
    if months:
        schedule["месяцы"] = months
    daily = []
    for xml_attrs in re.findall(r"<dailySchedules ([^>]*?)/>", text):
        by_day = {xml_attr: field for field, xml_attr in domain_value.DAILY}
        daily.append({by_day[a]: v for a, v in ATTRIBUTE.findall(xml_attrs) if a in by_day})
    if daily:
        schedule["расписанияДня"] = daily
    return schedule
