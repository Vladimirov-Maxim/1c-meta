"""Атомарные роли: по паре ролей на объект — «Просмотр» и «Изменение».

Так устроены права во многих конфигурациях: на каждый объект — роль, дающая
его видеть, и роль, дающая его менять, а права пользователю собирают из таких
пар. Заводить их руками при каждом новом объекте — та работа, из-за которой
создание объекта инструментом всё равно заканчивалось бы в конфигураторе.

Как роли называются, — соглашение команды: шаблоны имени и синонима
(`RoleSchema`) приходят из профиля соглашений, и без них атомарных ролей
инструмент не заводит — роль с чужим именем хуже, чем никакой. Состав прав в
роли — общий, он здесь: самое частое сочетание в замеренной выгрузке, где
такая схема ролей принята:

* документ: просмотр и изменение — почти у всех ролей;
* регистр сведений: просмотр — почти у всех, изменение — чуть больше чем у половины;
* регистр накопления: просмотр — у всех, изменение — меньше чем у половины;
* справочник: просмотр — у большинства, изменение — меньше чем у половины:
  состав «изменения» у справочников расходится сильнее всего (права на
  предопределённые данные, история данных).

Насколько ему следуют соседи в *этой* выгрузке, инструмент считает сам — по
ролям той же схемы (`совет`): число, снятое с одной конфигурации, в другой
было бы неправдой. С какими соседями сверять и чем устроены остальные,
говорится словами, которыми их можно найти.

У обработки и отчёта роль одна и без суффикса — «Использование» и
«Просмотр»: их нечем менять, и пара им не нужна.

Помимо прав на сам объект каждая роль несёт шесть прав на конфигурацию —
режимы основного окна и клиент системы аналитики. Их ставит конфигуратор
при создании роли.
"""

import re
import string
from collections import Counter
from dataclasses import dataclass

from .model import Refuse, Spec

#: Поля шаблона имени — каждое ровно один раз: без любого из них имена ролей
#: разных объектов, видов или прав совпали бы.
NAME_FIELDS = ("вид", "объект", "право")
#: Поля шаблона синонима: {вид} — словами («Регистр сведений»), {синоним} —
#: синоним объекта, {объект} — его имя.
SYNONYM_FIELDS = ("вид", "синоним", "объект", "право")


@dataclass(frozen=True)
class RoleSchema:
    """Как команда называет атомарные роли.

    `имя` — «мой_атом_{вид}_{объект}_{право}», `синоним` — «(Мой) Атом. {вид} -
    {синоним} - {право}». Неверная схема — отказ при создании: имена, которые
    она дала бы, совпадали бы у разных ролей или не были бы именами.
    """

    name: str
    synonym: str

    def __post_init__(self):
        fields = _fields(self.name, "имени")
        if Counter(fields) != Counter(NAME_FIELDS):
            raise Refuse(f"шаблон имени атомарной роли «{self.name}» — поля "
                         f"{', '.join('{' + pt + '}' for pt in NAME_FIELDS)}, каждое ровно один раз")
        surplus = "".join(literal for literal, *_ in string.Formatter().parse(self.name))
        if re.search(r"\W", surplus):
            raise Refuse(f"шаблон имени атомарной роли «{self.name}» — вне полей только буквы, "
                         "цифры и «_»: имя роли — идентификатор")
        fields = _fields(self.synonym, "синонима")
        if not set(fields) <= set(SYNONYM_FIELDS) or "право" not in fields or not (
                {"синоним", "объект"} & set(fields)):
            raise Refuse(f"шаблон синонима атомарной роли «{self.synonym}» — поля из "
                         f"{', '.join('{' + pt + '}' for pt in SYNONYM_FIELDS)}, среди них {{право}} "
                         "и {синоним} или {объект}: иначе синонимы разных ролей совпадут")


def _fields(pattern, of_what):
    try:
        parsed = list(string.Formatter().parse(pattern))
    except ValueError as error:
        raise Refuse(f"шаблон {of_what} атомарной роли «{pattern}» не разобрать: {error}") from error
    fields = []
    for _, field, fmt, conversion in parsed:
        if field is None:
            continue
        if fmt or conversion:
            raise Refuse(f"шаблон {of_what} атомарной роли «{pattern}» — поля без формата: "
                         f"{{{field}}}")
        fields.append(field)
    return fields


