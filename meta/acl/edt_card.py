"""Карточка выгрузки конфигуратора -> карточка проекта EDT.

Карточку выгрузки инструмент собирает давно и проверенно (`mapping`): каждое
её свойство названо и описано. Карточка EDT — тот же объект, записанный по
правилам EMF (`edt_model`): свойство называется так же, но с маленькой буквы,
равное умолчанию не пишется, порядок — порядок метамодели. Поэтому писатель
EDT не описывает объекты заново, а перекладывает карточку выгрузки:

    Properties/<Свойство>     -> <свойство> по виду свойства в метамодели:
                                 атрибут — текст, многоязычная строка — пары
                                 key/value, описание типов — types и
                                 квалификаторы, значение — xsi:type core:…Value,
                                 ссылка — текст, список ссылок — по элементу
    InternalInfo/GeneratedType -> producedTypes/<грань>Type typeId valueTypeId
    ChildObjects/<Вид>        -> <свойство-список>, тип которого — класс этого вида

Что правило не покрывает, перекладка называет (`problems`), а не теряет
молча: свойство без пары в метамодели, незнакомая запись типа или значения.
"""

from . import edt_model
from .mapping import Node

MDCLASS = "com._1c.g5.v8.dt.metadata.mdclass."
MCORE = "com._1c.g5.v8.dt.mcore."
LOCAL_STRING = MCORE + "LocalStringMapEntry"
TYPE_DESCRIPTION = MCORE + "TypeDescription"
VALUE = MCORE + "Value"

#: Свойство выгрузки -> имя свойства EDT там, где оно не «то же с маленькой буквы».
RENAMED = {}

#: Запись типа в выгрузке -> слово EDT.
PRIMITIVE_TYPES = {"xs:string": "String", "xs:decimal": "Number", "xs:boolean": "Boolean",
                   "xs:dateTime": "Date", "v8:ValueListType": "ValueList"}

#: Квалификатор выгрузки -> (свойство EDT, {поле выгрузки: поле EDT}).
QUALIFIERS = {
    "StringQualifiers": ("stringQualifiers", {"Length": "length", "AllowedLength": "fixed"}),
    "NumberQualifiers": ("numberQualifiers", {"Digits": "precision", "FractionDigits": "scale",
                                              "AllowedSign": "nonNegative"}),
    "DateQualifiers": ("dateQualifiers", {"DateFractions": "dateFractions"}),
    "BinaryDataQualifiers": ("binaryQualifiers", {"Length": "length", "AllowedLength": "fixed"}),
}
#: Значения квалификаторов, которые в EDT — булевы.
QUALIFIER_FLAGS = {"AllowedLength": "Fixed", "AllowedSign": "Nonnegative"}

#: `xsi:type` значения в выгрузке -> класс значения EDT.
VALUE_TYPES = {"xs:string": "StringValue", "xs:boolean": "BooleanValue", "xs:decimal": "NumberValue",
               "xs:dateTime": "DateValue"}


def feature_name(tag):
    """`UseStandardCommands` -> `useStandardCommands`."""
    return RENAMED.get(tag) or tag[:1].lower() + tag[1:]


