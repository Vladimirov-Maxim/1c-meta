"""Управляемая форма: чтение без потерь и взгляд на неё.

Форм в замеренной конфигурации 11 042 на 392 МБ — больше, чем всех карточек
вместе: это самая объёмная часть выгрузки.

Здесь два разных утверждения, и путать их нельзя:

* **разбор ничего не теряет** — это фундамент, и он проверяется побайтно
  на всех формах конфигурации. Без него строить язык описания не на чем;
* **взгляд приблизителен** — HTML передаёт структуру, вложенность и привязки,
  но не ширины, шрифты и отступы. Он нужен, чтобы увидеть «туда ли вложена
  группа», а не чтобы заменить платформу.
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import form  # noqa: E402
from meta.infra.tree_lxml import LxmlCardTree  # noqa: E402
from meta.tests import corpus  # noqa: E402

FORM = """<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform"\
 xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">
\t<WindowOpeningMode>LockOwner</WindowOpeningMode>
\t<Group>Vertical</Group>
\t<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>
\t<ChildItems>
\t\t<UsualGroup name="ГруппаШапка" id="10">
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>Отбор</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t\t<Group>AlwaysHorizontal</Group>
\t\t\t<Behavior>Collapsible</Behavior>
\t\t\t<Representation>StrongSeparation</Representation>
\t\t\t<ExtendedTooltip name="ГруппаШапкаРасширеннаяПодсказка" id="11"/>
\t\t\t<ChildItems>
\t\t\t\t<InputField name="СкладОтбор" id="12">
\t\t\t\t\t<DataPath>СкладОтбор</DataPath>
\t\t\t\t\t<ContextMenu name="СкладОтборКонтекстноеМеню" id="13"/>
\t\t\t\t\t<ExtendedTooltip name="СкладОтборРасширеннаяПодсказка" id="14"/>
\t\t\t\t</InputField>
\t\t\t\t<InputField name="Скрытое" id="15">
\t\t\t\t\t<DataPath>Объект.Ответственный</DataPath>
\t\t\t\t\t<TitleLocation>None</TitleLocation>
\t\t\t\t</InputField>
\t\t\t</ChildItems>
\t\t</UsualGroup>
\t</ChildItems>
\t<Attributes>
\t\t<Attribute name="СкладОтбор" id="7">
\t\t\t<Title>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>Склад</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Title>
\t\t</Attribute>
\t</Attributes>
</Form>"""


@pytest.fixture
def node():
    tree = LxmlCardTree()
    return tree.to_node(tree.parse(FORM))


@pytest.fixture(scope="module")
def form_corpus():
    """Один обход по 392 МБ форм на весь модуль, а не по обходу на утверждение.

    Если бы четыре корпусных проверки ходили по конфигурации каждая своим
    обходом, весь набор тестов шёл бы двенадцать минут вместо 73 секунд. Набор,
    который не запускают, не защищает ничего, поэтому обход один и общий.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    from lxml import etree

    tree = LxmlCardTree()
    result = {"форм": 0, "побайтно": 0, "разошлись": [], "чужие_виды": set(),
            "спутников": 0, "спутники_выводятся": 0, "номера_подряд": 0}
    for directory, _, files in os.walk(corpus.CORPUS):
        if os.path.basename(directory) != "Ext" or "Form.xml" not in files:
            continue
        path = os.path.join(directory, "Form.xml")
        source_text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
        result["форм"] += 1

        parsed_value = tree.parse(source_text)
        if tree.serialize(parsed_value) == source_text:
            result["побайтно"] += 1
        elif len(result["разошлись"]) < 5:
            result["разошлись"].append(os.path.relpath(path, corpus.CORPUS))

        node = tree.to_node(parsed_value)
        result["чужие_виды"] |= form.kinds_of(node) - set(form.ELEMENTS)

        for xml_node in parsed_value.iter():
            if not isinstance(xml_node.tag, str):
                continue
            if etree.QName(xml_node).localname not in form.SATELLITES:
                continue
            result["спутников"] += 1
            parent = xml_node.getparent().get("name") or ""
            is_own = xml_node.get("name") or ""
            if parent and is_own.startswith(parent):
                result["спутники_выводятся"] += 1

        numbers = [int(nn) for nn in re.findall(r' id="(\d+)"', source_text)]
        if numbers and sorted(numbers) == list(range(1, len(numbers) + 1)):
            result["номера_подряд"] += 1
    return result


