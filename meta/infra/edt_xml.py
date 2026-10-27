"""Текст файла проекта EDT: узел карточки (`acl.Node`) -> байты и обратно.

EDT пишет объект через EMF, и вид текста у него свой, отличный от выгрузки
конфигуратора. Замер — все карточки `.mdo` и формы `.form` проекта EDT
крупной типовой конфигурации:

* объявление `<?xml version="1.0" encoding="UTF-8"?>`, UTF-8 без BOM, LF,
  завершающий перевод строки есть;
* отступ — два пробела на уровень;
* пространства имён объявлены на корне — только те, что в документе
  встречаются: `xsi` первым, остальные по алфавиту приставок
  (`xsi core form mdclass`);
* текст экранируется так, как это делает EMF: `&` -> `&amp;`, `<` -> `&lt;`,
  `"` -> `&quot;`; `>` и переводы строк остаются как есть;
* пустой вложенный объект — одиночным тегом `<x/>`, пустая строка — парой
  `<x></x>`: это разные значения (объект без свойств и строка без символов).

Тег узла — имя свойства (`attributes`, `synonym`) или, у корня, имя с
приставкой (`mdclass:Catalog`); атрибут `xsi:type` несёт приставку пакета
(`core:UndefinedValue`). Объявления пространств имён корень несёт атрибутами
`xmlns:*`: разбор оставляет их в порядке файла, новому файлу они вычисляются.
"""

from lxml import etree

DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
INDENT = "  "

#: приставка -> пространство имён карточек: те, что встречаются в `.mdo`
NAMESPACES = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "core": "http://g5.1c.ru/v8/dt/mcore",
    "form": "http://g5.1c.ru/v8/dt/form",
    "mdclass": "http://g5.1c.ru/v8/dt/metadata/mdclass",
    # расширение конфигурации: блок `extension` у объектов расширения и у
    # заимствованных — что расширение контролирует и перехватывает
    "mdclassExtension": "http://g5.1c.ru/v8/dt/metadata/mdclass/extension",
    # схема компоновки внутри формы (динамический список); `core_1` — так EDT
    # называет второе пространство с именем `core`
    "schema": "http://g5.1c.ru/v8/dt/data-composition-system/schema",
    "core_1": "http://g5.1c.ru/v8/dt/data-composition-system/core",
    "settings": "http://g5.1c.ru/v8/dt/data-composition-system/settings",
}
XSI_TYPE = "{" + NAMESPACES["xsi"] + "}type"


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def escape_attribute(text):
    return escape(text).replace("\n", "&#xA;").replace("\r", "&#xD;").replace("\t", "&#x9;")


def _prefixes(node, found):
    if ":" in node.tag:
        found.add(node.tag.partition(":")[0])
    for name, value in node.attrs.items():
        if ":" in name and not name.startswith("xmlns:"):
            found.add(name.partition(":")[0])
        if name == "xsi:type" and ":" in value:
            found.add(value.partition(":")[0])
    for child in node.children:
        _prefixes(child, found)


def declarations(node):
    """Объявления пространств имён корня: `xsi` первым, остальные по алфавиту."""
    found = set()
    _prefixes(node, found)
    order = (["xsi"] if "xsi" in found else []) + sorted(found - {"xsi"})
    return [(pt, NAMESPACES[pt]) for pt in order]


def _open(node, extra=()):
    xml_attrs = [f'xmlns:{pt}="{uri}"' for pt, uri in extra]
    xml_attrs += [f'{name}="{escape_attribute(value)}"' for name, value in node.attrs.items()]
    return node.tag + "".join(" " + a for a in xml_attrs)


def _lines(node, level, out, extra=()):
    indent = INDENT * level
    head = _open(node, extra)
    if node.children:
        out.append(f"{indent}<{head}>")
        for child in node.children:
            _lines(child, level + 1, out)
        out.append(f"{indent}</{node.tag}>")
    elif node.text is not None:                     # пустая строка — тоже значение: <x></x>
        out.append(f"{indent}<{head}>{escape(node.text)}</{node.tag}>")
    else:
        out.append(f"{indent}<{head}/>")


def render(node):
    """Корневой узел -> текст файла EDT. Объявления пространств имён — те, что
    корень уже несёт (`xmlns:*`), иначе — вычисленные по документу."""
    out = [DECLARATION]
    if any(name.startswith("xmlns:") for name in node.attrs):
        _lines(node, 0, out)
    else:
        _lines(node, 0, out, declarations(node))
    return "\n".join(out) + "\n"


def to_bytes(node):
    return render(node).encode("utf-8")


def _declared_order(data, nsmap):
    """Объявления корня в том порядке, в каком они стоят в файле: lxml отдаёт
    их словарём, а не последовательностью."""
    start = data.find(b"<", data.find(b"?>") + 2)
    head = data[start:data.find(b">", start) + 1].decode("utf-8", "replace")
    found = sorted((head.find(f'xmlns:{pt}="'), pt, uri) for pt, uri in nsmap.items() if pt)
    return [(pt, uri) for _, pt, uri in found]


def parse(data):
    """Байты файла EDT -> `acl.Node` с приставками: тег корня `mdclass:Catalog`,
    атрибут `xsi:type` — с приставкой, как в файле.

    Пустой элемент разбор XML не различает: `<value></value>` и `<value/>`
    приходят одинаково. Различает метамодель: свойство-атрибут с пустым
    значением EDT пишет парой тегов, пустой вложенный объект — одиночным.
    Поэтому класс каждого элемента выводится по таблице, и пустому атрибуту
    ставится пустой текст."""
    from ..acl import edt_model
    from ..acl.mapping import Node

    root = etree.fromstring(data)

    def element_class(element, declared):
        explicit = element.get(XSI_TYPE)
        if explicit:
            prefix, _, name = explicit.rpartition(":")
            return edt_model.class_of(element.nsmap.get(prefix or None), name)
        if declared:
            return declared
        uri, _, name = element.tag[1:].partition("}")
        return edt_model.class_of(uri, name)

    def node(element, cls_name):
        uri, _, name = element.tag[1:].partition("}") if element.tag.startswith("{") else ("", "", element.tag)
        prefixes = {v: k for k, v in element.nsmap.items() if k}
        xml_attrs = {}
        if element is root:
            tag = f"{prefixes[uri]}:{name}" if uri in prefixes else name
            xml_attrs.update({f"xmlns:{pt}": u for pt, u in _declared_order(data, element.nsmap)})
        else:
            tag = name
        for key, value in element.attrib.items():
            if key.startswith("{"):
                a_uri, _, a_name = key[1:].partition("}")
                key = f"{prefixes.get(a_uri, '')}:{a_name}"
            xml_attrs[key] = value
        children = []
        for child in element:
            if not isinstance(child.tag, str):
                continue
            f = edt_model.feature(cls_name, etree.QName(child).localname) if cls_name else None
            sub = element_class(child, f.type) if f is not None and f.kind == "contains" else None
            n = node(child, sub)
            if f is not None and f.kind != "contains" and n.text is None and not n.children:
                n.text = ""
            children.append(n)
        text = element.text if not children else None
        return Node(tag, text=text, attrs=xml_attrs, children=children)

    return node(root, element_class(root, None))