#: Вид в синониме — словами, как его называет платформа: «Регистр сведений», а
#: не «РегистрСведений». Документ и справочник — одним словом.
SYNONYM_KIND = {"РегистрСведений": "Регистр сведений", "РегистрНакопления": "Регистр накопления"}

#: Права на конфигурацию, которые конфигуратор ставит новой роли сам.
CONFIGURATION_RIGHTS = (
    "РежимОсновногоОкнаОбычный", "РежимОсновногоОкнаРабочееМесто",
    "РежимОсновногоОкнаВстроенноеРабочееМесто",
    "РежимОсновногоОкнаПолноэкранноеРабочееМесто", "РежимОсновногоОкнаКиоск",
    "КлиентСистемыАналитики",
)

_REFERENCE_VIEW = ("Чтение", "Просмотр", "ВводПоСтроке")
_REGISTER_VIEW = ("Чтение", "Просмотр")
_DOCUMENT_CHANGE = (
    "Чтение", "Добавление", "Изменение", "Просмотр", "Редактирование",
    "ВводПоСтроке", "Проведение", "ОтменаПроведения",
    "ИнтерактивноеДобавление", "ИнтерактивнаяПометкаУдаления",
    "ИнтерактивноеСнятиеПометкиУдаления", "ИнтерактивноеПроведение",
    "ИнтерактивноеПроведениеНеОперативное", "ИнтерактивнаяОтменаПроведения",
    "ИнтерактивноеИзменениеПроведенных",
)
_CATALOG_CHANGE = (
    "Чтение", "Добавление", "Изменение", "Просмотр", "Редактирование",
    "ВводПоСтроке", "ИнтерактивноеДобавление", "ИнтерактивнаяПометкаУдаления",
    "ИнтерактивноеСнятиеПометкиУдаления",
    "ИнтерактивнаяПометкаУдаленияПредопределенныхДанных",
    "ИнтерактивноеСнятиеПометкиУдаленияПредопределенныхДанных",
    "ЧтениеИсторииДанных", "ПросмотрИсторииДанных", "ИзменениеИсторииДанных",
    "ЧтениеИсторииДанныхОтсутствующихДанных",
    "ИзменениеИсторииДанныхОтсутствующихДанных",
    "ИзменениеНастроекИсторииДанных", "ИзменениеКомментарияВерсииИсторииДанных",
    "РедактированиеКомментарияВерсииИсторииДанных", "ПереходНаВерсиюИсторииДанных",
)
_INFORMATION_REGISTER_CHANGE = ("Чтение", "Изменение", "Просмотр", "Редактирование")
_USE = ("Использование", "Просмотр")
_ACCUMULATION_REGISTER_CHANGE = ("Чтение", "Изменение", "Просмотр",
                                  "Редактирование", "УправлениеИтогами")

#: (вид, право) -> права на объект: типовой состав роли.
TEMPLATES = {
    ("Документ", "Просмотр"): _REFERENCE_VIEW,
    ("Документ", "Изменение"): _DOCUMENT_CHANGE,
    ("Справочник", "Просмотр"): _REFERENCE_VIEW,
    ("Справочник", "Изменение"): _CATALOG_CHANGE,
    ("РегистрСведений", "Просмотр"): _REGISTER_VIEW,
    ("РегистрСведений", "Изменение"): _INFORMATION_REGISTER_CHANGE,
    ("РегистрНакопления", "Просмотр"): _REGISTER_VIEW,
    ("РегистрНакопления", "Изменение"): _ACCUMULATION_REGISTER_CHANGE,
    # Обработка и отчёт: роль одна и без суффикса — «пользоваться». Замер по
    # проекту, где схема принята: у обработок 32 роли без суффикса против 11
    # с суффиксом, у отчётов 25 против 5; права — «Использование» и
    # «Просмотр» у 47 из них.
    ("Обработка", ""): _USE,
    ("Отчет", ""): _USE,
}

#: Права, которые заводятся по умолчанию, — обе роли пары.
DEFAULT_RIGHTS = ("Просмотр", "Изменение")
#: Виды с одной ролью без суффикса: право в имени и синониме пустое.
SINGLE_ROLE = {"Обработка": ("",), "Отчет": ("",)}
#: Ниже этой доли соседей с типовым составом совет говорит, что он не правило.
FIRM_SHARE = 0.85
#: Сколько других составов называет совет и сколько прав в каждом отличии.
OTHER_COMPOSITIONS = 3
RIGHTS_IN_DIFF = 3


