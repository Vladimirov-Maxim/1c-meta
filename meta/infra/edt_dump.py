"""Площадка «проект EDT»: та же площадка выгрузки, но файлы — проекта EDT.

Логика площадки выгрузки (`DesignerDump`: адресация, вставка детей, правка
свойств, удаление, переименование, ссылки) работает с карточкой в форме
выгрузки конфигуратора. Проект EDT подключается к ней переходником, а не
второй копией логики:

* чтение — карточка `.mdo` -> обратная перекладка (`acl.edt_card.Reverse`) ->
  текст в форме выгрузки; реестр `Configuration/Configuration.mdo` — так же;
* запись — текст в форме выгрузки -> прямая перекладка (`Translation`) ->
  `.mdo`; что выгрузка выразить не может, прошло переходником нетронутым;
* пути — раскладка EDT: объект `<Каталог>/<Имя>/<Имя>.mdo`, модули и права
  рядом с карточкой без `Ext`, макет `Templates/<Макет>/Template.dcs`;
* формат текста — UTF-8 без BOM; переводы строк у существующего файла — его
  собственные, у нового — принятые в репозитории (LF, если сверить не с чем).

Круг переходника сверен на проекте EDT крупной типовой конфигурации: все
23 385 карточек возвращаются байт в байт, — поэтому правка одного свойства
меняет в файле одну строку. Запись новых объектов сверена с тем, что пишет
сам EDT при импорте той же выгрузки (`tools/edt_oracle.py`).

Формы проекта EDT (`Form.form`) читаются (`infra.forms.edt`): показ формы и код
доработки типовой формы работают. Запись описания формы EDT пока не
поддерживается: отказ, а не запись наугад.
"""

import os
import re

from lxml import etree

from ..acl import edt_card, mapping
from ..domain.model import Refuse
from . import edt_xml, serializer
from .designer import DesignerDump
from .layout import OBJECT_FOLDERS
from .repository import Plan, ReferenceSource, _read_bytes
from .shape import shape_of
from .tree_lxml import LxmlCardTree

#: Шапка файла прав роли в проекте EDT: те же права, что в `Ext/Rights.xml`
#: выгрузки, но корень без версии формата и без `xs`.
RIGHTS_ROOT = ('<Rights xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
               'xmlns="http://v8.1c.ru/8.2/roles" xsi:type="Rights">')

#: Отказ записи описания формы. Тот же текст говорит реализация формата форм
#: EDT; здесь он свой — реализацию площадка берёт только через реестр.
WRITE_REFUSAL = ("запись формы проекта EDT (Form.form) инструмент пока не умеет: у EDT умолчания "
                 "платформы для каждого вида элемента записаны явно, и родить элемент наугад нельзя. "
                 "Типовую форму дорабатывают кодом («код»: true) — он работает и с формой EDT")

#: Спутник карточки выгрузки -> файл проекта EDT (относительно каталога объекта).
SATELLITES = (
    (re.compile(r"^Ext/Rights\.xml$"), "Rights.rights"),
    (re.compile(r"^Ext/(\w+\.bsl)$"), r"\1"),
    (re.compile(r"^Templates/([^/]+)/Ext/Template\.xml$"), r"Templates/\1/Template.dcs"),
)
#: Карточка макета выгрузки: в EDT она живёт в карточке хозяина (`templates`).
TEMPLATE_CARD = re.compile(r"^Templates/([^/]+)\.xml$")



class EdtCardTree(LxmlCardTree):
    """Дерево карточки в форме выгрузки, прочитанной из проекта EDT.

    EDT не пишет свойство, равное умолчанию, и в карточке, прочитанной
    переходником, его нет. Правка такого свойства — не «менять нечего», а
    первое его значение: свойство дописывается в конец раздела свойств. Место
    здесь не важно — порядок при записи ставит метамодель."""

    def set_property(self, node, tag, described):
        if self._property(node, tag) is not None:
            return super().set_property(node, tag, described)
        holder = shape_of(node.getroottree().getroot()).properties(node)
        if holder is None:
            raise Refuse(f"в карточке нет раздела свойств — «{tag}» поставить некуда")
        new = self._element(described, etree.QName(holder).namespace)
        holder.append(new)
        return "по умолчанию"


