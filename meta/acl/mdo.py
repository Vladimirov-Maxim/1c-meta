"""Перекладка проекта EDT: карточка `.mdo` -> понятия домена.

Карточка EDT устроена проще карточки выгрузки: корень — `mdclass:<Вид>`,
свойства лежат прямо в нём элементами в нижнем верблюжьем регистре (`name`,
`synonym`), разделов `Properties`/`ChildObjects` нет, дети — элементы своего
рода (`attributes`, `tabularSections`…) с атрибутом `uuid`.

Тип записан так же, как в выгрузке, но без приставок пространств имён:
`<types>CatalogRef.Контрагенты</types>`, `<types>String</types>` с
`stringQualifiers`, набор (`DefinedType.X`, `Characteristic.X`) — тем же тегом
`types`, а не отдельным `TypeSet`. Слова типов платформы — английские имена
платформы без `v8:`. Таблицы корней и граней — общие с выгрузкой
(`mapping`): обозначение `CatalogRef.X` — то же, что `cfg:CatalogRef.X`.

Словарь снят с проекта EDT крупной типовой конфигурации (69 тыс. типов
реквизитов, измерений и ресурсов): квалификаторы — `length`, `fixed`,
`precision`, `scale`, `nonNegative`, `dateFractions`; состав даты по
умолчанию — дата и время (тега нет).
"""

from ..domain import model as dm
from ..domain.model import Refuse
from ..domain.plan import Composition
from .mapping import DATE_PARTS, PLATFORM_TYPES, READ_ONLY_TYPES_BACK, Node, parse_type_notation

#: Тег ребёнка в карточке EDT -> группа состава (те же группы, что у выгрузки).
CHILD_GROUPS = {
    "attributes": "реквизиты",
    "tabularSections": "табличныеЧасти",
    "dimensions": "измерения",
    "resources": "ресурсы",
    "enumValues": "значения",
}

#: Наборы типов: в выгрузке это `TypeSet`, в EDT — тот же `types`.
SETS = ("DefinedType", "Characteristic")

#: Слова EDT, которые расходятся со словами выгрузки.
EDT_WORDS = {"AnyRef": "AnyIBRef", "ValueList": "ValueListType"}

#: Слово платформы без приставки -> слово показа.
_PLATFORM_BACK = {value.rpartition(":")[2]: word for word, value in PLATFORM_TYPES.items()}


def _tag(tag):
    """Имя тега без пространства имён и приставки: `mdclass:Catalog` -> `Catalog`."""
    return tag.rpartition("}")[2].rpartition(":")[2]


def _by_tag(node):
    found = {}
    for child in node.children:
        found.setdefault(_tag(child.tag), child)
    return found


def kind_word(node):
    """Слово вида из корня карточки EDT: `mdclass:Catalog` -> `Catalog`."""
    return _tag(node.tag)


def name_of(node):
    """Имя объекта или ребёнка — текст `name`; нет — пустая строка."""
    field = _by_tag(node).get("name")
    return ((field.text if field is not None else "") or "").strip()


def type_of(node):
    """Узел `type` карточки EDT -> тип домена (или список типов)."""
    by_tag = [(_tag(c.tag), c) for c in node.children]
    qualifiers = {name: c for name, c in by_tag if name.endswith("Qualifiers")}
    collected = []
    for name, child in by_tag:
        if name != "types":
            continue
        text = EDT_WORDS.get((child.text or "").strip(), (child.text or "").strip())
        if not text:
            continue
        if text == "String":
            q = _by_tag(qualifiers.get("stringQualifiers", Node("x")))
            length = int(q["length"].text or "0") if "length" in q else 0
            collected.append(dm.StringType(length, "fixed" in q and q["fixed"].text == "true"))
        elif text == "Number":
            q = _by_tag(qualifiers.get("numberQualifiers", Node("x")))
            collected.append(dm.NumberType(
                int(q["precision"].text or "0") if "precision" in q else 10,
                int(q["scale"].text or "0") if "scale" in q else 0,
                "nonNegative" in q and q["nonNegative"].text == "true"))
        elif text == "Date":
            q = _by_tag(qualifiers.get("dateQualifiers", Node("x")))
            word = q["dateFractions"].text if "dateFractions" in q else "DateTime"
            backward = {v: k for k, v in DATE_PARTS.items()}
            collected.append(dm.DateType(backward.get(word, "ДатаВремя")))
        elif text == "Boolean":
            collected.append(dm.BooleanType())
        elif text in _PLATFORM_BACK:
            collected.append(dm.PlatformType(_PLATFORM_BACK[text]))
        elif text in READ_ONLY_TYPES_BACK:
            collected.append(dm.PlatformType(READ_ONLY_TYPES_BACK[text]))
        else:
            collected.append(_reference(text))
    if not collected:
        return dm.AnyType()
    return collected[0] if len(collected) == 1 else collected


def _reference(text):
    """`CatalogRef.X`, `DefinedType.X` -> ссылка домена; незнакомое — как записано.

    Чтение служит проверкам, и одно редкое обозначение не должно ронять сверку
    всего объекта."""
    dataset = text.split(".", 1)[0] in SETS
    try:
        return parse_type_notation(f"cfg:{text}", is_set=dataset)
    except Refuse:
        return dm.PlatformType(text)


def _predefined_items(node):
    """Элементы блока `predefined` — с элементами групп (`content`) на любой глубине."""
    for child in node.children:
        if _tag(child.tag) in ("items", "content", "childItems"):
            yield child
            yield from _predefined_items(child)


def composition_from_node(node):
    """Разобранная карточка EDT -> `domain.plan.Состав`: группы детей объекта
    с типами. Вложенное (реквизиты табличных частей) в состав не входит — так
    же, как у выгрузки."""
    # Предопределённые EDT держит в карточке — группа есть всегда, пусть и
    # пустая: её отсутствие значит «формат её не читает» (выгрузка).
    members = {"предопределенные": {}}
    for child in node.children:
        if _tag(child.tag) == "predefined":
            for element in _predefined_items(child):
                name = name_of(element)
                if name:
                    members["предопределенные"][name] = ()
            continue
        group = CHILD_GROUPS.get(_tag(child.tag))
        if group is None:
            continue
        name = name_of(child)
        if not name:
            continue
        by_tag = _by_tag(child)
        types = ()
        if "type" in by_tag:
            type_ = type_of(by_tag["type"])
            types = tuple(type_) if isinstance(type_, list) else (type_,)
        members.setdefault(group, {})[name] = types
    return Composition(members)