def kinds():
    """Виды, для которых есть типовой состав."""
    return tuple(sorted({kind for kind, _ in TEMPLATES}))


def needs_schema(schema):
    """Схема команды или отказ: имени атомарной роли без неё не из чего взять."""
    if schema is None:
        raise Refuse("атомарные роли заводятся по схеме команды, а она не задана: "
                     "профиль соглашений, ключ «атомарныеРоли» — шаблоны имени и синонима "
                     "роли, например {\"имя\": \"мой_атом_{вид}_{объект}_{право}\", "
                     "\"синоним\": \"Атом. {вид} - {синоним} - {право}\"}")
    return schema


def role_name(schema, kind, name, right, abbreviation=None):
    """`сокращение` — короткое имя объекта для имени роли: у длинного объекта
    имя роли выходит за 80 символов (#std474 п. 2.3), и такие сокращают руками."""
    return _fill(schema.name, вид=kind, объект=abbreviation or name, право=right)


def _fill(pattern, **values):
    """Шаблон схемы с подстановкой. Пустое право убирает и разделитель перед
    ним: «мой_атом_{вид}_{объект}_{право}» -> «мой_атом_Обработка_Имя», а синоним
    «… - {синоним} - {право}» -> «… - Синоним»."""
    if values.get("право"):
        return pattern.format(**values)
    came_out = []
    for literal, field, _, _ in string.Formatter().parse(pattern):
        if field == "право":
            # Разделитель перед правом уходит вместе с ним; право в начале
            # шаблона — разделитель уходит после него.
            if came_out or literal:
                came_out.append(re.sub(r"[\W_]+$", "", literal))
            else:
                came_out.append(None)
            continue
        if came_out and came_out[-1] is None:
            came_out[-1] = ""
            literal = re.sub(r"^[\W_]+", "", literal)
        came_out.append(literal)
        if field:
            came_out.append(str(values[field]))
    return "".join(x for x in came_out if x)


def name_pattern(schema, kind=None):
    """Регулярное выражение имён атомарных ролей по схеме — с группами «объект» и
    «право»: так находятся соседи и пара, уже заведённая объекту. Без вида —
    роли любого вида, для которого есть типовой состав."""
    kind_names = [kind] if kind else list(kinds())
    parts = []
    for literal, field, _, _ in string.Formatter().parse(schema.name):
        if field == "право":
            # Право с разделителем перед ним — необязательно: у обработки и
            # отчёта роль одна и без суффикса.
            separator = re.search(r"[\W_]*$", literal).group(0)
            parts.append(re.escape(literal[:len(literal) - len(separator)]))
            parts.append("(?:" + re.escape(separator) + "(?P<право>"
                         + "|".join(map(re.escape, DEFAULT_RIGHTS)) + "))?")
            continue
        parts.append(re.escape(literal))
        if field == "вид":
            parts.append("(?:" + "|".join(map(re.escape, kind_names)) + ")")
        elif field == "объект":
            parts.append("(?P<объект>.+?)")
    return "".join(parts)


def is_atomic_role(schema, name):
    """Названа ли роль по схеме атомарных ролей команды; без схемы — нет."""
    return schema is not None and re.fullmatch(name_pattern(schema), name or "") is not None


def roles_of_object(kind, name, roles):
    """Имена ролей из `роли` ({имя роли: выдачи}), чьи права выданы на объект.

    Имя роли по имени объекта не угадать — длинные сокращают, — поэтому по
    правам, а не по имени."""
    target = f"{kind}.{name}"
    return sorted(role for role, grants in (roles or {}).items()
                  if any(vv["объект"] == target for vv in grants))


def compositions(kind, right, roles, schema):
    """Составы прав на свой объект у ролей вида с этим правом: [(состав, имя роли)]."""
    pattern = re.compile(name_pattern(schema, kind))
    result = []
    for role, grants in sorted((roles or {}).items()):
        found = pattern.fullmatch(role)
        if found is None or (found.group("право") or "") != right:
            continue
        own = [vv for vv in grants
                if vv["объект"].startswith(kind + ".") and vv["объект"].count(".") == 1]
        if len(own) == 1:
            result.append((frozenset(own[0]["права"]), role))
    return result