class Translation:
    """Перекладка одной карточки: узел EDT и то, чего перекладка не умеет."""

    def __init__(self, satellite=None):
        #: (вид-тег выгрузки, имя) -> узел карточки спутника (форма, макет) или None
        self.satellite = satellite or (lambda tag, name: None)
        self.problems = []

    def problem(self, where, what):
        self.problems.append(f"{where}: {what}")

    # --- объект ---

    def card(self, root):
        """`MetaDataObject` выгрузки -> корень карточки EDT."""
        вид = root.children[0] if root.tag == "MetaDataObject" else root
        cls = MDCLASS + вид.tag
        if edt_model.features(cls) is None:
            self.problem(вид.tag, "вида нет в метамодели EDT")
        # атрибуты корня — все: у плана обмена кроме uuid есть и thisNode
        узел = Node(f"mdclass:{вид.tag}", attrs={"uuid": вид.attrs.get("uuid", ""),
                                                 **{k: v for k, v in вид.attrs.items() if k != "uuid"}})
        self.fill(узел, вид, cls, вид.tag)
        return узел

    def fill(self, target, source, cls, where):
        """Свойства и дети элемента выгрузки -> дети узла EDT в порядке метамодели."""
        собрано = []
        for часть in source.children:
            if часть.tag == "InternalInfo":
                собрано += self.produced_types(часть, cls, where)
            elif часть.tag == "Properties":
                for свойство in часть.children:
                    собрано += self.property(свойство, cls, where)
            elif часть.tag == "ChildObjects":
                for ребёнок in часть.children:
                    собрано += self.child(ребёнок, cls, where)
            else:
                self.problem(where, f"незнакомый раздел карточки «{часть.tag}»")
        собрано.sort(key=lambda пара: пара[0])           # сортировка устойчива: список — по порядку
        target.children.extend(узел for _, узел in собрано)

    # --- порождаемые типы ---

    def produced_types(self, info, cls, where):
        f = edt_model.feature(cls, "producedTypes")
        if f is None:
            if info.children:
                self.problem(where, "порождаемые типы есть, а свойства producedTypes у класса нет")
            return []
        узел = Node("producedTypes")
        собрано = []
        for gen in info.children:
            if gen.tag != "GeneratedType":
                continue
            имя = self._produced_name(gen.attrs.get("category", ""), f.type)
            if имя is None:
                self.problem(where, f"порождаемый тип «{gen.attrs.get('category')}» не найден в {f.type}")
                continue
            поля = {c.tag: c.text or "" for c in gen.children}
            собрано.append((edt_model.position(f.type, имя),
                            Node(имя, attrs={"typeId": поля.get("TypeId", ""),
                                             "valueTypeId": поля.get("ValueId", "")})))
        собрано.sort(key=lambda пара: пара[0])
        узел.children = [n for _, n in собрано]
        return [(edt_model.position(cls, "producedTypes"), узел)]

    @staticmethod
    def _produced_name(category, types_cls):
        if category.startswith("@"):                   # имя свойства, перенесённое обратной перекладкой
            кандидаты = {category[1:]}
        else:
            кандидаты = {category[:1].lower() + category[1:] + "Type",
                         {"TabularSection": "objectType", "TabularSectionRow": "rowType",
                          "DefinedType": "containerType", "Characteristic": "containerType"}.get(category, "")}
        for f in edt_model.features(types_cls) or ():
            if f.name in кандидаты:
                return f.name
        return None

    # --- свойства ---

    def property(self, свойство, cls, where):
        if свойство.tag == RAW:                        # прошло переходник насквозь
            место = edt_model.position(cls, свойство.attrs.get("feature", ""))
            return [(место, restore_raw(n)) for n in свойство.children]
        имя = feature_name(свойство.tag)
        f = edt_model.feature(cls, имя)
        if f is None:
            if self._empty(свойство):
                return []                              # пустое свойство, которого у EDT нет, — не потеря
            self.problem(where, f"свойства «{свойство.tag}» нет у {cls.rsplit('.', 1)[-1]}")
            return []
        место = edt_model.position(cls, имя)
        return [(место, n) for n in self.value_nodes(свойство, f, cls, f"{where}.{свойство.tag}")]

    @staticmethod
    def _empty(свойство):
        return not свойство.children and not (свойство.text or "").strip()

    def value_nodes(self, свойство, f, cls, where):
        """Свойство выгрузки -> узлы EDT свойства `f` (пусто — не пишется)."""
        if f.kind == "contains" and f.type == LOCAL_STRING:
            return [Node(f.name, children=[Node("key", text=item_part(i, "lang")),
                                           Node("value", text=item_part(i, "content"))])
                    for i in свойство.children if i.tag == "item"]
        if f.kind == "contains" and f.type == TYPE_DESCRIPTION:
            return [self.type_description(свойство, f.name, where)]
        if f.kind == "contains" and f.type == VALUE:
            узел = self.value(свойство, f.name, where)
            return [узел] if узел is not None else []
        if f.kind == "refers":
            if f.many:
                return [Node(f.name, text=c.text or "") for c in свойство.children if c.text]
            return [Node(f.name, text=свойство.text)] if свойство.text else []
        if f.kind == "attribute":
            if f.many:
                return [Node(f.name, text=c.text or "") for c in свойство.children]
            if свойство.children:
                self.problem(where, "у атрибута вложенные элементы")
                return []
            текст = свойство.text or ""
            if текст == "" or edt_model.is_default(f, текст, cls):
                return []
            return [Node(f.name, text=текст)]
        if self._empty(свойство):
            return []
        if f.type == MCORE + "Color" and свойство.text == "auto" and not свойство.children:
            return []                                  # цвет по умолчанию: EDT его не пишет
        self.problem(where, f"вложенный объект {f.type.rsplit('.', 1)[-1]} не перекладывается")
        return []

    # --- тип и значение ---

    def type_description(self, свойство, name, where):
        узел = Node(name)
        типы, квалификаторы = [], []
        for c in свойство.children:
            if c.tag in ("Type", "TypeSet"):
                слово = edt_type_word(c.text or "")
                if слово is None:
                    self.problem(where, f"незнакомая запись типа «{c.text}»")
                    continue
                типы.append(Node("types", text=слово))
            elif c.tag in QUALIFIERS:
                имя_q, поля = QUALIFIERS[c.tag]
                q = Node(имя_q)
                класс_q = edt_model.feature(TYPE_DESCRIPTION, имя_q).type
                for поле in c.children:
                    имя_п = поля.get(поле.tag)
                    if имя_п is None:
                        self.problem(where, f"незнакомое поле квалификатора «{поле.tag}»")
                        continue
                    текст = поле.text or ""
                    if поле.tag in QUALIFIER_FLAGS:
                        текст = "true" if текст == QUALIFIER_FLAGS[поле.tag] else "false"
                    fq = edt_model.feature(класс_q, имя_п)
                    if not edt_model.is_default(fq, текст, класс_q):
                        q.children.append((edt_model.position(класс_q, имя_п), Node(имя_п, text=текст)))
                q.children = [n for _, n in sorted(q.children, key=lambda пара: пара[0])]
                квалификаторы.append((edt_model.position(TYPE_DESCRIPTION, имя_q), q))
            else:
                self.problem(where, f"незнакомая часть описания типа «{c.tag}»")
        узел.children = типы + [q for _, q in sorted(квалификаторы, key=lambda пара: пара[0])]
        return узел

    def value(self, свойство, name, where):
        if свойство.attrs.get("nil") == "true":
            return Node(name, attrs={"xsi:type": "core:UndefinedValue"})
        тип = свойство.attrs.get("type")
        класс = VALUE_TYPES.get(тип)
        if класс is None:
            if тип is None and not свойство.text:
                return None
            self.problem(where, f"незнакомое значение типа «{тип}»")
            return None
        узел = Node(name, attrs={"xsi:type": f"core:{класс}"})
        текст = свойство.text or ""
        f = edt_model.feature(MCORE + класс, "value")
        if текст and not edt_model.is_default(f, текст, MCORE + класс):
            узел.children.append(Node("value", text=текст))
        return узел

    # --- дети ---

    def child(self, ребёнок, cls, where):
        if cls == CONFIGURATION and not ребёнок.children and ребёнок.text:
            f = registry_feature(ребёнок.tag)          # запись реестра: <catalogs>Catalog.X</catalogs>
            if f is None:
                self.problem(where, f"в реестре EDT нет списка для вида «{ребёнок.tag}»")
                return []
            return [(edt_model.position(cls, f.name), Node(f.name, text=f"{ребёнок.tag}.{ребёнок.text}"))]
        f = child_feature(cls, ребёнок.tag)
        if f is None:
            self.problem(where, f"ребёнка вида «{ребёнок.tag}» нет у {cls.rsplit('.', 1)[-1]}")
            return []
        место = edt_model.position(cls, f.name)
        if not ребёнок.children and ребёнок.text:     # форма, макет, подсистема: имя, карточка — спутник
            спутник = self.satellite(ребёнок.tag, ребёнок.text)
            if спутник is None:
                self.problem(where, f"{ребёнок.tag} «{ребёнок.text}»: карточки спутника нет")
                return []
            ребёнок = спутник.children[0] if спутник.tag == "MetaDataObject" else спутник
        узел = Node(f.name, attrs={"uuid": ребёнок.attrs.get("uuid", "")})
        self.fill(узел, ребёнок, f.type, f"{where}.{ребёнок.tag}")
        return [(место, узел)]


