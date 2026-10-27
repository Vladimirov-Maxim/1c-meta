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
ENUM_WORDS_BACK = {type_: {edt: dump for dump, edt in words.items()} for type_, words in ENUM_WORDS.items()}


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
        node = Node(f"mdclass:{kind.tag}", attrs={"uuid": kind.attrs.get("uuid", ""),
                                                 **{k: v for k, v in kind.attrs.items() if k != "uuid"}})
        self.fill(node, kind, cls, kind.tag)
        return node

    def fill(self, target, source, cls, where):
        """Свойства и дети элемента выгрузки -> дети узла EDT в порядке метамодели."""
        collected = []
        for part in source.children:
            if part.tag == "InternalInfo":
                collected += self.produced_types(part, cls, where)
            elif part.tag == "Properties":
                for prop in part.children:
                    collected += self.property(prop, cls, where)
            elif part.tag == "ChildObjects":
                for child in part.children:
                    collected += self.child(child, cls, where)
            else:
                self.problem(where, f"незнакомый раздел карточки «{part.tag}»")
        collected.sort(key=lambda pair: pair[0])           # сортировка устойчива: список — по порядку
        target.children.extend(node for _, node in collected)

    # --- порождаемые типы ---

    def produced_types(self, info, cls, where):
        f = edt_model.feature(cls, "producedTypes")
        if f is None:
            if info.children:
                self.problem(where, "порождаемые типы есть, а свойства producedTypes у класса нет")
            return []
        node = Node("producedTypes")
        collected = []
        for gen in info.children:
            if gen.tag != "GeneratedType":
                continue
            name = self._produced_name(gen.attrs.get("category", ""), f.type)
            if name is None:
                self.problem(where, f"порождаемый тип «{gen.attrs.get('category')}» не найден в {f.type}")
                continue
            fields = {c.tag: c.text or "" for c in gen.children}
            collected.append((edt_model.position(f.type, name),
                            Node(name, attrs={"typeId": fields.get("TypeId", ""),
                                             "valueTypeId": fields.get("ValueId", "")})))
        collected.sort(key=lambda pair: pair[0])
        node.children = [n for _, n in collected]
        return [(edt_model.position(cls, "producedTypes"), node)]

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

    def property(self, prop, cls, where):
        if prop.tag == RAW:                        # прошло переходник насквозь
            place = edt_model.position(cls, prop.attrs.get("feature", ""))
            return [(place, restore_raw(n)) for n in prop.children]
        name = feature_name(prop.tag)
        f = edt_model.feature(cls, name)
        if f is None:
            if self._empty(prop):
                return []                              # пустое свойство, которого у EDT нет, — не потеря
            self.problem(where, f"свойства «{prop.tag}» нет у {cls.rsplit('.', 1)[-1]}")
            return []
        place = edt_model.position(cls, name)
        return [(place, n) for n in self.value_nodes(prop, f, cls, f"{where}.{prop.tag}")]

    @staticmethod
    def _empty(prop):
        return not prop.children and not (prop.text or "").strip()

    def value_nodes(self, prop, f, cls, where):
        """Свойство выгрузки -> узлы EDT свойства `f` (пусто — не пишется)."""
        if f.kind == "contains" and f.type == LOCAL_STRING:
            return [Node(f.name, children=[Node("key", text=item_part(i, "lang")),
                                           Node("value", text=item_part(i, "content"))])
                    for i in prop.children if i.tag == "item"]
        if f.kind == "contains" and f.type == TYPE_DESCRIPTION:
            return [self.type_description(prop, f.name, where)]
        if f.kind == "contains" and f.type == VALUE:
            node = self.value(prop, f.name, where)
            return [node] if node is not None else []
        if f.kind == "refers":
            if f.many:
                return [Node(f.name, text=c.text or "") for c in prop.children if c.text]
            return [Node(f.name, text=prop.text)] if prop.text else []
        if f.kind == "attribute":
            words = ENUM_WORDS.get(f.type, {})
            if f.many:
                return [Node(f.name, text=words.get(c.text or "", c.text or "")) for c in prop.children]
            if prop.children:
                self.problem(where, "у атрибута вложенные элементы")
                return []
            text = words.get(prop.text or "", prop.text or "")
            if text == "" or edt_model.is_default(f, text, cls):
                return []
            return [Node(f.name, text=text)]
        if self._empty(prop):
            return []
        if f.type == MCORE + "Color" and prop.text == "auto" and not prop.children:
            return []                                  # цвет по умолчанию: EDT его не пишет
        self.problem(where, f"вложенный объект {f.type.rsplit('.', 1)[-1]} не перекладывается")
        return []

    # --- тип и значение ---

    def type_description(self, prop, name, where):
        node = Node(name)
        types, qualifiers = [], []
        for c in prop.children:
            if c.tag in ("Type", "TypeSet"):
                word = edt_type_word(c.text or "")
                if word is None:
                    self.problem(where, f"незнакомая запись типа «{c.text}»")
                    continue
                types.append(Node("types", text=word))
            elif c.tag in QUALIFIERS:
                name_q, fields = QUALIFIERS[c.tag]
                q = Node(name_q)
                cls_q = edt_model.feature(TYPE_DESCRIPTION, name_q).type
                for field in c.children:
                    name_p = fields.get(field.tag)
                    if name_p is None:
                        self.problem(where, f"незнакомое поле квалификатора «{field.tag}»")
                        continue
                    text = field.text or ""
                    if field.tag in QUALIFIER_FLAGS:
                        text = "true" if text == QUALIFIER_FLAGS[field.tag] else "false"
                    fq = edt_model.feature(cls_q, name_p)
                    if not edt_model.is_default(fq, text, cls_q):
                        q.children.append((edt_model.position(cls_q, name_p), Node(name_p, text=text)))
                q.children = [n for _, n in sorted(q.children, key=lambda pair: pair[0])]
                qualifiers.append((edt_model.position(TYPE_DESCRIPTION, name_q), q))
            else:
                self.problem(where, f"незнакомая часть описания типа «{c.tag}»")
        node.children = types + [q for _, q in sorted(qualifiers, key=lambda pair: pair[0])]
        return node

    def value(self, prop, name, where):
        if prop.attrs.get("nil") == "true":
            return Node(name, attrs={"xsi:type": "core:UndefinedValue"})
        type_ = prop.attrs.get("type")
        cls_name = VALUE_TYPES.get(type_)
        if cls_name is None:
            if type_ is None and not prop.text:
                return None
            self.problem(where, f"незнакомое значение типа «{type_}»")
            return None
        node = Node(name, attrs={"xsi:type": f"core:{cls_name}"})
        text = prop.text or ""
        f = edt_model.feature(MCORE + cls_name, "value")
        if text and not edt_model.is_default(f, text, MCORE + cls_name):
            node.children.append(Node("value", text=text))
        return node

    # --- дети ---

    def child(self, child, cls, where):
        if cls == CONFIGURATION and not child.children and child.text:
            f = registry_feature(child.tag)          # запись реестра: <catalogs>Catalog.X</catalogs>
            if f is None:
                self.problem(where, f"в реестре EDT нет списка для вида «{child.tag}»")
                return []
            return [(edt_model.position(cls, f.name), Node(f.name, text=f"{child.tag}.{child.text}"))]
        f = child_feature(cls, child.tag)
        if f is None:
            self.problem(where, f"ребёнка вида «{child.tag}» нет у {cls.rsplit('.', 1)[-1]}")
            return []
        place = edt_model.position(cls, f.name)
        if not child.children and child.text:     # форма, макет, подсистема: имя, карточка — спутник
            satellite = self.satellite(child.tag, child.text)
            if satellite is None:
                self.problem(where, f"{child.tag} «{child.text}»: карточки спутника нет")
                return []
            child = satellite.children[0] if satellite.tag == "MetaDataObject" else satellite
        node = Node(f.name, attrs={"uuid": child.attrs.get("uuid", "")})
        self.fill(node, child, f.type, f"{where}.{child.tag}")
        return [(place, node)]


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
    def strip(n):
        attrs = dict(n.attrs)
        if n.text is not None and not n.children:
            attrs[RAW_TEXT] = n.text
        return Node(n.tag, attrs=attrs, children=[strip(c) for c in n.children])
    return Node(RAW, attrs={"feature": feature}, children=[strip(n) for n in nodes])


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
    props = edt_model.features(CONFIGURATION)
    start = [f.name for f in props].index("languages") + 1
    return tuple(f for f in props[start:] if f.kind == "refers" and f.many)


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
    props = [f for f in edt_model.features(cls) or () if f.kind == "contains" and f.many]
    by_name = feature_name(tag) + "s"
    for f in props:
        if f.name == by_name:
            return f
    candidates = [f for f in props if f.type.rsplit(".", 1)[-1].endswith(tag)]
    if not candidates:
        return None
    return min(candidates, key=lambda f: len(f.type.rsplit(".", 1)[-1]))


