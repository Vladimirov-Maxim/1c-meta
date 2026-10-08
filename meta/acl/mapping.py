"""Перекладка: язык домена -> словарь выгрузки 1С.

Антикоррупционный слой. Всё, что домен называет по-русски — «источник»,
«ПриЗаписи», «Справочник.Контрагенты, грань Объект», — здесь превращается
в то, чем это записано в файле: `<Source>`, `OnWrite`, `cfg:CatalogObject.Контрагенты`.
Обратно домен об этом ничего не знает.

Что тут держится и почему именно тут:

* порядок узлов внутри `<Properties>` — факт формата, а не правило предметной
  области (проверено: у всех 639 подписок он один и тот же). Домену он не виден;
* обозначения типов — чистая склейка «корень вида + грань», без единого
  исключения на 26 встреченных обозначений. Отдельной гранью «МенеджерЗначения»
  снимается и единственный кандидат в исключения (константа);
* выбор тега `v8:Type` против `v8:TypeSet` — по доменному признаку «набор»,
  а не по форме обозначения. Из формы он не выводится: `cfg:DocumentObject`
  без имени записан как TypeSet, а `cfg:DocumentManager` без имени — как Type;
* признак «писать тег даже пустым»: `<Comment/>` стоит в 555 карточках из 639,
  то есть отсутствие комментария и отсутствие тега — разные вещи.

Невыразимое здесь не угадывается, а отвергается: `Refuse` вместо «примерно так».
"""


import collections
import functools
import re
from collections import OrderedDict

from ..domain.model import (
    Refuse,
    Spec,
    TypeRef,
    ValueType,
    Собранные,
    вид_табличной_части,
)
from ..domain.plan import Состав
from ..domain.platform import RIGHTS_BY_KIND
from .schema import SCHEMA, Field
from .vocabulary import (
    BOOLEAN,
    CARD_ORDER,
    DATE_PARTS,
    FACETS,
    FACETS_BACK,
    FIELDS,
    FOLDERS,
    FOREIGN_NAMESPACES,
    FORMAT_VERSION,
    GENERATED_TYPES,
    ITEMS,
    MEMBER_TAGS,
    MULTILANG,
    NESTED,
    NESTED_ROOTS,
    NUMBER_SIGN,
    OBJECT_REFERENCE,
    OBJECT_WORDS,
    OBJECT_WORDS_BACK,
    PLATFORM_TYPES,
    QUALIFIER_ORDER,
    READ_ONLY_TYPES_BACK,
    REORDER,
    RIGHTS,
    RIGHTS_HOSTS,
    RIGHTS_ORDER,
    ROOTS,
    ROOTS_BACK,
    SETTINGS_NAMESPACES,
    STRING_LENGTH,
    TEXT,
    TYPED_VALUE,
    TYPES,
    VALUE,
    VALUE_TYPE,
    XSI_BY_PYTHON,
)

# --- результат перекладки ---------------------------------------------------

class Node:
    """Узел карточки: тег, текст, атрибуты, дети.

    Порядок детей значим — последовательность узлов внутри `<Properties>`
    фиксирована схемой, «дописать куда удобно» нельзя. Поэтому список, а не словарь.
    """

    def __init__(self, tag, text=None, attrs=None, children=None):
        self.tag = tag
        self.text = text
        self.attrs = OrderedDict(attrs or {})
        self.children = list(children or [])


class Card:
    """Карточка объекта, готовая к записи: чем он является и что в нём лежит.

    `element` — имя элемента внутри `MetaDataObject`; `registry_tag` — имя тега
    в `<ChildObjects>` файла `Configuration.xml`. У встреченных видов они совпадают,
    но это два разных факта, и смешивать их не стоит.
    """

    def __init__(self, element, container, registry_tag, name, uuid, properties,
                 satellites=None, internal_info=None, children=None):
        self.element = element
        self.container = container
        self.registry_tag = registry_tag
        self.name = name
        self.uuid = uuid
        self.properties = list(properties)
        # Спутники — файлы рядом с карточкой, в каталоге её имени: у общего
        # модуля это `Ext/Module.bsl`. Список пар (путь от каталога, текст).
        self.satellites = list(satellites or [])
        # Порождаемые типы: узлы `xr:GeneratedType`, идут перед свойствами.
        self.internal_info = list(internal_info or [])
        # Раздел детей: `None` — вида без детей, список — пишется даже пустым.
        self.children = children


# --- собственно перекладка --------------------------------------------------

def type_notation(vtype):
    """«Справочник.Контрагенты, грань Объект» -> `cfg:CatalogObject.Контрагенты`."""
    root = ROOTS.get(vtype.kind)
    if root is None:
        raise Refuse("не знаю, как записать вид «{}»; известны: {}".format(
            vtype.kind, ", ".join(sorted(ROOTS))))
    if vtype.facet is None:
        facet = ""                       # определяемый тип: грани нет
    else:
        facet = FACETS.get(vtype.facet)
        if facet is None:
            raise Refuse("не знаю грани «{}»; известны: {}".format(vtype.facet, ", ".join(sorted(FACETS))))
    notation = "cfg:" + root + facet
    return notation if vtype.whole_kind else notation + "." + vtype.name


def parse_type_notation(notation, is_set):
    """`cfg:CatalogObject.Контрагенты` -> ссылка на языке домена.

    Обратная сторона той же таблицы. Живёт здесь, а не в читателе файлов, чтобы
    словарь выгрузки был описан в одном месте: иначе чтение и запись разъедутся
    незаметно — каждая по-своему права.
    """
    if not notation.startswith("cfg:"):
        raise Refuse(f"обозначение типа «{notation}» не начинается с «cfg:»")
    body = notation[len("cfg:"):]
    name = None
    if "." in body:                    # у набора имя тоже бывает: DefinedType.Имя
        body, name = body.split(".", 1)
    for tail, facet in FACETS_BACK:   # ValueManager раньше Manager
        if body.endswith(tail) and body[:-len(tail)] in ROOTS_BACK:
            return TypeRef(ROOTS_BACK[body[:-len(tail)]], name, facet, is_set=is_set)
    if body in ROOTS_BACK:            # определяемый тип — грани нет
        return TypeRef(ROOTS_BACK[body], name, None, is_set=is_set)
    raise Refuse(f"не знаю обозначения «{notation}»; пополните ROOTS или FACETS")


def multilang(value, lang="ru"):
    """Многоязычная строка: <v8:item><v8:lang>ru</v8:lang><v8:content>…

    Домен передаёт либо строку — тогда это язык по умолчанию, либо словарь
    «язык → текст». Словарь нужен не для красоты: в конфигурации бывает два
    языка, и часть карточек несёт синоним и по-русски, и по-английски. Порядок языков
    сохраняется тот, в котором их дал домен.
    """
    pairs = value.items() if hasattr(value, "items") else [(lang, value)]
    return [Node("v8:item", children=[
        Node("v8:lang", text=lang),
        Node("v8:content", text=text),
    ]) for lang, text in pairs]


def _word(table, value, what):
    if value not in table:
        raise Refuse("не знаю {} «{}»; допустимы: {}".format(what, value, ", ".join(sorted(table))))
    return table[value]


