"""Сверка таблицы метамодели EDT с проектом EDT: порядок свойств и умолчания.

Для каждой карточки `.mdo` проекта: класс каждого элемента выводится из
метамодели (корень — вид, ребёнок — тип своего свойства, `xsi:type` — явно),
и проверяется, что

* каждый элемент — свойство своего класса (неизвестных нет);
* свойства идут в порядке таблицы (`acl.edt_model.order`);
* ни одно записанное значение атрибута не равно умолчанию EMF;
* атрибутом XML записаны ровно свойства-атрибуты XML.

Запуск: `py -3 tools/edt_order_check.py <каталог исходников EDT> [предел файлов]`.
Печатает сводку расхождений по виду — исключения, которые таблица ещё не знает.
"""

import collections
import os
import sys

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.acl import edt_model  # noqa: E402

XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
#: Приставка длинного пути Windows; на других площадках — пусто.
SUFFIXES = tuple(os.environ.get("EDT_SUFFIXES", ".mdo").split(","))
LONG = r"\\?" + "\\" if os.name == "nt" else ""


def local(tag):
    return tag.rpartition("}")[2]


def class_of_element(element, declared=None):
    """Класс элемента: `xsi:type` (приставка — по пространствам имён элемента),
    иначе объявленный тип свойства; у корня — пространство имён и имя тега."""
    явный = element.get(XSI)
    if явный:
        приставка, _, имя = явный.rpartition(":")
        return edt_model.class_of(element.nsmap.get(приставка or None), имя)
    if declared:
        return declared
    uri, _, имя = element.tag[1:].partition("}")
    return edt_model.class_of(uri, имя)


def short(класс):
    return (класс or "?").rsplit(".", 1)[-1]


def check(element, класс, путь, расхождения):
    свойства = edt_model.features(класс)
    if свойства is None:
        расхождения[("класс неизвестен", str(класс))].append(путь)
        return
    по_имени = {f.name: f for f in свойства}
    for имя in element.attrib:
        if имя == XSI:
            continue
        f = по_имени.get(local(имя))
        if f is None:
            расхождения[("атрибут неизвестен", f"{short(класс)}.{local(имя)}")].append(путь)
        elif not edt_model.is_xml_attribute(f):
            расхождения[("атрибутом, а не элементом", f"{short(класс)}.{f.name}")].append(путь)
    последний = -1
    for ребёнок in element:
        if not isinstance(ребёнок.tag, str):
            continue
        имя = local(ребёнок.tag)
        f = по_имени.get(имя)
        if f is None:
            расхождения[("элемент неизвестен", f"{short(класс)}.{имя}")].append(путь)
            continue
        if edt_model.is_xml_attribute(f):
            расхождения[("элементом, а не атрибутом", f"{short(класс)}.{имя}")].append(путь)
        место = edt_model.position(класс, имя)
        if место < последний:
            расхождения[("порядок", f"{short(класс)}.{имя}")].append(путь)
        последний = место
        if f.kind == "contains":
            check(ребёнок, class_of_element(ребёнок, f.type), путь, расхождения)
        elif f.kind == "attribute" and not f.many and len(ребёнок) == 0:
            if edt_model.is_default(f, ребёнок.text or "", класс):
                расхождения[("умолчание записано", f"{short(класс)}.{имя}={ребёнок.text}")].append(путь)


def main(argv):
    root = argv[0]
    предел = int(argv[1]) if len(argv) > 1 else None
    расхождения = collections.defaultdict(list)
    файлов = 0
    for папка, _, имена in os.walk(root):
        for имя in имена:
            if not имя.endswith(SUFFIXES):
                continue
            путь = os.path.join(папка, имя)
            # приставка «\\?\» — пути проекта EDT бывают длиннее 260 знаков
            with open(LONG + os.path.abspath(путь), "rb") as файл:
                корень = etree.fromstring(файл.read())
            класс = class_of_element(корень)
            if класс is None:                         # не объект EMF: схема компоновки, настройки
                continue
            check(корень, класс, os.path.relpath(путь, root), расхождения)
            файлов += 1
            if предел and файлов >= предел:
                break
        if предел and файлов >= предел:
            break
    print(f"карточек: {файлов}, видов расхождений: {len(расхождения)}")
    for (что, где), пути in sorted(расхождения.items(), key=lambda x: -len(x[1])):
        print(f"{len(пути):7}  {что:28} {где}   например {пути[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
