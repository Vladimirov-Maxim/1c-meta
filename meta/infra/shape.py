"""Устройство документа выгрузки: где дети, где свойства, чем опознаются.

Это знание про формат, а не про библиотеку XML: карточка метаданных
и схема компоновки устроены по-разному, и разница одна и та же, каким бы
разборщиком их ни читали. Живи оно в файле реализации lxml, вторая
реализация переписывала бы его заново — то есть «новый файл рядом»
оказался бы новым файлом плюс копией формы документа.

Остаток связи с библиотекой честно виден: имя элемента без пространства
имён берётся у `etree.QName`. Другому разборщику понадобится здесь
переходник в одну строку, а не копия всего модуля.
"""

from lxml import etree

from ..domain.model import Refuse
from . import format as fmt

#: Раздел детей. Глубина у него не одна: у объекта это уровень 2,
#: у табличной части — 4, и брать её надо у самого узла. Фиксированное
#: число переформатировало бы карточку при удалении реквизита табличной части.
CHILDREN = "ChildObjects"
#: «пространство по умолчанию не задано» — не то же самое, что «его нет»
UNSET = object()


def _qualified(name, default=UNSET):
    """`xr:GeneratedType` -> `{http://…/readable}GeneratedType`.

    Без префикса берётся пространство по умолчанию: в карточке оно объявлено
    на корне, и элемент без него lxml записал бы как `<Тег xmlns="">`.
    Какое именно — можно задать: узел, вставляемый в чужое дерево, обязан
    попасть в то же пространство, что и его новые соседи, а не в то, которое
    мы считаем правильным. У дерева его может не быть вовсе.
    """
    prefix, _, local = name.rpartition(":")
    if not prefix:
        uri = fmt.URI[""] if default is UNSET else default
        return f"{{{uri}}}{local}" if uri else local
    uri = fmt.URI.get(prefix)
    if uri is None:
        raise Refuse(f"неизвестный префикс пространства имён в теге «{name}»")
    return f"{{{uri}}}{local}"


class Shape:
    """Где у документа дети, чем они опознаются и где лежат свойства."""

    #: тег корня, по которому форма и распознаётся
    root = None
    #: чем опознаётся сущность среди себе подобных, по порядку проверки
    identity = ("Name",)

    def owner(self, tree):
        """Узел, внутри которого живут дети верхнего уровня."""
        raise NotImplementedError

    def section(self, owner, create=False):
        """Узел, в котором лежат дети. `None` — раздела нет."""
        raise NotImplementedError

    def properties(self, element):
        """Узел, в котором лежат свойства."""
        raise NotImplementedError

    def identity_of(self, element):
        """Имя сущности — или `None`, если узел сущностью не является.

        В отличие от `name_of` без запасного хода к тексту узла: здесь вопрос
        не «как назвать», а «сущность ли это». Тип реквизита и пункт состава
        подсистемы — тоже узлы с текстом, но сущностями не являются.
        """
        holder = self.properties(element)
        if holder is None:
            return None
        for field in holder:
            if isinstance(field.tag, str) \
                    and etree.QName(field).localname in self.identity:
                return field.text or ""
        return None

    def name_of(self, element):
        for holder in (self.properties(element), element):
            if holder is None:
                continue
            for field in holder:
                if etree.QName(field).localname in self.identity:
                    return field.text or ""
        return element.text or ""


class CardShape(Shape):
    """Карточка метаданных: `MetaDataObject` -> вид -> `Properties`/`ChildObjects`."""

    root = "MetaDataObject"
    identity = ("Name",)

    def owner(self, tree):
        kinds = list(tree)
        if not kinds:
            raise Refuse("в карточке нет элемента вида — это не карточка объекта")
        return kinds[0]

    def section(self, owner, create=False):
        for candidate in owner:
            if etree.QName(candidate).localname == CHILDREN:
                return candidate
        if not create:
            return None
        return etree.SubElement(
            owner, _qualified(CHILDREN, etree.QName(owner).namespace))

    def properties(self, element):
        for candidate in element:
            if etree.QName(candidate).localname == "Properties":
                return candidate
        return None


class SchemaShape(Shape):
    """Схема компоновки данных: дети и свойства лежат прямо в узле.

    Чем сущность опознаётся, замерено по 63 328 пунктов настроек 926 схем:
    набор данных и параметр — по `name`, вычисляемое и итоговое поле —
    по `dataPath` (имени у них нет вовсе), выбираемое поле, поле порядка
    и элемент группировки — по `field` (16 125, 2038 и 8829), отбор —
    по `left` (6583), группировка структуры — по `name`, когда он есть.

    Порядок проверки — от более определённого к менее: два ключа у одного
    пункта не встречаются, но искать надо в известном порядке, а не в любом.

    Пункты «авто» (5782 поля порядка, 5027 выбираемых, 1620 папок и 1861
    группировка без имени) не опознаются ничем и адресовать их нельзя.
    Инструмент их и не создаёт; при попытке адресовать — «нет такого»,
    а не молчаливое попадание в первый подходящий.
    """

    root = "DataCompositionSchema"
    identity = ("name", "dataPath", "field", "left")

    def owner(self, tree):
        return tree

    def section(self, owner, create=False):
        return owner

    def properties(self, element):
        return element


SHAPES = (CardShape(), SchemaShape())


def shape_of(tree):
    """Форма документа по его корню. Незнакомый корень — отказ, а не догадка."""
    root = etree.QName(tree).localname
    for shape in SHAPES:
        if shape.root == root:
            return shape
    raise Refuse(f"не знаю документа с корнем «{root}»; известны: "
                 + ", ".join(s.root for s in SHAPES))
