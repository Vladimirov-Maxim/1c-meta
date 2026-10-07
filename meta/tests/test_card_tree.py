"""Договор `CardTree`: разобрать карточку и собрать её обратно символ в символ.

Главная проверка здесь одна: круг сходится на **всех** карточках
конфигурации, а не на выборке. Инструмент правит чужие файлы; если разбор
что-то теряет или нормализует, правка одного свойства даст diff, неотличимый
от переписывания файла целиком, — и по нему не прочитать, что изменилось.

Тесты параметризованы по списку реализаций. Сейчас в нём одна — на lxml;
вторая (другая библиотека) просто дописывается в `IMPLEMENTATIONS` и обязана
пройти те же проверки. Ради этого договор и вынесен отдельно — в `infra/tree.py`.
"""

import os
import re
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.domain.model import Refuse  # noqa: E402
from meta.infra.tree_lxml import DECLARATION, LxmlCardTree  # noqa: E402
from meta.tests import corpus  # noqa: E402

IMPLEMENTATIONS = [LxmlCardTree]


@pytest.fixture(params=IMPLEMENTATIONS, ids=lambda cls: cls.__name__)
def tree(request):
    return request.param()


#: Имена реквизитов по отступу в три табуляции — независимая сверка
#: разбора. Ценна она тем, что написана иначе, чем разбор.
ATTRIBUTE_NAMES_RE = (r"^\t{3}<Attribute uuid=[^>]+>\s*"
                    r"\t{4}<Properties>\s*"
                    r"\t{5}<Name>([^<]+)</Name>")

def cards():
    """Все карточки объектов выгрузки плюс сама конфигурация."""
    yield os.path.join(corpus.CORPUS, "Configuration.xml")
    for kind in sorted(os.listdir(corpus.CORPUS)):
        folder = os.path.join(corpus.CORPUS, kind)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".xml"):
                yield os.path.join(folder, name)


def text_of(path):
    return open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")


def test_round_trip_on_every_card(tree):
    """Гейт: 22 292 карточки, 197 МБ, ни одного расхождения.

    Своей грамматики XML у инструмента нет: построчный разборщик спотыкается
    о текст, перенесённый на несколько строк внутри `<v8:content>`.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    started = time.time()
    checked = 0
    broken = []
    for path in cards():
        source = text_of(path)
        result = tree.serialize(tree.parse(source))
        if result != source:
            at = next((i for i in range(min(len(source), len(result)))
                       if source[i] != result[i]), 0)
            broken.append(f"{path}\n   было  {source[max(0, at - 45):at + 45]!r}\n   стало {result[max(0, at - 45):at + 45]!r}")
            if len(broken) > 3:
                break
        checked += 1
    assert not broken, "круг не сошёлся:\n" + "\n".join(broken)
    print(f"карточек сверено {checked} за {time.time() - started:.0f} с")


def test_own_attributes_match_the_indent_reading(tree):
    """Состав объекта читается разбором — и совпадает с чтением по отступам.

    Регулярное выражение отсекает реквизиты табличных частей отступом в три
    табуляции: это верно, но держится на том, что файл отформатирован именно
    так. Здесь оно — независимая вторая пара глаз: две разные механики обязаны
    дать один ответ на тысячах объектов.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    checked = with_attributes = 0
    for kind in ("Catalogs", "Documents", "InformationRegisters", "DataProcessors"):
        folder = os.path.join(corpus.CORPUS, kind)
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".xml"):
                continue
            source = text_of(os.path.join(folder, name))
            expected = re.findall(ATTRIBUTE_NAMES_RE, source, re.M)
            assert tree.child_names(tree.parse(source), "Attribute") == expected, name
            checked += 1
            with_attributes += bool(expected)
    print(f"состав сверен у {checked} объектов, из них с реквизитами {with_attributes}")
    assert with_attributes > 1000


