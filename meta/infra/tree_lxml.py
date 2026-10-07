"""`CardTree` на lxml: одно дерево и для чтения карточки, и для записи.

Почему именно lxml, а не то, что под рукой. Требование к реализации —
побайтный круг на чужом файле, и оно отсеивает почти всё: `xml.etree`
из стандартной библиотеки переименовывает пространства имён (`MetaDataObject`
становится `ns0:MetaDataObject`) и не сходится ни на одном из двухсот файлов
выборки. lxml сходится на всех двухстах и на всех 22 292 карточках
реальной выгрузки: он сохраняет порядок атрибутов, форму пустого тега,
экранирование `>`, которого XML не требует, и отступы.

Свой построчный разборщик не годится: текст, перенесённый на несколько строк
внутри `<v8:content>`, он разбирает неверно. Держать собственную грамматику
XML ради этого незачем — края у неё не кончатся.

Здесь же и обратное направление. Представление дерева одно и для чтения, и
для записи: описание узла (`acl.Node`) превращается в элемент здесь, а дальше
и создание, и правка идут одинаково. Своя запись строками, вклиненными в
байты файла, дала бы два представления дерева, встречающихся ровно в самом
хрупком месте инструмента.

Зависимость заперта в этом файле: за пределы инфраструктуры типы lxml
не выходят, приложение видит только договор `CardTree`, а гард в тестах следит,
чтобы так и осталось. Заменить lxml на другую библиотеку — это новый файл рядом.
"""

from lxml import etree

from ..acl import mapping
from ..domain.model import Refuse
from . import format as fmt
from .shape import (  # noqa: F401
    CHILDREN,
    UNSET,
    CardShape,
    SchemaShape,
    Shape,
    _qualified,
    shape_of,
)
from .tree import CardTree

#: Объявление XML одинаково у всех карточек выгрузки — проверено на всех
#: 22 292 карточках реальной выгрузки. В дерево оно не попадает (это не элемент),
#: поэтому хранится здесь и восстанавливается при сборке.
DECLARATION = fmt.XML_DECLARATION





def _local(tag):
    """Имя тега без приставки пространства имён.

    Схема называет теги так, как они стоят в файле (`dcsset:item`), а разбор
    возвращает разобранное имя — всегда без приставки. Сравнивать их надо
    приведёнными, и приводить в одном месте: стоит одному вызову забыть, и
    свойство схемы компоновки не найдётся совсем, а сообщение скажет «в
    карточке нет свойства» вместо «не вижу».
    """
    return tag.rpartition(":")[2]


def _attribute_name(name):
    """Атрибут без префикса пространства имён не имеет — таково правило XML."""
    if ":" not in name:
        return name
    return _qualified(name)


def _depth(element):
    """Уровень узла в дереве: у корня `MetaDataObject` — 0."""
    return sum(1 for _ in element.iterancestors())


def _relayout(element, level):
    """Отступы у прямых детей узла. Вглубь не идёт — чужое не трогаем."""
    children = list(element)
    if not children:
        return
    element.text = "\n" + fmt.INDENT * (level + 1)
    for child in children:
        child.tail = "\n" + fmt.INDENT * (level + 1)
    children[-1].tail = "\n" + fmt.INDENT * level


def _indent(element, level):
    """Расставить отступы во всём поддереве: один узел — одна строка."""
    for child in element:
        _indent(child, level + 1)
    _relayout(element, level)


# --- форма документа --------------------------------------------------------
#
# Инструмент правит два разных документа, и устроены они по-разному. Карточка
# метаданных: `MetaDataObject` -> элемент вида -> `Properties` со свойствами
# и `ChildObjects` с детьми; ребёнок опознаётся по `Properties/Name`. Схема
# компоновки данных: корень `DataCompositionSchema`, дети лежат прямо в нём
# без обёртки, свойства — тоже прямые дети, а опознаётся сущность по `name`
# (набор, параметр, вариант настроек) или по `dataPath` (вычисляемое
# и итоговое поле).
#
# Эти три различия вынесены сюда, а не зашиты в навигацию, затем, чтобы
# `find`, `insert_child`, `remove_child` и `set_property` работали на обоих
# документах одним кодом: операции изменения и удаления от формы не зависят.


