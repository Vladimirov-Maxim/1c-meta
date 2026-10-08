"""Метамодель EDT: какие свойства у класса, в каком порядке они пишутся и что
у них по умолчанию.

EDT хранит объект метаданных объектом EMF и пишет его по правилам EMF:

* свойства — в порядке `eAllStructuralFeatures`: свойства суперклассов (в
  порядке объявления суперклассов, каждый — один раз), затем свои;
* исключение одно — `producedTypes` (порождаемые типы) EDT пишет первым;
* свойство, равное умолчанию EMF, не пишется: `false`, `0`, первый литерал
  перечисления, пустой список, пустая строка — у атрибута с явным умолчанием
  в метамодели умолчание оно;
* служебные свойства (`transient`, `derived`, `volatile`) не пишутся никогда;
* свойства типа `Uuid` и свойства-идентификаторы (`id` в метамодели) —
  атрибутами XML (`uuid`, `typeId`, `valueTypeId`, `id`), остальное — элементами.

Классы названы полными именами (`com._1c.g5.v8.dt.metadata.mdclass.Catalog`):
короткое имя (`Field`, `Parameter`, `EnumValue`) бывает в разных пакетах.
Пакет элемента XML — по адресу его пространства имён (`packages`).

Таблица снята с метамодели установленного EDT (`tools/edt_model_from_xcore.py`
-> `edt_metamodel.py`), правила порядка и умолчаний сверены со всеми
карточками и формами проекта EDT крупной типовой конфигурации (23 375 и
11 058, `tools/edt_order_check.py`) — ни одного расхождения.
"""

import functools
from dataclasses import dataclass

from ..domain.model import Refuse

#: Таблица не хранится в репозитории: она снята с моделей установленного 1C:EDT
#: и создаётся на месте при установке инструмента.
NO_TABLE = ("таблица метамодели EDT не сгенерирована — без неё запись в проект EDT и показ его объектов и форм невозможны (проверки и нормализация работают). "
            "Создайте её из установленного 1C:EDT: py -3 tools/edt_model_from_xcore.py "
            "(без аргумента — пул p2 пользователя, %USERPROFILE%\\.p2\\pool\\plugins)")

#: Свойства, которые EDT пишет первыми, вопреки порядку EMF.
FIRST = ("producedTypes",)

#: Свойства, которые EDT пишет и равными умолчанию: у класса свой `eIsSet`.
#: Замер — все формы проекта EDT крупной типовой конфигурации (9 562 записи
#: `false` у групп-страниц, ни одной группы-страницы без свойства).
WRITTEN_AT_DEFAULT = {("com._1c.g5.v8.dt.form.model.PageGroupExtInfo", "scrollOnCompress")}

#: Типы, которые пишутся атрибутом XML.
XML_ATTRIBUTE_TYPES = ("com._1c.g5.v8.dt.mcore.Uuid",)

#: Примитивы EMF с ненулевым умолчанием; у объектных типов (`BigDecimal`,
#: `String`, `Date`) умолчание — null, и записанное значение умолчанием не бывает.
PRIMITIVE_DEFAULTS = {"boolean": "false", "int": "0", "long": "0", "short": "0", "byte": "0",
                      "double": "0.0", "float": "0.0"}


@dataclass(frozen=True)
class Feature:
    name: str
    type: str
    kind: str            # attribute | contains | refers
    many: bool
    required: bool
    default: str | None
    unsettable: bool
    id: bool = False


@functools.cache
def _table():
    try:
        from .edt_metamodel import METAMODEL
    except ImportError as нет:
        raise Refuse(NO_TABLE) from нет
    return METAMODEL


def available():
    """Таблица метамодели EDT создана — с проектом EDT можно работать."""
    try:
        _table()
    except Refuse:
        return False
    return True


def classes():
    return _table()["classes"]


def enums():
    return _table()["enums"]


def package_of(uri):
    """Пакет метамодели по адресу пространства имён XML; незнакомый — None."""
    return _table()["packages"].get(uri)


def class_of(uri, local):
    """Полное имя класса по пространству имён и имени элемента или `xsi:type`."""
    пакет = package_of(uri)
    return f"{пакет}.{local}" if пакет else None


@functools.cache
def features(cls):
    """Сохраняемые свойства класса по порядку записи; класса нет — None."""
    все = classes()
    if cls not in все:
        return None
    собрано, имена = [], set()

    def обойти(имя, виденные):
        if имя in виденные or имя not in все:
            return
        виденные.add(имя)
        for супер in все[имя]["supers"]:
            обойти(супер, виденные)
        for f in все[имя]["features"]:
            if f["name"] not in имена and not f["service"]:
                имена.add(f["name"])
                собрано.append(Feature(f["name"], f["type"], f["kind"], f["many"], f["required"],
                                       f["default"], f["unsettable"], f["id"]))

    обойти(cls, set())
    первые = [f for имя in FIRST for f in собрано if f.name == имя]
    return tuple(первые + [f for f in собрано if f.name not in FIRST])


@functools.cache
def _positions(cls):
    return {f.name: i for i, f in enumerate(features(cls) or ())}


def position(cls, name):
    """Место свойства в порядке записи класса; нет такого — -1."""
    return _positions(cls).get(name, -1)


def feature(cls, name):
    for f in features(cls) or ():
        if f.name == name:
            return f
    return None


def is_xml_attribute(f):
    return f.kind == "attribute" and (f.type in XML_ATTRIBUTE_TYPES or f.id)


def default_text(f):
    """Текст умолчания атрибута, как его записал бы EMF; у списка и строки без
    явного умолчания — None (пустое не пишется)."""
    if f.default is not None:
        return f.default
    if f.type in PRIMITIVE_DEFAULTS:
        return PRIMITIVE_DEFAULTS[f.type]
    литералы = enums().get(f.type)
    if литералы:
        return литералы[0]
    return None


def is_default(f, text, cls=None):
    """Значение атрибута равно умолчанию EMF — такое EDT не пишет. `cls` —
    класс, у которого свойство пишется и при умолчании (`WRITTEN_AT_DEFAULT`)."""
    if f.unsettable or f.many or (cls, f.name) in WRITTEN_AT_DEFAULT:
        return False
    умолчание = default_text(f)
    return умолчание is not None and text == умолчание


def is_abstract(cls):
    return classes().get(cls, {}).get("abstract", False)