class EdtDump(DesignerDump):
    """Проект EDT по пути `root` — каталог исходников (`…/src`), где лежит
    `Configuration/Configuration.mdo`."""

    def __init__(self, root, eol=None, tree=None):
        self.root = os.path.abspath(root)
        self.tree = tree or EdtCardTree()
        self._schemas = {}
        if not os.path.isdir(self.root):
            raise Refuse(f"каталога «{self.root}» не существует")
        if not os.path.isfile(self.registry_path()):
            raise Refuse(f"в «{self.root}» нет Configuration/Configuration.mdo — "
                         "это не исходники проекта EDT")
        self.eol = eol or self._accepted_eol()

    def _accepted_eol(self):
        """Переводы строк нового файла — как у реестра проекта; CRLF в нём
        бывает от записи EDT на Windows, принятые в репозитории — LF."""
        return "\n"

    # --- пути -------------------------------------------------------------

    def registry_path(self):
        return os.path.join(self.root, "Configuration", "Configuration.mdo")

    def object_path(self, kind, name):
        path = super().object_path(kind, name)
        if path is None:
            return None
        return os.path.join(os.path.dirname(path), name, name + ".mdo")

    def card_path(self, card):
        return os.path.join(self.root, card.container, card.name, card.name + ".mdo")

    def _module_path(self, name):
        return os.path.join(self.root, "CommonModules", name, "Module.bsl")

    def _rights_path(self, role):
        return os.path.join(self.root, "Roles", role, "Rights.rights")

    def template_path(self, kind, name, template):
        card = self.object_path(kind, name)
        if card is None:
            return None
        return os.path.join(os.path.dirname(card), "Templates", template, "Template.dcs")

    # --- формат -----------------------------------------------------------

    def format_version(self):
        return None                      # у проекта EDT версии формата выгрузки нет

    def _writable(self):
        return None

    def configuration_name(self):
        try:
            with open(self.registry_path(), encoding="utf-8-sig") as source:
                head = source.read(self.EOL_HEAD)
        except OSError:
            return None
        found = re.search(r"<name>([^<]+)</name>", head)
        return found.group(1) if found else None

    def defined_type_facets(self, name):
        path = self.object_path("ОпределяемыйТип", name)
        if path is None or not os.path.isfile(path):
            return None
        text = open(path, encoding="utf-8-sig").read()
        facets = []
        for word in re.findall(r"<types>([^<]+)</types>", text):
            if "." not in word:
                continue
            набор = word.split(".", 1)[0] in edt_card.SETS
            try:
                vtype = mapping.parse_type_notation("cfg:" + word, набор)
            except Refuse:
                continue
            if vtype.facet and vtype.facet not in facets:
                facets.append(vtype.facet)
        return facets or None

    # --- текст: переходник ------------------------------------------------

    def _designer_text(self, data):
        """Байты карточки EDT -> текст в форме выгрузки."""
        узел = edt_card.Reverse().card(edt_xml.parse(data.replace(b"\r\n", b"\n")))
        return self.tree.serialize(self.tree.build(узел))

    def _read_text(self, path):
        data = _read_bytes(path)
        if path.endswith(".mdo"):
            return self._designer_text(data)
        return data.decode("utf-8-sig").replace("\r\n", "\n")

    def _source_text(self, path, data):
        if path.endswith(".mdo"):
            return self._designer_text(data)
        return data.decode("utf-8-sig", "replace").replace("\r\n", "\n")

    def _edt_text(self, designer_text, satellite=None):
        """Текст в форме выгрузки -> текст карточки EDT; чего перекладка не
        умеет — отказ: недописанная карточка хуже, чем никакой."""
        узел = self.tree.to_node(self.tree.parse(designer_text))
        перекладка = edt_card.Translation(satellite)
        карточка = перекладка.card(узел)
        if перекладка.problems:
            raise Refuse("в формат EDT не перекладывается: " + "; ".join(перекладка.problems))
        return edt_xml.render(карточка)

    def _encode(self, text, path=None):
        """Текст -> байты файла проекта EDT: без BOM, переводы строк файла."""
        if path is not None and path.endswith(".mdo"):
            text = self._edt_text(text)
        elif path is not None and path.endswith(".rights"):
            text = rights_text(text)
        text = text.replace("\r\n", "\n")
        if text.startswith(serializer.BOM):
            text = text[1:]
        return text.replace("\n", self._eol_of(path)).encode("utf-8")

    # --- создание ---------------------------------------------------------

    def prepare(self, cards):
        """Plan на создание объектов: карточка `.mdo`, спутники рядом с ней
        и записи в реестре. Карточка макета у EDT — часть карточки хозяина."""
        plan = Plan()
        taken = set()
        registry_path = self.registry_path()
        registry = self.tree.parse(self._read_text(registry_path))
        for card in cards:
            path = self.card_path(card)
            if path in taken:
                вид = mapping.ROOTS_BACK.get(card.element, card.element)
                raise Refuse(f"«{вид}.{card.name}» создаётся этим заданием дважды")
            if os.path.exists(path):
                raise Refuse(f"карточка уже существует: {path}")
            taken.add(path)
            folder = os.path.dirname(path)
            макеты = {}
            for rel_path, content in card.satellites:
                найдено = TEMPLATE_CARD.match(rel_path)
                if найдено:
                    макеты[найдено.group(1)] = self.tree.to_node(self.tree.build(content))
                    continue
                target = satellite_target(folder, rel_path)
                if os.path.exists(target):
                    raise Refuse(f"файл уже существует: {target}")
                text = (content if isinstance(content, str)
                        else self.tree.serialize(self.tree.build(content)))
                plan.add(target, self._encode(text, target), True)
            text = self.tree.serialize(self.tree.build(serializer.card_to_node(card)))
            карточка = self._edt_text(
                text, lambda tag, name, макеты=макеты: макеты.get(name) if tag == "Template" else None)
            plan.add(path, карточка.replace("\n", self.eol).encode("utf-8"), True)
            self._register(registry, card)
        plan.add(registry_path, self._encode(self.tree.serialize(registry), registry_path), False)
        return plan

    # --- удаление и переименование: каталог объекта ----------------------

    def _erase_objects(self, plan, removed):
        """Каталог объекта целиком (карточка, модули, права, макеты, формы) и
        запись в реестре — за один план."""
        registry_path = self.registry_path()
        registry = self.tree.parse(self._read_text(registry_path))
        for (kind, name), file_path in removed:
            plan.note(f"удалить {kind}.{name} целиком")
            self._note_query_mentions(plan, [(kind, name)], f"{kind}.{name}")
            for inside, _, names in os.walk(os.path.dirname(file_path)):
                for файл in sorted(names):
                    plan.erase(os.path.join(inside, файл))
            tag = mapping.registry_tag_of(kind)
            if not self.tree.remove_child(registry, [(tag, name)]):
                raise Refuse(f"объекта «{name}» нет в Configuration.mdo")
        plan.add(registry_path, self._encode(self.tree.serialize(registry), registry_path), False)

    def _move_satellites(self, plan, old_path, old_name, new_name):
        """Каталог объекта переезжает целиком; карточку переносит переименование."""
        old_folder = os.path.dirname(old_path)
        new_folder = os.path.join(os.path.dirname(old_folder), new_name)
        for inside, _, names in os.walk(old_folder):
            for файл in sorted(names):
                source = os.path.join(inside, файл)
                if source == old_path:
                    continue
                plan.add(os.path.join(new_folder, os.path.relpath(source, old_folder)),
                         _read_bytes(source), True)
                plan.erase(source)

    # --- обратный поиск ---------------------------------------------------

    def _reference_sources(self):
        """Файлы проекта EDT, где бывают ссылки: реестр, карточки (и
        подчинённых подсистем), права ролей, схемы компоновки."""
        back = {folder: kind for folder, (kind, _) in OBJECT_FOLDERS.items()}
        yield ReferenceSource(self.registry_path(), "Конфигурация", "Конфигурация", None)
        for folder, subfolders, names in os.walk(self.root):
            relative = os.path.relpath(folder, self.root)
            subfolders[:] = [d for d in subfolders if d not in self.SKIP_FOLDERS]
            if relative == "." or relative.split(os.sep)[0] == "Configuration":
                continue
            parts = relative.split(os.sep)
            kind = back.get(parts[0], parts[0])
            for name in sorted(names):
                path = os.path.join(folder, name)
                if name == "Rights.rights" and len(parts) == 2:
                    yield ReferenceSource(path, f"{kind}.{parts[1]} (права)", None, kind)
                elif name == "Template.dcs" and len(parts) >= 4 and parts[-2] == "Templates":
                    yield ReferenceSource(path, f"{kind}.{parts[1]} (макет {parts[-1]})",
                                          f"{kind}.{parts[1]}.{self.TEMPLATE_STEP}.{parts[-1]}", None)
                elif name.endswith(".mdo") and name[:-4] == parts[-1]:
                    inner = [back.get(part, part) if position % 2 else part
                             for position, part in enumerate(parts[1:])]
                    owner = ".".join([kind, *inner])
                    yield ReferenceSource(path, owner, owner, kind)

    def _query_mentions(self, path):
        """Схемы, где объект назван в тексте запроса: в проекте EDT схема —
        `Template.dcs`."""
        kind, name = path[0]
        from ..acl import vocabulary
        if len(path) != 1 or kind not in vocabulary.QUERY_DESIGNATION:
            return []
        needle = name.encode("utf-8")
        pattern = re.compile(r"(?<![\w.])" + kind + r"\." + re.escape(name) + r"(?![\w])")
        found = []
        for source in self._reference_sources():
            if not source.path.endswith("Template.dcs"):
                continue
            data = _read_bytes(source.path)
            if needle in data and pattern.search(data.decode("utf-8-sig", "replace")):
                found.append(source.owner)
        return found

    # --- формы: чтение — да, запись описания формы — пока нет --------------

    def form_paths(self, owner, name):
        """(карточка, описание, модуль) формы. Карточка формы объекта у EDT —
        карточка хозяина: форма описана в ней (`forms`)."""
        if owner is None:
            base = os.path.join(self.root, "CommonForms", name)
            return (os.path.join(base, name + ".mdo"), os.path.join(base, "Form.form"),
                    os.path.join(base, "Module.bsl"))
        folder = os.path.join(self.root, mapping.container_of(owner[0]), owner[1])
        base = os.path.join(folder, "Forms", name)
        return (os.path.join(folder, owner[1] + ".mdo"), os.path.join(base, "Form.form"),
                os.path.join(base, "Module.bsl"))

    def prepare_form_edits(self, items, new_id):
        raise Refuse(WRITE_REFUSAL)

    def prepare_form_files(self, prepared):
        raise Refuse(WRITE_REFUSAL)


def satellite_target(folder, rel_path):
    """Спутник карточки выгрузки -> путь файла проекта EDT."""
    for шаблон, замена in SATELLITES:
        if шаблон.match(rel_path):
            return os.path.join(folder, *шаблон.sub(замена, rel_path).split("/"))
    raise Refuse(f"спутник «{rel_path}» в раскладку проекта EDT не переводится")


def rights_text(text):
    """Права роли в форме выгрузки -> файл прав проекта EDT: корень без версии
    формата и без `xs`, завершающий перевод строки."""
    text = re.sub(r"<Rights\b[^>]*>", RIGHTS_ROOT, text.replace("\r\n", "\n"), count=1)
    return text if text.endswith("\n") else text + "\n"
