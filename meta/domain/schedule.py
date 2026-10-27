"""Расписание регламентного задания — словами задания и его проверка.

Поля — те, что встречаются у расписаний крупной типовой конфигурации (209
заданий): даты начала и окончания, повтор дней, время начала, окончания и
завершения, повтор в течение дня, интервал завершения, пауза повтора, повтор
недель, день месяца, дни недели, месяцы и расписания дня. Числа — секунды или
счётчики, время — «ЧЧ:ММ:СС», дата — «ГГГГ-ММ-ДД». Незаданное — как у
платформы: пустые даты и время, повторов нет, дни недели и месяцы не
ограничены.
"""

import re

#: поле задания -> атрибут расписания проекта EDT, в порядке файла
ATTRIBUTES = (
    ("датаНачала", "beginDate"),
    ("датаОкончания", "endDate"),
    ("повторДней", "daysRepeatPeriod"),
    ("времяНачала", "beginTime"),
    ("времяОкончания", "endTime"),
    ("времяЗавершения", "completionTime"),
    ("интервалЗавершения", "completionInterval"),
    ("повторВТечениеДня", "repeatPeriodInDay"),
    ("паузаПовтора", "repeatPause"),
    ("повторНедель", "weeksPeriod"),
    ("деньМесяца", "dayInMonth"),
)
#: атрибуты, которые пишутся всегда, — с их пустыми значениями
ALWAYS = {"датаНачала": "0001-01-01", "датаОкончания": "0001-01-01", "времяНачала": "00:00:00",
          "времяОкончания": "00:00:00", "времяЗавершения": "00:00:00"}
#: расписание дня — свои атрибуты, все обязательные
DAILY = (("времяНачала", "beginTime"), ("времяОкончания", "endTime"), ("времяЗавершения", "completionTime"))

WEEKDAYS = {"Понедельник": "Mon", "Вторник": "Tue", "Среда": "Wed", "Четверг": "Thu",
            "Пятница": "Fri", "Суббота": "Sat", "Воскресенье": "Sun"}
MONTHS = {"Январь": "Jan", "Февраль": "Feb", "Март": "Mar", "Апрель": "Apr", "Май": "May",
          "Июнь": "Jun", "Июль": "Jul", "Август": "Aug", "Сентябрь": "Sep", "Октябрь": "Oct",
          "Ноябрь": "Nov", "Декабрь": "Dec"}
LISTS = ("дниНедели", "месяцы", "расписанияДня")
FIELDS = tuple(field for field, _ in ATTRIBUTES) + LISTS

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")
NUMBERS = ("повторДней", "повторВТечениеДня", "интервалЗавершения", "паузаПовтора", "повторНедель",
         "деньМесяца")


def problems(schedule):
    """Беды расписания задания словами — пусто, если всё понятно."""
    if not isinstance(schedule, dict):
        return ["«расписание» — объект с полями: " + ", ".join(FIELDS)]
    problems = []
    extra = [field for field in schedule if field not in FIELDS]
    if extra:
        problems.append(f"неизвестные поля расписания: {', '.join(extra)}; известны: {', '.join(FIELDS)}")
    for field, value in schedule.items():
        if field.startswith("дата") and (not isinstance(value, str) or not DATE.match(value)):
            problems.append(f"«{field}» — дата «ГГГГ-ММ-ДД», получено {value!r}")
        elif field.startswith("время") and (not isinstance(value, str) or not TIME.match(value)):
            problems.append(f"«{field}» — время «ЧЧ:ММ:СС», получено {value!r}")
        elif field in NUMBERS and (not isinstance(value, int) or isinstance(value, bool)
                                 or (value < 0 and field != "деньМесяца")):
            problems.append(f"«{field}» — целое число" + (" (−1 — последний день)" if field == "деньМесяца" else "")
                        + f", получено {value!r}")
    for field, vocabulary in (("дниНедели", WEEKDAYS), ("месяцы", MONTHS)):
        value = schedule.get(field)
        if value is not None and (not isinstance(value, list)
                                     or any(x not in vocabulary for x in value)):
            problems.append(f"«{field}» — список из: {', '.join(vocabulary)}; получено {value!r}")
    days = schedule.get("расписанияДня")
    if days is not None:
        if not isinstance(days, list) or not all(isinstance(x, dict) for x in days):
            problems.append("«расписанияДня» — список объектов {времяНачала, времяОкончания, времяЗавершения}")
        else:
            for x in days:
                problems += [f"расписание дня: {problem}" for problem in problems_daily(x)]
    return problems


def problems_daily(day):
    problems = []
    for field, _ in DAILY:
        value = day.get(field, "00:00:00")
        if not isinstance(value, str) or not TIME.match(value):
            problems.append(f"«{field}» — время «ЧЧ:ММ:СС», получено {value!r}")
    extra = [field for field in day if field not in dict(DAILY)]
    if extra:
        problems.append(f"неизвестные поля: {', '.join(extra)}")
    return problems
