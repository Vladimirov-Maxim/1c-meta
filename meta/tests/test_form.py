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

ФОРМА = """<?xml version="1.0" encoding="UTF-8"?>
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
def узел():
    дерево = LxmlCardTree()
    return дерево.to_node(дерево.parse(ФОРМА))


@pytest.fixture(scope="module")
def корпус_форм():
    """Один обход по 392 МБ форм на весь модуль, а не по обходу на утверждение.

    Если бы четыре корпусных проверки ходили по конфигурации каждая своим
    обходом, весь набор тестов шёл бы двенадцать минут вместо 73 секунд. Набор,
    который не запускают, не защищает ничего, поэтому обход один и общий.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    from lxml import etree

    дерево = LxmlCardTree()
    итог = {"форм": 0, "побайтно": 0, "разошлись": [], "чужие_виды": set(),
            "спутников": 0, "спутники_выводятся": 0, "номера_подряд": 0}
    for каталог, _, файлы in os.walk(corpus.CORPUS):
        if os.path.basename(каталог) != "Ext" or "Form.xml" not in файлы:
            continue
        путь = os.path.join(каталог, "Form.xml")
        исходник = open(путь, encoding="utf-8-sig").read().replace("\r\n", "\n")
        итог["форм"] += 1

        разобранное = дерево.parse(исходник)
        if дерево.serialize(разобранное) == исходник:
            итог["побайтно"] += 1
        elif len(итог["разошлись"]) < 5:
            итог["разошлись"].append(os.path.relpath(путь, corpus.CORPUS))

        узел = дерево.to_node(разобранное)
        итог["чужие_виды"] |= form.kinds_of(узел) - set(form.ЭЛЕМЕНТЫ)

        for узел_xml in разобранное.iter():
            if not isinstance(узел_xml.tag, str):
                continue
            if etree.QName(узел_xml).localname not in form.СПУТНИКИ:
                continue
            итог["спутников"] += 1
            родитель = узел_xml.getparent().get("name") or ""
            своё = узел_xml.get("name") or ""
            if родитель and своё.startswith(родитель):
                итог["спутники_выводятся"] += 1

        номера = [int(н) for н in re.findall(r' id="(\d+)"', исходник)]
        if номера and sorted(номера) == list(range(1, len(номера) + 1)):
            итог["номера_подряд"] += 1
    return итог


def test_every_form_of_the_configuration_survives_the_round_trip(корпус_форм):
    """Разбор и сборка обратно — байт в байт, на всех 11 042 формах замеренной
    конфигурации.

    Это фундамент: пока разбор теряет хоть что-то, язык описания формы
    строить не на чем — потеря всплывёт испорченной формой в конфигурации.
    """
    assert корпус_форм["форм"] > 10000, корпус_форм["форм"]
    assert корпус_форм["побайтно"] == корпус_форм["форм"], корпус_форм["разошлись"]


def test_the_view_keeps_the_tree_and_the_bindings(узел):
    """Взгляд передаёт то, ради чего он нужен: вложенность и привязки."""
    html = form.html_from_node(узел, "Проба")
    assert 'data-путь="СкладОтбор"' in html
    assert 'data-путь="Объект.Ответственный"' in html
    # группа горизонтальная и в рамке — и то и другое из свойств
    assert 'data-направление="Горизонтальная"' in html
    assert 'data-рамка="StrongSeparation"' in html
    # поле лежит внутри группы, а не рядом с ней
    группа = html.index('data-рамка="StrongSeparation"')
    поле = html.index('data-путь="СкладОтбор"')
    закрытие = html.index("</div>", группа)
    assert группа < поле < закрытие


def test_a_caption_comes_from_the_form_attribute(узел):
    """У поля своего заголовка нет — подпись лежит на реквизите формы.

    `СкладОтбор` в элементе не несёт ничего, кроме пути; «Склад» написано
    в `<Attributes>`. Печатать вместо этого имя элемента — показывать не ту
    подпись, которую видит пользователь живой формы.
    """
    html = form.html_from_node(узел)
    assert ">Склад<" in html
    assert "СкладОтбор<" not in html.split("data-путь")[1]


def test_a_hidden_caption_stays_hidden(узел):
    """`TitleLocation = None` — подписи нет вовсе, так у 6534 полей замеренной
    конфигурации."""
    html = form.html_from_node(узел)
    кусок = html[html.index('data-путь="Объект.Ответственный"'):]
    assert "Ответственный</span>" not in кусок.split("</label>")[0]


def test_a_group_title_shows_unless_it_is_switched_off(узел):
    """Платформа пишет `ShowTitle` только чтобы спрятать заголовок.

    В замеренной конфигурации `false` стоит явно у 54 984 групп, а тега нет у
    5347 — и у них заголовок виден. Трактовать отсутствие как «не показывать»
    значит потерять заголовок у каждой одиннадцатой группы.
    """
    html = form.html_from_node(узел)
    assert "▾ Отбор" in html


def test_satellites_are_dropped(узел):
    """Контекстное меню и подсказка есть у каждого поля и смысла не несут.

    Их 597 296 в замеренной конфигурации — больше половины всех элементов
    формы. Показывать их значит показывать не форму, а её разбор.
    """
    html = form.html_from_node(узел)
    for спутник in ("КонтекстноеМеню", "РасширеннаяПодсказка"):
        assert спутник not in html


def test_an_unknown_kind_is_shown_and_not_dropped():
    """Незнакомый вид остаётся видимым — молча потерять элемент хуже."""
    дерево = LxmlCardTree()
    подменённая = ФОРМА.replace("<InputField name=\"Скрытое\" id=\"15\">",
                                "<НовыйВидПоля name=\"Скрытое\" id=\"15\">")
    подменённая = подменённая.replace("</InputField>\n\t\t\t</ChildItems>",
                                      "</НовыйВидПоля>\n\t\t\t</ChildItems>")
    html = form.html_from_node(дерево.to_node(дерево.parse(подменённая)))
    assert 'data-вид="НовыйВидПоля"' in html
    assert "неизвестный" in html


def test_every_element_kind_of_the_configuration_is_known(корпус_форм):
    """Видов элементов 31, и все они названы: «не знаю» на корпусе быть не должно."""
    assert not корпус_форм["чужие_виды"], sorted(корпус_форм["чужие_виды"])


def test_satellite_names_are_derived_from_the_parent(корпус_форм):
    """Спутники выводимы: в замеренной конфигурации 595 591 имя из 597 296 —
    имя родителя плюс суффикс.

    Отсюда следует, что язык описания формы может их не хранить, а это
    больше половины элементов файла.
    """
    доля = корпус_форм["спутники_выводятся"] / корпус_форм["спутников"]
    print(f"спутников: {корпус_форм['спутников']}, выводится {доля:.2%}")
    assert доля > 0.99, доля


def test_the_element_numbers_are_not_derivable(корпус_форм):
    """А номера элементов нести придётся: в замеренной конфигурации подряд они
    лишь у 112 форм из 11 042.

    Это записано тестом, потому что соблазн «пронумеруем сами» велик,
    а побайтный круг он ломает.
    """
    доля = корпус_форм["номера_подряд"] / корпус_форм["форм"]
    print(f"форм с номерами подряд: {корпус_форм['номера_подряд']}")
    assert доля < 0.05, доля
