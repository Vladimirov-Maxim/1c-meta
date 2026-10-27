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


#: Литералы перечислений, которые выгрузка и EDT называют по-разному: тип
#: свойства EDT -> {слово выгрузки: литерал EDT}.
ENUM_WORDS = {
    "com._1c.g5.v8.dt.metadata.common.ApplicationUsePurpose": {
        "PlatformApplication": "PersonalComputer", "MobilePlatformApplication": "MobileDevice"},
}
ENUM_WORDS_BACK = {type_: {edt: выгр for выгр, edt in слова.items()} for type_, слова in ENUM_WORDS.items()}


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
        kind = root.children[0] if root.tag == "MetaDataObject" else root
        cls = MDCLASS + kind.tag
        if edt_model.features(cls) is None:
            self.problem(kind.tag, "вида нет в метамодели EDT")
        # атрибуты корня — все: у плана обмена кроме uuid есть и thisNode
        узел = Node(f"mdclass:{kind.tag}", attrs={"uuid": kind.attrs.get("uuid", ""),
                                                 **{k: v for k, v in kind.attrs.items() if k != "uuid"}})
        self.fill(узел, kind, cls, kind.tag)
        return узел

    def fill(self, target, source, cls, where):
        """Свойства и дети элемента выгрузки -> дети узла EDT в порядке метамодели."""
        собрано = []
        for part in source.children:
            if part.tag == "InternalInfo":
                собрано += self.produced_types(part, cls, where)
            elif part.tag == "Properties":
                for свойство in part.children:
                    собрано += self.property(свойство, cls, where)
            elif part.tag == "ChildObjects":
                for ребёнок in part.children:
                    собрано += self.child(ребёнок, cls, where)
            else:
                self.problem(where, f"незнакомый раздел карточки «{part.tag}»")
        собрано.sort(key=lambda pair: pair[0])           # сортировка устойчива: список — по порядку
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
            name = self._produced_name(gen.attrs.get("category", ""), f.type)
            if name is None:
                self.problem(where, f"порождаемый тип «{gen.attrs.get('category')}» не найден в {f.type}")
                continue
            fields = {c.tag: c.text or "" for c in gen.children}
            собрано.append((edt_model.position(f.type, name),
                            Node(name, attrs={"typeId": fields.get("TypeId", ""),
                                             "valueTypeId": fields.get("ValueId", "")})))
        собрано.sort(key=lambda pair: pair[0])
        узел.children = [n for _, n in собрано]
        return [(edt_model.position(cls, "producedTypes"), узел)]

    @staticmethod
    def _produced_name(category, types_cls):
        if category.startswith("@"):                   # имя свойства, перенесённое обратной перекладкой
            candidates = {category[1:]}
        else:
            candidates = {category[:1].lower() + category[1:] + "Type",
                         {"TabularSection": "objectType", "TabularSectionRow": "rowType",
                          "DefinedType": "containerType", "Characteristic": "containerType"}.get(category, "")}
        for f in edt_model.features(types_cls) or ():
            if f.name in candidates:
                return f.name
        return None

    # --- свойства ---

    def property(self, свойство, cls, where):
        if свойство.tag == RAW:                        # прошло переходник насквозь
            place = edt_model.position(cls, свойство.attrs.get("feature", ""))
            return [(place, restore_raw(n)) for n in свойство.children]
        name = feature_name(свойство.tag)
        f = edt_model.feature(cls, name)
        if f is None:
            if self._empty(свойство):
                return []                              # пустое свойство, которого у EDT нет, — не потеря
            self.problem(where, f"свойства «{свойство.tag}» нет у {cls.rsplit('.', 1)[-1]}")
            return []
        place = edt_model.position(cls, name)
        return [(place, n) for n in self.value_nodes(свойство, f, cls, f"{where}.{свойство.tag}")]

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
            слова = ENUM_WORDS.get(f.type, {})
            if f.many:
                return [Node(f.name, text=слова.get(c.text or "", c.text or "")) for c in свойство.children]
            if свойство.children:
                self.problem(where, "у атрибута вложенные элементы")
                return []
            text = слова.get(свойство.text or "", свойство.text or "")
            if text == "" or edt_model.is_default(f, text, cls):
                return []
            return [Node(f.name, text=text)]
        if self._empty(свойство):
            return []
        if f.type == MCORE + "Color" and свойство.text == "auto" and not свойство.children:
            return []                                  # цвет по умолчанию: EDT его не пишет
        self.problem(where, f"вложенный объект {f.type.rsplit('.', 1)[-1]} не перекладывается")
        return []

    # --- тип и значение ---

    def type_description(self, свойство, name, where):
        узел = Node(name)
        types, квалификаторы = [], []
        for c in свойство.children:
            if c.tag in ("Type", "TypeSet"):
                word = edt_type_word(c.text or "")
                if word is None:
                    self.problem(where, f"незнакомая запись типа «{c.text}»")
                    continue
                types.append(Node("types", text=word))
            elif c.tag in QUALIFIERS:
                имя_q, fields = QUALIFIERS[c.tag]
                q = Node(имя_q)
                класс_q = edt_model.feature(TYPE_DESCRIPTION, имя_q).type
                for field in c.children:
                    имя_п = fields.get(field.tag)
                    if имя_п is None:
                        self.problem(where, f"незнакомое поле квалификатора «{field.tag}»")
                        continue
                    text = field.text or ""
                    if field.tag in QUALIFIER_FLAGS:
                        text = "true" if text == QUALIFIER_FLAGS[field.tag] else "false"
                    fq = edt_model.feature(класс_q, имя_п)
                    if not edt_model.is_default(fq, text, класс_q):
                        q.children.append((edt_model.position(класс_q, имя_п), Node(имя_п, text=text)))
                q.children = [n for _, n in sorted(q.children, key=lambda pair: pair[0])]
                квалификаторы.append((edt_model.position(TYPE_DESCRIPTION, имя_q), q))
            else:
                self.problem(where, f"незнакомая часть описания типа «{c.tag}»")
        узел.children = types + [q for _, q in sorted(квалификаторы, key=lambda pair: pair[0])]
        return узел

    def value(self, свойство, name, where):
        if свойство.attrs.get("nil") == "true":
            return Node(name, attrs={"xsi:type": "core:UndefinedValue"})
        type_ = свойство.attrs.get("type")
        класс = VALUE_TYPES.get(type_)
        if класс is None:
            if type_ is None and not свойство.text:
                return None
            self.problem(where, f"незнакомое значение типа «{type_}»")
            return None
        узел = Node(name, attrs={"xsi:type": f"core:{класс}"})
        text = свойство.text or ""
        f = edt_model.feature(MCORE + класс, "value")
        if text and not edt_model.is_default(f, text, MCORE + класс):
            узел.children.append(Node("value", text=text))
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
        place = edt_model.position(cls, f.name)
        if not ребёнок.children and ребёнок.text:     # форма, макет, подсистема: имя, карточка — спутник
            спутник = self.satellite(ребёнок.tag, ребёнок.text)
            if спутник is None:
                self.problem(where, f"{ребёнок.tag} «{ребёнок.text}»: карточки спутника нет")
                return []
            ребёнок = спутник.children[0] if спутник.tag == "MetaDataObject" else спутник
        узел = Node(f.name, attrs={"uuid": ребёнок.attrs.get("uuid", "")})
        self.fill(узел, ребёнок, f.type, f"{where}.{ребёнок.tag}")
        return [(place, узел)]


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
    for key, value in n.attrs.items():
        if key == RAW_TEXT:
            continue
        if key == "type" and ":" in value:
            key = "xsi:type"
        attrs[key] = value
    return Node(n.tag, text=n.attrs.get(RAW_TEXT), attrs=attrs, children=[restore_raw(c) for c in n.children])