# --- обратная перекладка ------------------------------------------------------------------


#: Слово EDT -> запись типа выгрузки (обратное `PRIMITIVE_TYPES`).
PRIMITIVE_BACK = {word: record for record, word in PRIMITIVE_TYPES.items()}
#: Поле квалификатора EDT -> поле выгрузки; булевы — словом выгрузки.
QUALIFIERS_BACK = {name_q: (tag, {edt: dump for dump, edt in fields.items()})
                   for tag, (name_q, fields) in QUALIFIERS.items()}
FLAGS_BACK = {"fixed": ("Fixed", "Variable"), "nonNegative": ("Nonnegative", "Any")}
VALUE_BACK = {cls_name: type_ for type_, cls_name in VALUE_TYPES.items()}


def is_md_object(cls):
    """Класс — объект метаданных (у него есть имя и uuid): такие дети живут в
    `ChildObjects` выгрузки, остальное — свойства."""
    seen, queue = set(), [cls]
    while queue:
        c = queue.pop()
        if c == MDCLASS + "MdObject":
            return True
        if c in seen:
            continue
        seen.add(c)
        queue += edt_model.classes().get(c, {}).get("supers", [])
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
        for child in node.children:
            if groups and groups[-1][0] == child.tag:
                groups[-1][1].append(child)
            else:
                groups.append((child.tag, [child]))
        for name, nodes in groups:
            f = edt_model.feature(cls, name)
            if f is None:
                props.children.append(raw(name, nodes))
            elif name == "producedTypes":
                info.children += self.produced(nodes[0], cls)
            elif f.kind == "contains" and f.many and is_md_object(f.type):
                for n in nodes:
                    children.children.append(self.element(n, f.type, designer_tag(name[:-1])))
            elif cls == CONFIGURATION and f in registry_features() and self.registry_entries(f, nodes):
                children.children += self.registry_entries(f, nodes)
            else:
                props.children += self.property(f, nodes)
        attrs = {k: v for k, v in node.attrs.items() if not k.startswith("xmlns:")}
        parts = [p for p in (info, props, children) if p.children or p is props] + more
        return Node(tag, attrs=attrs, children=parts)

    @staticmethod
    def registry_entries(f, nodes):
        """`<catalogs>Catalog.X</catalogs>` -> `<Catalog>X</Catalog>` реестра выгрузки;
        запись не того вида — None (свойство пойдёт переходником)."""
        kind = f.type.rsplit(".", 1)[-1]
        records = []
        for n in nodes:
            text = n.text or ""
            if n.children or n.attrs or not text.startswith(kind + ".") or not plain(text):
                return None
            records.append(Node(kind, text=text[len(kind) + 1:]))
        return records

    @staticmethod
    def produced(node, cls):
        return [Node("GeneratedType", attrs={"name": "", "category": designer_tag(n.tag[:-4])
                                             if n.tag.endswith("Type") else "@" + n.tag},
                     children=[Node("TypeId", text=n.attrs.get("typeId", "")),
                               Node("ValueId", text=n.attrs.get("valueTypeId", ""))])
                for n in node.children]

    def property(self, f, nodes):
        tag = designer_tag(f.name)
        if f.kind == "contains" and f.type == LOCAL_STRING:
            items = []
            for n in nodes:
                fields = {c.tag: c for c in n.children}
                if set(fields) != {"key", "value"} or any(c.children for c in n.children)                         or any(c.text and not plain(c.text) for c in n.children):
                    return [raw(f.name, nodes)]
                items.append(Node("item", children=[Node("lang", text=fields["key"].text or ""),
                                                    Node("content", text=fields["value"].text or "")]))
            return [Node(tag, children=items)]
        if f.kind == "contains" and f.type == TYPE_DESCRIPTION and len(nodes) == 1:
            type_ = self.type_description(nodes[0], tag)
            return [type_] if type_ is not None else [raw(f.name, nodes)]
        if f.kind == "contains" and f.type == VALUE and len(nodes) == 1:
            value = self.value(nodes[0], tag)
            return [value] if value is not None else [raw(f.name, nodes)]
        if f.kind in ("refers", "attribute"):
            if any(n.children or n.attrs or not plain(n.text) for n in nodes):
                return [raw(f.name, nodes)]
            words = ENUM_WORDS_BACK.get(f.type, {})
            if f.many:
                return [Node(tag, children=[Node("Item", text=words.get(n.text, n.text)) for n in nodes])]
            if len(nodes) == 1:
                return [Node(tag, text=words.get(nodes[0].text, nodes[0].text))]
        return [raw(f.name, nodes)]

    def type_description(self, node, tag):
        children = []
        for n in node.children:
            if n.tag == "types":
                word = n.text or ""
                if word in PRIMITIVE_BACK:
                    children.append(Node("Type", text=PRIMITIVE_BACK[word]))
                elif "." in word or word in ("AnyRef",):
                    dataset = word.split(".", 1)[0] in ("DefinedType", "Characteristic")
                    children.append(Node("TypeSet" if dataset else "Type", text="cfg:" + word))
                else:
                    children.append(Node("Type", text="v8:" + word))
            elif n.tag in QUALIFIERS_BACK:
                tag_q, fields = QUALIFIERS_BACK[n.tag]
                q = Node(tag_q)
                for field in n.children:
                    if field.tag not in fields or field.children:
                        return None
                    text = field.text or ""
                    if field.tag in FLAGS_BACK:
                        text = FLAGS_BACK[field.tag][0] if text == "true" else FLAGS_BACK[field.tag][1]
                    q.children.append(Node(fields[field.tag], text=text))
                children.append(q)
            else:
                return None
        return Node(tag, children=children)

    @staticmethod
    def value(node, tag):
        cls_name = node.attrs.get("xsi:type", "").partition(":")[2]
        if cls_name == "UndefinedValue" and not node.children:
            return Node(tag, attrs={"nil": "true"})
        type_ = VALUE_BACK.get(cls_name)
        if type_ is None:
            return None
        value = [c for c in node.children if c.tag == "value"]
        if len(value) != len(node.children) or len(value) > 1:
            return None
        text = value[0].text if value else None
        if value and not plain(text):
            return None                                # пустая строка, края пробелами — переходником
        return Node(tag, text=text, attrs={"type": type_})
