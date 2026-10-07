"""Вложенные сущности: ресурс, значение перечисления, табличная часть.

Проверяются тем же приёмом, что и реквизит: разобрать написанное платформой
обратно в доменную спецификацию, собрать инструментом и сравнить байты.
Эталоны — вся конфигурация: 7216 ресурсов, 11 629 значений перечислений,
2891 табличная часть вместе с их реквизитами.

Непокрытое считается и печатается, а не прячется: часть эталонов несёт то,
чего домен не выражает (настоящее значение заполнения, параметры выбора,
многоязычный синоним), — такие пропускаются.
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping  # noqa: E402
from meta.domain import model as dm  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Spec  # noqa: E402
from meta.infra import serializer  # noqa: E402
from meta.tests import corpus  # noqa: E402
from meta.tests.test_attribute import (  # noqa: E402
    NESTED_TAGS,
    SET_VALUE_RE,
    spec_from_xml,
    unescape,
)

SOURCES = corpus.CORPUS

FILL_CHECKING_BACK = {"DontCheck": "НеПроверять", "ShowError": "ВыдаватьОшибку"}
USE_FOR_BACK = {"ForItem": "ДляЭлемента", "ForFolder": "ДляГруппы",
                "ForFolderAndItem": "ДляГруппыИЭлемента"}


def need_corpus():
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {SOURCES}")


def files(folder):
    path = os.path.join(SOURCES, folder)
    for name in sorted(os.listdir(path)):
        if name.endswith(".xml"):
            yield open(os.path.join(path, name),
                       encoding="utf-8-sig").read().replace("\r\n", "\n"), name


def text_of(block, tag):
    """Значение простого тега как есть — без обрезки: в комментариях бывает пробел."""
    found = re.search(rf"<{tag}(?:\s[^>]*)?(?:/>|>(.*?)</{tag}>)", block, re.S)
    return None if not found else unescape(found.group(1) or "")


def multilang(block, tag):
    found = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    if not found:
        return ""
    pairs = re.findall(r"<v8:lang>(\w+)</v8:lang>\s*<v8:content>([^<]*)</v8:content>",
                       found.group(1))
    return {lang: unescape(text) for lang, text in pairs} if pairs else ""


def test_all_resources_bytewise():
    """Ресурс регистра сведений: 28 свойств, те же умолчания, что у измерения."""
    need_corpus()
    matched = skipped = 0
    block_re = re.compile(r"^\t{3}<Resource uuid=\"([^\"]+)\">\n.*?^\t{3}</Resource>",
                          re.M | re.S)
    for text, _ in files("InformationRegisters"):
        for found in block_re.finditer(text):
            block, uuid = found.group(0), found.group(1)
            # ресурс лежит на том же уровне, что и реквизит объекта, — разбирается
            # тем же разборщиком, надо только назвать тег его именем
            body = block.replace("<Resource ", "<Attribute ").replace(
                "</Resource>", "</Attribute>")
            if (any(re.search(rf"<{t}>", block) for t in NESTED_TAGS)
                    or SET_VALUE_RE.search(block)):
                skipped += 1
                continue
            spec = spec_from_xml(body, "РегистрСведений")
            spec.fields.pop("использование", None)
            node = mapping.translate_node(
                kind_of("Ресурс").fill(Spec("Ресурс", spec.fields)),
                uuid, "РегистрСведений")
            assert "\n".join(serializer.node_to_lines(node, 3)) == block
            matched += 1
    print(f"ресурсов сверено {matched}, пропущено {skipped}")
    assert matched > 3000


def test_all_enum_values_bytewise():
    """Значение перечисления: четыре свойства и цвет, всегда «Авто»."""
    need_corpus()
    matched = skipped = 0
    block_re = re.compile(r"^\t{3}<EnumValue uuid=\"([^\"]+)\">\n.*?^\t{3}</EnumValue>",
                          re.M | re.S)
    for text, _ in files("Enums"):
        for found in block_re.finditer(text):
            block, uuid = found.group(0), found.group(1)
            synonym = multilang(block, "Synonym")
            # многоязычный синоним домен выражает, но разбирать его здесь нечем:
            # порядок языков в файле не совпадает с порядком в словаре
            if isinstance(synonym, dict) and len(synonym) > 1:
                skipped += 1
                continue
            spec = Spec("ЗначениеПеречисления", {
                "имя": text_of(block, "Name"),
                "синоним": synonym,
                "комментарий": text_of(block, "Comment") or ""})
            node = mapping.translate_node(
                kind_of("ЗначениеПеречисления").fill(spec), uuid, "Перечисление")
            assert "\n".join(serializer.node_to_lines(node, 3)) == block
            matched += 1
    print(f"значений перечислений сверено {matched}, пропущено {skipped}")
    assert matched > 10000


def test_all_tabular_sections_bytewise():
    """Табличная часть вместе со своими реквизитами.

    Блок `StandardAttributes` из эталона убирается: его пишет платформа, когда
    стандартный реквизит «номер строки» настроили руками, а у только что
    созданной табличной части его нет — так же, как у нового объекта.
    """
    need_corpus()
    # Хозяева берутся у самого вида, а не перечисляются здесь: расширив
    # `HOSTS`, покрытие расширишь заодно. Со списком, прибитым гвоздями,
    # добавление хозяина требовало бы вспомнить ещё и про этот тест — а состав
    # свойств у нового хозяина может оказаться другим, и сверка бы молчала.
    from meta.acl.vocabulary import FOLDERS
    from meta.domain.kinds import kind_of

    kinds = {FOLDERS[host]: host for host in kind_of("ТабличнаяЧасть").HOSTS
             if host in FOLDERS}
    block_re = re.compile(
        r"^\t{3}<TabularSection uuid=\"([^\"]+)\">\n.*?^\t{3}</TabularSection>",
        re.M | re.S)
    standard_re = re.compile(
        r"\n\t{5}<StandardAttributes>.*?\n\t{5}</StandardAttributes>", re.S)
    attribute_re = re.compile(
        r"^\t{5}(<Attribute uuid=\"([^\"]+)\">.*?\n\t{5}</Attribute>)", re.M | re.S)
    matched = skipped = 0
    for folder, host in kinds.items():
        for text, _ in files(folder):
            for found in block_re.finditer(text):
                block, uuid = found.group(0), found.group(1)
                properties = block.split("</Properties>", 1)[0].split("<Properties>", 1)[1]
                owner = re.search(r'name="\w+TabularSection\.([^.]+)\.', block).group(1)
                fields = {
                    "имя": text_of(properties, "Name"),
                    "синоним": multilang(properties, "Synonym"),
                    "комментарий": text_of(properties, "Comment") or "",
                    "подсказка": multilang(properties, "ToolTip"),
                    "проверкаЗаполнения":
                        FILL_CHECKING_BACK[text_of(properties, "FillChecking")],
                    "длинаНомераСтроки": text_of(properties, "LineNumberLength"),
                }
                use = text_of(properties, "Use")
                if use is not None:
                    fields["использование"] = USE_FOR_BACK[use]
                attributes, complex_value = [], False
                for child in attribute_re.finditer(block):
                    body = child.group(1)
                    if (any(re.search(rf"<{t}>", body) for t in NESTED_TAGS)
                            or SET_VALUE_RE.search(body)):
                        complex_value = True
                        break
                    level = "\n".join(line[2:] if line.startswith("\t\t") else line
                                      for line in body.split("\n"))
                    attributes.append(spec_from_xml(
                        level, dm.вид_табличной_части(host)))
                if complex_value:
                    skipped += 1
                    continue
                fields["реквизиты"] = attributes
                queue = re.findall(r"<xr:(?:TypeId|ValueId)>([^<]+)<", block)
                queue += [child.group(2) for child in attribute_re.finditer(block)]
                node = mapping.translate_node(
                    kind_of("ТабличнаяЧасть").fill(
                        Spec("ТабличнаяЧасть", fields), dm.Host(host, owner)),
                    uuid, host, owner, lambda q=queue: q.pop(0))
                assert ("\n".join(serializer.node_to_lines(node, 3))
                        == standard_re.sub("", block))
                matched += 1
    print(f"табличных частей сверено {matched}, пропущено {skipped}")
    assert matched > 2000


def test_register_with_dimension_and_resource():
    """Регистр заводится сразу с измерением и ресурсом — и это снимает замечание."""

    class World:
        def object_exists(self, kind, name):
            return True

    spec = Spec("РегистрСведений", {
        "имя": "мой_Проба",
        "измерения": [Spec("Измерение", {"имя": "Организация",
                                         "тип": dm.StringType(10)})],
        "ресурсы": [Spec("Ресурс", {"имя": "Сумма", "тип": dm.NumberType(15, 2)})],
    })
    kind = kind_of("РегистрСведений")
    codes = [f.code for f in kind.check(kind.fill(spec), World())]
    assert "РЕГИСТР-БЕЗ-ИЗМЕРЕНИЙ" not in codes, codes

    ids = iter(f"id{n}" for n in range(100))
    card = mapping.translate(kind.fill(spec), "x", new_id=lambda: next(ids))
    lines = "\n".join(serializer.card_to_lines(card))
    # порядок в выгрузке — ресурсы, реквизиты, измерения (снято с 400 регистров)
    assert lines.index("<Resource ") < lines.index("<Dimension ")


def test_catalog_with_tabular_section():
    """Справочник заводится сразу с табличной частью и её реквизитами."""
    spec = Spec("Справочник", {
        "имя": "мой_Проба",
        "табличныеЧасти": [Spec("ТабличнаяЧасть", {
            "имя": "Строки",
            "реквизиты": [Spec("Реквизит", {"имя": "Товар",
                                            "тип": dm.StringType(50)})],
        })],
    })
    ids = iter(f"id{n}" for n in range(100))
    card = mapping.translate(kind_of("Справочник").fill(spec), "x",
                             new_id=lambda: next(ids))
    lines = "\n".join(serializer.card_to_lines(card))
    assert ('name="CatalogTabularSection.мой_Проба.Строки"' in lines)
    assert ('name="CatalogTabularSectionRow.мой_Проба.Строки"' in lines)
    # у реквизита табличной части нет ни «использования», ни свойств заполнения
    attribute = lines.split("<TabularSection ", 1)[1].split("<Attribute ", 1)[1]
    assert "<Use>" not in attribute, attribute
    assert "<FillValue" not in attribute, attribute
    assert "<DataHistory>Use</DataHistory>" in attribute


def test_tabular_section_refuses_unknown_host():
    """Состав замерен у четырёх видов; про остальных — сказать вслух.

    У отчёта и обработки состав замерен на 160 и 365 табличных частях, по
    одному варианту на каждый. Непокрытым остаётся, среди прочих, план обмена —
    на нём проверка и держится.
    """
    kind = kind_of("ТабличнаяЧасть")
    codes = [f.code for f in kind.check(
        kind.fill(Spec("ТабличнаяЧасть", {"имя": "Строки"})), None,
        ("ПланОбмена", None))]
    assert "ТАБЛИЧНАЯЧАСТЬ-ВИД-ХОЗЯИНА" in codes, codes
