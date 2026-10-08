"""Разбор задания: диалект JSON -> спецификации на языке домена.

Это язык заданий, а не сценарий и не канал. Формат задания — подробность
того, как с инструментом разговаривают снаружи, и говорят с ним по двум
каналам: терминал читает задание из файла, MCP получает его параметрами. Оба
переводят его в модель приложения этим модулем — поэтому он лежит под
каналами, а не в одном из них, и сценарий о формате не знает ничего.

Границу стережёт `tests/test_architecture.py`: `jobs` разрешено обращаться
только к `domain`.
"""

import difflib
import re

from ..domain import forms as fm
from ..domain import model as dm
from ..domain.model import Refuse, Spec, TypeRef, Собранные

#: Ключи пункта каждой операции. Лишний ключ — отказ, а не тишина: иначе
#: «атомарныеРоли» рядом с «вид» молча терялись бы, и роли не заводились — в
#: плане их просто не было бы, а отказ на соседнем шаге («имя не заполнено»)
#: уводил бы в сторону.
ITEM_KEYS = {
    "objects": ("вид", "поля"),
    "attributes": ("объект", "поля"),
    "additions": ("путь", "вид", "поля"),
    "changes": ("путь", "поля"),
    "deletions": ("путь",),
    "renames": ("путь", "имя"),
    "atomic_roles": ("объект", "права", "сокращение", "комментарий"),
}


def item_of(data, operation):
    """Пункт операции — объект с её ключами, «поля» — объект. Иначе отказ."""
    allowed = ITEM_KEYS[operation]
    if not isinstance(data, dict):
        raise Refuse(f"пункт «{operation}» — объект с ключами {', '.join(allowed)}; "
                     f"получено {data!r}")
    unknown = [key for key in data if key not in allowed]
    if unknown:
        hint = ""
        if "поля" in allowed:
            hint = ('; поля самого объекта пишутся внутри «поля»: '
                    f'{{"поля": {{"{unknown[0]}": …}}}}')
        raise Refuse(f"в пункте «{operation}» неизвестные ключи: {', '.join(unknown)}; "
                     f"допустимы: {', '.join(allowed)}{hint}")
    if "поля" in data and not isinstance(data["поля"], dict):
        raise Refuse(f"«поля» в пункте «{operation}» — объект {{поле: значение}}, "
                     f"получено {data['поля']!r}")
    return data


#: «Вид», «Вид.Имя» или «Вид.Имя (Грань)» — так обозначение типа печатает показ.
SHORT_TYPE_REF = re.compile(r"\s*([^.\s()]+)(?:\.([^\s()]*))?\s*(?:\(\s*([^()\s]+)\s*\))?\s*")


def type_ref_from_json(data):
    """{"вид": "Справочник", "имя": "Контрагенты", "грань": "Объект"} -> ссылка на тип.

    `набор` — признак «набор типов», а не один тип; для определяемого типа он
    подразумевается. Грань можно не указывать: у определяемого типа её нет.
    """
    if isinstance(data, str):                     # краткая запись: "Справочник.Контрагенты"
        # Грань — в скобках, как её печатает показ: «Справочник.Контрагенты
        # (Объект)». Иначе скопированная из показа запись читалась бы именем
        # «Контрагенты (Объект)» — источника с таким именем нет.
        краткая = SHORT_TYPE_REF.fullmatch(data)
        if краткая is None:
            raise Refuse(f"обозначение «{data}» не разобрано: пишется «Вид.Имя» или "
                         "«Вид.Имя (Грань)», например «Справочник.Контрагенты (Объект)»")
        kind, name, facet = краткая.groups()
        data = {"вид": kind, "имя": name or None}
        if facet:
            data["грань"] = facet
    _check_keys(data, ("вид", "имя", "грань", "набор"), data.get("вид") or "?")
    kind = data.get("вид")
    name = data.get("имя")
    if kind == "ОпределяемыйТип":
        return TypeRef.defined(name)
    facet = data.get("грань", "Объект")
    is_set = data.get("набор", name is None and data.get("грань") is None)
    return TypeRef(kind, name, facet, is_set=bool(is_set))


def spec_from_json(data):
    """Задание на создание объекта -> спецификация на языке домена."""
    kind = item_of(data, "objects").get("вид")
    if not kind:
        raise Refuse("в задании не указан вид объекта")
    # Поля с типом разбирает `child_spec_from_json` — по списку, который
    # объявил домен. Отдельной ветки на источник подписки здесь нет: она
    # стала бы третьим местом, где эти поля перечисляются руками.
    return child_spec_from_json(kind, dict(data.get("поля") or {}))