#: Свойство-переходник: часть карточки EDT, у которой в карточке выгрузки нет
#: пары или которую перекладка не понимает. Лежит в дереве выгрузки нетронутой
#: и возвращается в карточку EDT как была.
RAW = "EdtRaw"
#: Текст узла внутри переходника — атрибутом, а не текстом элемента: дерево
#: выгрузки обрезает пробелы по краям текста и не отличает `<x></x>` от `<x/>`,
#: а значение атрибута доходит как было.
RAW_TEXT = "edtText"


def raw(feature, nodes):
    """Узлы EDT свойства `feature` -> свойство-переходник выгрузки."""
    def снять(n):
        attrs = dict(n.attrs)
        if n.text is not None and not n.children:
            attrs[RAW_TEXT] = n.text
        return Node(n.tag, attrs=attrs, children=[снять(c) for c in n.children])
    return Node(RAW, attrs={"feature": feature}, children=[снять(n) for n in nodes])


def restore_raw(n):
    """Узел из переходника -> узел EDT: текст и приставка `xsi:type` — как были
    (дерево выгрузки приставки атрибутов снимает)."""
    attrs = {}
    for ключ, значение in n.attrs.items():
        if ключ == RAW_TEXT:
            continue
        if ключ == "type" and ":" in значение:
            ключ = "xsi:type"
        attrs[ключ] = значение
    return Node(n.tag, text=n.attrs.get(RAW_TEXT), attrs=attrs, children=[restore_raw(c) for c in n.children])