class LxmlCardTree(CardTree):
    """Разбор и сборка карточки. Состояния не хранит — можно один на всех."""

    # --- чтение --------------------------------------------------------------

    def parse(self, text):
        declaration, separator, body = text.partition("\n")
        if declaration != DECLARATION or not separator:
            raise Refuse(
                "первая строка карточки должна быть объявлением XML "
                f"«{DECLARATION}», получено «{declaration[:60]}»")
        try:
            # Именно из байтов: lxml отказывается разбирать строку, в которой
            # объявлена кодировка, и он прав — иначе объявление и настоящая
            # кодировка могут разойтись.
            return etree.fromstring(body.encode("utf-8"))
        except etree.XMLSyntaxError as broken:
            raise Refuse(f"карточка не разбирается как XML: {broken}") from broken

    def serialize(self, tree):
        return (DECLARATION + "\n"
                + etree.tostring(tree, xml_declaration=False, encoding="unicode"))

    def granted(self, tree):
        """Выданные права из файла прав роли — XPath, а не `to_node`: у иной роли
        названы тысячи объектов со всеми правами `false` (29 МБ у одной роли
        корпуса), и перевод всего дерева в узлы занимал бы минуту на вид объектов."""
        пространства = {"r": tree.nsmap.get(None)}
        return [(объект.findtext("r:name", namespaces=пространства) or "",
                 объект.xpath("r:right[r:value='true']/r:name/text()", namespaces=пространства))
                for объект in tree.xpath("r:object[r:right/r:value='true']",
                                         namespaces=пространства)]

    def to_node(self, element):
        """Элемент -> `acl.Node`. Зеркало `build`, приставки сняты."""
        return mapping.Node(
            self.tag_of(element),
            text=(element.text or "").strip() or None,
            attrs={etree.QName(имя).localname if "}" in имя else имя: значение
                   for имя, значение in element.attrib.items()},
            children=[self.to_node(ребёнок) for ребёнок in element
                      if isinstance(ребёнок.tag, str)])

    def build(self, node):
        """Описание узла (`acl.Node`) -> дерево с проставленными отступами."""
        element = self._element(node)
        _indent(element, 0)
        return element

    def render(self, node, level):
        """Узел -> текст на заданной глубине, без объявления и обёртки.

        Собирается внутри временного корня и вырезается из него: пространство
        имён по умолчанию объявлено на корне карточки, и в одиночку узел получил
        бы от библиотеки собственный префикс (`ns0:Comment`). Отступы ставятся
        сразу на нужном уровне, а не подклеиваются к строкам — иначе табуляции
        уехали бы и внутрь многострочного текста, которого в карточках хватает.
        """
        root = etree.Element(_qualified("MetaDataObject"),
                             nsmap={prefix or None: uri for prefix, uri in fmt.NAMESPACES})
        element = self._element(node)
        _indent(element, level)
        root.append(element)
        text = etree.tostring(root, encoding="unicode")
        return fmt.INDENT * level + text[text.index(">") + 1:text.rindex("</")]

    # --- дети объекта --------------------------------------------------------

    def child_names(self, tree, element=None):
        """Имена детей. `element` — только заданного вида, `None` — всех.

        Тег сравнивается без приставки пространства имён: у пунктов настроек
        компоновки он записан как `dcsset:item`, а разобранное имя — `item`.
        Без снятия приставки совпадений не было бы ни одного, и защита от
        повторного пункта молчала бы на всех схемах разом.
        """
        element = None if element is None else _local(element)
        section = self._section_in(tree if tree.getparent() is not None
                                   else self._owner(tree))
        return [self._name_of(child)
                for child in (section if section is not None else [])
                if element is None
                or etree.QName(child).localname == element]

    def child_elements(self, tree):
        """Теги детей объекта по порядку: `["Attribute", "Attribute", "TabularSection"]`.

        Для `Configuration.xml` это тот же вопрос и та же глубина — раздел детей
        у конфигурации устроен так же, как у объекта, поэтому механизм один.
        """
        return self.child_elements_of(self._owner(tree))

    def child_elements_of(self, host):
        """То же, но у произвольного хозяина: табличной части, схемы, набора."""
        section = self._section_in(host)
        return [etree.QName(x).localname
                for x in (section if section is not None else [])]

    def insert_child(self, tree, index, node):
        """Вставить описанный узел в раздел детей на указанное место.

        Раздела может не быть вовсе (`<ChildObjects/>` у только что созданного
        объекта) — тогда он разворачивается деревом, а не вклиниванием байтов
        в файл: это было бы самым хрупким местом инструмента.
        """
        self.insert_child_of(self._owner(tree), index, node)

    def insert_child_of(self, host, index, node):
        """Вставить узел в раздел детей произвольного хозяина."""
        section = self._section_in(host, create=True)
        element = self._element(node, etree.QName(section).namespace)
        _indent(element, _depth(section) + 1)
        section.insert(index, element)
        # Переставляем отступы только там, где состав изменился: у самого раздела
        # и у его владельца (раздел мог появиться только что и сдвинуть хвост
        # у `Properties`). Вглубь не идём — чужое форматирование не трогаем.
        _relayout(section, _depth(section))
        # У схемы компоновки раздел детей — сам корень, и родителя у него нет.
        # Переставлять там нечего: хвост корня в документе не участвует.
        holder = section.getparent()
        if holder is not None:
            _relayout(holder, _depth(holder))

    # --- навигация и правка --------------------------------------------------

    def find(self, tree, path):
        """Путь `[("Attribute", "Код"), …]` -> узел. `None`, если не нашлось.

        Пустой путь — сам объект. Шаги идут по разделам детей: реквизит объекта,
        реквизит его табличной части — тот же механизм на любой глубине.
        """
        node = self._owner(tree)
        for element, name in path:
            element = _local(element)
            section = self._section_in(node)
            found = None
            for child in (section if section is not None else []):
                if etree.QName(child).localname != element:
                    continue
                # Шаг без имени — контейнер: в своём хозяине он один, и
                # опознавать его нечем, кроме тега.
                if name is None or self._name_of(child) == name:
                    found = child
                    break
            if found is None:
                return None
            node = found
        return node

    def property_text(self, node, tag):
        """Значение свойства как текст. `None` — свойства нет.

        Именно значение, а не разметка: `tostring` у вложенного элемента тащит
        за собой все унаследованные объявления пространств имён, и в отчёте
        «было → стало» они топят собой то единственное, ради чего отчёт нужен.
        У многоязычных свойств склеиваются части: «ru Код подразделения».
        """
        found = self._property(node, tag)
        if found is None:
            return None
        return " ".join(part.strip() for part in found.itertext() if part.strip())

    def set_text(self, node, text):
        """Заменить текст узла, не трогая его места среди соседей."""
        node.text = text

    def set_property(self, node, tag, described):
        """Заменить свойство описанным узлом. Вернуть прежний текст.

        Свойство заменяется на месте, соседи не двигаются, отступ берётся
        из глубины самого узла — правка одного значения не должна выглядеть
        как переписывание карточки.
        """
        old = self._property(node, tag)
        if old is None:
            raise Refuse(f"в карточке нет свойства «{tag}» — менять нечего")
        before = " ".join(p.strip() for p in old.itertext() if p.strip())
        properties = old.getparent()
        new = self._element(described, etree.QName(properties).namespace)
        _indent(new, len(list(properties.iterancestors())) + 1)
        new.tail = old.tail
        properties.replace(old, new)
        return before

    @staticmethod
    def _property(node, tag):
        shape = shape_of(node.getroottree().getroot())
        holder = shape.properties(node)
        if holder is None:
            return None
        tag = _local(tag)
        for field in holder:
            if etree.QName(field).localname == tag:
                return field
        return None

    def tag_of(self, node):
        """Имя тега узла без приставки пространства имён."""
        return etree.QName(node).localname

    def local_name(self, tag):
        """Тег, как его называет схема, -> имя без приставки."""
        return _local(tag)

    def child_by_tag(self, host, tag):
        """Прямой ребёнок хозяина с таким тегом. `None`, если его нет."""
        section = self._section_in(host)
        for child in (section if section is not None else []):
            if etree.QName(child).localname == _local(tag):
                return child
        return None

    def document(self, tree):
        return etree.QName(tree).localname

    def remove_child(self, tree, path):
        """Удалить вложенную сущность по пути. `False`, если её нет.

        Пустой раздел детей возвращается к одиночному тегу `<ChildObjects/>` —
        так его пишет платформа у объекта без содержимого, и оставлять после
        себя развёрнутый пустой раздел значит менять файл сверх заявленного.
        """
        node = self.find(tree, path)
        if node is None:
            return False
        section = node.getparent()
        section.remove(node)
        if len(section):
            _relayout(section, _depth(section))
        else:
            section.text = None
        holder = section.getparent()
        if holder is not None:
            _relayout(holder, _depth(holder))
        return True

    def reference_places(self, tree, pattern):
        """Где в дереве стоят ссылки: `[(шаги, свойство)]` без повторов, по порядку.

        Подъём идёт от узла со ссылкой к объекту. Сущность опознаёт форма
        документа — по `Properties/Name` в карточке, по `name`, `dataPath`
        и прочим ключам в схеме компоновки, — поэтому код один на оба документа.
        """
        shape = shape_of(tree)
        owner = shape.owner(tree)
        places = []
        for element in owner.iter():
            if not isinstance(element.tag, str):
                continue                      # комментарий, инструкция обработки
            if not element.text or not pattern.search(element.text):
                continue
            chain = [element, *element.iterancestors()]
            steps, prop = [], None
            for node in chain:
                # Объект — сущность всегда, даже без имени в свойствах: так
                # бывает у реестра конфигурации, собранного не платформой.
                name = shape.identity_of(node)
                if name is None and node is not owner:
                    continue
                if not steps and prop is None:
                    # Свойство самой глубокой сущности: тот узел пути,
                    # что лежит прямо в её свойствах.
                    holder = shape.properties(node)
                    prop = next((etree.QName(below).localname for below in chain
                                 if below.getparent() is holder), None)
                if node is owner:
                    break
                # Тег с приставкой, как в файле: `dcsset:item` у пунктов
                # настроек и `item` у наборов объединения — разные сущности.
                tag = etree.QName(node).localname
                steps.append((f"{node.prefix}:{tag}" if node.prefix else tag, name))
            place = (tuple(reversed(steps)), prop)
            if place not in places:
                places.append(place)
        return [(list(steps), prop) for steps, prop in places]

    # --- внутреннее ----------------------------------------------------------

    @staticmethod
    def _owner(tree):
        return shape_of(tree).owner(tree)

    @staticmethod
    def _section_in(owner, create=False):
        """Раздел детей внутри любого узла.

        Форма берётся у корня документа: узел табличной части и узел набора
        данных живут в разных документах и устроены по-разному.
        """
        return shape_of(owner.getroottree().getroot()).section(owner, create)

    @staticmethod
    def _name_of(child):
        """Чем сущность опознаётся — решает форма документа."""
        return shape_of(child.getroottree().getroot()).name_of(child)

    def _element(self, node, namespace=UNSET):
        """`acl.Node` -> элемент lxml.

        Пространства имён карточки объявляются на корне. Но не все: тип
        `dcsset:SettingsComposer` у реквизита обработки несёт своё объявление
        прямо на узле `<v8:Type>` — платформа пишет его там, а не в шапке.
        Для библиотеки это не атрибут, а объявление, и задать его можно только
        при создании элемента, поэтому `xmlns:*` отбираются заранее.
        """
        # Объявления корня — только у корня: вложенный `<Form>` карточки
        # (элемент вида и запись в детях хозяина) зовётся так же, как корень
        # описания формы, и без этой оговорки получал бы чужие пространства имён.
        declared = fmt.ROOT_NAMESPACES.get(node.tag) if namespace is UNSET else None
        if declared:
            # Корень документа задаёт пространство по умолчанию всему своему
            # поддереву: у карточки одно, у схемы компоновки другое.
            nsmap = {prefix or None: uri for prefix, uri in declared}
            namespace = dict(declared).get("", namespace)
        else:
            nsmap = {}
        # Объявления берутся в том порядке, в каком их перечислил узел:
        # библиотека пишет их этим же порядком, а платформа ставит пространство
        # по умолчанию первым. Узел может объявить и своё пространство
        # по умолчанию — файл прав роли живёт не в пространстве карточек.
        own = node.attrs.get("xmlns")
        for name, value in node.attrs.items():
            if name == "xmlns":
                nsmap[None] = value
            elif name.startswith("xmlns:"):
                nsmap[name.partition(":")[2]] = value
        if own:
            namespace = own
        element = etree.Element(_qualified(node.tag, namespace), nsmap=nsmap or None)
        for name, value in node.attrs.items():
            if name == "xmlns" or name.startswith("xmlns:"):
                continue
            element.set(_attribute_name(name), value)
        if node.children:
            for child in node.children:
                element.append(self._element(child, namespace))
        elif node.text:
            element.text = node.text
        return element
