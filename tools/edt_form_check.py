"""Перекладка форм `Form.xml` -> `Form.form` против того, что пишет сам EDT.

    py -3 tools/edt_form_check.py <выгрузка> <исходники EDT> [--шаг N] [--умолчания]

Выгрузка — каталог `Configuration.xml`, полученный из того же проекта EDT
командой `export` (или выгрузка конфигуратора той же версии конфигурации);
исходники EDT — каталог `src` проекта. Для каждой формы перекладка сравнивается
с файлом EDT побайтно; печатаются число совпавших, частые расхождения (первая
разошедшаяся строка) и то, чего перекладка не умеет.

`--умолчания` — вместо сверки снять таблицу умолчаний платформы: для каждого
вида элемента — свойства, которые EDT пишет, а перекладка из выгрузки не даёт;
постоянные (одно значение не меньше чем в 99 % случаев) пишутся в
`meta/acl/edt_form_defaults.py`.
"""

import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from meta.acl import edt_form  # noqa: E402
from meta.infra import edt_xml  # noqa: E402
from meta.infra.tree_lxml import LxmlCardTree  # noqa: E402

LONG = "\\\\?\\" if os.name == "nt" else ""
TREE = LxmlCardTree()


def pairs(xml, edt):
    for top in sorted(os.listdir(xml)):
        d = os.path.join(xml, top)
        if not os.path.isdir(d):
            continue
        for папка, _, файлы in os.walk(LONG + d):
            if "Form.xml" in файлы and os.path.basename(папка) == "Ext":
                rel = os.path.relpath(os.path.dirname(папка), LONG + xml)
                yield rel, os.path.join(папка, "Form.xml"), os.path.join(LONG + edt, rel, "Form.form")


def designer_node(path):
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    return TREE.to_node(TREE.parse(text))


def translate(path):
    перекладка = edt_form.FormTranslation()
    узел = перекладка.form(designer_node(path))
    return edt_xml.render(узел), перекладка.problems


def edt_forms(edt):
    for папка, _, файлы in os.walk(LONG + edt):
        if "Form.form" in файлы:
            yield os.path.relpath(папка, LONG + edt), os.path.join(папка, "Form.form")


def designer_root(node):
    """Дерево формы выгрузки из обратной перекладки — с пространствами имён
    корня, как у формы, которую пишет инструмент."""
    from meta.infra.forms.designer221 import vocabulary as voc
    attrs = {("xmlns" if not prefix else f"xmlns:{prefix}"): uri for prefix, uri in voc.NAMESPACES}
    attrs["version"] = voc.FORMAT_VERSION
    return edt_form.Node("Form", attrs=attrs, children=node.children)


def round_trip(edt, шаг):
    """Форма EDT -> дерево выгрузки (lxml) -> форма EDT: байт в байт?"""
    import time
    совпало = всего = 0
    расхождения, примеры, скелеты, сбои = Counter(), {}, Counter(), Counter()
    начало = time.time()
    for k, (rel, e) in enumerate(edt_forms(edt)):
        if k % шаг:
            continue
        всего += 1
        было = open(e, encoding="utf-8").read()
        обратно = edt_form.ReverseForm()
        try:
            дерево = обратно.form(edt_xml.parse(было.encode("utf-8")))
        except Exception as беда:                     # noqa: BLE001 — сводка, а не падение
            сбои[f"{type(беда).__name__}: {re.sub(r'«[^»]*»', '«…»', str(беда))[:120]}"] += 1
            примеры.setdefault("сбой", rel)
            continue
        for вид, _ in обратно.skeletons:
            скелеты[вид] += 1
        lxml = TREE.build(designer_root(дерево))
        стало = edt_xml.render(edt_form.FormTranslation().form(TREE.to_node(lxml)))
        if стало == было:
            совпало += 1
        else:
            вид = first_difference(было, стало)
            расхождения[вид] += 1
            примеры.setdefault(вид, rel)
    print(f"форм: {всего}, круг сошёлся: {совпало}, сбоев: {sum(сбои.values())}, "
          f"{time.time() - начало:.0f} с")
    print("скелетом:", dict(скелеты.most_common()))
    for беда, n in сбои.most_common(15):
        print(f"{n:6}  {беда}")
    for вид, n in расхождения.most_common(30):
        print(f"{n:6}  {вид}    [{примеры[вид]}]")


