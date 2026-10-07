"""Прикладные объекты: справочник, перечисление, регистр сведений, документ.

Эталоны здесь не из корпуса, а получены опытом: в пустой базе конфигуратором
созданы объекты, к которым не притрагивались, и выгружены. Это и есть ответ
на вопрос «каким платформа создаёт новый объект» — по тысяче настоящих
справочников его не выведешь, у каждого свои настройки.

Сверка побайтная, включая порождаемые типы: их идентификаторы берутся из
эталона, чтобы сравнивать всё остальное.
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
from meta.tests.conftest import ТЕСТ  # noqa: E402

REFERENCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны")

# вид -> (файл эталона, имя объекта, тег элемента)
CASES = {
    "Справочник": ("Справочник-платформа.xml", "мой_Эталон", "Catalog"),
    "Перечисление": ("Перечисление-платформа.xml", "мой_ЭталонПеречисление", "Enum"),
    "РегистрСведений": ("РегистрСведений-платформа.xml", "мой_ЭталонРС",
                        "InformationRegister"),
    "Документ": ("Документ-платформа.xml", "мой_ЭталонДокумент", "Document"),
}


def reference(kind):
    filename, name, tag = CASES[kind]
    path = os.path.join(REFERENCES, filename)
    if not os.path.isfile(path):
        pytest.skip(f"пропущен: нет {path}")
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    return text, name, tag


def build(kind, text, name, tag):
    """Собрать карточку инструментом на идентификаторах эталона."""
    uid = re.search(rf'<{tag} uuid="([^"]+)"', text).group(1)
    ids = re.findall(r"<xr:(?:TypeId|ValueId)>([^<]+)<", text)
    synonym = re.search(
        r"<Synonym>\s*<v8:item>\s*<v8:lang>ru</v8:lang>\s*<v8:content>([^<]*)</v8:content>",
        text)
    fields = {"имя": name}
    if synonym:
        fields["синоним"] = {"ru": synonym.group(1)}
    queue = list(ids)
    card = mapping.translate(kind_of(kind).fill(Spec(kind, fields)), uid,
                             new_id=lambda: queue.pop(0))
    return "\n".join(serializer.card_to_lines(card))


def test_catalog_matches_platform_reference():
    text, name, tag = reference("Справочник")
    assert build("Справочник", text, name, tag) == text


def test_enum_matches_platform_reference():
    text, name, tag = reference("Перечисление")
    assert build("Перечисление", text, name, tag) == text


def test_register_matches_platform_reference():
    """У эталонного регистра есть измерение — оно добавлено руками.

    Регистр без измерений конфигуратор сохранить не даёт, поэтому эталон иначе
    не получить. Измерения создаются отдельной операцией, здесь сверяется
    карточка без них: раздел детей приводится к пустому.
    """
    text, name, tag = reference("РегистрСведений")
    without_children = re.sub(r"<ChildObjects>.*?</ChildObjects>",
                              "<ChildObjects/>", text, flags=re.S)
    assert build("РегистрСведений", text, name, tag) == without_children


def test_register_warns_without_dimensions():
    """Регистр без измерений — предупреждение: конфигуратор такой не сохраняет, загрузка принимает."""

    class World:
        def object_exists(self, kind, name):
            return True

    findings = kind_of("РегистрСведений").check(
        Spec("РегистрСведений", {"имя": "мой_Проба"}), World())
    codes = [f.code for f in findings]
    assert "РЕГИСТР-БЕЗ-ИЗМЕРЕНИЙ" in codes, codes


def test_applied_kinds_carry_children_section():
    """У прикладных объектов раздел детей пишется всегда, даже пустым.

    У плоских видов его нет вовсе — это различие видно в эталонах: модуль
    и подписка идут без `<ChildObjects>`, справочник и перечисление — с пустым.
    """
    for kind in CASES:
        card = mapping.translate(
            kind_of(kind).fill(Spec(kind, {"имя": "мой_Проба"})), "x",
            new_id=lambda: "id")
        assert card.children == [], kind
    module = mapping.translate(
        kind_of("ОбщийМодуль").fill(Spec("ОбщийМодуль", {"имя": "мой_Проба"})), "x")
    assert module.children is None

def test_catalog_created_with_attributes():
    """Справочник можно завести сразу с реквизитами, одной операцией.

    Отдельно проверяется, что детям подставились умолчания: без них платформа
    отвергает карточку («Ошибка XDTO… Тип: FillChecking»).
    """
    spec = Spec("Справочник", {
        "имя": "мой_Проба",
        "реквизиты": [
            Spec("Реквизит", {"имя": "мой_Первый", "синоним": "Первый",
                              "тип": dm.StringType(20)}),
            Spec("Реквизит", {"имя": "мой_Второй", "синоним": "Второй",
                              "тип": dm.BooleanType()}),
        ],
    })
    ids = iter(f"id{n}" for n in range(100))
    card = mapping.translate(kind_of("Справочник").fill(spec), "x",
                             new_id=lambda: next(ids))
    assert len(card.children) == 2
    lines = "\n".join(serializer.card_to_lines(card))
    assert lines.count("<Attribute uuid=") == 2
    assert lines.count("<FillChecking>DontCheck</FillChecking>") == 2
    assert "<Use>ForItem</Use>" in lines          # реквизит справочника


def test_duplicate_attribute_names_rejected():
    spec = Spec("Справочник", {
        "имя": "мой_Проба",
        "реквизиты": [Spec("Реквизит", {"имя": "мой_Один", "синоним": "а",
                                        "тип": dm.BooleanType()}),
                      Spec("Реквизит", {"имя": "мой_Один", "синоним": "б",
                                        "тип": dm.BooleanType()})],
    })

    class World:
        def object_exists(self, kind, name):
            return True

    codes = [f.code for f in kind_of("Справочник").check(
        kind_of("Справочник").fill(spec), World())]
    assert "ДЕТИ-ИМЯ-ПОВТОРЯЕТСЯ" in codes, codes

def test_prefix_required_only_in_foreign_objects():
    """Внутри своего объекта префикс реквизиту не нужен, в чужом — обязателен.

    Правило приставки говорит о «типовых объектах» — то есть о чужих: внутри
    своего объекта коллизии с вендором не бывает, и в своих объектах реквизиты
    обычно называют без префикса.
    """

    class World:
        def object_exists(self, kind, name):
            return True

        def taken_names(self, path):
            return []

    attribute = kind_of("Реквизит", ТЕСТ)
    spec = attribute.fill(Spec("Реквизит", {"имя": "ТестЧисло", "синоним": "Тест",
                                            "тип": dm.NumberType(10)}))
    свой = [f.code for f in attribute.check(spec, World(), ("Справочник", "мой_Наш"))]
    чужой = [f.code for f in attribute.check(spec, World(), ("Справочник", "Контрагенты"))]
    создаётся = [f.code for f in attribute.check(spec, World(), ("Справочник", None))]
    assert "МД-ПРЕФИКС" not in свой, свой
    assert "МД-ПРЕФИКС" in чужой, чужой
    assert "МД-ПРЕФИКС" not in создаётся, создаётся

def test_document_matches_platform_reference():
    text, name, tag = reference("Документ")
    assert build("Документ", text, name, tag) == text
