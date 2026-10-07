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
    for имя, значение in node.attrs.items():
        if ":" in имя and not имя.startswith("xmlns:"):
            found.add(имя.partition(":")[0])
        if имя == "xsi:type" and ":" in значение:
            found.add(значение.partition(":")[0])
    for ребёнок in node.children:
        _prefixes(ребёнок, found)


def declarations(node):
    """Объявления пространств имён корня: `xsi` первым, остальные по алфавиту."""
    found = set()
    _prefixes(node, found)
    порядок = (["xsi"] if "xsi" in found else []) + sorted(found - {"xsi"})
    return [(п, NAMESPACES[п]) for п in порядок]


def _open(node, extra=()):
    атрибуты = [f'xmlns:{п}="{uri}"' for п, uri in extra]
    атрибуты += [f'{имя}="{escape_attribute(значение)}"' for имя, значение in node.attrs.items()]
    return node.tag + "".join(" " + a for a in атрибуты)


def _lines(node, level, out, extra=()):
    отступ = INDENT * level
    голова = _open(node, extra)
    if node.children:
        out.append(f"{отступ}<{голова}>")
        for ребёнок in node.children:
            _lines(ребёнок, level + 1, out)
        out.append(f"{отступ}</{node.tag}>")
    elif node.text is not None:                     # пустая строка — тоже значение: <x></x>
        out.append(f"{отступ}<{голова}>{escape(node.text)}</{node.tag}>")
    else:
        out.append(f"{отступ}<{голова}/>")


def render(node):
    """Корневой узел -> текст файла EDT. Объявления пространств имён — те, что
    корень уже несёт (`xmlns:*`), иначе — вычисленные по документу."""
    out = [DECLARATION]
    if any(имя.startswith("xmlns:") for имя in node.attrs):
        _lines(node, 0, out)
    else:
        _lines(node, 0, out, declarations(node))
    return "\n".join(out) + "\n"


def to_bytes(node):
    return render(node).encode("utf-8")


def _declared_order(data, nsmap):
    """Объявления корня в том порядке, в каком они стоят в файле: lxml отдаёт
    их словарём, а не последовательностью."""
    начало = data.find(b"<", data.find(b"?>") + 2)
    голова = data[начало:data.find(b">", начало) + 1].decode("utf-8", "replace")
    найдено = sorted((голова.find(f'xmlns:{п}="'), п, uri) for п, uri in nsmap.items() if п)
    return [(п, uri) for _, п, uri in найдено]


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

    корень = etree.fromstring(data)

    def класс_элемента(element, объявлен):
        явный = element.get(XSI_TYPE)
        if явный:
            приставка, _, имя = явный.rpartition(":")
            return edt_model.class_of(element.nsmap.get(приставка or None), имя)
        if объявлен:
            return объявлен
        uri, _, имя = element.tag[1:].partition("}")
        return edt_model.class_of(uri, имя)

    def узел(element, класс):
        uri, _, имя = element.tag[1:].partition("}") if element.tag.startswith("{") else ("", "", element.tag)
        приставки = {v: k for k, v in element.nsmap.items() if k}
        атрибуты = {}
        if element is корень:
            тег = f"{приставки[uri]}:{имя}" if uri in приставки else имя
            атрибуты.update({f"xmlns:{п}": u for п, u in _declared_order(data, element.nsmap)})
        else:
            тег = имя
        for ключ, значение in element.attrib.items():
            if ключ.startswith("{"):
                a_uri, _, a_имя = ключ[1:].partition("}")
                ключ = f"{приставки.get(a_uri, '')}:{a_имя}"
            атрибуты[ключ] = значение
        дети = []
        for ребёнок in element:
            if not isinstance(ребёнок.tag, str):
                continue
            f = edt_model.feature(класс, etree.QName(ребёнок).localname) if класс else None
            под = класс_элемента(ребёнок, f.type) if f is not None and f.kind == "contains" else None
            n = узел(ребёнок, под)
            if f is not None and f.kind != "contains" and n.text is None and not n.children:
                n.text = ""
            дети.append(n)
        текст = element.text if not дети else None
        return Node(тег, text=текст, attrs=атрибуты, children=дети)

    return узел(корень, класс_элемента(корень, None))
