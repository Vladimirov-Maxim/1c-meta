"""План изменений задачи и его сверка с фактом.

План — намерение: какие объекты задача создаёт, меняет или удаляет, какие
члены у них появляются — реквизиты, измерения, ресурсы, табличные части,
значения перечислений, с типами — и какие методы в модулях. Факт — что лежит
в выгрузке после задачи против базы. Сверка идёт в обе стороны: заявлено, но
не сделано; сделано, но не заявлено; типы не совпали.

Структурную сверку «план — код» чтением делают по многу раз и с
пропусками; здесь она — правило. Расхождение не обязательно дефект кода: план
мог устареть, — но объяснить его обязан автор правок.

Здесь модель и правила, без диска: состав объектов и методы модулей приносит
площадка.
"""

import re
from dataclasses import dataclass, field

from .changes import ADDED, DELETED
from .model import Finding, type_record
from .modules import SINGLE_MODULE

#: Группы состава объекта — те же слова, что в задании на объект.
GROUPS = ("реквизиты", "измерения", "ресурсы", "табличныеЧасти", "значения", "предопределенные")
#: Группы без типов: у табличной части, значения перечисления и
#: предопределённого элемента типа нет.
WITHOUT_TYPES = ("табличныеЧасти", "значения", "предопределенные")
#: Группы, которые читает не всякий формат: предопределённые проекта EDT лежат в
#: карточке, а у выгрузки конфигуратора — отдельным файлом, которого сверка не
#: читает. Нет группы в факте — не «не сделано», а «сверять не с чем».
NOT_EVERYWHERE = ("предопределенные",)
#: Член группы в единственном числе — для текста находки: слово и окончание
#: причастия («заявлен», «заявлено», «заявлена»).
MEMBER = {"реквизиты": ("реквизит", ""), "измерения": ("измерение", "о"),
        "ресурсы": ("ресурс", ""), "табличныеЧасти": ("табличная часть", "а"),
        "значения": ("значение", "о"), "предопределенные": ("предопределённый элемент", "")}

CREATE, CHANGE, DELETE = "создать", "изменить", "удалить"
ACTIONS = (CREATE, CHANGE, DELETE)

#: Виды, которые правятся попутно: право на новый объект выдаётся в роли,
#: место в интерфейсе — в подсистеме. Не заявлены — предупреждение.
INCIDENTAL = ("Роль", "Подсистема")

#: Ссылочные виды. Тип ссылки пишут и «Справочник.Имя» — как задание и показ,
#: и «СправочникСсылка.Имя» — как синтакс-помощник; это один тип.
REFERENCE_KINDS = ("Справочник", "Документ", "Перечисление", "ПланВидовХарактеристик", "ПланСчетов",
             "ПланВидовРасчета", "ПланОбмена", "БизнесПроцесс", "Задача")

# --- коды правил ---------------------------------------------------------------------

OBJECT_NOT_DONE = "ПЛАН-ОБЪЕКТ-НЕ-СДЕЛАН"
OBJECT_EXISTED = "ПЛАН-ОБЪЕКТ-УЖЕ-БЫЛ"
OBJECT_REMAINED = "ПЛАН-ОБЪЕКТ-ОСТАЛСЯ"
OBJECT_UNCHANGED = "ПЛАН-ОБЪЕКТ-БЕЗ-ПРАВОК"
OBJECT_UNDECLARED = "ПЛАН-ОБЪЕКТ-НЕ-ЗАЯВЛЕН"
INCIDENTAL_UNDECLARED = "ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО"
CARD_UNREADABLE = "ПЛАН-КАРТОЧКА-НЕ-ЧИТАЕТСЯ"
MEMBER_NOT_DONE = "ПЛАН-ЧЛЕН-НЕ-СДЕЛАН"
MEMBER_UNDECLARED = "ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"
TYPES_DIFFER = "ПЛАН-ТИПЫ-РАСХОДЯТСЯ"
MODULE_NOT_DONE = "ПЛАН-МОДУЛЬ-НЕ-СДЕЛАН"
METHOD_NOT_DONE = "ПЛАН-МЕТОД-НЕ-СДЕЛАН"
METHOD_UNDECLARED = "ПЛАН-МЕТОД-НЕ-ЗАЯВЛЕН"

ERROR, WARNING = Finding.ERROR, Finding.WARNING