def _type_and_qualifier(vtype):
    """Один тип -> (узел типа, узел квалификатора или None)."""
    from ..domain import model as dm

    if isinstance(vtype, dm.StringType):
        return (Node("v8:Type", text="xs:string"),
                Node("v8:StringQualifiers", children=[
                    Node("v8:Length", text=str(vtype.length)),
                    Node("v8:AllowedLength", text=_word(
                        STRING_LENGTH,
                        "Фиксированная" if vtype.fixed else "Переменная",
                        "длину строки"))]))
    if isinstance(vtype, dm.NumberType):
        return (Node("v8:Type", text="xs:decimal"),
                Node("v8:NumberQualifiers", children=[
                    Node("v8:Digits", text=str(vtype.digits)),
                    Node("v8:FractionDigits", text=str(vtype.fraction_digits)),
                    Node("v8:AllowedSign", text=_word(
                        NUMBER_SIGN,
                        "Неотрицательный" if vtype.nonnegative else "Любой",
                        "знак числа"))]))
    if isinstance(vtype, dm.DateType):
        return (Node("v8:Type", text="xs:dateTime"),
                Node("v8:DateQualifiers", children=[
                    Node("v8:DateFractions",
                         text=_word(DATE_PARTS, vtype.parts, "состав даты"))]))
    if isinstance(vtype, dm.BooleanType):
        return (Node("v8:Type", text="xs:boolean"), None)
    if isinstance(vtype, dm.PlatformType):
        foreign = FOREIGN_NAMESPACES.get(vtype.name)
        if foreign:
            prefix, namespace, local_name = foreign
            return (Node("v8:Type", text=f"{prefix}:{local_name}",
                         attrs={"xmlns:" + prefix: namespace}), None)
        return (Node("v8:Type",
                     text=_word(PLATFORM_TYPES, vtype.name, "платформенный тип")), None)
    if isinstance(vtype, dm.TypeRef):
        return (Node("v8:TypeSet" if vtype.is_set else "v8:Type",
                     text=type_notation(vtype)), None)
    raise Refuse(f"не знаю, как записать тип «{vtype}»")


def type_children(vtype):
    """Тип значения -> содержимое узла `<Type>`.

    Квалификатор не «добавляется по желанию», а следует из типа: строка всегда
    несёт длину и признак фиксированности, число — разрядность, дробную часть
    и знак, дата — состав. Исключений в замеренной выгрузке нет ни одного.

    У составного типа сначала идут все типы и только потом квалификаторы —
    не «каждый за своим типом», как кажется по одиночному случаю. Порядок
    самих квалификаторов задан `QUALIFIER_ORDER`.
    """
    from ..domain import model as dm
    if isinstance(vtype, dm.AnyType):
        return []                      # <Type/>: тип не задан
    items = vtype if isinstance(vtype, (list, tuple)) else [vtype]
    types, qualifiers = [], []
    for one in items:
        node, qual = _type_and_qualifier(one)
        types.append(node)
        if qual is not None:
            qualifiers.append(qual)
    qualifiers.sort(key=lambda n: QUALIFIER_ORDER.index(n.tag))
    return types + qualifiers


def _value(field, value):
    if field.value_kind == BOOLEAN:
        return Node(field.tag, text="true" if value else "false")
    if field.value_kind == VALUE:
        # Два состояния и они разные: «не задано» и «задано пустой строкой».
        # Второе платформа пишет как <FillValue xsi:type="xs:string"/> — так
        # выглядит значение заполнения у строкового реквизита.
        if value is None:
            return Node(field.tag, attrs={"xsi:nil": "true"})
        if value == "":
            return Node(field.tag, attrs={"xsi:type": "xs:string"})
        raise Refuse(f"поле «{field.domain}» принимает только «не задано» и пустую строку")
    if field.value_kind == FIELDS:
        return Node(field.tag, children=[Node("xr:Field", text=s)
                                         for s in (value or [])])
    if field.value_kind == ITEMS:
        # Обозначения объектов, а не текст: задание пишет «Справочник.Имя»,
        # в файл идёт «Catalog.Имя». Тип элемента один и тот же во всех
        # четырёх местах, где такой список бывает.
        return Node(field.tag, children=[
            Node("xr:Item", attrs={"xsi:type": "xr:MDObjectRef"},
                 text=object_notation(s)) for s in (value or [])])
    if field.value_kind == VALUE_TYPE:
        _require_type(field, value)
        return Node(field.tag, children=type_children(value))
    if field.value_kind == NESTED:
        # У этих свойств своя структура (ссылки на параметры выбора, путь
        # к данным). Пустое пишется одиночным тегом, заполненное — отвергается:
        # записать текстом значит записать неверно.
        if value:
            raise Refuse(f"свойство «{field.domain}» имеет собственную структуру, которую "
                         "инструмент не выражает: задать его нельзя")
        return Node(field.tag)

    if field.value_kind == OBJECT_REFERENCE:
        return Node(field.tag,
                    text=object_notation(value) if value else "")
    if field.value_kind == TYPED_VALUE:
        # Пустое значение — не отсутствие тега, а явное «ничего»: платформа
        # дописывает `<value xsi:nil="true"/>` параметру без значения. Это её
        # собственная правка записанного инструментом файла в круге
        # «записали → загрузили → выгрузили», и спорить с ней нечем.
        if value is None or value == "":
            return Node(field.tag, attrs={"xsi:nil": "true"})
        # Тип объявляется по тому, что лежит в значении: это не догадка,
        # а прямое соответствие — платформа пишет ровно так.
        marked = XSI_BY_PYTHON.get(type(value))
        if marked is None:
            raise Refuse(f"не знаю, каким типом объявить значение {value!r}")
        return Node(field.tag, attrs={"xsi:type": marked},
                    text="true" if value is True else
                         "false" if value is False else str(value))
    if field.value_kind == TEXT:
        if value and not isinstance(value, str):
            # Без этой проверки здесь упал бы `TypeError` из недр перекладки:
            # стек Python вместо ответа на вопрос «что не так в задании».
            raise Refuse(
                f"поле «{field.domain}» записывается текстом, а получено "
                f"{type(value).__name__} {value!r}; напишите строкой: \"{value}\"")
        return Node(field.tag, attrs=field.attrs,
                    text=(field.prefix + value) if value else "")
    if field.value_kind == MULTILANG:
        # Пустая многоязычная строка — это `<Synonym/>`, а не узел с пустым
        # содержимым: так записаны модули без синонима.
        return Node(field.tag, children=multilang(value) if value else [])
    if field.value_kind == TYPES:
        children = []
        for vtype in value if isinstance(value, list) else [value]:
            _require_type(field, vtype)
            # Тег выбирается по смыслу ссылки, а не по наличию имени:
            # `cfg:DefinedType.Имя` записан именно как TypeSet — 95 подписок из 639.
            children.append(Node("v8:TypeSet" if vtype.is_set else "v8:Type",
                             text=type_notation(vtype)))
        return Node(field.tag, children=children)
    raise Refuse(f"неизвестный вид значения «{field.value_kind}» у поля «{field.domain}»")