def plain(text):
    """Текст переживает дерево выгрузки: не пустой и без пробелов по краям."""
    return bool(text) and text == text.strip()


CONFIGURATION = MDCLASS + "Configuration"


def registry_features():
    """Списки объектов в реестре EDT — свойства конфигурации после `languages`:
    `subsystems`, `roles`, …, `catalogs`, …, каждое — ссылки «Вид.Имя»."""
    свойства = edt_model.features(CONFIGURATION)
    начало = [f.name for f in свойства].index("languages") + 1
    return tuple(f for f in свойства[начало:] if f.kind == "refers" and f.many)


def registry_feature(tag):
    """Список реестра EDT для вида реестра выгрузки (`Catalog` -> `catalogs`)."""
    for f in registry_features():
        if f.type.rsplit(".", 1)[-1] == tag:
            return f
    return None


def item_part(item, tag):
    for c in item.children:
        if c.tag == tag:
            return c.text or ""
    return ""


def edt_type_word(text):
    """Запись типа выгрузки -> слово EDT; незнакомая — None."""
    if text in PRIMITIVE_TYPES:
        return PRIMITIVE_TYPES[text]
    приставка, _, слово = text.partition(":")
    if приставка in ("cfg", "v8") and слово:
        return слово
    return None


def child_feature(cls, tag):
    """Свойство-список класса, в котором живут дети вида `tag` выгрузки
    (`Attribute` -> `attributes` с типом `CatalogAttribute`): прежде всего —
    по имени (вид во множественном числе), иначе из кандидатов, тип которых
    кончается видом, — с самым коротким типом. По одному типу выбирать нельзя:
    `standardAttributes` (тип `StandardAttribute`) короче `attributes`."""
    свойства = [f for f in edt_model.features(cls) or () if f.kind == "contains" and f.many]
    по_имени = feature_name(tag) + "s"
    for f in свойства:
        if f.name == по_имени:
            return f
    кандидаты = [f for f in свойства if f.type.rsplit(".", 1)[-1].endswith(tag)]
    if not кандидаты:
        return None
    return min(кандидаты, key=lambda f: len(f.type.rsplit(".", 1)[-1]))


