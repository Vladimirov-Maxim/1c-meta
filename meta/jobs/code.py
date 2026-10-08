"""Задание на код: JSON -> модель приложения.

Формат задания:

    {"repo": "C:/путь/к/выгрузке/cf", "task": "ЗАДАЧА-123", "date": "31.08.2026",
     "author": "Автор",
     "modules": [
       {"модуль": "ОбщийМодуль.мой_X", "edits": [
          {"line": 41, "lines": 5, "first_line": "\\tЕсли Отказ Тогда",
           "last_line": "\\tКонецЕсли;", "code": "…"}]},
       {"path": "CommonModules/мой_Y/Ext/Module.bsl", "revert": true},
       {"модуль": "ОбщийМодуль.мой_Z", "rename": {"from": "Старое", "to": "Новое"}}],
     "move_method": {"from": "ОбщийМодуль.мой_A", "method": "Имя",
                     "to": "ОбщийМодуль.мой_B", "to_line": 42}}

Модуль называется ровно одним ключом: «модуль» — адресом по метаданным (тем
же, что у bsl-ls), «path» — путём файла. У переноса
метода то же самое: «from»/«to» — адреса, «from_path»/«to_path» — пути.

Для одного модуля допустима короткая форма: «модуль» или «path» с «edits»
прямо в шапке.

Автор обязателен: у инструмента нет своего автора. Подставить автора по
умолчанию может только тот, кто инструмент вызывает.
"""

import datetime
import re

from ..domain.edits import CodeJob, Edit, MethodMove, ModuleJob, Signature
from ..domain.model import Refuse
from ..domain.modules import ModuleAddress, ModuleRef

HEADER_KEYS = ("repo", "task", "date", "author", "base", "modules", "move_method", "принято")
MODULE_KEYS = ("модуль", "path", "edits", "revert", "rename")
EDIT_KEYS = ("line", "lines", "first_line", "last_line", "code")
RENAME_KEYS = ("from", "to")
MOVE_KEYS = ("from", "from_path", "method", "to", "to_path", "to_line")
#: Ключи, по которым задание опознаётся как задание на код.
CODE_KEYS = ("modules", "модуль", "path", "move_method")


def _check_keys(data, allowed, where):
    unknown = [key for key in data if key not in allowed]
    if unknown:
        raise Refuse(f"в «{where}» не знаю ключей: {', '.join(unknown)}; "
                     f"бывают: {', '.join(allowed)}")


def module_ref(data, address_key, path_key, where):
    """Ссылка на модуль: ровно один из двух ключей."""
    address, path = data.get(address_key), data.get(path_key)
    if bool(address) == bool(path):
        raise Refuse(f"в «{where}» модуль называется ровно одним ключом: "
                     f"«{address_key}» (адрес, например «ОбщийМодуль.мой_X») или "
                     f"«{path_key}» (путь файла)")
    if address:
        return ModuleRef(address=ModuleAddress.parse(address))
    return ModuleRef(path=path)


def _edit(data):
    if not isinstance(data, dict):
        raise Refuse(f"правка — объект с «line», получено {data!r}")
    _check_keys(data, EDIT_KEYS, "edits")
    if not isinstance(data.get("line"), int) or isinstance(data.get("line"), bool):
        raise Refuse(f"у правки нужен номер строки «line», получено {data.get('line')!r}")
    lines = data.get("lines", 0)
    if not isinstance(lines, int) or isinstance(lines, bool) or lines < 0:
        raise Refuse(f"«lines» — сколько строк заменяется, число от 0; получено {lines!r}")
    return Edit(line=data["line"], lines=lines, first_line=data.get("first_line"),
                last_line=data.get("last_line"), code=data.get("code") or "")