def test_every_form_of_the_configuration_survives_the_round_trip(form_corpus):
    """Разбор и сборка обратно — байт в байт, на всех 11 042 формах замеренной
    конфигурации.

    Это фундамент: пока разбор теряет хоть что-то, язык описания формы
    строить не на чем — потеря всплывёт испорченной формой в конфигурации.
    """
    assert form_corpus["форм"] > 10000, form_corpus["форм"]
    assert form_corpus["побайтно"] == form_corpus["форм"], form_corpus["разошлись"]


def test_the_view_keeps_the_tree_and_the_bindings(node):
    """Взгляд передаёт то, ради чего он нужен: вложенность и привязки."""
    html = form.html_from_node(node, "Проба")
    assert 'data-путь="СкладОтбор"' in html
    assert 'data-путь="Объект.Ответственный"' in html
    # группа горизонтальная и в рамке — и то и другое из свойств
    assert 'data-направление="Горизонтальная"' in html
    assert 'data-рамка="StrongSeparation"' in html
    # поле лежит внутри группы, а не рядом с ней
    group = html.index('data-рамка="StrongSeparation"')
    field = html.index('data-путь="СкладОтбор"')
    closing_line = html.index("</div>", group)
    assert group < field < closing_line


def test_a_caption_comes_from_the_form_attribute(node):
    """У поля своего заголовка нет — подпись лежит на реквизите формы.

    `СкладОтбор` в элементе не несёт ничего, кроме пути; «Склад» написано
    в `<Attributes>`. Печатать вместо этого имя элемента — показывать не ту
    подпись, которую видит пользователь живой формы.
    """
    html = form.html_from_node(node)
    assert ">Склад<" in html
    assert "СкладОтбор<" not in html.split("data-путь")[1]


def test_a_hidden_caption_stays_hidden(node):
    """`TitleLocation = None` — подписи нет вовсе, так у 6534 полей замеренной
    конфигурации."""
    html = form.html_from_node(node)
    piece = html[html.index('data-путь="Объект.Ответственный"'):]
    assert "Ответственный</span>" not in piece.split("</label>")[0]


def test_a_group_title_shows_unless_it_is_switched_off(node):
    """Платформа пишет `ShowTitle` только чтобы спрятать заголовок.

    В замеренной конфигурации `false` стоит явно у 54 984 групп, а тега нет у
    5347 — и у них заголовок виден. Трактовать отсутствие как «не показывать»
    значит потерять заголовок у каждой одиннадцатой группы.
    """
    html = form.html_from_node(node)
    assert "▾ Отбор" in html


def test_satellites_are_dropped(node):
    """Контекстное меню и подсказка есть у каждого поля и смысла не несут.

    Их 597 296 в замеренной конфигурации — больше половины всех элементов
    формы. Показывать их значит показывать не форму, а её разбор.
    """
    html = form.html_from_node(node)
    for satellite in ("КонтекстноеМеню", "РасширеннаяПодсказка"):
        assert satellite not in html


def test_an_unknown_kind_is_shown_and_not_dropped():
    """Незнакомый вид остаётся видимым — молча потерять элемент хуже."""
    tree = LxmlCardTree()
    substituted_one = FORM.replace("<InputField name=\"Скрытое\" id=\"15\">",
                                "<НовыйВидПоля name=\"Скрытое\" id=\"15\">")
    substituted_one = substituted_one.replace("</InputField>\n\t\t\t</ChildItems>",
                                      "</НовыйВидПоля>\n\t\t\t</ChildItems>")
    html = form.html_from_node(tree.to_node(tree.parse(substituted_one)))
    assert 'data-вид="НовыйВидПоля"' in html
    assert "неизвестный" in html


def test_every_element_kind_of_the_configuration_is_known(form_corpus):
    """Видов элементов 31, и все они названы: «не знаю» на корпусе быть не должно."""
    assert not form_corpus["чужие_виды"], sorted(form_corpus["чужие_виды"])


def test_satellite_names_are_derived_from_the_parent(form_corpus):
    """Спутники выводимы: в замеренной конфигурации 595 591 имя из 597 296 —
    имя родителя плюс суффикс.

    Отсюда следует, что язык описания формы может их не хранить, а это
    больше половины элементов файла.
    """
    share = form_corpus["спутники_выводятся"] / form_corpus["спутников"]
    print(f"спутников: {form_corpus['спутников']}, выводится {share:.2%}")
    assert share > 0.99, share


def test_the_element_numbers_are_not_derivable(form_corpus):
    """А номера элементов нести придётся: в замеренной конфигурации подряд они
    лишь у 112 форм из 11 042.

    Это записано тестом, потому что соблазн «пронумеруем сами» велик,
    а побайтный круг он ломает.
    """
    share = form_corpus["номера_подряд"] / form_corpus["форм"]
    print(f"форм с номерами подряд: {form_corpus['номера_подряд']}")
    assert share < 0.05, share