def first_difference(было, стало):
    a, b = было.split("\n"), стало.split("\n")
    for _i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return re.sub(r">[^<]*<", "><", x.strip()) + "  |  " + re.sub(r">[^<]*<", "><", y.strip())
    return f"длина {len(a)} / {len(b)}"


def check(xml, edt, шаг):
    совпало = всего = 0
    расхождения, проблемы, примеры = Counter(), Counter(), {}
    for k, (rel, x, e) in enumerate(pairs(xml, edt)):
        if k % шаг:
            continue
        всего += 1
        стало, беды = translate(x)
        было = open(e, encoding="utf-8").read()
        for беда in беды:
            проблемы[re.sub(r"«[^»]*»", "«…»", беда, count=1)] += 1
        if стало == было:
            совпало += 1
        else:
            вид = first_difference(было, стало)
            расхождения[вид] += 1
            примеры.setdefault(вид, rel)
    print(f"форм: {всего}, совпало побайтно: {совпало}")
    print("\nпервое расхождение (EDT | перекладка):")
    for вид, n in расхождения.most_common(40):
        print(f"{n:6}  {вид}    [{примеры[вид]}]")
    print("\nчего перекладка не умеет:")
    for беда, n in проблемы.most_common(int(os.environ.get("META_PROBLEMS", "40"))):
        print(f"{n:6}  {беда}")


# --- умолчания -----------------------------------------------------------------------------

def _items(node, out):
    """id -> узел элемента или спутника формы EDT (реквизиты и команды — мимо)."""
    for c in node.children:
        if c.tag in ("attributes", "formCommands", "parameters", "commandInterface", "handlers"):
            continue
        i = next((x for x in c.children if x.tag == "id"), None)
        if i is not None and any(x.tag == "name" for x in c.children):
            out[i.text] = c
        _items(c, out)
    return out


def _key(node):
    """Ключ вида: `класс|вид` у элемента, `свойство|вид` у спутника; вид — как
    записан в файле (умолчание EMF не пишется — пусто)."""
    тип = next((x.text for x in node.children if x.tag == "type"), None)
    класс = node.attrs.get("xsi:type", "").partition(":")[2]
    return f"{класс or node.tag}|{тип or ''}"


def _value(n):
    """Значение свойства для таблицы умолчаний: текст простого; у плоского
    объекта — `@класс|поле=значение;…` (вложенный — None, не умолчание)."""
    if not n.children:
        if "xsi:type" in n.attrs or n.text is None:
            return f"@{n.attrs.get('xsi:type', '')}|"
        return n.text
    if any(c.children for c in n.children):
        return None
    return f"@{n.attrs.get('xsi:type', '')}|" + ";".join(f"{c.tag}={c.text or ''}" for c in n.children)


def _name(n):
    return next((x.text for x in n.children if x.tag == "name"), "")


def _named(было, стало, задано):
    """Реквизиты, их колонки и команды формы: пары «EDT — перекладка» по имени."""
    тройки = []
    for вид in ("attributes", "formCommands"):
        с = {_name(n): n for n in стало.children if n.tag == вид}
        for б in (n for n in было.children if n.tag == вид):
            имя = _name(б)
            if имя not in с:
                continue
            ext = next((n for n in б.children if n.tag == "extInfo"), None)
            класс = ext.attrs.get("xsi:type", "").partition(":")[2] if ext is not None else ""
            ключ_вида = f"{вид}|{класс}" if вид == "attributes" else f"{вид}|"
            тройки.append((ключ_вида, б, с[имя], задано.get(f"{вид}:{имя}", set())))
            if вид == "attributes":
                ск = {_name(n): n for n in с[имя].children if n.tag == "columns"}
                for бк in (n for n in б.children if n.tag == "columns"):
                    if _name(бк) in ск:
                        ключ = f"columns:Attribute «{имя}».{_name(бк)}"
                        тройки.append(("columns|", бк, ск[_name(бк)], задано.get(ключ, set())))
    return тройки