def _module(data):
    if not isinstance(data, dict):
        raise Refuse(f"модуль задания — объект, получено {data!r}")
    _check_keys(data, MODULE_KEYS, "modules")
    ref = module_ref(data, "модуль", "path", "modules")
    rename = None
    if data.get("rename"):
        said = data["rename"]
        if not isinstance(said, dict):
            raise Refuse("«rename» — объект {«from»: …, «to»: …}")
        _check_keys(said, RENAME_KEYS, "rename")
        if not said.get("from") or not said.get("to"):
            raise Refuse("у «rename» нужны оба имени: «from» и «to»")
        rename = (said["from"], said["to"])
    return ModuleJob(ref, tuple(_edit(item) for item in data.get("edits") or ()),
                     bool(data.get("revert")), rename)


def _move(data):
    if not isinstance(data, dict):
        raise Refuse("«move_method» — объект с «from», «method», «to», «to_line»")
    _check_keys(data, MOVE_KEYS, "move_method")
    if not data.get("method"):
        raise Refuse("у «move_method» нужно имя метода «method»")
    if not isinstance(data.get("to_line"), int):
        raise Refuse("у «move_method» нужна строка приёмника «to_line»")
    return MethodMove(module_ref(data, "from", "from_path", "move_method"), data["method"],
                      module_ref(data, "to", "to_path", "move_method"), data["to_line"])


def code_job_from_json(job):
    """Задание словарём -> `CodeJob`. Всё задание — одна работа."""
    _check_keys(job, HEADER_KEYS + MODULE_KEYS, "задание на код")
    # Короткая форма: один модуль прямо в шапке. Правки без модуля — отказ:
    # иначе они молча пропали бы, и задание «прошло» бы, ничего не сделав.
    short = None
    if job.get("модуль") or job.get("path"):
        short = {key: job[key] for key in MODULE_KEYS if key in job}
    elif any(job.get(key) for key in ("edits", "revert", "rename")):
        raise Refuse("правки в шапке задания без модуля: назовите его ключом «модуль» "
                     "или «path», либо перенесите правки в «modules»")
    modules = [_module(item) for item in job.get("modules") or ()]
    if short is not None:
        modules.append(_module(short))
    move = _move(job["move_method"]) if job.get("move_method") else None
    # Откату нужна только задача — чьи вставки снимать; дату и автора у него
    # не спрашивают.
    только_откат = move is None and modules and all(
        m.revert and not m.edits and m.rename is None for m in modules)
    # Недостающие — все разом: отказ по одному звал бы на второй круг ради
    # второго поля.
    нет = [key for key in (("task",) if только_откат else ("task", "date", "author"))
           if not job.get(key)]
    if нет:
        raise Refuse("в задании на код " + ("нужно поле " if len(нет) == 1 else "нужны поля ")
                     + ", ".join(f"«{key}»" for key in нет)
                     + ": вставка подписывается задачей, датой и автором")
    date, author = job.get("date") or "", job.get("author") or ""
    # Подпись проверяется: «#TEAM Автор» дал бы в метке «#TEAM #TEAM Автор», а дата
    # «2026-09-30» ушла бы в метки, которые поиск по шаблону меток не находит.
    # Метка команды в начале срезается любая: её ставит инструмент по
    # соглашениям команды, а переписанная из соседней метки она в подписи —
    # не имя.
    author = re.sub(r"^\s*#\S+\s+", "", author).strip()
    if "#" in author:
        raise Refuse(f"автор «{author}» — только имя: метку команды и ИД задачи "
                     "ставит инструмент")
    if date and not _is_date(date):
        raise Refuse(f"дата «{date}» — пишется дд.мм.гггг, как в метках вставок, "
                     "например 05.10.2026")
    signature = Signature(job["task"], date, author)
    base = job.get("base")
    if base is not None and (not isinstance(base, str) or not base.strip()):
        raise Refuse("«base» — ревизия до задачи строкой: коммит, ветка или «HEAD»")
    return CodeJob(signature, tuple(modules), move, base.strip() if base else None)


def _is_date(text):
    """Дата дд.мм.гггг, существующая в календаре."""
    try:
        datetime.datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        return False
    return re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text) is not None