#: Код -> (уровень по умолчанию, что правило требует).
RULES = {
    OBJECT_NOT_DONE: (ERROR, "объект, заявленный к созданию или изменению, есть в выгрузке"),
    OBJECT_EXISTED: (ERROR, "объект, заявленный к созданию, до задачи не существовал"),
    OBJECT_REMAINED: (ERROR, "объект, заявленный к удалению, удалён"),
    OBJECT_UNCHANGED: (WARNING, "в объекте, заявленном к изменению, есть правки"),
    OBJECT_UNDECLARED: (ERROR, "объект, который задача создала, изменила или удалила, заявлен"),
    INCIDENTAL_UNDECLARED: (WARNING, "роль или подсистема, которую задача правила, заявлена"),
    CARD_UNREADABLE: (ERROR, "карточка заявленного объекта читается"),
    MEMBER_NOT_DONE: (ERROR, "заявленный член объекта есть в выгрузке"),
    MEMBER_UNDECLARED: (ERROR, "член, который появился в задаче, заявлен"),
    TYPES_DIFFER: (ERROR, "типы члена — заявленные"),
    MODULE_NOT_DONE: (ERROR, "модуль, где заявлены методы, есть"),
    METHOD_NOT_DONE: (ERROR, "заявленный метод объявлен в модуле"),
    METHOD_UNDECLARED: (WARNING, "экспортный метод, появившийся в задаче, заявлен"),
}


# --- модель ------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanObject:
    """Объект в плане: вид, имя, действие; `члены` — {группа: {имя: (типы,) или
    None — типы не сверяются}}; `модули` — {модуль: (имена методов,)}. У
    изменяемого объекта перечисляется только то, что задача добавляет."""

    kind: str
    name: str
    action: str
    members: dict = field(default_factory=dict)
    modules: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    objects: tuple = ()


@dataclass(frozen=True)
class Composition:
    """Что объект содержит: {группа: {имя: (типы домена,)}}; `сломан` — почему
    карточка не прочиталась."""

    members: dict = field(default_factory=dict)
    broken: str | None = None


@dataclass(frozen=True)
class FactModule:
    """Модуль объекта до и после задачи: {имя: (экспортный, строка)}; `после`
    None — файла модуля нет."""

    path: str | None
    after: dict | None
    before_: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectFact:
    """Объект в выгрузке до и после задачи. `после`/`до` — `Состав` или None:
    карточки нет; `карточка` — путь карточки от корня выгрузки; `модули` —
    {модуль: `FactModule`}."""

    kind: str
    name: str
    card: str | None
    after: Composition | None
    before_: Composition | None
    modules: dict = field(default_factory=dict)


class PlanFinding(Finding):
    """Расхождение плана и факта: объект, файл (карточка или модуль) и строка,
    если она есть, — у членов карточки строки нет."""

    def __init__(self, code, obj, message, path=None, line=None):
        super().__init__(code, f"{obj} — {message}", None, RULES[code][0])
        self.obj = obj
        self.path = path
        self.line = line

    def __repr__(self):
        return f"[{self.code}] {self.message}"


# --- типы ---------------------------------------------------------------------------

_WITH_REFINEMENT = re.compile(r"^(Строка|Число)\s*\(.*\)$")
_PREVIOUS_REFERENCE = re.compile(r"^(\w+)Ссылка\.(.+)$")
_DATES = ("Дата", "ДатаВремя", "Время")


def type_genus(type_):
    """Тип записью — как в плане или в показе — без уточнений: «Строка(50)» ->
    «Строка», «ДатаВремя» -> «Дата», «СправочникСсылка.Х» -> «Справочник.Х».

    Длина, точность и состав даты не сверяются: план описывает устройство
    данных, а не их разрядность, и уточнений в планах обычно не пишут.
    """
    text = " ".join(str(type_).split())
    found = _WITH_REFINEMENT.match(text)
    if found:
        return found.group(1)
    if text in _DATES:
        return "Дата"
    found = _PREVIOUS_REFERENCE.match(text)
    if found and found.group(1) in REFERENCE_KINDS:
        return f"{found.group(1)}.{found.group(2)}"
    return text


def type_records(types):
    """Типы домена (один или список) -> записи показа по одной на тип."""
    if types is None:
        return ()
    return tuple(type_record(tk) for tk in (types if isinstance(types, (list, tuple)) else [types]))


# --- сверка ---------------------------------------------------------------------------


def reconcile(plan, facts, touched, declared_only=False):
    """План против факта: расхождения в обе стороны.

    `факты` — {(вид, имя): `ObjectFact`} по объектам плана; `затронутые` —
    {(вид, имя): статусы файлов объекта} — объекты, файлы которых задача
    добавила, изменила или удалила; у карточки статус свой, у прочих файлов —
    «изменён».

    `declared_only` — сверка урезанного плана (круг задачи с частью
    объектов): тронутое, но не заявленное находкой не считается — его
    называет `незаявленные`.
    """
    findings, declared_items = [], set()
    for obj in plan.objects:
        key = (obj.kind, obj.name)
        declared_items.add(key)
        findings += _object(obj, facts[key], key in touched)
    if declared_only:
        return findings
    for (kind, name), statuses in sorted(touched.items()):
        if (kind, name) in declared_items:
            continue
        what = "новый объект" if ADDED in statuses else "удалён" if DELETED in statuses else "изменён"
        code = INCIDENTAL_UNDECLARED if kind in INCIDENTAL else OBJECT_UNDECLARED
        findings.append(PlanFinding(code, f"{kind}.{name}", f"{what}, в плане не заявлен"))
    return findings