def child_spec_from_json(kind, data):
    """Вложенная сущность: те же поля, что и отдельным заданием, и свои дети.

    Какие поля являются детьми, знает домен, а не диалект: иначе каждый новый
    вид объекта пришлось бы вписывать сюда руками — и забыть вписать.
    Глубина не ограничена: у справочника есть табличные части, у них реквизиты.
    """
    собранные = Собранные("в задании непонятно")
    spec = _spec(kind, data, "", собранные)
    собранные.предъявить()
    return spec


def _spec(kind, data, адрес, собранные):
    """То же, но беды копятся с адресом, а не рвут разбор на первой.

    Домен собирает все свои находки разом — и разбор задания тоже: иначе
    четыре беды в описании типов стоили бы четырёх запусков, и каждый раз
    человек узнавал бы ровно об одной. При этом на экране рядом печатался бы
    разбор остальных полей, из-за чего непонятое выглядело бы понятым.
    """
    from ..domain.kinds import REGISTRY

    fields = dict(data)
    for field, как in (getattr(REGISTRY.get(kind), "type_fields", {}) or {}).items():
        if field not in fields:
            continue
        значение = fields[field]
        try:
            if как == "объект":
                # Поле-перечень: одно обозначение без списка — список из одного.
                # Так источник подписки печатает показ, и скопированное оттуда
                # значение иначе ушло бы в домен одним обозначением, а проверка
                # подписки упала бы трассировкой.
                значения = значение if isinstance(значение, list) else [значение]
                fields[field] = [type_ref_from_json(x) for x in значения]
            else:
                fields[field] = value_type_from_json(значение)
        except Refuse as отказ:
            собранные.добавить(f"{адрес}{field}: {отказ}")
            fields.pop(field)             # неразобранное не выдаём за разобранное
    # Списки обозначений («движения», «состав», «основание») принимаются
    # и строкой «Вид.Имя», и объектом {"вид", "имя"} — как типы. Объект
    # иначе уронил бы инструмент трассировкой из недр перекладки, а не
    # отказом с адресом поля.
    for field in getattr(REGISTRY.get(kind), "object_lists", ()) or ():
        if field not in fields:
            continue
        try:
            fields[field] = [designation_from_json(x) for x in (fields[field] or [])]
        except Refuse as отказ:
            собранные.добавить(f"{адрес}{field}: {отказ}")
            fields.pop(field)
    for field, child_kind in getattr(REGISTRY.get(kind), "child_fields", ()) or ():
        if field not in fields:
            continue
        дети = []
        for место, child in enumerate(fields[field] or [], 1):
            имя = child.get("имя") if isinstance(child, dict) else None
            дети.append(_spec(child_kind, child,
                              f"{адрес}{field}[{имя or место}].", собранные))
        fields[field] = дети
    return Spec(kind, fields)