# --- обратная перекладка ------------------------------------------------------------------


#: Слово EDT -> запись типа выгрузки (обратное `PRIMITIVE_TYPES`).
PRIMITIVE_BACK = {слово: запись for запись, слово in PRIMITIVE_TYPES.items()}
#: Поле квалификатора EDT -> поле выгрузки; булевы — словом выгрузки.
QUALIFIERS_BACK = {имя_q: (тег, {edt: выгр for выгр, edt in поля.items()})
                   for тег, (имя_q, поля) in QUALIFIERS.items()}
FLAGS_BACK = {"fixed": ("Fixed", "Variable"), "nonNegative": ("Nonnegative", "Any")}
VALUE_BACK = {класс: тип for тип, класс in VALUE_TYPES.items()}


def is_md_object(cls):
    """Класс — объект метаданных (у него есть имя и uuid): такие дети живут в
    `ChildObjects` выгрузки, остальное — свойства."""
    виденные, очередь = set(), [cls]
    while очередь:
        c = очередь.pop()
        if c == MDCLASS + "MdObject":
            return True
        if c in виденные:
            continue
        виденные.add(c)
        очередь += edt_model.classes().get(c, {}).get("supers", [])
    return False


def designer_tag(feature):
    """`useStandardCommands` -> `UseStandardCommands`."""
    return feature[:1].upper() + feature[1:]


