"""Карточка -> описание узлов -> текст файла выгрузки.

Слой сериализации знает немного — как устроена карточка: обёртка `MetaDataObject`, элемент вида
с `uuid`, затем `InternalInfo`, `Properties`, `ChildObjects`, — а во что это
превращается посимвольно, знает реализация договора `CardTree`.

Так и задумано: устройство карточки — факт формата выгрузки, он переживёт смену
библиотеки XML; экранирование и расстановка отступов к формату отношения
не имеют и живут у того, кто делает байты.

Факты о формате (пространства имён, версия, объявление, BOM) вынесены
в `format.py`: их одинаково нужно знать и здесь, и в реализации дерева.
"""

from ..acl.mapping import Node
from .format import BOM, FORMAT_VERSION, XML_DECLARATION  # noqa: F401
from .tree_lxml import LxmlCardTree

#: Разбор и сборка по умолчанию — для тех, кто зовёт сериализацию напрямую
#: (сверка с корпусом, проверки). Рабочий путь реализацию не берёт отсюда:
#: `Repository` передаёт свою, и это единственное место выбора.
TREE = LxmlCardTree()


def card_to_node(card):
    """Карточка -> описание дерева от корня `MetaDataObject`.

    Раздел детей пишется, только если он у вида вообще бывает: у плоских
    (общий модуль, подписка) его нет, у прикладных есть всегда, хотя бы пустым.
    """
    inner = []
    if card.internal_info:
        inner.append(Node("InternalInfo", children=card.internal_info))
    inner.append(Node("Properties", children=card.properties))
    if card.children is not None:
        inner.append(Node("ChildObjects", children=card.children))
    element = Node(card.element, attrs={"uuid": card.uuid}, children=inner)
    return Node("MetaDataObject",
                attrs={"version": FORMAT_VERSION}, children=[element])


def card_to_text(card, tree=TREE):
    """Карточка -> текст файла (без BOM, переводы строк ставит записывающий)."""
    return tree.serialize(tree.build(card_to_node(card)))


def card_to_lines(card, tree=TREE):
    return card_to_text(card, tree).split("\n")


def node_to_lines(node, level=0, tree=TREE):
    """Узел -> строки с отступом от заданного уровня.

    Нужен там, где узел показывают отдельно от карточки: в сверке с корпусом
    и в проверках. Запись идёт не через него — врезка вставляет узел в дерево,
    а не приклеивает строки к файлу.

    """
    return tree.render(node, level).split("\n")

