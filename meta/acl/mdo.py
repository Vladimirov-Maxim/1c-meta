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
from ..domain.plan import Состав
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
_PLATFORM_BACK = {значение.rpartition(":")[2]: слово for слово, значение in PLATFORM_TYPES.items()}


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
    поле = _by_tag(node).get("name")
    return ((поле.text if поле is not None else "") or "").strip()


def type_of(node):
    """Узел `type` карточки EDT -> тип домена (или список типов)."""
    по_тегам = [(_tag(c.tag), c) for c in node.children]
    квалификаторы = {имя: c for имя, c in по_тегам if имя.endswith("Qualifiers")}
    собрано = []
    for имя, узел in по_тегам:
        if имя != "types":
            continue
        текст = EDT_WORDS.get((узел.text or "").strip(), (узел.text or "").strip())
        if not текст:
            continue
        if текст == "String":
            q = _by_tag(квалификаторы.get("stringQualifiers", Node("x")))
            длина = int(q["length"].text or "0") if "length" in q else 0
            собрано.append(dm.StringType(длина, "fixed" in q and q["fixed"].text == "true"))
        elif текст == "Number":
            q = _by_tag(квалификаторы.get("numberQualifiers", Node("x")))
            собрано.append(dm.NumberType(
                int(q["precision"].text or "0") if "precision" in q else 10,
                int(q["scale"].text or "0") if "scale" in q else 0,
                "nonNegative" in q and q["nonNegative"].text == "true"))
        elif текст == "Date":
            q = _by_tag(квалификаторы.get("dateQualifiers", Node("x")))
            слово = q["dateFractions"].text if "dateFractions" in q else "DateTime"
            назад = {v: k for k, v in DATE_PARTS.items()}
            собрано.append(dm.DateType(назад.get(слово, "ДатаВремя")))
        elif текст == "Boolean":
            собрано.append(dm.BooleanType())
        elif текст in _PLATFORM_BACK:
            собрано.append(dm.PlatformType(_PLATFORM_BACK[текст]))
        elif текст in READ_ONLY_TYPES_BACK:
            собрано.append(dm.PlatformType(READ_ONLY_TYPES_BACK[текст]))
        else:
            собрано.append(_reference(текст))
    if not собрано:
        return dm.AnyType()
    return собрано[0] if len(собрано) == 1 else собрано


def _reference(текст):
    """`CatalogRef.X`, `DefinedType.X` -> ссылка домена; незнакомое — как записано.

    Чтение служит проверкам, и одно редкое обозначение не должно ронять сверку
    всего объекта."""
    набор = текст.split(".", 1)[0] in SETS
    try:
        return parse_type_notation(f"cfg:{текст}", is_set=набор)
    except Refuse:
        return dm.PlatformType(текст)


def composition_from_node(node):
    """Разобранная карточка EDT -> `domain.plan.Состав`: группы детей объекта
    с типами. Вложенное (реквизиты табличных частей) в состав не входит — так
    же, как у выгрузки."""
    члены = {}
    for ребёнок in node.children:
        группа = CHILD_GROUPS.get(_tag(ребёнок.tag))
        if группа is None:
            continue
        имя = name_of(ребёнок)
        if not имя:
            continue
        по_тегам = _by_tag(ребёнок)
        типы = ()
        if "type" in по_тегам:
            тип = type_of(по_тегам["type"])
            типы = tuple(тип) if isinstance(тип, list) else (тип,)
        члены.setdefault(группа, {})[имя] = типы
    return Состав(члены)