def undeclared(plan, touched):
    """«Вид.Имя» объектов, которые задача тронула, а план не называет."""
    declared_items = {(obj.kind, obj.name) for obj in plan.objects}
    return [f"{kind}.{name}" for kind, name in sorted(touched) if (kind, name) not in declared_items]


def _object(obj, fact, is_touched):
    who = f"{obj.kind}.{obj.name}"
    card = fact.card if fact.after is not None else None
    if obj.action == DELETE:
        if fact.after is not None:
            return [PlanFinding(OBJECT_REMAINED, who, "заявлен к удалению, но в выгрузке остался",
                                 fact.card)]
        return []
    findings = []
    if fact.after is None:
        applies_to = "к созданию" if obj.action == CREATE else "к изменению"
        return [PlanFinding(OBJECT_NOT_DONE, who, f"заявлен {applies_to}, в выгрузке нет")]
    if obj.action == CREATE and fact.before_ is not None:
        findings.append(PlanFinding(OBJECT_EXISTED, who, "заявлен к созданию, но уже был в базе",
                                    card))
    if obj.action == CHANGE and not is_touched:
        findings.append(PlanFinding(OBJECT_UNCHANGED, who, "заявлен к изменению, правок в объекте нет",
                                    card))
    if fact.after.broken:
        return findings + [PlanFinding(CARD_UNREADABLE, who,
                                       f"карточка не читается: {fact.after.broken}", card)]
    base = fact.before_ if fact.before_ is not None and not fact.before_.broken else None
    for group in GROUPS:
        if group in NOT_EVERYWHERE and group not in fact.after.members:
            continue
        findings += _group(who, group, obj.members.get(group) or {}, fact.after.members.get(group, {}),
                           None if base is None else base.members.get(group, {}), card)
    for module, names in obj.modules.items():
        findings += _module(who, obj.kind, module, names, fact.modules.get(module))
    return findings


def _group(who, group, declared_set, exists, before, card):
    word, ending = MEMBER[group]
    findings = []
    for name, types in declared_set.items():
        if name not in exists:
            findings.append(PlanFinding(MEMBER_NOT_DONE, who, f"{word} «{name}» заявлен{ending}, "
                                        "в выгрузке нет", card))
            continue
        if not types:
            continue
        in_plan = {type_genus(tk): tk for tk in types}
        in_dump = {type_genus(tk): tk for tk in type_records(exists[name])}
        missing = [in_plan[rr] for rr in in_plan if rr not in in_dump]
        extra = [in_dump[rr] for rr in in_dump if rr not in in_plan]
        if missing or extra:
            detailed = (("; в плане, но не в выгрузке: " + ", ".join(missing)) if missing else "") + \
                       (("; в выгрузке, но не в плане: " + ", ".join(extra)) if extra else "")
            findings.append(PlanFinding(TYPES_DIFFER, who, f"{word} «{name}»: типы расходятся{detailed}",
                                        card))
    for name in exists:
        if name not in declared_set and (before is None or name not in before):
            findings.append(PlanFinding(MEMBER_UNDECLARED, who, f"{word} «{name}» есть в выгрузке, "
                                        f"в плане не заявлен{ending}", card))
    return findings


def _module(who, kind, module, names, fact):
    which = "" if SINGLE_MODULE.get(kind) == module else f" ({module})"
    if fact is None or fact.after is None:
        return [PlanFinding(MODULE_NOT_DONE, who, f"заявлены методы модуля{which}, а модуля нет")]
    findings = [PlanFinding(METHOD_NOT_DONE, who, f"метод {name}{which} заявлен, в модуле нет", fact.path)
               for name in names if name not in fact.after]
    for name, (export, line) in fact.after.items():
        if export and name not in names and name not in fact.before_:
            findings.append(PlanFinding(METHOD_UNDECLARED, who, f"экспортный метод {name}{which} есть "
                                        "в модуле, в плане не заявлен", fact.path, line))
    return findings


# --- план по факту ---------------------------------------------------------------------


def plan_from_fact(facts):
    """Факт задачи -> план того же вида: объекты, их новые члены с типами —
    записью показа, с уточнениями, — и новые методы модулей, все, а не только
    экспортные. `факты` — [`ObjectFact`] в порядке, в каком их называть."""
    objects = []
    for fact in facts:
        action = DELETE if fact.after is None else CREATE if fact.before_ is None else CHANGE
        members, modules = {}, {}
        if fact.after is not None and not fact.after.broken:
            base = fact.before_ if fact.before_ is not None and not fact.before_.broken else None
            for group in GROUPS:
                before = {} if base is None else base.members.get(group, {})
                new_items = {name: (None if group in WITHOUT_TYPES else type_records(types))
                         for name, types in fact.after.members.get(group, {}).items() if name not in before}
                if new_items:
                    members[group] = new_items
        if fact.after is not None:
            for module, mf in fact.modules.items():
                new_items = tuple(name for name in (mf.after or {}) if name not in mf.before_)
                if new_items:
                    modules[module] = new_items
        objects.append(PlanObject(fact.kind, fact.name, action, members, modules))
    return Plan(tuple(objects))
