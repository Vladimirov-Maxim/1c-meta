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
        узел = Node(f"mdclass:{вид.tag}", attrs={"uuid": вид.attrs.get("uuid", "")})
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
        кандидаты = {category[:1].lower() + category[1:] + "Type",
                     {"TabularSection": "objectType", "TabularSectionRow": "rowType"}.get(category, "")}
        for f in edt_model.features(types_cls) or ():
            if f.name in кандидаты:
                return f.name
        return None

    # --- свойства ---

    def property(self, свойство, cls, where):
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
