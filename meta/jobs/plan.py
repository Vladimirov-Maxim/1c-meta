"""Язык плана изменений: JSON <-> модель домена (`domain.plan`).

План пишут руками, до кода, — это намерение, — и получают из факта (план по
факту). Формат один:

    {"объекты": [
      {"вид": "РегистрСведений", "имя": "мой_Остатки", "действие": "создать",
       "измерения": {"Договор": ["Справочник.ДоговорыКонтрагентов"]},
       "ресурсы": {"Сумма": ["Число(15,2)"]},
       "модули": {"МодульМенеджера": ["ЗарегистрироватьИзменение"]}},
      {"вид": "Перечисление", "имя": "мой_Виды", "действие": "создать",
       "значения": ["Первый", "Второй"]},
      {"вид": "ОбщийМодуль", "имя": "мой_Сервер", "действие": "изменить",
       "методы": ["Пересчитать"]}
    ]}

Состав — по группам: имя -> список типов (null — тип не сверяется) или просто
список имён. Типы — записью показа («Строка(50)», «Справочник.Имя») или
записью синтакс-помощника («СправочникСсылка.Имя»): сверяется род типа, без
длины и точности. Методы — `методы` у вида с одним модулем (общий модуль,
общая команда, сервисы), `модули` — у прочих, по модулю.

Неизвестный ключ — отказ: опечатка в плане («реквизит» вместо «реквизиты»)
молча выключила бы сверку того, что за ней стоит.
"""

import json
import re

from ..domain.model import Collected, Refuse
from ..domain.modules import FORM_MARK, OWN_MODULES, SINGLE_MODULE
from ..domain.plan import ACTIONS, GROUPS, WITHOUT_TYPES, Plan, PlanObject

КЛЮЧИ_ОБЪЕКТА = ("вид", "имя", "действие") + GROUPS + ("методы", "модули")
_БЕЗ_ТИПОВ_У = {"табличныеЧасти": "табличной части", "значения": "значения перечисления",
                "предопределенные": "предопределённого элемента"}
_ЭКСПОРТ = re.compile(r"\s+Экспорт$")


def план_из_json(data):
    """JSON плана (словарь или текст) -> `План`. Беды копятся и предъявляются разом."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as error:
            raise Refuse(f"план — не JSON: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("объекты"), list):
        raise Refuse("план — объект JSON с ключом «объекты»: список объектов задачи")
    extra = [key for key in data if key != "объекты"]
    problems = Collected("план не разобран")
    if extra:
        problems.add(f"неизвестные ключи плана: {', '.join(extra)}; известен: объекты")
    objects, встречены = [], set()
    for number, item in enumerate(data["объекты"], start=1):
        obj = _object(item, number, problems)
        if obj is None:
            continue
        key = (obj.kind, obj.name)
        if key in встречены:
            problems.add(f"«{obj.kind}.{obj.name}» в плане дважды — объект называется один раз")
            continue
        встречены.add(key)
        objects.append(obj)
    problems.raise_collected()
    return Plan(tuple(objects))


def _object(data, number, problems):
    if not isinstance(data, dict):
        problems.add(f"объект {number}: ожидается объект JSON с ключами вид, имя, действие")
        return None
    who = f"«{data.get('вид')}.{data.get('имя')}»" if data.get("имя") else f"объект {number}"
    before = len(problems.problems)
    extra = [key for key in data if key not in КЛЮЧИ_ОБЪЕКТА]
    if extra:
        problems.add(f"{who}: неизвестные ключи {', '.join(extra)}; известны: {', '.join(КЛЮЧИ_ОБЪЕКТА)}")
    for key in ("вид", "имя", "действие"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            problems.add(f"{who}: нет «{key}»")
    if isinstance(data.get("действие"), str) and data["действие"] not in ACTIONS:
        problems.add(f"{who}: действие «{data['действие']}»; бывает: {', '.join(ACTIONS)}")
    members = {}
    for group in GROUPS:
        if data.get(group) is not None:
            members[group] = _group(data[group], f"{who}, «{group}»", group, problems)
    modules = _модули(data, who, problems)
    if len(problems.problems) > before:
        return None
    return PlanObject(data["вид"].strip(), data["имя"].strip(), data["действие"], members, modules)


def _group(value, where, group, problems):
    if isinstance(value, list):
        value = {name: None for name in value if isinstance(name, str)} \
            if all(isinstance(name, str) for name in value) else None
    if not isinstance(value, dict):
        problems.add(f"{where}: ожидается {{имя: [типы]}} или список имён")
        return {}
    members = {}
    for name, types in value.items():
        if types is not None and (not isinstance(types, list)
                                 or not all(isinstance(tk, str) and tk.strip() for tk in types)):
            problems.add(f"{where}, «{name}»: типы — список строк («Строка(50)», «Справочник.Имя») или null")
            continue
        if types and group in WITHOUT_TYPES:
            problems.add(f"{where}, «{name}»: у {_БЕЗ_ТИПОВ_У[group]} типов не бывает — список имён "
                          "или null")
            continue
        members[name] = tuple(tk.strip() for tk in types) if types else None
    return members


def _модули(data, who, problems):
    kind = data.get("вид")
    единственный = SINGLE_MODULE.get(kind)
    modules = {}
    if единственный == FORM_MARK and (data.get("методы") is not None or data.get("модули") is not None):
        problems.add(f"{who}: модуль общей формы — модуль формы; методы форм план не сверяет")
        return {}
    if data.get("методы") is not None:
        if единственный is None:
            problems.add(f"{who}: «методы» — у вида с одним модулем; у «{kind}» модули называются "
                          f"в «модули»: {', '.join(OWN_MODULES)}")
        else:
            modules[единственный] = data["методы"]
    if data.get("модули") is not None:
        if not isinstance(data["модули"], dict):
            problems.add(f"{who}: «модули» — {{модуль: [методы]}}")
        else:
            allowed = (единственный,) if единственный else OWN_MODULES
            for module, names in data["модули"].items():
                if module not in allowed:
                    problems.add(f"{who}: модуль «{module}»; у «{kind}» бывают: {', '.join(allowed)}")
                elif module in modules:
                    problems.add(f"{who}: методы модуля «{module}» названы дважды — в «методы» и в «модули»")
                else:
                    modules[module] = names
    result = {}
    for module, names in modules.items():
        if not isinstance(names, list) or not all(isinstance(ii, str) and ii.strip() for ii in names):
            problems.add(f"{who}: методы модуля «{module}» — список имён")
            continue
        result[module] = tuple(_ЭКСПОРТ.sub("", ii.strip()) for ii in names)
    return result


def план_в_json(plan):
    """`План` -> JSON-словарь того же формата: группы без типов — списком имён,
    методы вида с одним модулем — «методы»."""
    objects = []
    for obj in plan.objects:
        data = {"вид": obj.kind, "имя": obj.name, "действие": obj.action}
        for group in GROUPS:
            members = obj.members.get(group)
            if not members:
                continue
            if all(types is None for types in members.values()):
                data[group] = list(members)
            else:
                data[group] = {name: (list(types) if types is not None else None)
                                  for name, types in members.items()}
        единственный = SINGLE_MODULE.get(obj.kind)
        for module, names in obj.modules.items():
            if module == единственный:
                data["методы"] = list(names)
            else:
                data.setdefault("модули", {})[module] = list(names)
        objects.append(data)
    return {"объекты": objects}