def plain(text):
    """Текст переживает дерево выгрузки: не пустой и без пробелов по краям."""
    return bool(text) and text == text.strip()


CONFIGURATION = MDCLASS + "Configuration"


def registry_features():
    """Списки объектов в реестре EDT — свойства конфигурации после `languages`:
    `subsystems`, `roles`, …, `catalogs`, …, каждое — ссылки «Вид.Имя»."""
    свойства = edt_model.features(CONFIGURATION)
    start = [f.name for f in свойства].index("languages") + 1
    return tuple(f for f in свойства[start:] if f.kind == "refers" and f.many)


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
    prefix, _, word = text.partition(":")
    if prefix in ("cfg", "v8") and word:
        return word
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
    candidates = [f for f in свойства if f.type.rsplit(".", 1)[-1].endswith(tag)]
    if not candidates:
        return None
    return min(candidates, key=lambda f: len(f.type.rsplit(".", 1)[-1]))


# --- обратная перекладка ------------------------------------------------------------------


#: Слово EDT -> запись типа выгрузки (обратное `PRIMITIVE_TYPES`).
PRIMITIVE_BACK = {word: запись for запись, word in PRIMITIVE_TYPES.items()}
#: Поле квалификатора EDT -> поле выгрузки; булевы — словом выгрузки.
QUALIFIERS_BACK = {имя_q: (тег, {edt: выгр for выгр, edt in fields.items()})
                   for тег, (имя_q, fields) in QUALIFIERS.items()}