def difference(composition, is_standard):
    """Чем состав отличается от типового — словами: «без A, B и ещё 3; с C»."""
    def listing(rights):
        if len(rights) <= RIGHTS_IN_DIFF:
            return ", ".join(rights)
        return ", ".join(rights[:RIGHTS_IN_DIFF]) + f" и ещё {len(rights) - RIGHTS_IN_DIFF}"
    without = [pt for pt in is_standard if pt not in composition]
    beyond = sorted(composition - set(is_standard))
    chunks = ([f"без {listing(without)}"] if without else []) + ([f"с {listing(beyond)}"] if beyond else [])
    return "; ".join(chunks)


def advice(kind, right, schema, roles):
    """Совет о составе роли по соседям в выгрузке или `None`.

    `роли` — {имя роли: выдачи} ролей вида по схеме; `None` — выгрузку не
    спросить, и сказать о соседях нечего. Совета нет и там, где соседей нет
    или типовому составу следуют почти все.
    """
    is_standard = TEMPLATES[(kind, right)]
    found = compositions(kind, right, roles, schema)
    if not found:
        return None
    as_is = sum(1 for composition, _ in found if composition == frozenset(is_standard))
    if as_is / len(found) >= FIRM_SHARE:
        return None
    count = Counter(composition for composition, _ in found if composition != frozenset(is_standard))
    example = {}
    for composition, role in found:
        example.setdefault(composition, role)
    others = "; ".join(f"{difference(composition, is_standard)} — {how_many}, например «Роль.{example[composition]}»"
                       for composition, how_many in count.most_common(OTHER_COMPOSITIONS))
    neighbours = _fill(schema.name, вид=kind, объект="*", право=right)
    # И как получить другой состав: «права» у атомарных ролей выбирают роли, а
    # не права платформы, и без подсказки путь пришлось бы искать самому.
    return (f"типовой состав прав роли «{right}» у вида «{kind}» в выгрузке не правило: "
            f"так устроены {as_is} из {len(found)} ролей «{right}» этого вида"
            + (f"; другие составы: {others}" if others else "")
            + f". Сверьте с ролями {neighbours} соседних объектов — права роли показывает show "
            "по адресу «Роль.<имя>». Нужен другой состав — заведите эту роль не атомарной "
            "парой, а пунктом objects вида «Роль» с полем «права» (имя и синоним — как в "
            "этом плане)")


def roles_for(kind, name, synonym, rights=None, abbreviation=None, schema=None, roles=None,
              comment=None):
    """Спецификации ролей для объекта. `права` — какие из пары заводить;
    `роли` — роли вида по схеме, что уже есть в выгрузке (для совета);
    `комментарий` — комментарий роли (у соседей — дата, автор, задача).

    Возвращает список пар (спецификация роли, совет или `None`).
    """
    needs_schema(schema)
    if kind in SINGLE_ROLE and rights:
        raise Refuse(f"у вида «{kind}» атомарная роль одна, без суффикса — права "
                     "«Использование» и «Просмотр»; «права» здесь не задаются")
    result = []
    for right in rights or SINGLE_ROLE.get(kind) or DEFAULT_RIGHTS:
        own = TEMPLATES.get((kind, right))
        if own is None:
            known_set = sorted({pt for vv, pt in TEMPLATES if vv == kind})
            raise Refuse(
                f"атомарной роли «{right}» для вида «{kind}» нет типового состава; "
                + (f"для него есть: {', '.join(known_set)}" if known_set
                   else f"типовой состав есть для: {', '.join(kinds())}"))
        # Синоним роли пишет инструмент, и «ё» из синонима объекта в нём не
        # оставляет (#std474 п. 4): у чужого объекта синоним не исправить.
        role_synonym = _fill(
            schema.synonym, вид=SYNONYM_KIND.get(kind, kind), синоним=synonym or name,
            объект=name, право=right).replace("ё", "е").replace("Ё", "Е")
        fields = {
            "имя": role_name(schema, kind, name, right, abbreviation),
            "синоним": role_synonym,
            "права": [
                {"объект": f"{kind}.{name}", "права": list(own)},
                {"объект": "Конфигурация", "права": list(CONFIGURATION_RIGHTS)},
            ],
        }
        if comment:
            fields["комментарий"] = comment
        spec = Spec("Роль", fields)
        result.append((spec, advice(kind, right, schema, roles)))
    return result