class Reverse:
    """Карточка EDT -> дерево в форме карточки выгрузки, такое, что прямая
    перекладка (`Translation`) возвращает ту же карточку EDT байт в байт.

    Дерево не обязано быть карточкой, которую принял бы конфигуратор: оно
    нужно площадке, чтобы читать и править объект теми же средствами, что и
    выгрузку. Что выгрузка выразить не может (пустая строка, вложенные
    объекты, которых перекладка не знает), проходит переходником `RAW`.
    """

    def card(self, root):
        cls = edt_model.class_of("http://g5.1c.ru/v8/dt/metadata/mdclass", root.tag.partition(":")[2])
        вид = self.element(root, cls, root.tag.partition(":")[2])
        return Node("MetaDataObject", children=[вид])

    def element(self, node, cls, tag):
        info, props, children = Node("InternalInfo"), Node("Properties"), Node("ChildObjects")
        ещё = []
        группы = []
        for ребёнок in node.children:
            if группы and группы[-1][0] == ребёнок.tag:
                группы[-1][1].append(ребёнок)
            else:
                группы.append((ребёнок.tag, [ребёнок]))
        for имя, узлы in группы:
            f = edt_model.feature(cls, имя)
            if f is None:
                props.children.append(raw(имя, узлы))
            elif имя == "producedTypes":
                info.children += self.produced(узлы[0], cls)
            elif f.kind == "contains" and f.many and is_md_object(f.type):
                for n in узлы:
                    children.children.append(self.element(n, f.type, designer_tag(имя[:-1])))
            elif cls == CONFIGURATION and f in registry_features() and self.registry_entries(f, узлы):
                children.children += self.registry_entries(f, узлы)
            else:
                props.children += self.property(f, узлы)
        attrs = {k: v for k, v in node.attrs.items() if not k.startswith("xmlns:")}
        части = [p for p in (info, props, children) if p.children or p is props] + ещё
        return Node(tag, attrs=attrs, children=части)

    @staticmethod
    def registry_entries(f, узлы):
        """`<catalogs>Catalog.X</catalogs>` -> `<Catalog>X</Catalog>` реестра выгрузки;
        запись не того вида — None (свойство пойдёт переходником)."""
        вид = f.type.rsplit(".", 1)[-1]
        записи = []
        for n in узлы:
            текст = n.text or ""
            if n.children or n.attrs or not текст.startswith(вид + ".") or not plain(текст):
                return None
            записи.append(Node(вид, text=текст[len(вид) + 1:]))
        return записи

    @staticmethod
    def produced(узел, cls):
        return [Node("GeneratedType", attrs={"name": "", "category": designer_tag(n.tag[:-4])
                                             if n.tag.endswith("Type") else "@" + n.tag},
                     children=[Node("TypeId", text=n.attrs.get("typeId", "")),
                               Node("ValueId", text=n.attrs.get("valueTypeId", ""))])
                for n in узел.children]

    def property(self, f, узлы):
        тег = designer_tag(f.name)
        if f.kind == "contains" and f.type == LOCAL_STRING:
            items = []
            for n in узлы:
                поля = {c.tag: c for c in n.children}
                if set(поля) != {"key", "value"} or any(c.children for c in n.children)                         or any(c.text and not plain(c.text) for c in n.children):
                    return [raw(f.name, узлы)]
                items.append(Node("item", children=[Node("lang", text=поля["key"].text or ""),
                                                    Node("content", text=поля["value"].text or "")]))
            return [Node(тег, children=items)]
        if f.kind == "contains" and f.type == TYPE_DESCRIPTION and len(узлы) == 1:
            тип = self.type_description(узлы[0], тег)
            return [тип] if тип is not None else [raw(f.name, узлы)]
        if f.kind == "contains" and f.type == VALUE and len(узлы) == 1:
            значение = self.value(узлы[0], тег)
            return [значение] if значение is not None else [raw(f.name, узлы)]
        if f.kind in ("refers", "attribute"):
            if any(n.children or n.attrs or not plain(n.text) for n in узлы):
                return [raw(f.name, узлы)]
            if f.many:
                return [Node(тег, children=[Node("Item", text=n.text) for n in узлы])]
            if len(узлы) == 1:
                return [Node(тег, text=узлы[0].text)]
        return [raw(f.name, узлы)]

    def type_description(self, узел, тег):
        дети = []
        for n in узел.children:
            if n.tag == "types":
                слово = n.text or ""
                if слово in PRIMITIVE_BACK:
                    дети.append(Node("Type", text=PRIMITIVE_BACK[слово]))
                elif "." in слово or слово in ("AnyRef",):
                    набор = слово.split(".", 1)[0] in ("DefinedType", "Characteristic")
                    дети.append(Node("TypeSet" if набор else "Type", text="cfg:" + слово))
                else:
                    дети.append(Node("Type", text="v8:" + слово))
            elif n.tag in QUALIFIERS_BACK:
                тег_q, поля = QUALIFIERS_BACK[n.tag]
                q = Node(тег_q)
                for поле in n.children:
                    if поле.tag not in поля or поле.children:
                        return None
                    текст = поле.text or ""
                    if поле.tag in FLAGS_BACK:
                        текст = FLAGS_BACK[поле.tag][0] if текст == "true" else FLAGS_BACK[поле.tag][1]
                    q.children.append(Node(поля[поле.tag], text=текст))
                дети.append(q)
            else:
                return None
        return Node(тег, children=дети)

    @staticmethod
    def value(узел, тег):
        класс = узел.attrs.get("xsi:type", "").partition(":")[2]
        if класс == "UndefinedValue" and not узел.children:
            return Node(тег, attrs={"nil": "true"})
        тип = VALUE_BACK.get(класс)
        if тип is None:
            return None
        значение = [c for c in узел.children if c.tag == "value"]
        if len(значение) != len(узел.children) or len(значение) > 1:
            return None
        текст = значение[0].text if значение else None
        if значение and not plain(текст):
            return None                                # пустая строка, края пробелами — переходником
        return Node(тег, text=текст, attrs={"type": тип})