def _schema(kind):
    schema = SCHEMA.get(kind)
    if schema is None:
        raise Refuse("перекладка не знает вида «{}»; известны: {}".format(kind, ", ".join(sorted(SCHEMA))))
    return schema


def _properties(schema, spec, host=None):
    fields = [f for f in schema.fields
            if not f.only_for or host in f.only_for]
    reorder = REORDER.get(host)
    if reorder:
        what, before_what = reorder
        names = [f.domain for f in fields]
        if what in names and before_what in names:
            field = fields.pop(names.index(what))
            fields.insert([f.domain for f in fields].index(before_what), field)
    properties = []
    # Непонятые значения копятся и предъявляются вместе. Отказ с первого же
    # заставил бы исправлять задание с двумя неверными словами в два круга:
    # человек правил бы одно, запускал снова и узнавал про второе.
    #
    # Копится всё, чем может возразить укладка значения, а не только
    # незнакомые слова словаря: два поля-длины, записанные числом, иначе
    # тоже стоили бы двух запусков, хотя про второе инструмент уже знает.
    непонятые = Собранные("непонятых значений")
    for field in fields:
        value = spec.get(field.domain)
        if field.dictionary is not None and value:
            if value not in field.dictionary:
                непонятые.добавить(
                    "не знаю, как записать «{}» в поле «{}»; допустимо: {}".format(
                        value, field.domain, ", ".join(field.dictionary)))
                continue
            value = field.dictionary[value]
        if field.omit_when is not Field.OMIT_NOTHING and value == field.omit_when:
            continue                  # у платформы это умолчание — она его не пишет
        if not value and not field.always and field.omit_when is Field.OMIT_NOTHING:
            continue
        try:
            properties.append(_value(field, value))
        except Refuse as отказ:
            непонятые.добавить(str(отказ))
    непонятые.предъявить()
    return properties


def element_of(kind):
    """Доменный вид -> имя элемента в выгрузке: «Справочник» -> `Catalog`."""
    return _schema(kind).element


def container_of(kind):
    """Доменный вид -> каталог выгрузки, где лежат его карточки.

    Схема знает контейнер у всех видов, которые инструмент умеет создавать;
    `FOLDERS` — таблица другого назначения (виды, у которых бывают реквизиты),
    и она их не покрывает: общего модуля и подписки там нет.
    """
    return _schema(kind).container


def containers_of(kind):
    """Контейнеры внутри хозяина, куда ложится сущность этого вида."""
    return _schema(kind).inside


def object_notation(address):
    """`Отчет.X.Макет.Y` -> `Report.X.Template.Y`.

    Обозначение объекта, стоящее значением свойства: основная схема отчёта,
    основная форма, хранилище настроек. Задание называет его по-русски, как
    и всё остальное, а в файл идёт форма платформы — все 417 отчётов
    замеренной выгрузки записаны как `Report.Имя.Template.Макет`.

    Простым текстом поле приняло бы дословно что дали: и русскую форму, и
    английскую, обе с вердиктом «замечаний нет», — а неверное обозначение
    всплывает только при загрузке.
    """
    parts = [p for p in (address or "").split(".") if p]
    if len(parts) < 2 or len(parts) % 2:
        raise Refuse(
            f"обозначение объекта задаётся парами «Вид.Имя», получено "
            f"«{address}». Например: «Отчет.мой_Реестр.Макет.ОсновнаяСхема»")
    out = []
    for i in range(0, len(parts), 2):
        kind, name = parts[i], parts[i + 1]
        root = (OBJECT_WORDS.get(kind) if i == 0 else NESTED_ROOTS.get(kind))
        if root is None:
            known = sorted(OBJECT_WORDS if i == 0 else NESTED_ROOTS)
            raise Refuse(
                f"в обозначении «{address}» не знаю вида «{kind}»; "
                f"известны: {', '.join(known)}")
        out.append(root)
        out.append(name)
    return ".".join(out)


def steps_of(path):
    """Адрес парами «вид, имя» -> шаги спуска по дереву.

    Контейнеры в адресе не называются: пункт отбора пишется как
    `ВариантНастроек.Основной.Отбор.Организация`, а лежит в
    `settingsVariant/settings/filter/item`. Разворачивает их та же таблица,
    по которой запись их и заводит, — иначе адрес читался бы при добавлении
    и не читался при правке и удалении: пункт настроек нельзя было бы ни
    изменить, ни убрать.

    Шаг без имени (`None`) — контейнер: он в своём хозяине один, и опознавать
    его нечем, кроме тега.
    """
    steps = []
    for kind, name in path:
        steps.extend((tag, None) for tag in containers_of(kind))
        steps.append((element_of(kind), name))
    return steps


def registry_tag_of(kind):
    """Доменный вид -> тег записи в `Configuration.xml`."""
    return _schema(kind).registry_tag


def translate_field(kind, field_name, value, host=None):
    """Одно поле -> узел свойства. Нужно изменению: там правится одно, не всё.

    Значение проверяется теми же правилами, что и при создании: неизвестное
    слово перечисления — отказ со списком допустимых, а не запись наугад.
    """
    schema = _schema(kind)
    for field in schema.fields:
        if field.domain != field_name:
            continue
        if field.only_for and host not in field.only_for:
            raise Refuse(f"у вида «{host}» свойства «{field_name}» нет")
        value_ = value
        if field.dictionary is not None and value_:
            if value_ not in field.dictionary:
                raise Refuse("не знаю, как записать «{}» в поле «{}»; допустимо: {}".format(
                    value_, field_name, ", ".join(field.dictionary)))
            value_ = field.dictionary[value_]
        return _value(field, value_)
    raise Refuse("вид «{}» не знает поля «{}»; известны: {}".format(
        kind, field_name, ", ".join(f.domain for f in schema.fields)))


