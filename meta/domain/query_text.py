"""Текст запроса набора данных: что правка фрагментом не должна сломать.

Скобки — круглые и фигурные (расширения компоновки `{ГДЕ …}`) — парные, а
число запросов пакета (`;` между ними) правка меняет только намеренно.
Считается вне строковых литералов (`"…"`, кавычка внутри — удвоенная) и
комментариев (`//`).
"""


def counts(text):
    """{символ: сколько} для `(`, `)`, `{`, `}`, `;` — вне литералов и комментариев."""
    count = dict.fromkeys("(){};", 0)
    for line in (text or "").split("\n"):
        in_literal, i = False, 0
        while i < len(line):
            ch = line[i]
            if ch == '"':
                in_literal = not in_literal
            elif not in_literal and line.startswith("//", i):
                break
            elif not in_literal and ch in count:
                count[ch] += 1
            i += 1
    return count


def problems(old, new):
    """([ошибка], [предупреждение]) правки запроса: непарные скобки, которых
    не было, и сменившееся число запросов пакета."""
    before, after_ = counts(old), counts(new)
    errors, warnings = [], []
    for opened, closed, what in (("(", ")", "круглые"), ("{", "}", "фигурные")):
        if after_[opened] != after_[closed] and before[opened] == before[closed]:
            errors.append(f"{what} скобки в запросе непарные после правки: «{opened}» {after_[opened]}, "
                          f"«{closed}» {after_[closed]}")
    if after_[";"] != before[";"]:
        warnings.append(f"число запросов пакета меняется: «;» было {before[';']}, стало {after_[';']} — "
                              "правка выходит за один запрос пакета или добавляет запрос")
    return errors, warnings
