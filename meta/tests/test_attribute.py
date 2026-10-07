"""Реквизит: сверка со всеми реквизитами конфигурации.

Тот же приём, что у сверки карточек: разобрать написанное платформой
в доменную спецификацию, собрать обратно и сравнить. Эталонов в замеренной
конфигурации 27 548 — и они покрывают всё, что бывает: шесть примитивных
типов с квалификаторами, ссылки, составные типы, все значения
свойств-перечислений.

Отдельно считается непокрытое. Часть реквизитов несёт то, чего домен не
выражает (параметры выбора, связи по типу, формат): такие не сверяются,
но и не прячутся — их число печатается.
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from collections import OrderedDict  # noqa: E402

from meta.acl import mapping, schema, vocabulary  # noqa: E402
from meta.domain import model as dm  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Refuse, Spec  # noqa: E402
from meta.infra import serializer  # noqa: E402
from meta.tests.corpus import CORPUS as SOURCES  # noqa: E402

# Свойства, которые домен не выражает: у них своя вложенная структура
# (ссылки на параметры выбора, связь по типу). Если такое свойство не пусто,
# сверять реквизит нечем — и это честнее, чем подогнать сравнение.
NESTED_TAGS = ("ChoiceParameterLinks", "ChoiceParameters", "LinkByType")

# Многоязычные свойства: устроены как синоним и читаются так же.
MULTILANG_TAGS = ("Synonym", "Format", "EditFormat", "ToolTip")

# Значение заполнения бывает настоящим (а не «пусто»/«не задано») — такое
# домен не выражает, и подгонять сравнение под это нельзя.
SET_VALUE_RE = re.compile(r'<(FillValue|MinValue|MaxValue)( xsi:type="(?!xs:string"/)[^>]*)>')

ENUMS_BACK = {field.tag: {v: k for k, v in field.dictionary.items()}
         for field in schema.SCHEMA["Реквизит"].fields if field.dictionary}
LENGTH_BACK = {v: k for k, v in vocabulary.STRING_LENGTH.items()}
DATE_BACK = {v: k for k, v in vocabulary.DATE_PARTS.items()}
PLATFORM_BACK = {v: k for k, v in vocabulary.PLATFORM_TYPES.items()}
FOREIGN_BACK = {f"{p}:{m}": name
               for name, (p, _, m) in vocabulary.FOREIGN_NAMESPACES.items()}


def unescape(text):
    """Обратное к экранированию сериализатора: читаем то же, что он пишет."""
    return (text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def type_from_xml(text):
    """Содержимое узла <Type> -> тип на языке домена.

    Квалификаторы ищутся во всём узле, а не «за своим типом»: у составного
    типа они собраны в конце, после всех перечисленных типов.
    """
    types = []
    for tag, foreign, name in re.findall(
            r"<v8:(Type|TypeSet)( xmlns:[^>]+)?>([^<]+)</v8:\1>", text):
        if foreign:
            types.append(dm.PlatformType(FOREIGN_BACK[name]))
            continue
        if name == "xs:string":
            m = re.search(r"<v8:Length>(\d+)</v8:Length>\s*"
                          r"<v8:AllowedLength>(\w+)</v8:AllowedLength>", text)
            types.append(dm.StringType(int(m.group(1)),
                                  LENGTH_BACK[m.group(2)] == "Фиксированная"))
        elif name == "xs:decimal":
            m = re.search(r"<v8:Digits>(\d+)</v8:Digits>\s*"
                          r"<v8:FractionDigits>(\d+)</v8:FractionDigits>\s*"
                          r"<v8:AllowedSign>(\w+)</v8:AllowedSign>", text)
            types.append(dm.NumberType(int(m.group(1)), int(m.group(2)),
                                 m.group(3) == "Nonnegative"))
        elif name == "xs:dateTime":
            m = re.search(r"<v8:DateFractions>(\w+)</v8:DateFractions>", text)
            types.append(dm.DateType(DATE_BACK[m.group(1)]))
        elif name == "xs:boolean":
            types.append(dm.BooleanType())
        elif name.startswith("v8:"):
            types.append(dm.PlatformType(PLATFORM_BACK[name]))
        elif name.startswith("cfg:"):
            types.append(mapping.parse_type_notation(name, tag == "TypeSet"))
        else:
            raise Refuse(f"тип «{name}» не разобран")
    return types[0] if len(types) == 1 else types


def spec_from_xml(block, host_kind):
    properties = re.search(r"<Properties>(.*?)\n\t{4}</Properties>", block, re.S).group(1)
    texts = dict(re.findall(r"^\t{5}<(\w+)>(.*?)</\1>$", properties, re.M))
    fields = {"имя": texts["Name"],
            "комментарий": unescape(texts.get("Comment", ""))}

    type_node = re.search(r"<Type>(.*?)\n\t{5}</Type>", properties, re.S)
    fields["тип"] = type_from_xml(type_node.group(1)) if type_node else dm.AnyType()

    for field in schema.SCHEMA["Реквизит"].fields:
        value = texts.get(field.tag)
        if field.tag in MULTILANG_TAGS:
            node = re.search(rf"<{field.tag}(/>|>.*?</{field.tag}>)",
                             properties, re.S).group(0)
            pairs = re.findall(
                r"<v8:lang>(.*?)</v8:lang>\s*<v8:content>(.*?)</v8:content>", node, re.S)
            fields[field.domain] = (OrderedDict(
                (lang_code, unescape(s)) for lang_code, s in pairs) if pairs else "")
        elif field.value_kind == vocabulary.BOOLEAN:
            fields[field.domain] = value == "true"
        elif field.value_kind == vocabulary.VALUE:
            # «Не задано» и «задано пустой строкой» — разные состояния,
            # и читать их надо из файла, а не подставлять умолчанием.
            m = re.search(rf"<{field.tag}([^>]*)/>", properties)
            attrs = m.group(1).strip() if m else ""
            fields[field.domain] = "" if 'xsi:type="xs:string"' in attrs else None
        elif field.dictionary is not None and value is not None:
            fields[field.domain] = ENUMS_BACK[field.tag][value]
        elif field.value_kind == vocabulary.TEXT and field.domain not in fields:
            fields[field.domain] = unescape(value or "")
    # Состав свойств зависит от вида-хозяина: чего у него нет, того и в
    # спецификации быть не должно, иначе сверяли бы не то.
    from meta.domain.kinds import AttributeKind
    for field, kinds in AttributeKind.APPLIES_TO.items():
        if host_kind not in kinds:
            fields.pop(field, None)
    return Spec("Реквизит", fields)


def build(block, host_kind):
    uuid = re.match(r'<Attribute uuid="([^"]+)">', block).group(1)
    spec = kind_of("Реквизит").fill(spec_from_xml(block, host_kind))
    node = mapping.translate_node(spec, uuid, host_kind)
    return "\n".join(serializer.node_to_lines(node, 3))


def test_all_attributes_bytewise():
    if not os.path.isdir(os.path.join(SOURCES, "Catalogs")):
        pytest.skip(f"пропущен: нет выгрузки {SOURCES}")
    total = checked = skipped = mismatched = 0
    first = None
    from meta.domain.kinds import AttributeKind
    # «ТабличнаяЧасть» тоже вид хозяина, но каталога в выгрузке у неё нет:
    # её реквизиты сверяются отдельным тестом, изнутри объектов.
    kinds = [(vocabulary.FOLDERS[k], k) for k in AttributeKind.HOSTS
            if k in vocabulary.FOLDERS
            and os.path.isdir(os.path.join(SOURCES, vocabulary.FOLDERS[k]))]
    for folder, kind in kinds:
        for filename in sorted(os.listdir(os.path.join(SOURCES, folder))):
            if not filename.endswith(".xml"):
                continue
            text = open(os.path.join(SOURCES, folder, filename),
                            encoding="utf-8-sig").read().replace("\r\n", "\n")
            for m in re.finditer(
                    r'^\t{3}(<Attribute uuid="[^"]+">.*?\n\t{3}</Attribute>)',
                    text, re.S | re.M):
                block = m.group(1)
                total += 1
                if (any(re.search(rf"<{s}>", block) for s in NESTED_TAGS)
                        or SET_VALUE_RE.search(block)):
                    skipped += 1
                    continue
                reference = "\t\t\t" + block
                if build(block, kind) != reference:
                    mismatched += 1
                    first = first or "{}/{}: {}".format(
                        folder, filename, re.search(r"<Name>([^<]+)", block).group(1))
                else:
                    checked += 1
    assert mismatched == 0, f"разошлось {mismatched} из {total}, первое: {first}"
    print(f"сверено {checked} из {total} по {len(kinds)} видам, "
            f"не выражается доменом {skipped}")


# --- запись: врезка в существующую карточку ----------------------------------

CARD_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\r\n'
    '<MetaDataObject>\r\n'
    '\t<Catalog uuid="c0000000-0000-0000-0000-000000000001">\r\n'
    '\t\t<Properties>\r\n'
    '\t\t\t<Name>мой_Проверка</Name>\r\n'
    '\t\t</Properties>\r\n'
    '\t\t<ChildObjects>\r\n'
    '\t\t\t<Attribute uuid="a0000000-0000-0000-0000-000000000001">\r\n'
    '\t\t\t\t<Properties>\r\n'
    '\t\t\t\t\t<Name>Существующий</Name>\r\n'
    '\t\t\t\t</Properties>\r\n'
    '\t\t\t</Attribute>\r\n'
    '\t\t\t<TabularSection uuid="b0000000-0000-0000-0000-000000000001">\r\n'
    '\t\t\t</TabularSection>\r\n'
    '\t\t</ChildObjects>\r\n'
    '\t</Catalog>\r\n'
    '</MetaDataObject>'
)


def sandbox():
    import tempfile
    root = tempfile.mkdtemp(prefix="meta-атр-")
    open(os.path.join(root, "Configuration.xml"), "w",
            encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\r\n<MetaDataObject>\r\n'
        '\t<Configuration>\r\n\t\t<ChildObjects>\r\n'
        '\t\t\t<Catalog>мой_Проверка</Catalog>\r\n'
        '\t\t</ChildObjects>\r\n\t</Configuration>\r\n</MetaDataObject>')
    os.makedirs(os.path.join(root, "Catalogs"))
    open(os.path.join(root, "Catalogs", "мой_Проверка.xml"), "w",
            encoding="utf-8-sig", newline="").write(CARD_XML)
    return root


def job(name="мой_Технический", vtype=None, host="мой_Проверка", **extra):
    """Задание на врезку: адрес хозяина и спецификация реквизита.

    Тот же вид задания, что у добавления любого другого ребёнка: `attributes`
    — частный случай `additions` с адресом из одной пары, и сценарий у них
    один: два сценария разошлись бы.
    """
    fields = {"имя": name, "синоним": "(Мой) Технический",
            "тип": vtype or dm.BooleanType()}
    fields.update(extra)
    return ([("Справочник", host)], Spec("Реквизит", fields))


def platform(root):
    from meta.infra.designer import DesignerDump
    return DesignerDump(root)


def card(root):
    return open(os.path.join(root, "Catalogs", "мой_Проверка.xml"),
                   encoding="utf-8-sig", newline="").read()


def test_attribute_appended_to_group():
    import shutil

    from meta.application.add_child.use_case import AddChildUseCase
    root = sandbox()
    try:
        result = AddChildUseCase(platform(root)).execute([job()], apply_now=True)
        assert result.ok, [str(f) for f in result.errors]
        after = card(root)
        lines = after.split("\r\n")
        # новый реквизит — после существующего и перед табличной частью
        # Новый реквизит ищется по имени: идентификатор порождает сценарий,
        # и задавать его снаружи ради проверки места незачем.
        name_at = lines.index("\t\t\t\t\t<Name>мой_Технический</Name>")
        i = max(n for n, s in enumerate(lines[:name_at])
                if s.startswith("\t\t\t<Attribute uuid="))
        assert lines[i - 1] == "\t\t\t</Attribute>", lines[i - 3:i + 1]
        end = lines.index("\t\t\t</Attribute>", i)
        assert lines[end + 1].startswith("\t\t\t<TabularSection")
        # прежнее содержимое не тронуто
        for line in CARD_XML.split("\r\n"):
            assert line in lines, line
        assert "<Use>ForItem</Use>" in after, "справочнику положено «использование»"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_attribute_name_taken():
    import shutil

    from meta.application.add_child.use_case import AddChildUseCase
    root = sandbox()
    try:
        result = AddChildUseCase(platform(root)).execute([job("Существующий")], apply_now=True)
        codes = [f.code for f in result.findings]
        assert "РЕКВИЗИТ-ИМЯ-ЗАНЯТО" in codes, codes
        assert result.plan is None and card(root) == CARD_XML
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_host_missing():
    import shutil

    from meta.application.add_child.use_case import AddChildUseCase
    root = sandbox()
    try:
        result = AddChildUseCase(platform(root)).execute([job(host="мой_НетТакого")], apply_now=True)
        assert "РЕКВИЗИТ-ХОЗЯИНА-НЕТ" in [f.code for f in result.findings]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_two_attributes_stack():
    import shutil

    from meta.application.add_child.use_case import AddChildUseCase
    root = sandbox()
    try:
        result = AddChildUseCase(platform(root)).execute([job("мой_Первый"), job("мой_Второй")],
            apply_now=True)
        assert result.ok, [str(f) for f in result.errors]
        after = card(root)
        assert after.count("<Attribute uuid=") == 3, "реквизиты затёрли друг друга"
        assert after.index("мой_Первый") < after.index("мой_Второй")
        assert len(result.written) == 1, "карточка одна, файл должен быть один"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_attribute_preview_writes_nothing():
    import shutil

    from meta.application.add_child.use_case import AddChildUseCase
    root = sandbox()
    try:
        result = AddChildUseCase(platform(root)).execute([job()])
        assert result.written == [] and card(root) == CARD_XML
        # Строки две: пояснение и сам файл. Без пояснения просмотр показывал
        # бы только «изменить файл (N Б)» и не отвечал на главный вопрос
        # «то ли записано». Вид пункта назван рядом с именем: в одном задании
        # бывают выбираемое поле, отбор и поле порядка с одним и тем же полем,
        # и три одинаковые строки плана различить было бы нечем.
        assert result.plan.describe() == [
            "добавить «мой_Технический» (Реквизит) в Справочник.мой_Проверка",
            result.plan.describe()[1]]
    finally:
        shutil.rmtree(root, ignore_errors=True)
