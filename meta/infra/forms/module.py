"""Заготовки обработчиков в модуле формы.

Пишутся только для новой формы: у неё модуля ещё нет, и маркеры вставок
не нужны: модуль создан текущей задачей. В существующий модуль
процедуры кладёт задание на код с метками — здесь для него собирается
перечень нужных процедур с сигнатурами.

Области — по стандарту структуры модуля формы: события формы, элементов
шапки, каждой таблицы, команд. Сигнатуры — из замера по 10 239 модулям
(`vocabulary.HANDLER_SIGNATURES`); незамеренное событие получает пустую
сигнатуру и пояснение в плане.
"""

from . import platform as voc

#: Тело заготовки — та же строка, что пишет конфигуратор новому обработчику.
PLACEHOLDER = "// Вставить содержимое обработчика."

REGION_FORM = "ОбработчикиСобытийФормы"
REGION_HEADER = "ОбработчикиСобытийЭлементовШапкиФормы"
REGION_TABLE = "ОбработчикиСобытийЭлементовТаблицыФормы{}"
REGION_COMMANDS = "ОбработчикиКомандФормы"


def signature_of(where, event, notes, handler):
    """(директива, параметры) обработчика; незамеренное — пусто и пояснение."""
    if where == "команда":
        return "&НаКлиенте", "Команда"
    signature = voc.HANDLER_SIGNATURES.get((where, event))
    if signature is None and where == "надпись":
        signature = voc.HANDLER_SIGNATURES.get(("элемент", event))
    if signature is None:
        notes.append(f"обработчик «{handler}» ({event}): сигнатура не замерена — "
                     "параметры допишите руками")
        return "&НаКлиенте", ""
    return signature


def procedures(handlers, edits):
    """[(область, имя, директива, параметры)] в порядке областей стандарта."""
    tables = {e.name for e in edits.all_elements() if e.kind == "ТаблицаФормы"}
    column_table = {c.name: t.name for t in edits.all_elements() if t.kind == "ТаблицаФормы"
                    for c in t.children}
    notes = []
    out = []
    for where, event, handler, element_name in handlers:
        directive, parameters = signature_of(where, event, notes, handler)
        if where == "команда":
            region = REGION_COMMANDS
        elif where == "форма":
            region = REGION_FORM
        elif element_name in tables:
            region = REGION_TABLE.format(element_name)
        elif element_name in column_table:
            region = REGION_TABLE.format(column_table[element_name])
        else:
            region = REGION_HEADER
        out.append((region, handler, directive, parameters))
    order = {REGION_FORM: 0, REGION_HEADER: 1, REGION_COMMANDS: 3}
    out.sort(key=lambda p: (order.get(p[0], 2), p[0] if order.get(p[0], 2) == 2 else ""))
    return out, notes


def module_text(handlers, edits):
    """Текст модуля новой формы; `None` — обработчиков нет, модуль не нужен:
    у 617 форм корпуса модуля нет, пустой модуль конфигуратор не выгружает."""
    listed, notes = procedures(handlers, edits)
    if not listed:
        return None, notes
    lines = []
    current = None
    for region, handler, directive, parameters in listed:
        if region != current:
            if current is not None:
                lines += ["#КонецОбласти", ""]
            lines += [f"#Область {region}", ""]
            current = region
        lines += [directive, f"Процедура {handler}({parameters})",
                  "\t" + PLACEHOLDER, "КонецПроцедуры", ""]
    lines.append("#КонецОбласти")
    return "\n".join(lines) + "\n", notes