FLAGS_BACK = {"fixed": ("Fixed", "Variable"), "nonNegative": ("Nonnegative", "Any")}
VALUE_BACK = {класс: type_ for type_, класс in VALUE_TYPES.items()}


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
        kind = self.element(root, cls, root.tag.partition(":")[2])
        return Node("MetaDataObject", children=[kind])

    def element(self, node, cls, tag):
        info, props, children = Node("InternalInfo"), Node("Properties"), Node("ChildObjects")
        more = []
        groups = []
        for ребёнок in node.children:
            if groups and groups[-1][0] == ребёнок.tag:
                groups[-1][1].append(ребёнок)
            else:
                groups.append((ребёнок.tag, [ребёнок]))
        for name, узлы in groups:
            f = edt_model.feature(cls, name)
            if f is None:
                props.children.append(raw(name, узлы))
            elif name == "producedTypes":
                info.children += self.produced(узлы[0], cls)
            elif f.kind == "contains" and f.many and is_md_object(f.type):
                for n in узлы:
                    children.children.append(self.element(n, f.type, designer_tag(name[:-1])))
            elif cls == CONFIGURATION and f in registry_features() and self.registry_entries(f, узлы):
                children.children += self.registry_entries(f, узлы)
            else:
                props.children += self.property(f, узлы)
        attrs = {k: v for k, v in node.attrs.items() if not k.startswith("xmlns:")}
        parts = [p for p in (info, props, children) if p.children or p is props] + more
        return Node(tag, attrs=attrs, children=parts)

    @staticmethod
    def registry_entries(f, узлы):
        """`<catalogs>Catalog.X</catalogs>` -> `<Catalog>X</Catalog>` реестра выгрузки;
        запись не того вида — None (свойство пойдёт переходником)."""
        kind = f.type.rsplit(".", 1)[-1]
        записи = []
        for n in узлы:
            text = n.text or ""
            if n.children or n.attrs or not text.startswith(kind + ".") or not plain(text):
                return None
            записи.append(Node(kind, text=text[len(kind) + 1:]))
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
                fields = {c.tag: c for c in n.children}
                if set(fields) != {"key", "value"} or any(c.children for c in n.children)                         or any(c.text and not plain(c.text) for c in n.children):
                    return [raw(f.name, узлы)]
                items.append(Node("item", children=[Node("lang", text=fields["key"].text or ""),
                                                    Node("content", text=fields["value"].text or "")]))
            return [Node(тег, children=items)]
        if f.kind == "contains" and f.type == TYPE_DESCRIPTION and len(узлы) == 1:
            type_ = self.type_description(узлы[0], тег)
            return [type_] if type_ is not None else [raw(f.name, узлы)]
        if f.kind == "contains" and f.type == VALUE and len(узлы) == 1:
            value = self.value(узлы[0], тег)
            return [value] if value is not None else [raw(f.name, узлы)]
        if f.kind in ("refers", "attribute"):
            if any(n.children or n.attrs or not plain(n.text) for n in узлы):
                return [raw(f.name, узлы)]
            слова = ENUM_WORDS_BACK.get(f.type, {})
            if f.many:
                return [Node(тег, children=[Node("Item", text=слова.get(n.text, n.text)) for n in узлы])]
            if len(узлы) == 1:
                return [Node(тег, text=слова.get(узлы[0].text, узлы[0].text))]
        return [raw(f.name, узлы)]

    def type_description(self, узел, тег):
        дети = []
        for n in узел.children:
            if n.tag == "types":
                word = n.text or ""
                if word in PRIMITIVE_BACK:
                    дети.append(Node("Type", text=PRIMITIVE_BACK[word]))
                elif "." in word or word in ("AnyRef",):
                    набор = word.split(".", 1)[0] in ("DefinedType", "Characteristic")
                    дети.append(Node("TypeSet" if набор else "Type", text="cfg:" + word))
                else:
                    дети.append(Node("Type", text="v8:" + word))
            elif n.tag in QUALIFIERS_BACK:
                тег_q, fields = QUALIFIERS_BACK[n.tag]
                q = Node(тег_q)
                for field in n.children:
                    if field.tag not in fields or field.children:
                        return None
                    text = field.text or ""
                    if field.tag in FLAGS_BACK:
                        text = FLAGS_BACK[field.tag][0] if text == "true" else FLAGS_BACK[field.tag][1]
                    q.children.append(Node(fields[field.tag], text=text))
                дети.append(q)
            else:
                return None
        return Node(тег, children=дети)

    @staticmethod
    def value(узел, тег):
        класс = узел.attrs.get("xsi:type", "").partition(":")[2]
        if класс == "UndefinedValue" and not узел.children:
            return Node(тег, attrs={"nil": "true"})
        type_ = VALUE_BACK.get(класс)
        if type_ is None:
            return None
        value = [c for c in узел.children if c.tag == "value"]
        if len(value) != len(узел.children) or len(value) > 1:
            return None
        text = value[0].text if value else None
        if value and not plain(text):
            return None                                # пустая строка, края пробелами — переходником
        return Node(тег, text=text, attrs={"type": type_})