def learn(источники):
    """Умолчания платформы: для каждого вида — свойства, которые перекладка без
    таблицы не даёт и выгрузка явно не задаёт; значение, которое EDT пишет
    в таком случае (∅ — не пишет), должно быть одним не меньше чем в 99 %."""
    edt_form.DEFAULTS = {}
    случаи = []                                      # (ключ, {путь: значение}, {даёт перекладка}, {задано})
    for k, (_rel, x, e, шаг) in enumerate((*пара, шаг) for xml, edt, шаг in источники
                                         for пара in pairs(xml, edt)):
        if k % шаг:
            continue
        перекладка = edt_form.FormTranslation()
        стало = перекладка.form(designer_node(x))
        было = edt_xml.parse(open(e, "rb").read())
        с, б = _items(стало, {}), _items(было, {})
        тройки = [("Form|", было, стало, перекладка.specified_by_id.get("Form", set()))]
        тройки += [(_key(узел), узел, с[i], перекладка.specified_by_id.get(i, set()))
                   for i, узел in б.items() if i in с]
        тройки += _named(было, стало, перекладка.specified_by_id)
        for ключ, б_узел, с_узел, задано in тройки:
            записано = {}
            for n in б_узел.children:
                if n.tag == "extInfo":
                    for m in n.children:
                        if _value(m) is not None:
                            записано["extInfo/" + m.tag] = _value(m)
                elif _value(n) is not None and n.tag not in ("name", "id", "type"):
                    записано[n.tag] = _value(n)
            даёт = {n.tag for n in с_узел.children if n.tag != "extInfo"}
            ext_с = next((n for n in с_узел.children if n.tag == "extInfo"), None)
            даёт |= {"extInfo/" + n.tag for n in ext_с.children} if ext_с is not None else set()
            случаи.append((ключ, записано, даёт, {"extInfo/" + з for з in задано} | задано))
    пути = defaultdict(set)
    for ключ, записано, даёт, _ in случаи:
        пути[ключ] |= set(записано) - даёт
    счёт = defaultdict(Counter)
    for ключ, записано, даёт, задано in случаи:
        for путь in пути[ключ]:
            if путь in даёт or путь in задано:
                continue
            счёт[(ключ, путь)][записано.get(путь, "∅")] += 1
    таблица = defaultdict(dict)
    print("непостоянные:")
    for (ключ, путь), значения in sorted(счёт.items()):
        значение, n = значения.most_common(1)[0]
        доля = n / sum(значения.values())
        if значение != "∅" and доля >= 0.99:
            таблица[ключ][путь] = значение
        elif значение != "∅" or доля < 0.99:
            print(f"  {ключ:36} {путь:36} {dict(значения.most_common(4))}")
    текст = ['"""Умолчания платформы, которые EDT пишет в форме явно.', "",
             "Снято с корпуса скриптом `tools/edt_form_check.py --умолчания`: для каждого",
             "вида элемента — свойства, которые EDT пишет, когда выгрузка их не задаёт,",
             "с одним значением не меньше чем в 99 % случаев. Ключ — `класс|вид`",
             "(`FormField|InputField`), у спутника — `свойство|вид` (`extendedTooltip|Label`),",
             "у формы — `Form|`; путь свойства вида — `extInfo/имя`.", '"""', "", "DEFAULTS = {"]
    for ключ in sorted(таблица):
        текст.append(f"    {ключ!r}: {{")
        for путь, значение in sorted(таблица[ключ].items()):
            текст.append(f"        {путь!r}: {значение!r},")
        текст.append("    },")
    текст.append("}")
    with open(os.path.join(ROOT, "meta", "acl", "edt_form_defaults.py"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(текст) + "\n")
    print(f"видов в таблице: {len(таблица)}")


def main(argv):
    шаг = int(argv[argv.index("--шаг") + 1]) if "--шаг" in argv else 1
    if "--круг" in argv:
        round_trip(argv[argv.index("--круг") + 1], шаг)
    elif "--умолчания" in argv:
        источники = [(argv[0], argv[1], шаг)]
        if "--и" in argv:                            # второй источник — каждая форма
            i = argv.index("--и")
            источники.append((argv[i + 1], argv[i + 2], 1))
        learn(источники)
    else:
        check(argv[0], argv[1], шаг)


if __name__ == "__main__":
    main(sys.argv[1:])