def test_tabular_section_attributes_stay_out(tree):
    """Реквизиты табличной части — не реквизиты объекта, и глубже разбор не идёт."""
    card = (DECLARATION + "\n"
            '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">\n'
            "\t<Catalog uuid=\"1\">\n"
            "\t\t<ChildObjects>\n"
            "\t\t\t<Attribute uuid=\"2\">\n"
            "\t\t\t\t<Properties>\n\t\t\t\t\t<Name>Свой</Name>\n\t\t\t\t</Properties>\n"
            "\t\t\t</Attribute>\n"
            "\t\t\t<TabularSection uuid=\"3\">\n"
            "\t\t\t\t<Properties>\n\t\t\t\t\t<Name>Строки</Name>\n\t\t\t\t</Properties>\n"
            "\t\t\t\t<ChildObjects>\n"
            "\t\t\t\t\t<Attribute uuid=\"4\">\n"
            "\t\t\t\t\t\t<Properties>\n\t\t\t\t\t\t\t<Name>Вложенный</Name>\n"
            "\t\t\t\t\t\t</Properties>\n"
            "\t\t\t\t\t</Attribute>\n"
            "\t\t\t\t</ChildObjects>\n"
            "\t\t\t</TabularSection>\n"
            "\t\t</ChildObjects>\n"
            "\t</Catalog>\n"
            "</MetaDataObject>")
    parsed = tree.parse(card)
    assert tree.child_names(parsed, "Attribute") == ["Свой"]
    assert tree.child_names(parsed, "TabularSection") == ["Строки"]
    assert tree.serialize(parsed) == card


def test_declaration_is_required(tree):
    with pytest.raises(Refuse) as refusal:
        tree.parse("<MetaDataObject/>")
    assert "объявлением XML" in str(refusal.value)


def test_broken_xml_is_refused_not_crashed(tree):
    with pytest.raises(Refuse) as refusal:
        tree.parse(DECLARATION + "\n<MetaDataObject><Catalog></MetaDataObject>")
    assert "не разбирается как XML" in str(refusal.value)


def test_long_empty_tag_is_the_one_thing_normalized(tree):
    """Единственная известная граница: `<Тег></Тег>` сворачивается в `<Тег/>`.

    Это настоящая нормализация, и прятать её нельзя. Она безопасна ровно потому,
    что платформа длинную форму не пишет: на всех 22 292 карточках конфигурации
    её нет ни разу, а круг сходится побайтно. Если такая карточка появится —
    упадёт гейт `test_round_trip_on_every_card`, а не пользователь.
    """
    card = DECLARATION + "\n<MetaDataObject><Comment></Comment></MetaDataObject>"
    assert tree.serialize(tree.parse(card)) == (
        DECLARATION + "\n<MetaDataObject><Comment/></MetaDataObject>")


@pytest.mark.parametrize("body", [
    '<MetaDataObject><Comment/></MetaDataObject>',          # одиночный тег
    '<MetaDataObject><Name>a &gt; b</Name></MetaDataObject>',  # `>` экранирован зря
    '<MetaDataObject b="2" a="1"/>',                        # порядок атрибутов
    '<MetaDataObject><T>две\nстроки</T></MetaDataObject>',   # перенос внутри текста
])
def test_forms_that_a_normalizing_parser_would_change(tree, body):
    """Ровно то, на чём ломаются другие разборщики.

    `xml.etree` не проходит ни одного файла из двухсот: он переписывает
    пространства имён (`MetaDataObject` -> `ns0:MetaDataObject`). Построчный
    разбор спотыкается о последний случай — перенос строки в тексте.
    """
    card = DECLARATION + "\n" + body
    assert tree.serialize(tree.parse(card)) == card


def test_every_operation_uses_the_injected_tree(tmp_path):
    """Реализация дерева выбирается в одном месте — и слушают её все.

    `Repository` принимает `tree=`, и создание объекта обязано собирать
    карточку переданной реализацией, а не модульным разборщиком сериализации.
    Иначе подмена даёт полуподменённый репозиторий: правка и врезка идут по
    новой реализации, создание — по старой, и ничто не падает. Гард
    `test_third_party_is_locked_in_its_layer` такого не видит: он смотрит
    импорты, а обе реализации внутри `infra`.

    Здесь подсовывается счётчик поверх настоящей реализации: он обязан
    увидеть сборку карточки.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump
    from meta.infra.tree_lxml import LxmlCardTree
    from meta.jobs import dialect as job_dialect

    считано = []

    class Счётчик(LxmlCardTree):
        def build(self, node):
            считано.append("build")
            return LxmlCardTree.build(self, node)

        def serialize(self, tree):
            считано.append("serialize")
            return LxmlCardTree.serialize(self, tree)

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n"
        "\t</Configuration>\n</MetaDataObject>")

    platform = DesignerDump(root, tree=Счётчик())
    AddObjectUseCase(platform).execute(
        [job_dialect.spec_from_json({"вид": "ОбщийМодуль", "поля": {
            "имя": "мой_Проба", "синоним": "Проба"}})], apply_now=True)

    assert "build" in считано, (
        "создание объекта собрало карточку не переданной реализацией")