# Пространства имён файла прав — свои, не те, что у карточки объекта.
RIGHTS_NAMESPACES = {
    "xmlns": "http://v8.1c.ru/8.2/roles",
    "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
    "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

#: три флага файла прав в порядке записи: доменное поле -> тег
RIGHTS_FLAGS = (
    ("праваДляНовыхОбъектов", "setForNewObjects"),
    ("праваРеквизитовПоУмолчанию", "setForAttributesByDefault"),
    ("независимыеПраваПодчинённых", "independentRightsOfChildObjects"),
)


def render_rights(spec, configuration=None):
    """Спецификация роли -> дерево файла `Ext/Rights.xml`.

    Возвращается описание, а не текст: превращать узлы в байты — дело
    инфраструктуры, перекладка про файлы не знает.

    `configuration` — имя конфигурации: право «на конфигурацию целиком»
    в файле адресуется `Configuration.<Имя>`, и имя это знает только тот,
    кто читал `Configuration.xml`.
    """
    children = [Node(tag, text="true" if spec.get(field) else "false")
                for field, tag in RIGHTS_FLAGS]
    for granted in spec.get("права") or []:
        named = []
        for name in granted.get("права") or []:
            if name not in RIGHTS:
                # Список сужается до вида, если он назван: всех прав 70,
                # а у справочника их 25 — и читать нужно те самые.
                вид = (granted.get("объект") or "").partition(".")[0]
                у_вида = RIGHTS_BY_KIND.get(вид)
                raise Refuse("не знаю права «{}»; у вида «{}» бывают: {}".format(
                    name, вид, ", ".join(sorted(у_вида)))
                    if у_вида else "не знаю права «{}»; допустимы: {}".format(
                        name, ", ".join(sorted(RIGHTS))))
            named.append(RIGHTS[name])
        # Порядок прав канонический: платформа всё равно переставит их в него
        # при загрузке, и написать иначе — значит гарантировать себе diff
        # на каждом круге. Незамеренные права идут в конец, порядком задания.
        named.sort(key=lambda right: (RIGHTS_ORDER.index(right)
                                      if right in RIGHTS_ORDER else len(RIGHTS_ORDER)))
        rights = [Node("right", children=[Node("name", text=right),
                                          Node("value", text="true")])
                  for right in named]
        children.append(Node("object", children=[
            Node("name", text=_rights_target(granted.get("объект"), configuration)),
            *rights]))
    return Node("Rights", attrs={**RIGHTS_NAMESPACES, "xsi:type": "Rights",
                                 "version": FORMAT_VERSION}, children=children)


def rights_from_node(node):
    """Дерево `Ext/Rights.xml` -> поля роли: три флага и «права».

    Обратное `render_rights` — для показа: без него роль с заполненным файлом
    прав показывалась бы как «ещё 5 полей пусты». Незнакомое право остаётся
    словом файла, а не пропадает.
    """
    flags = {tag: field for field, tag in RIGHTS_FLAGS}
    по_русски = {англ: рус for рус, англ in RIGHTS.items()}
    fields, granted = {}, []
    for child in node.children:
        if child.tag in flags:
            fields[flags[child.tag]] = child.text == "true"
        elif child.tag == "object":
            name = next((c.text for c in child.children if c.tag == "name"), "") or ""
            права = []
            for right in child.children:
                if right.tag == "right":
                    значения = {c.tag: c.text for c in right.children}
                    if значения.get("value") == "true":
                        права.append(по_русски.get(значения.get("name"), значения.get("name")))
            granted.append({"объект": _rights_object(name), "права": права})
    fields["права"] = granted
    return fields


def granted_rights(pairs):
    """[(объект словом файла, [права словом файла])] -> [{«объект», «права»}] —
    по-русски, как у `rights_from_node`. Для чтения многих ролей разом: файл
    разбирает площадка, а слова переводятся здесь."""
    по_русски = {англ: рус for рус, англ in RIGHTS.items()}
    return [{"объект": _rights_object(name), "права": [по_русски.get(п, п) for п in права]}
            for name, права in pairs]


def _rights_object(name):
    """`Catalog.Контрагенты` -> «Справочник.Контрагенты»; `Configuration.<Имя>` -> «Конфигурация»."""
    head, _, rest = (name or "").partition(".")
    return "Конфигурация" if head == "Configuration" else f"{_виды_файла().get(head, head)}.{rest}"


@functools.cache
def _виды_файла():
    """Слово вида в файле прав -> вид по-русски: корни выгрузки и элементы схемы."""
    виды = dict(ROOTS_BACK)
    виды.update({kind.element: имя for имя, kind in SCHEMA.items()})
    return виды


def _rights_target(address, configuration=None):
    """«Справочник.Контрагенты» -> `Catalog.Контрагенты`; «Конфигурация» -> `Configuration.<Имя>`.

    Право на конфигурацию целиком не пишется буквально — `<name>Конфигурация</name>`:
    в корпусе так не записана ни одна роль, 2702 из 2709 несут
    `Configuration.<ИмяКонфигурации>`, то есть корень и имя конфигурации.
    Буквальная запись через платформу не проходит.
    """
    if not address:
        raise Refuse("в праве не указан объект")
    if "." not in address:
        if address != "Конфигурация":
            raise Refuse(f"право выдаётся на объект «Вид.Имя» или на «Конфигурация», "
                         f"получено «{address}»")
        if not configuration:
            raise Refuse("право на конфигурацию целиком требует её имени, "
                         "а оно не прочитано из Configuration.xml")
        return f"Configuration.{configuration}"
    kind, _, name = address.partition(".")
    root = SCHEMA[kind].element if kind in SCHEMA else ROOTS.get(kind)
    if root is None:
        raise Refuse("не знаю вида «{}»; известны: {}".format(
            kind, ", ".join(sorted(set(SCHEMA) | set(ROOTS)))))
    if root not in RIGHTS_HOSTS:
        raise Refuse(
            f"у вида «{kind}» прав не бывает: на него не выдано ни одного права "
            "ни в одной из 2709 ролей замеренной конфигурации. Право на общий модуль "
            "подвешивает загрузку конфигурации намертво — платформа не сообщает "
            "об ошибке, а уходит в бесконечный цикл")
    return f"{root}.{name}"


# Пустая схема компоновки: то, что пишет конфигуратор новому макету вида
# «Схема компоновки данных». Снято с самой маленькой схемы замеренной
# выгрузки (1093 Б) — источник данных и вариант настроек «Основной», больше
# ничего.


def render_template_card(spec, new_id):
    """Карточка макета: `Templates/<Имя>.xml` рядом с карточкой объекта."""
    name = spec.get("схема")
    properties = [
        Node("Name", text=name),
        Node("Synonym", children=multilang(spec.get("синонимСхемы") or name)),
        Node("Comment"),
        Node("TemplateType", text="DataCompositionSchema"),
    ]
    element = Node("Template", attrs={"uuid": new_id()},
                   children=[Node("Properties", children=properties)])
    return Node("MetaDataObject", attrs={"version": FORMAT_VERSION},
                children=[element])


def render_empty_schema(spec):
    """Содержимое макета: схема с одним источником данных и вариантом настроек."""
    source = Node("dataSource", children=[
        Node("name", text="ИсточникДанных1"),
        Node("dataSourceType", text="Local"),
    ])
    variant = Node("settingsVariant", children=[
        Node("dcsset:name", text="Основной"),
        Node("dcsset:presentation", attrs={"xsi:type": "xs:string"},
             text="Основной"),
        Node("dcsset:settings", attrs={
            f"xmlns:{prefix}": uri for prefix, uri in SETTINGS_NAMESPACES}),
    ])
    return Node("DataCompositionSchema", children=[source, variant])


def translate(spec, uuid, host=None, new_id=None, configuration=None):
    """Спецификация на языке домена -> карточка на языке выгрузки."""
    schema = _schema(spec.kind)
    if schema.container is None:
        raise Refuse(f"«{spec.kind}» живёт узлом внутри чужой карточки — нужен translate_node")
    satellites = []
    for satellite in schema.satellites:
        value = spec.get(satellite.domain)
        if satellite.render in ("макет", "схема", "модуль") and not value:
            continue                      # макет или модуль не заказан — файлов и нет
        path = satellite.path.format(**{
            field: said for field, said in spec.fields.items()
            if isinstance(said, str)})
        if satellite.render == "права":
            content = render_rights(spec, configuration)
        elif satellite.render == "макет":
            content = render_template_card(spec, new_id)
        elif satellite.render == "схема":
            content = render_empty_schema(spec)
        else:
            content = value or ""
        satellites.append((path, content))
    return Card(schema.element, schema.container, schema.registry_tag,
                spec.get("имя"), uuid, _properties(schema, spec, host), satellites,
                _contained(schema, new_id) + _generated(schema, spec, new_id),
                _children(schema, spec, new_id, spec.get("имя"))
                if schema.children else None)


def _named_children(schema, spec):
    """Дети, записанные одним именем: `<Template>ОсновнаяСхема</Template>`.

    Так макет числится в карточке объекта — не элементом с содержимым,
    а именем, как объект в реестре конфигурации.
    """
    return [Node(tag, text=spec.get(field))
            for field, tag in schema.named_children if spec.get(field)]


def _children(schema, spec, new_id, owner, host=None):
    """Вложенные сущности, заданные вместе с объектом.

    `owner` — имя объекта верхнего уровня. Оно нужно табличной части: её
    порождаемый тип называется «DocumentTabularSection.Документ.ТЧ», то есть
    знает и хозяина, и себя. Дальше вглубь передаётся то же имя — реквизиту
    табличной части оно не нужно, но и врать ему нечем.
    """
    out = []
    for field, _ in schema.child_fields:
        for child in spec.get(field) or []:
            if new_id is None:
                raise Refuse("детям нужны идентификаторы, а источник не задан")
            out.append(translate_node(child, new_id(), host or spec.kind,
                                      owner, new_id))
    # Макет — после реквизитов и табличных частей: так их ставит
    # конфигуратор (`CARD_ORDER`: Attribute, TabularSection, Form, Template),
    # круг через платформу 8.5.1.
    return out + list(_named_children(schema, spec))


#: Внешние виды: корни своей выгрузки.
EXTERNAL_KINDS = ("ВнешняяОбработка", "ВнешнийОтчет")

#: Стандартный реквизит «НомерСтроки» табличной части внешнего объекта:
#: (тег, значение; `None` — `xsi:nil`, пустая строка — пустой узел).
#: Конфигуратор 8.5.1 дописывает этот блок при выгрузке внешней обработки
#: всегда, даже если в загруженном его не было, — у табличных частей
#: обработки конфигурации его нет (корпус). Значения — круг через платформу.
LINE_NUMBER_STANDARD = (
    ("LinkByType", ""), ("FillChecking", "DontCheck"), ("MultiLine", "false"),
    ("FillFromFillingValue", "false"), ("CreateOnInput", "Auto"),
    ("TypeReductionMode", "TransformValues"), ("MaxValue", None), ("ToolTip", ""),
    ("ExtendedEdit", "false"), ("Format", ""), ("ChoiceForm", ""), ("QuickChoice", "Auto"),
    ("ChoiceHistoryOnInput", "Auto"), ("EditFormat", ""), ("PasswordMode", "false"),
    ("DataHistory", "Use"), ("MarkNegatives", "false"), ("MinValue", None), ("Synonym", ""),
    ("Comment", ""), ("FullTextSearch", "Use"), ("ChoiceParameterLinks", ""),
    ("FillValue", None), ("Mask", ""), ("ChoiceParameters", ""),
)


def _line_number_block():
    """`<StandardAttributes>` с «НомерСтроки» — у табличной части внешнего объекта."""
    def node(tag, value):
        if value is None:
            return Node(f"xr:{tag}", attrs={"xsi:nil": "true"})
        return Node(f"xr:{tag}", text=value) if value else Node(f"xr:{tag}")
    return Node("StandardAttributes", children=[
        Node("xr:StandardAttribute", attrs={"name": "LineNumber"},
             children=[node(tag, value) for tag, value in LINE_NUMBER_STANDARD])])


def _contained(schema, new_id):
    """`xr:ContainedObject` внешних обработки и отчёта: класс вида и свой
    идентификатор объекта. Стоит в служебном блоке первым — так выгружает
    конфигуратор."""
    if schema.contained is None:
        return []
    if new_id is None:
        raise Refuse("внешнему объекту нужен идентификатор, а источник не задан")
    return [Node("xr:ContainedObject", children=[
        Node("xr:ClassId", text=schema.contained),
        Node("xr:ObjectId", text=new_id())])]


def _generated(schema, spec, new_id, host=None, owner=None):
    """Порождаемые типы объекта: по два идентификатора на каждый.

    Платформа заводит их сама, когда объект создают в конфигураторе. При записи
    прямо в выгрузку их пишет инструмент — на пустой базе такие идентификаторы
    платформа принимает без изменений.
    """
    if not schema.generated:
        return []
    if new_id is None:
        raise Refuse(f"виду «{spec.kind}» нужны порождаемые типы, "
                     "а источник идентификаторов не задан")
    name = spec.get("имя")
    out = []
    for prefix, category in schema.generated:
        # У табличной части приставка зависит от вида хозяина, а имя типа
        # включает и хозяина, и её саму: «CatalogTabularSection.Спр.ТЧ».
        if "{host}" in prefix:
            if host is None or host not in SCHEMA:
                raise Refuse(f"«{spec.kind}» не знает, внутри какого вида находится")
            prefix = prefix.format(host=SCHEMA[host].type_word)
        full = ".".join(part for part in (prefix, owner, name) if part)
        out.append(Node("xr:GeneratedType",
                        attrs={"name": full, "category": category},
                        children=[Node("xr:TypeId", text=new_id()),
                                  Node("xr:ValueId", text=new_id())]))
    return out


def translate_node(spec, uuid, host=None, owner=None, new_id=None):
    """Вложенная сущность (реквизит) -> узел для врезки в чужую карточку.

    `host` — доменный вид объекта-владельца («Справочник», «Документ»):
    от него зависит состав свойств, см. `Field.only_for`. `owner` — его имя;
    оно нужно только тем, у кого имя порождаемого типа составное.

    Узел устроен как карточка без обёртки: внутренний блок, свойства, дети.
    """
    schema = _schema(spec.kind)
    if schema.container is not None:
        raise Refuse(f"«{spec.kind}» — самостоятельный объект, ему нужна карточка, а не узел")
    if not schema.wrapped:
        # Схема компоновки: ни идентификатора, ни обёртки `<Properties>` —
        # свойства лежат прямыми детьми. Вид пункта настроек задаётся
        # атрибутом `xsi:type`: тег у них у всех один и тот же.
        return Node(schema.element, attrs=dict(schema.node_attrs),
                    children=_properties(schema, spec, host))
    inner = []
    if schema.generated:
        inner.append(Node("InternalInfo",
                          children=_generated(schema, spec, new_id, host, owner)))
    properties = _properties(schema, spec, host)
    if spec.kind == "ТабличнаяЧасть" and host in EXTERNAL_KINDS:
        properties.append(_line_number_block())
    inner.append(Node("Properties", children=properties))
    if schema.children:
        # Детям передаётся вид, от которого зависит их состав, а не имя
        # ближайшего родителя: у реквизитов табличной части он разный
        # смотря по тому, хранится ли объект. Тот же вопрос домен решает
        # в `_child_host` — и решать его надо одинаково, иначе проверка
        # и запись разойдутся.
        внутрь = (вид_табличной_части(host) if spec.kind == "ТабличнаяЧасть"
                  else spec.kind)
        inner.append(Node("ChildObjects",
                          children=_children(schema, spec, new_id, owner,
                                             внутрь)))
    return Node(schema.element, attrs={"uuid": uuid}, children=inner)


def _require_type(field, value):
    """Значение поля с типом обязано быть типом, а не тем, что было в JSON.

    Запасная проверка: разбирает такие поля диалект по списку, который
    объявил домен, и мимо неё пройти можно только ошибкой в этом списке.
    Без неё здесь упал бы `AttributeError` из недр перекладки — стек Python
    вместо ответа на вопрос «что не так в задании».
    """
    # Составной тип — список: у реквизита их бывает несколько.
    for одно in value if isinstance(value, list) else [value]:
        _one_type(field, одно)


def _one_type(field, value):
    if not isinstance(value, ValueType):
        raise Refuse(
            f"поле «{field.domain}» описывает тип, а получено "
            f"{type(value).__name__} {value!r}. Тип пишется как "
            '{"вид": "Строка", "длина": 20} или {"вид": "Справочник", '
            '"имя": "Контрагенты"}')


def check_layers():
    """Согласованность слоёв: домен объявляет словарь полей, перекладка его накрывает.

    Список полей у каждого вида назван дважды: у вида — как словарь, у схемы —
    как левая колонка таблицы. Это не дублирование по недосмотру, а цена
    разделения: домен не знает тегов, перекладка не знает инвариантов, и гард
    направления зависимостей это стережёт. Цена оплачивается здесь — швом,
    который проверяется, а не соблюдается.

    Проверяется четыре расхождения, каждое из которых иначе всплывает поздно
    и молча: состав полей, где вид живёт, умолчание вне собственного словаря
    и умолчание для поля, которого вид не знает.
    """
    from ..domain.kinds import REGISTRY
    problems = []
    for name, schema in SCHEMA.items():
        kind = REGISTRY.get(name)
        if kind is None:
            problems.append(f"схема знает вид «{name}», домен — нет")
            continue
        schema_fields = {f.domain for f in schema.fields}
        schema_fields |= {s.domain for s in schema.satellites}
        schema_fields |= {f for s in schema.satellites for f in s.fields}
        schema_fields |= {field for field, _ in schema.child_fields}
        if schema_fields != set(kind.fields):
            problems.append(f"вид «{name}»: домен {sorted(kind.fields)}, схема {sorted(schema_fields)}")
    for name in REGISTRY:
        if name not in SCHEMA:
            problems.append(f"домен знает вид «{name}», схема — нет")
    # Где вид живёт, сказано в трёх местах: `ROOTS` и `FOLDERS` покрывают
    # и виды, которых мы не пишем (на них ссылаются и их ищут), а `SCHEMA` —
    # те, что пишем. Пересечение невелико, и потому расхождение в нём
    # незаметно вдвойне: обозначение ссылки берёт корень из схемы, а поиск
    # по выгрузке — из `ROOTS`, и разойтись они могут молча.
    for name, schema in SCHEMA.items():
        if name in ROOTS and schema.element != ROOTS[name]:
            problems.append(f"вид «{name}»: схема {schema.element}, "
                            f"ROOTS {ROOTS[name]}")
        if name in FOLDERS and schema.container != FOLDERS[name]:
            problems.append(f"вид «{name}»: схема {schema.container}, "
                            f"FOLDERS {FOLDERS[name]}")
        kind = REGISTRY.get(name)
        if kind is None:
            continue
        # Умолчание вне собственного словаря даёт отказ на значении, которое
        # никто не задавал: перекладка отвергнет его так же, как опечатку.
        for field in schema.fields:
            default = kind.defaults.get(field.domain)
            if field.dictionary and default and default not in field.dictionary:
                problems.append(
                    f"вид «{name}», поле «{field.domain}»: умолчание "
                    f"«{default}» вне словаря ({', '.join(field.dictionary)})")
        unknown = [f for f in kind.required if f not in kind.fields]
        if unknown:
            problems.append(
                f"вид «{name}»: обязательные поля вне состава: {unknown}")
        stray = [f for f in kind.defaults if f not in kind.fields]
        if stray:
            problems.append(
                f"вид «{name}»: умолчание для неизвестного поля: {stray}")
        # Дети названы дважды: у вида — какое поле каким видом заполняется,
        # у схемы — то же самое. Сверяются обе половины: при сверке одной
        # левой опечатка в правой прошла бы молча.
        if tuple(schema.child_fields) != tuple(kind.child_fields):
            problems.append(
                f"вид «{name}»: дети у домена {list(kind.child_fields)}, "
                f"у схемы {list(schema.child_fields)}")
        # Забытый порождаемый тип не отказывает и не предупреждает: карточка
        # пишется без `InternalInfo` и выглядит правильной. Единственное
        # место, где это видно, — здесь. Спрашивается только у самостоятельных
        # видов: у вложенных порождаемые типы собираются от имени хозяина
        # (`{host}TabularSection`), и своей записи в таблице у них нет.
        if schema.container and schema.generated and name not in GENERATED_TYPES:
            problems.append(
                f"вид «{name}»: схема обещает порождаемые типы, "
                "а `GENERATED_TYPES` о нём не знает")
        # Без порядка групп ребёнка некуда вставить — это отказ, но поздний,
        # уже при записи. Здесь он виден при первом же запуске проверок.
        # Тоже только у самостоятельных: у вложенных своего каталога нет,
        # и порядок внутри них — отдельный вопрос (внутри табличной части
        # он не замерен, и запись про это отказывает вслух).
        # Схема компоновки и карточка объекта описываются одним классом,
        # и половина его полей для каждой из них бессмысленна. Какие
        # сочетания законны, из класса не видно — здесь видно.
        if not schema.wrapped:
            лишнее = [имя for имя, значение in (
                ("container", schema.container),
                ("registry_tag", schema.registry_tag),
                ("generated", schema.generated),
                ("satellites", schema.satellites)) if значение]
            if лишнее:
                problems.append(
                    f"вид «{name}» живёт в схеме компоновки, а у него "
                    f"заполнено карточное: {', '.join(лишнее)}")
        elif schema.inside or schema.node_attrs:
            problems.append(
                f"вид «{name}» пишется карточкой, а у него заполнено "
                "то, что бывает только у схемы: inside/node_attrs")
        # Каталог берётся у самой схемы, а не из `FOLDERS`: та таблица про
        # виды, у которых бывают реквизиты, и подсистемы в ней нет — а порядок
        # групп ей нужен наравне со всеми.
        if schema.container and schema.children and schema.container not in CARD_ORDER:
            problems.append(
                f"вид «{name}»: раздел детей есть, а порядок групп "
                f"(`CARD_ORDER[{schema.container!r}]`) не замерен")
    return problems

def _reference_suffixes():
    """Чем платформа дописывает корень вида в обозначении.

    Собирается из таблиц, а не перечисляется руками: грани типов, категории
    порождаемых типов (`CatalogSelection`, `InformationRegisterRecordKey`)
    и табличные части (`DocumentTabularSection.Документ.ТЧ`). Плюс пустая —
    `Catalog.Имя` без приставки стоит в составе подсистем, движениях документа,
    полях блокировки и в правах ролей.

    Список нужен именно перечнем, а не свободным хвостом: корень одного вида
    бывает
    приставкой другого (`Document` и `DocumentJournal`), и свободный хвост
    переименовал бы журнал документов вместе с документом.
    """
    suffixes = {"", "TabularSection", "TabularSectionRow"}
    suffixes.update(FACETS.values())
    for kind, generated in GENERATED_TYPES.items():
        root = ROOTS.get(kind, "")
        for prefix, _ in generated:
            if root and prefix.startswith(root):
                suffixes.add(prefix[len(root):])
    return sorted(suffixes, key=len, reverse=True)


_FACET_SUFFIXES = _reference_suffixes()


def reference_pattern(path):
    """Как выглядит ссылка на объект (или его часть) в тексте выгрузки.

    Одно выражение на все места, где имя встречается: тип реквизита
    (`cfg:CatalogRef.Имя`), источник подписки (`cfg:CatalogObject.Имя`), состав
    подсистемы и движения документа (`Catalog.Имя`), права роли, ввод по строке
    (`Catalog.Имя.StandardAttribute.Код`).

    Границы важны обе: без правой `мой_Эталон` нашёлся бы внутри
    `мой_ЭталонДокумент`, без левой — `Catalog.Имя` внутри `SomeCatalog.Имя`.
    """
    kind, name = path[0]
    # У ссылочных видов корень обозначения типа и имя элемента совпадают
    # (`Catalog`), а у нессылочных обозначения типа нет вовсе: на общий модуль
    # ссылаются как `CommonModule.Имя.Метод` в обработчике подписки и как
    # `CommonModule.Имя` в составе подсистемы. Поэтому имя элемента — общий
    # случай, а `ROOTS` нужен видам, у которых своей карточки нет.
    root = SCHEMA[kind].element if kind in SCHEMA else ROOTS.get(kind)
    if root is None:
        raise Refuse("не знаю, как на «{}» ссылаются; известны: {}".format(
            kind, ", ".join(sorted(set(SCHEMA) | set(ROOTS)))))
    facets = "|".join(_FACET_SUFFIXES)
    tail = ""
    for child_kind, child_name in path[1:]:
        tail += r"\." + _schema(child_kind).element + r"\." + re.escape(child_name)
    return re.compile(
        r"(?<![\w.])" + root + "(?:" + facets + r")?\.(?P<name>" + re.escape(name)
        + ")" + tail + r"(?![\w])")


@functools.cache
def _слова_мест():
    """Тег сущности -> слово адреса и тег свойства -> поле задания.

    Из той же схемы видов, что пишет карточки: `Attribute` -> «Реквизит»,
    `Type` -> «тип». Тег, общий для нескольких видов (`dcsset:item` у четырёх
    пунктов настроек), словом не становится — по одному тегу вид не угадать.
    Поле ищется сперва у самого вида, потом по всей схеме: «состав» у
    функциональной опции тот же `Content`, что у подсистемы.
    """
    сколько = collections.Counter(схема.element for схема in SCHEMA.values())
    сущности = {тег: вид for вид, тег in NESTED_ROOTS.items()}
    сущности.update((схема.element, вид) for вид, схема in SCHEMA.items()
                    if схема.container is None and сколько[схема.element] == 1)
    сущности.update((тег, слово) for слово, теги in MEMBER_TAGS.items()
                    for тег in теги)
    поля = {}
    for схема in SCHEMA.values():
        for поле in схема.fields:
            поля.setdefault(_хвост_тега(поле.tag), поле.domain)
    return сущности, поля


def reference_place(prefix, owner_kind, steps, prop):
    """Место ссылки словами задания: «Документ.мой_Заявка.Реквизит.Склад (тип)».

    `prefix` — адрес держателя, `steps` и `prop` — шаги и свойство тегами
    выгрузки (их находит дерево карточки). Тег, которого словарь не знает,
    остаётся как есть: точный тег полезнее придуманного слова — по нему место
    находится поиском в файле. Так у графы журнала свойство `References`:
    инструмент его не пишет, своего слова у него нет.
    """
    сущности, поля = _слова_мест()
    адрес = prefix + "".join(f".{сущности.get(тег, тег)}.{имя}" for тег, имя in steps)
    if prop is None:
        return адрес
    вид = сущности.get(steps[-1][0]) if steps else owner_kind
    свои = {_хвост_тега(поле.tag): поле.domain
            for поле in (SCHEMA[вид].fields if вид in SCHEMA else ())}
    return f"{адрес} ({свои.get(prop) or поля.get(prop, prop)})"

# --- обратная сторона: карточка -> спецификация ------------------------------
#
# Запись и чтение ходят по одной и той же схеме видов, а не по двум описаниям
# формата: иначе они разъедутся незаметно, и каждая будет по-своему права.
# Отсюда же берётся и польза чтения помимо «показать»: круг «записали ->
# прочитали -> сверили» проверяет перекладку без всякой платформы.


def _хвост_тега(tag):
    """`dcsset:use` -> `use`: приставку пространства схема и файл пишут по-разному."""
    return tag.split(":")[-1]


def _по_тегам(node):
    return {_хвост_тега(ребёнок.tag): ребёнок for ребёнок in node.children}


def _многоязычное(node):
    """`<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>…` -> текст."""
    for item in node.children:
        по_тегам = _по_тегам(item)
        содержимое = по_тегам.get("content")
        if содержимое is not None:
            return содержимое.text or ""
    return ""


def _тип_из_узлов(children):
    """Узлы `<v8:Type>` и квалификаторы -> тип (или список типов) домена."""
    from ..domain import model as dm

    по_тегам = [(_хвост_тега(c.tag), c) for c in children]
    # Набор («все ссылки справочников», определяемый тип, характеристика)
    # записан тегом TypeSet. Без него реквизит определяемого типа показывался
    # бы «Произвольным» — а так в замеренной выгрузке записаны 1597 типов в
    # справочниках и документах.
    типы = [(имя == "TypeSet", c) for имя, c in по_тегам if имя in ("Type", "TypeSet")]
    квалификаторы = {имя: c for имя, c in по_тегам if имя.endswith("Qualifiers")}
    собрано = []
    for набор, узел in типы:
        текст = (узел.text or "").strip()
        if набор or текст.startswith("cfg:"):
            собрано.append(_ссылка_или_как_записано(текст, набор))
        elif текст == "xs:string":
            q = _по_тегам(квалификаторы.get("StringQualifiers", Node("x")))
            длина = int(q["Length"].text or "0") if "Length" in q else 0
            фикс = ("AllowedLength" in q
                    and q["AllowedLength"].text == STRING_LENGTH["Фиксированная"])
            собрано.append(dm.StringType(длина, фикс))
        elif текст == "xs:decimal":
            q = _по_тегам(квалификаторы.get("NumberQualifiers", Node("x")))
            собрано.append(dm.NumberType(
                int(q["Digits"].text or "0") if "Digits" in q else 0,
                int(q["FractionDigits"].text or "0") if "FractionDigits" in q else 0,
                "AllowedSign" in q
                and q["AllowedSign"].text == NUMBER_SIGN["Неотрицательный"]))
        elif текст == "xs:dateTime":
            q = _по_тегам(квалификаторы.get("DateQualifiers", Node("x")))
            слово = q["DateFractions"].text if "DateFractions" in q else None
            назад = {v: k for k, v in DATE_PARTS.items()}
            собрано.append(dm.DateType(назад.get(слово, "ДатаВремя")))
        elif текст == "xs:boolean":
            собрано.append(dm.BooleanType())
        elif текст:
            собрано.append(dm.PlatformType(_слово_платформы(текст)))
    if not собрано:
        return dm.AnyType()
    return собрано[0] if len(собрано) == 1 else собрано


def _ссылка_или_как_записано(текст, набор):
    """`cfg:…` -> ссылка домена; незнакомое обозначение — как записано.

    Чтение служит показу и проверкам, и одно редкое обозначение не должно
    ронять просмотр всего объекта: отказ здесь значил бы «не покажу ничего».
    """
    from ..domain import model as dm
    try:
        return parse_type_notation(текст, is_set=набор)
    except Refuse:
        return dm.PlatformType(текст)


def _слово_платформы(текст):
    """`v8:ValueTable`, `mxl:SpreadsheetDocument` -> слово задания или показа."""
    назад = {v: k for k, v in PLATFORM_TYPES.items()}
    if текст in назад:
        return назад[текст]
    return READ_ONLY_TYPES_BACK.get(текст.rpartition(":")[2], текст)


def _обозначение_назад(текст):
    """`Report.X.Template.Y` -> `Отчет.X.Макет.Y`."""
    части = [ч for ч in (текст or "").split(".") if ч]
    if len(части) < 2 or len(части) % 2:
        return текст
    назад_корни = OBJECT_WORDS_BACK
    назад_вложенные = {v: k for k, v in NESTED_ROOTS.items()}
    вышло = []
    for i in range(0, len(части), 2):
        корень, имя = части[i], части[i + 1]
        словарь = назад_корни if i == 0 else назад_вложенные
        вышло += [словарь.get(корень, корень), имя]
    return ".".join(вышло)


def _значение_поля(field, node):
    """Узел свойства -> значение на языке задания. `None` — читать нечем."""
    текст = node.text
    if field.dictionary:
        назад = {v: k for k, v in field.dictionary.items()}
        return назад.get(текст, текст)
    if field.value_kind == BOOLEAN:
        return текст == "true"
    if field.value_kind == MULTILANG:
        return _многоязычное(node)
    if field.value_kind in (VALUE_TYPE, TYPES):
        return _тип_из_узлов(node.children)
    if field.value_kind == OBJECT_REFERENCE:
        return _обозначение_назад(текст) if текст else ""
    if field.value_kind == FIELDS:
        return [ребёнок.text for ребёнок in node.children if ребёнок.text]
    if field.value_kind == ITEMS:
        return [_обозначение_назад(ребёнок.text) for ребёнок in node.children
                if ребёнок.text]
    if field.value_kind == TEXT:
        значение = текст or ""
        приставка = field.prefix
        return значение[len(приставка):] if приставка and значение.startswith(
            приставка) else значение
    return текст


def spec_from_node(kind, node):
    """Разобранная карточка -> спецификация на языке задания.

    Читается то же, что пишется: состав полей берётся из схемы вида, а не
    из отдельного описания формата. Свойства, которых в файле нет, в
    спецификацию не попадают — «не задано» и «задано пустым» это разные вещи.
    """
    schema = _schema(kind)
    карточка = node
    if _хвост_тега(node.tag) == "MetaDataObject":
        свои = [c for c in node.children
                if _хвост_тега(c.tag) == _хвост_тега(schema.element)]
        if not свои:
            raise Refuse(f"в файле нет элемента «{schema.element}»")
        карточка = свои[0]
    по_тегам = _по_тегам(карточка)
    свойства = по_тегам.get("Properties")
    исходные = _по_тегам(свойства) if свойства is not None else по_тегам
    fields = {}
    for field in schema.fields:
        узел = исходные.get(_хвост_тега(field.tag))
        if узел is None:
            continue
        fields[field.domain] = _значение_поля(field, узел)
    состав = по_тегам.get("ChildObjects")
    for поле, вид_ребёнка in schema.child_fields or ():
        if состав is None:
            continue
        тег = _schema(вид_ребёнка).element
        дети = [c for c in состав.children
                if _хвост_тега(c.tag) == _хвост_тега(тег)]
        if дети:
            fields[поле] = [spec_from_node(вид_ребёнка, ребёнок) for ребёнок in дети]
    return Spec(kind, fields)


@functools.cache
def _группы_по_тегам():
    """Тег ребёнка в карточке -> группа состава: из схемы видов, а не отдельным
    словарём — читается то же, что пишется."""
    группы = {}
    for схема in SCHEMA.values():
        for группа, вид_ребёнка in схема.child_fields or ():
            группы[_хвост_тега(_schema(вид_ребёнка).element)] = группа
    return группы


def composition_from_node(node):
    """Разобранная карточка -> `domain.plan.Состав`: группы детей объекта —
    реквизиты, измерения, ресурсы, табличные части, значения — с типами.

    Типы читаются тем же разбором, что у показа, а дети — у любого вида, и у
    того, которого схема не описывает: состав плана видов характеристик или
    регистра бухгалтерии устроен так же. Вложенное (реквизиты табличных
    частей) в состав не входит.
    """
    карточка = node
    if _хвост_тега(node.tag) == "MetaDataObject":
        карточка = node.children[0] if node.children else Node("x")
    члены, группы = {}, _группы_по_тегам()
    состав = _по_тегам(карточка).get("ChildObjects")
    for ребёнок in (состав.children if состав is not None else ()):
        группа = группы.get(_хвост_тега(ребёнок.tag))
        свойства = _по_тегам(ребёнок).get("Properties")
        if группа is None or свойства is None:
            continue
        по_тегам = _по_тегам(свойства)
        имя = (по_тегам["Name"].text or "").strip() if "Name" in по_тегам else ""
        if not имя:
            continue
        типы = ()
        if "Type" in по_тегам:
            тип = _тип_из_узлов(по_тегам["Type"].children)
            типы = tuple(тип) if isinstance(тип, list) else (тип,)
        члены.setdefault(группа, {})[имя] = типы
    return Состав(члены)


def forms_from_node(node):
    """Имена форм объекта из `ChildObjects/Form` — для показа.

    Схема видов форм не описывает: их заводит задание на формы, а не на
    объекты. Но спрашивают про объект и затем, чтобы узнать, какие у него
    формы, — показ обязан их перечислять.
    """
    карточка = node
    if _хвост_тега(node.tag) == "MetaDataObject" and node.children:
        карточка = node.children[0]
    состав = _по_тегам(карточка).get("ChildObjects")
    if состав is None:
        return []
    имена = []
    for c in состав.children:
        if _хвост_тега(c.tag) != "Form":
            continue
        if c.text:
            имена.append(c.text)
        else:
            # Форма целиком — так её отдаёт карточка проекта EDT: имя в свойствах.
            свойства = _по_тегам(c).get("Properties")
            имя = _по_тегам(свойства).get("Name") if свойства is not None else None
            if имя is not None and имя.text:
                имена.append(имя.text)
    return имена
