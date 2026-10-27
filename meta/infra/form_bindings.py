"""Привязки обработчиков формы по тексту её описания — `Form.xml` выгрузки или
`Form.form` проекта EDT.

Событие формы связывается с процедурой модуля записью в описании формы, а не
именем: процедура `ПередЗакрытием` без записи `BeforeClose` платформой не
вызывается. Правилу «процедура с именем события, а привязки нет» нужны три
вещи: какие процедуры привязаны (события формы и элементов, действия команд),
какие у формы элементы и какие события бывают у формы. Разбор — выражениями,
а не деревом: ответ нужен по любой форме, в том числе такой, которую полная
перекладка не читает, а записи здесь однозначны.
"""

import os
import re

from .forms.platform import FORM_EVENTS

#: Выгрузка: `<Event name="OnOpen">ПриОткрытии</Event>`, `<Action>Команда</Action>`.
DESIGNER_BOUND = re.compile(r"<Event name=\"[^\"]+\"[^>]*>([^<]+)</Event>|<Action>([^<]+)</Action>")
#: Выгрузка: элемент — тег с именем и идентификатором, `<InputField name="Дата" id="1">`.
DESIGNER_ELEMENT = re.compile(r"<\w+ name=\"([^\"]+)\" id=\"-?\d+\"")
#: EDT: `<handlers><event>OnOpen</event><name>ПриОткрытии</name></handlers>`,
#: действие команды — `<handler><name>Команда</name></handler>`.
EDT_BOUND = re.compile(r"<handlers>\s*<event>[^<]*</event>\s*<name>([^<]+)</name>"
                       r"|<handler>\s*<name>([^<]+)</name>")
#: EDT: элемент — `<items …>` и первым ребёнком `<name>`.
EDT_ELEMENT = re.compile(r"<items[^>]*>\s*<name>([^<]+)</name>")

#: События самой формы — по-русски, как их пишут процедуры.
FORM_EVENT_NAMES = tuple(FORM_EVENTS)


def bindings(text):
    """Текст описания формы -> (привязанные процедуры, имена элементов)."""
    if text.lstrip().startswith("<?xml") and "<form:Form" in text[:500]:
        связанные, элементы = EDT_BOUND, EDT_ELEMENT
    else:
        связанные, элементы = DESIGNER_BOUND, DESIGNER_ELEMENT
    привязаны = {next(g for g in m.groups() if g).strip() for m in связанные.finditer(text)}
    return привязаны, {m.group(1) for m in элементы.finditer(text)}


def form_file(module_path):
    """Путь модуля формы -> путь описания формы рядом: у выгрузки
    `…/Ext/Form/Module.bsl` -> `…/Ext/Form.xml`, у EDT `…/Module.bsl` ->
    `…/Form.form`; не модуль формы — None. Разделитель — как у пути на входе."""
    sep = "/" if "/" in module_path and "\\" not in module_path else os.sep
    части = module_path.split(sep)
    if части[-1] != "Module.bsl":
        return None
    if len(части) >= 3 and части[-3:-1] == ["Ext", "Form"]:
        return sep.join(части[:-2] + ["Form.xml"])
    return sep.join(части[:-1] + ["Form.form"])