def designation_from_json(value):
    """Обозначение объекта из задания -> «Вид.Имя».

    Строка отдаётся как есть (форму проверяет домен), объект собирается
    из «вид» и «имя»; лишние ключи — отказ, как у описания типа: молча
    проглоченный ключ здесь невидим и в задании, и в результате.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        лишние = sorted(set(value) - {"вид", "имя"})
        if лишние or not value.get("вид") or not value.get("имя"):
            raise Refuse(
                "обозначение объекта — это «Вид.Имя» строкой или объект "
                '{"вид": …, "имя": …}; получено ' + repr(value))
        return f"{value['вид']}.{value['имя']}"
    raise Refuse(
        "обозначение объекта — это «Вид.Имя» строкой или объект "
        f'{{"вид": …, "имя": …}}; получено {type(value).__name__} {value!r}')


def attribute_spec_from_json(data):
    """Реквизит, заданный внутри объекта."""
    return child_spec_from_json("Реквизит", data)


# Ключи, допустимые внутри описания типа, по видам. Таблица нужна затем же,
# зачем домену список полей: без неё лишний ключ молча заменялся бы
# умолчанием — «длина»/«точность» вместо «разрядность»/«дробнаяЧасть» дали бы
# Число(10,0) вместо Число(15,2), и ни просмотр, ни план этого не показали бы.
TYPE_KEYS = {
    "Строка": ("вид", "длина", "фиксированная"),
    "Число": ("вид", "разрядность", "дробнаяЧасть", "неотрицательное"),
    "Дата": ("вид", "состав"),
    "Булево": ("вид",),
    "Произвольный": ("вид",),
    "ОпределяемыйТип": ("вид", "имя"),
}
PLATFORM_KINDS = ("ХранилищеЗначения", "УникальныйИдентификатор", "СтандартныйПериод",
                  "СписокЗначений", "ТаблицаЗначений", "ДеревоЗначений",
                  "СтандартнаяДатаНачала")
REFERENCE_KEYS = ("вид", "имя", "грань")


def _check_keys(data, allowed, what):
    unknown = [key for key in data if key not in allowed]
    if unknown:
        raise Refuse("в описании типа «{}» неизвестные ключи: {}; допустимы: {}".format(
            what, ", ".join(unknown), ", ".join(allowed)))


#: Виды, у которых есть квалификатор: краткой записью их не задать.
#: Значение — что вышло бы, если разрешить.
#: Значения, которые бывают у квалификатора. Проверяются здесь, при разборе,
#: а не в перекладке, на ступень позже инвариантов: там вместе с любой другой
#: ошибкой они не показывались бы вовсе — в разборе печаталось бы
#: `Дата(ТолькоДата)`, будто значение принято, а отказ приходил бы только
#: следующим запуском, когда первая ошибка уже исправлена.
QUALIFIER_VALUES = {("Дата", "состав"): dm.DateType.PARTS}

#: Ключ квалификатора, без которого тип не задан. Краткую запись («тип»:
#: «Строка») отвергает разбор строки, а объектная, `{"вид": "Строка"}`, без
#: этой проверки давала бы ровно то же самое молча. У даты это ещё и выбор,
#: а не мелочь: в замеренной выгрузке `ДатаВремя` стоит у 2884 реквизитов,
#: `Дата` — у 2653, то есть почти поровну, и угадывать за человека тут нечего.
QUALIFIER_KEY = {"Строка": "длина", "Число": "разрядность", "Дата": "состав"}

QUALIFIED = {
    "Строка": "строка неограниченной длины",
    "Число": "Число(10,0)",
    "Дата": "дата с временем",
}

#: То же краткой записью — как её печатает просмотр.
SHORT_EXAMPLE = {"Строка": "«Строка(20)»", "Число": "«Число(15,2)»"}

#: Как написать такой тип правильно — прямо в тексте отказа.
EXAMPLE = {
    "Строка": '{"вид": "Строка", "длина": 20}',
    "Число": '{"вид": "Число", "разрядность": 15, "дробнаяЧасть": 2}',
    "Дата": '{"вид": "Дата", "состав": "Дата"}',
}


def value_type_from_json(data):
    """Описание типа из задания -> тип на языке домена.

    Ссылка на объект пишется как `{"вид": "Справочник", "имя": "Контрагенты"}`:
    у реквизита это грань «Ссылка», в отличие от источника подписки, где
    участвует объект целиком.

    Неизвестный ключ — отказ, а не умолчание: ошибку в имени ключа иначе
    не видно ни в просмотре, ни в результате, а метаданные пишутся не те.
    """
    if isinstance(data, list):
        return [value_type_from_json(x) for x in data]
    if isinstance(data, str):
        # У строки и числа есть квалификатор, и `"тип": "Строка"` иначе
        # разобралось бы в строку неограниченной длины — молча, с вердиктом
        # «замечаний нет». Это ровно то умолчание, которое незаметно и в
        # задании, и в результате.
        if data in ("Строка", "Число"):
            raise Refuse(
                f"у типа «{data}» нужен квалификатор, без него вышла бы "
                f"{QUALIFIED[data]}: напишите {SHORT_EXAMPLE[data]} "
                f"или объектом, например {EXAMPLE[data]}")
        # Краткая запись — та же, что у задания на формы и в просмотре: тип,
        # выданный `show`, вставляется в задание на метаданные как есть. Состав
        # даты в ней — само слово: «Дата» — только дата, «ДатаВремя», «Время».
        if (data in dm.DateType.PARTS or data in dm.TypeRef.NAMELESS
                or any(знак in data for знак in "(.|")):
            return value_type_from_text(data)
        data = {"вид": data}
    kind = data.get("вид")
    if kind in TYPE_KEYS:
        _check_keys(data, TYPE_KEYS[kind], kind)
        for (вид, поле), значения in QUALIFIER_VALUES.items():
            if вид == kind and поле in data and data[поле] not in значения:
                близкое = difflib.get_close_matches(
                    str(data[поле]), значения, n=1, cutoff=0.5)
                raise Refuse(
                    f"у типа «{kind}» не знаю {поле} «{data[поле]}»; "
                    f"допустимо: {', '.join(значения)}"
                    + (f" — возможно, {близкое[0]}" if близкое else ""))
        ключ = QUALIFIER_KEY.get(kind)
        if ключ and ключ not in data:
            raise Refuse(
                f"у типа «{kind}» не задан «{ключ}», а без него вышла бы "
                f"{QUALIFIED[kind]}. Напишите, например, {EXAMPLE[kind]}")
    elif kind in PLATFORM_KINDS:
        _check_keys(data, ("вид",), kind)
    if kind == "Строка":
        return dm.StringType(data.get("длина", 0), data.get("фиксированная", False))
    if kind == "Число":
        return dm.NumberType(data.get("разрядность", 10),
                             data.get("дробнаяЧасть", 0),
                             data.get("неотрицательное", False))
    if kind == "Дата":
        return dm.DateType(data.get("состав", "ДатаВремя"))
    if kind == "Булево":
        return dm.BooleanType()
    if kind == "Произвольный":
        return dm.AnyType()
    if kind in PLATFORM_KINDS:
        return dm.PlatformType(kind)
    if kind == "ОпределяемыйТип":
        return dm.TypeRef.defined(data.get("имя"))
    name = data.get("имя")
    # Незнакомое слово на месте вида — скорее опечатка в примитивном типе,
    # чем ссылка на объект. Совет «допишите имя объекта: {"вид": "Строчка",
    # "имя": "Контрагенты"}» предлагал бы достроить вид, которого не бывает;
    # подсказка — как у опечаток в именах полей.
    похоже = difflib.get_close_matches(
        kind or "", list(TYPE_KEYS) + list(PLATFORM_KINDS), n=2, cutoff=0.55)
    if kind and not name and похоже:
        raise Refuse(f"вида «{kind}» среди типов нет — возможно, "
                     f"{' или '.join(похоже)}")
    # Вид назван, а имя нет — это не «невнятно», это «не хватает имени»,
    # и сказать надо именно так: пересказ всего формата заново заставил бы
    # человека искать в нём ошибку, которой он не делал.
    if kind and not name:
        raise Refuse(
            f"у ссылочного типа «{kind}» не указано имя объекта: "
            f"{{\"вид\": \"{kind}\", \"имя\": \"Контрагенты\"}}")
    if not kind:
        raise Refuse(
            f"тип задан невнятно: {data!r}. Примитив пишется как {{\"вид\": \"Строка\", "
            "\"длина\": 20}, ссылка — как {\"вид\": \"Справочник\", \"имя\": "
            "\"Контрагенты\"} (грань «Ссылка» подразумевается)")
    _check_keys(data, REFERENCE_KEYS, kind)
    return dm.TypeRef(kind, name, data.get("грань", "Ссылка"))


def attribute_job_from_json(data):
    """{"объект": "Справочник.Контрагенты", "поля": {…}} -> (адрес, спецификация).

    Реквизит в объект — частный случай «ребёнок по адресу хозяина», и задание
    получается такое же, как у `additions`. Ключ свой — «объект»: он короче,
    а операция за ним одна. Два сценария на одну операцию разошлись бы —
    скажем, врезка не писала бы в план пояснения, и просмотр не отвечал бы на
    главный вопрос «то ли записано, что задумано».
    """
    # У `additions` адрес зовётся «путь», у `attributes` — «объект»,
    # и справка подаёт их как одну операцию. Написавший «путь» иначе получил
    # бы «получено «»» — сообщение про значение, которого он не писал, вместо
    # сообщения про ключ.
    if isinstance(data, dict) and "объект" not in data:
        подсказка = (' (в задании есть «путь» — это ключ операции '
                     '"additions"; здесь нужен «объект»)'
                     if "путь" in data else "")
        raise Refuse("в реквизите не указан объект-хозяин (ключ «объект»)"
                     + подсказка)
    obj = item_of(data, "attributes").get("объект") or ""
    kind, _, name = obj.partition(".")
    if not kind or not name:
        raise Refuse(f"объект-хозяин задаётся как «Справочник.Имя», получено «{obj}»")
    return ([(kind, name)],
            child_spec_from_json("Реквизит", dict(data.get("поля") or {})))

def path_from_json(text):
    """`Справочник.мой_Эталон.Реквизит.Комментарий` -> [("Справочник", "мой_Эталон"), …].

    Адрес читается парами «вид, имя» и уходит вглубь ровно так же, как устроена
    карточка: объект, его реквизит, реквизит его табличной части. Нечётное
    число частей — ошибка, а не повод угадать недостающую.
    """
    parts = [p for p in (text or "").split(".") if p]
    if len(parts) < 2 or len(parts) % 2:
        raise Refuse(
            f"адрес задаётся парами «Вид.Имя», получено «{text}». "
            "Примеры: «Справочник.мой_Эталон», "
            "«Справочник.мой_Эталон.Реквизит.Комментарий», "
            "«Документ.мой_Заявка.ТабличнаяЧасть.Строки.Реквизит.Сумма»")
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts), 2)]


#: Режимы правки поля-перечня в `changes`.
LIST_MODES = ("добавить", "убрать", "заменить")


def change_job_from_json(data):
    """{"путь": "…", "поля": {…}} -> (путь, поля) для сценария изменения."""
    from ..domain.kinds import REGISTRY
    path = path_from_json(item_of(data, "changes").get("путь"))
    поля = dict(data.get("поля") or {})
    kind = path[-1][0]
    перечни = {}
    for field in getattr(REGISTRY.get(kind), "object_lists", ()) or ():
        if field in поля:
            перечни[field] = list_edit_from_json(field, поля.pop(field))
    fields = dict(child_spec_from_json(kind, поля).fields) if поля else {}
    fields.update(перечни)
    if not fields:
        raise Refuse("в правке не указано ни одного поля")
    return path, fields


def list_edit_from_json(field, value):
    """Правка поля-перечня: {"добавить": […]}, {"убрать": […]} или {"заменить": […]}.

    Голый список — отказ: при правке он заменил бы перечень целиком, и всё,
    что в нём было, пропало бы без единого слова в ответе.
    """
    if not isinstance(value, dict):
        raise Refuse(
            f"«{field}» в правке задаётся явно: {{\"добавить\": […]}}, "
            f"{{\"убрать\": […]}} (можно вместе) или {{\"заменить\": […]}} — "
            "голый список заменил бы перечень целиком, и всё, что в нём было, "
            "пропало бы молча")
    лишние = sorted(set(value) - set(LIST_MODES))
    if лишние or not value:
        raise Refuse(f"«{field}»: ключи правки перечня — {', '.join(LIST_MODES)}; "
                      f"получено {', '.join(лишние) or 'пусто'}")
    if "заменить" in value and len(value) > 1:
        raise Refuse(f"«{field}»: «заменить» задаётся один, без «добавить» и «убрать»")
    разобрано = {}
    for ключ, что in value.items():
        if not isinstance(что, list):
            raise Refuse(f"«{field}.{ключ}» — список обозначений «Вид.Имя»")
        разобрано[ключ] = [designation_from_json(x) for x in что]
    return dm.ListEdit(разобрано.get("добавить", ()), разобрано.get("убрать", ()),
                       разобрано.get("заменить"))


def delete_job_from_json(data):
    """{"путь": "…"} -> адрес для сценария удаления.

    Краткая запись строкой тоже принимается: удалять — операция короткая,
    и городить объект ради одного поля незачем.
    """
    return path_from_json(data if isinstance(data, str) else item_of(data, "deletions").get("путь"))


def atomic_roles_job_from_json(data):
    """{"объект": "Документ.мой_X", "права": ["Просмотр"], "сокращение": "мой_Х"}
    -> (вид, имя, права, сокращение, комментарий).

    Краткая запись строкой тоже принимается: «Документ.мой_X» — обе роли.
    «сокращение» — короткое имя объекта для имён ролей, когда полное не
    укладывается в 80 символов (#std474 п. 2.3).
    """
    if isinstance(data, str):
        data = {"объект": data}
    объект = item_of(data, "atomic_roles").get("объект") or ""
    вид, _, имя = объект.partition(".")
    if not вид or not имя:
        raise Refuse(f"атомарные роли заводятся к объекту «Вид.Имя», получено «{объект}»")
    права = data.get("права")
    if права is not None and not isinstance(права, list):
        raise Refuse(f"«права» — список из Просмотр/Изменение, получено {права!r}")
    return вид, имя, права, data.get("сокращение"), data.get("комментарий")


def rename_job_from_json(data):
    """{"путь": "Справочник.Старое", "имя": "Новое"} -> (адрес, новое имя)."""
    new_name = item_of(data, "renames").get("имя")
    if not new_name:
        raise Refuse("в переименовании не указано новое имя (поле «имя»)")
    return path_from_json(data.get("путь")), new_name


def addition_job_from_json(data):
    """{"путь": "…", "вид": "Параметр", "поля": {…}} -> (адрес хозяина, спецификация).

    Адрес указывает **хозяина**, а не то, что добавляем: «куда», а не «что».
    Вид ребёнка называется отдельно — иначе адрес пришлось бы читать до конца,
    чтобы понять, существует ли уже последняя пара.
    """
    kind = item_of(data, "additions").get("вид")
    if not kind:
        raise Refuse("в добавлении не указан вид (поле «вид»)")
    return (path_from_json(data.get("путь")),
            child_spec_from_json(kind, data.get("поля") or {}))


# --- формы --------------------------------------------------------------------

FORM_KEYS = ("форма", "создать", "реквизиты", "команды", "элементы", "события",
             "удалить", "удалитьРеквизиты", "удалитьКоманды", "код")
CREATE_KEYS = ("назначение", "основная", "синоним", "заголовок")
CODE_TARGET_KEYS = ("модуль", "процедура")
FORM_ATTRIBUTE_KEYS = ("имя", "тип", "заголовок", "колонки", "таблица")
FORM_COMMAND_KEYS = ("имя", "заголовок", "обработчик")
FORM_ELEMENT_KEYS = ("вид", "имя", "путь", "родитель", "перед", "после", "свойства",
                     "обработчики", "команда", "элементы", "колонки")
FORM_COLUMN_KEYS = ("вид", "имя", "путь", "свойства", "обработчики")

PLATFORM_WORDS = ("ТаблицаЗначений", "ДеревоЗначений", "СписокЗначений",
                  "ХранилищеЗначения", "УникальныйИдентификатор",
                  "СтандартныйПериод", "СтандартнаяДатаНачала",
                  "ДинамическийСписок", "ТабличныйДокумент")
_TYPE_CALL = re.compile(r"^([A-Za-zА-Яа-яЁё]+)\s*(?:\(([^)]*)\))?$")


def value_type_from_text(text, where=None):
    """«Строка(200)», «Число(15,2)», «Дата», «Справочник.Номенклатура» -> тип.

    Краткая запись — как тип называет разработчик: `Строка(20)`, `Число(15,2)`.
    Ею же тип печатает просмотр, и её принимают
    оба задания — на формы и на метаданные. Составной тип — через «|».
    Строка и число требуют квалификатор в скобках: без него вышла бы строка
    нулевой длины или Число(10,0) — молча. Объектная запись (`{"вид": …}`)
    принимается тоже.
    """
    if not isinstance(text, str):
        return value_type_from_json(text)
    parts = [p.strip() for p in text.split("|") if p.strip()]
    prefix = f"{where}: " if where else ""
    if not parts:
        raise Refuse(prefix + "тип не задан")
    typed = [_one_type_from_text(p, prefix) for p in parts]
    return typed[0] if len(typed) == 1 else typed


_TYPE_REF = re.compile(r"^([A-Za-zА-Яа-яЁё]+)\.([\wЁё]+|\*)\s*(?:\(([A-Za-zА-Яа-яЁё]+)\))?$")


def _one_type_from_text(text, prefix):
    # Ссылка пишется так же, как её печатает просмотр: «Справочник.Имя»
    # (грань «Ссылка» подразумевается), «Документ.Имя (Объект)», весь вид —
    # «Справочник.*», виды без грани — «ОпределяемыйТип.Имя»,
    # «Характеристика.ИмяПВХ», «ЛюбаяСсылка».
    if text in dm.TypeRef.NAMELESS:
        return dm.TypeRef(text, None, None, is_set=dm.TypeRef.FACETLESS[text])
    if "." in text:
        ref = _TYPE_REF.match(text)
        if not ref:
            kind, _, name = text.partition(".")
            if not name:
                raise Refuse(prefix + f"у ссылочного типа «{text}» нет имени объекта")
            raise Refuse(prefix + f"не разбираю тип «{text}»; ссылка пишется "
                         "«Справочник.Имя», с гранью — «Документ.Имя (Объект)»")
        kind, name, facet = ref.groups()
        if kind in dm.TypeRef.FACETLESS:
            if facet or name == "*":
                raise Refuse(prefix + f"у «{kind}» нужно имя и не бывает грани: «{kind}.Имя»")
            return (dm.TypeRef.defined(name) if kind == "ОпределяемыйТип"
                    else dm.TypeRef(kind, name, None, is_set=dm.TypeRef.FACETLESS[kind]))
        if name == "*":
            return dm.TypeRef.of_kind(kind, facet or "Ссылка")
        return dm.TypeRef(kind, name, facet or "Ссылка")
    call = _TYPE_CALL.match(text)
    if not call:
        raise Refuse(prefix + f"не разбираю тип «{text}»")
    word = call.group(1)
    args = [a.strip() for a in (call.group(2) or "").split(",") if a.strip()]
    if word == "Строка":
        if not args or not args[0].isdigit():
            raise Refuse(prefix + "у строки нужна длина: Строка(200)")
        return dm.StringType(int(args[0]), "фиксированная" in args[1:])
    if word == "Число":
        if not args or not args[0].isdigit():
            raise Refuse(prefix + "у числа нужна разрядность: Число(15,2)")
        fraction = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        return dm.NumberType(int(args[0]), fraction, "неотрицательное" in args)
    if args and word not in ("Строка", "Число"):
        raise Refuse(prefix + f"у типа «{word}» не бывает скобок; состав даты — само "
                     "слово: Дата, ДатаВремя, Время")
    if word in dm.DateType.PARTS:
        return dm.DateType(word)
    if word == "Булево":
        return dm.BooleanType()
    if word == "Произвольный":
        return dm.AnyType()
    if word in PLATFORM_WORDS:
        return dm.PlatformType(word)
    raise Refuse(prefix + f"не знаю типа «{text}»; примитивы: Строка(N), Число(N,M), "
                 "Дата, ДатаВремя, Время, Булево; ссылка: Справочник.Имя, "
                 "ОпределяемыйТип.Имя; платформенные: " + ", ".join(PLATFORM_WORDS))


def form_edits_from_json(data):
    """Пункт «forms» -> правки формы словами домена.

    Слова — домена форм: вид элемента, родитель, «перед»/«после», путь
    к данным, свойства по русским именам платформы, обработчики, команды. Привязки здесь не разрешаются: что такое «Номер» —
    реквизит формы или хозяина — известно только рядом с самой формой.
    """
    if not isinstance(data, dict):
        raise Refuse(f"пункт «forms» — объект с ключом «форма», получено {data!r}")
    _check_keys(data, FORM_KEYS, "форма")
    owner, name = _form_address(data.get("форма"))
    create = None
    if data.get("создать"):
        said = data["создать"] if isinstance(data["создать"], dict) else {}
        _check_keys(said, CREATE_KEYS, "создать")
        create = fm.Form(name, owner, said.get("назначение"), said.get("синоним"),
                         bool(said.get("основная")), said.get("заголовок"))
    attributes = [_form_attribute(item) for item in data.get("реквизиты") or []]
    commands = [_form_command(item) for item in data.get("команды") or []]
    elements = [_form_element(item) for item in data.get("элементы") or []]
    events = {}
    for event, handler in (data.get("события") or {}).items():
        events[event] = event if handler is True else str(handler)
    # «код»: true — фрагмент кода формы; объектом — ещё и куда ляжет его
    # процедура: {«модуль»: «ОбщийМодуль.мой_X», «процедура»: «Имя»}.
    код = data.get("код")
    модуль = процедура = None
    if isinstance(код, dict):
        _check_keys(код, CODE_TARGET_KEYS, "код")
        модуль, процедура = код.get("модуль"), код.get("процедура")
    return fm.FormEdits(owner, name, create, attributes, commands, elements, events,
                        _names(data.get("удалить"), "удалить"),
                        _names(data.get("удалитьРеквизиты"), "удалитьРеквизиты"),
                        _names(data.get("удалитьКоманды"), "удалитьКоманды"),
                        bool(код), модуль, процедура)


def _form_parts(text):
    """Адрес формы -> ((вид, имя) или None у общей, имя формы); не форма — None.

    Объекты адресуются парами «вид, имя», и у них частей всегда чётное
    число; у формы — три, потому что имя формы стоит без своего слова. Так
    её пишут в заданиях, так же и спрашивают. Принимается и запись bsl-ls и
    заданий на код — «Вид.Имя.Форма.ИмяФормы[.Форма]», «ОбщаяФорма.Имя»:
    иначе одна форма звалась бы двумя адресами, и пришлось бы угадывать,
    какой куда.
    """
    parts = [p for p in (text or "").split(".") if p]
    if len(parts) == 2 and parts[0] in ("Общая", "ОбщаяФорма"):
        return None, parts[1]
    if len(parts) == 3:
        return (parts[0], parts[1]), parts[2]
    if len(parts) in (4, 5) and parts[2] == "Форма" and (len(parts) == 4 or parts[4] == "Форма"):
        return (parts[0], parts[1]), parts[3]
    return None


def looks_like_a_form(address):
    """Адрес формы, а не объекта (см. `_form_parts`)."""
    return _form_parts(address) is not None


def form_address(text):
    """«Документ.мой_Заявка.ФормаДокумента» -> ((вид, имя), имя формы)."""
    return _form_address(text)


def _form_address(text):
    found = _form_parts(text)
    if found is None:
        raise Refuse("форма адресуется как «Вид.Имя.ИмяФормы» (или «Вид.Имя.Форма.ИмяФормы», "
                     f"как у bsl-ls) или «Общая.ИмяФормы», получено «{text}»")
    return found


def _names(value, key):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Refuse(f"«{key}» — имя или список имён, получено {value!r}")
    return value


def _form_attribute(item):
    _check_keys(item, FORM_ATTRIBUTE_KEYS, "реквизит формы")
    name = item.get("имя")
    if not name:
        raise Refuse("у реквизита формы нет «имя»")
    if "тип" not in item:
        raise Refuse(f"у реквизита формы «{name}» не задан «тип»")
    value_type = value_type_from_text(item["тип"], f"реквизит «{name}»")
    columns = []
    for column in item.get("колонки") or []:
        column_name = column.get("имя")
        if not column_name or "тип" not in column:
            raise Refuse(f"у колонки реквизита «{name}» нужны «имя» и «тип»")
        columns.append(fm.FormAttribute(
            column_name, value_type_from_text(column["тип"], f"колонка «{column_name}»"),
            column.get("заголовок")))
    return fm.FormAttribute(name, value_type, item.get("заголовок"), columns,
                            table=item.get("таблица"))


def _form_command(item):
    _check_keys(item, FORM_COMMAND_KEYS, "команда")
    if not item.get("имя"):
        raise Refuse("у команды нет «имя»")
    return fm.FormCommand(item["имя"], item.get("заголовок"), item.get("обработчик"))


def _handlers(said, element_name):
    out = {}
    for event, handler in (said or {}).items():
        out[event] = f"{element_name}{event}" if handler is True else str(handler)
    return out


def _form_element(item, parent=None):
    _check_keys(item, FORM_ELEMENT_KEYS, "элемент")
    kind, name = item.get("вид"), item.get("имя")
    if not kind or not name:
        raise Refuse(f"у элемента нужны «вид» и «имя», получено {item!r}")
    children = [_form_element(child, name) for child in item.get("элементы") or []]
    if item.get("колонки"):
        if kind != "ТаблицаФормы":
            raise Refuse(f"«колонки» бывают только у таблицы, а «{name}» — {kind}")
        children += [_column_element(column, name, item.get("путь"))
                     for column in item["колонки"]]
    return fm.FormElement(kind, name, item.get("путь"), item.get("родитель", parent),
                          item.get("перед"), item.get("после"), item.get("свойства"),
                          _handlers(item.get("обработчики"), name), item.get("команда"),
                          children)


def _column_element(item, table_name, table_path):
    _check_keys(item, FORM_COLUMN_KEYS, "колонка")
    column = item.get("имя")
    if not column:
        raise Refuse(f"у колонки таблицы «{table_name}» нет «имя»")
    name = table_name + column
    element = fm.FormElement(item.get("вид", "ПолеВвода"), name, item.get("путь"), table_name,
                             properties=item.get("свойства"),
                             events=_handlers(item.get("обработчики"), name), column=column)
    element.kind_defaulted = "вид" not in item
    return element
