"""Выгрузка конфигурации на диске: чтение и запись.

Единственный слой, который знает про пути, байты и файловую систему. Он же
реализует порт `Configuration` — то, что домену нужно знать о конфигурации,
чтобы проверять инварианты. Домен об этом классе не подозревает.

Две вещи, ради которых слой существует отдельно:

* **Атомарность по всему заданию.** Карточка и запись в реестре — два файла,
  и половина изменения хуже, чем никакого: конфигурация с карточкой без записи
  в `Configuration.xml` не загрузится. Поэтому сначала готовятся все файлы
  в памяти, потом пишутся, а при сбое посередине откатываются.
* **`ConfigDumpInfo.xml` не трогается вовсе.** Его `configVersion` — хеш,
  который считает платформа; снаружи его не вычислить, а подставить неверный
  опаснее, чем не подставить никакого. Его пересобирает платформа при выгрузке,
  и в изменениях задачи его быть не должно.
"""

import os
import re
from collections import OrderedDict, namedtuple

from ..acl import mapping, vocabulary
from ..acl.schema import SCHEMA
from ..application.ports import Plan as PlanContract
from ..domain.kinds import REGISTRY
from ..domain.model import Configuration, Refuse, Собранные
from . import serializer
from .format import FORMAT_VERSION
from .layout import OBJECT_FOLDERS
from .tree_lxml import LxmlCardTree

#: Файл, где бывают ссылки: путь, держатель для сообщения, адрес держателя,
#: от которого строится место ссылки (`None` — места не назвать: права роли),
#: и вид держателя (`None` у схемы компоновки и у реестра конфигурации).
ReferenceSource = namedtuple("ReferenceSource", "path owner address kind")


class Plan(PlanContract):
    """Подготовленные изменения. Пишутся все разом или ни одного."""

    def __init__(self):
        self.files = []           # (путь, новые байты, создаётся ли файл)
        self.notes = []           # пояснения к плану, по строке на правку
        # Размер файла до правки. Снимается здесь, при подготовке: печатается
        # план после `apply`, и вычисленное на печати «было» читало бы уже
        # переписанный файл. Получилось бы «станет 12251 Б, было 12251 Б» —
        # строка, отрицающая только что произошедшее и наводящая на мысль,
        # что просмотр пишет на диск вопреки обещанию.
        self.before = {}

    def add(self, path, raw, created):
        if not created and path not in self.before:
            self.before[path] = (os.path.getsize(path)
                                 if os.path.isfile(path) else None)
        self.files.append((path, raw, created))

    def erase(self, path):
        """Удалить файл. `raw is None` — признак удаления, а не пустого файла."""
        self.files.append((path, None, False))

    def note(self, text):
        """Пояснение к плану. Размер файла не говорит, что именно изменится."""
        self.notes.append(text)

    def describe(self):
        lines = []
        for path, raw, created in self.files:
            if raw is None:
                lines.append(f"удалить  {path}")
            elif created:
                lines.append(f"создать  {path} ({len(raw)} Б)")
            else:
                # Голое число читается как текущий размер файла, а это размер
                # после записи: без «было» разницу не понять, не померив файл
                # самому.
                было = self.before.get(path)
                стало = (f"станет {len(raw)} Б, было {было} Б" if было is not None
                         else f"{len(raw)} Б")
                lines.append(f"изменить {path} ({стало})")
        return self.notes + lines

    def contents(self):
        def текст(raw):
            return None if raw is None else raw.decode("utf-8-sig", errors="replace")
        return [(path, None if created or not os.path.isfile(path) else текст(_read_bytes(path)),
                 текст(raw))
                for path, raw, created in self.files]

    def apply(self):
        previous_bytes = []
        try:
            for path, raw, created in self.files:
                previous_bytes.append((path, None if created else _read_bytes(path)))
                if raw is None:
                    os.remove(path)
                else:
                    _write_bytes(path, raw)
        except Exception:
            # Откат обязан вернуть и удалённое: половина удаления хуже, чем
            # ни одного — карточки нет, а ссылки на неё остались.
            for path, old in reversed(previous_bytes):
                if old is None:
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    _write_bytes(path, old)
            raise
        _remove_empty_folders(path for path, raw, _ in self.files if raw is None)
        return [path for path, _, _ in self.files]


class PreparedForm:
    """Форма, подготовленная реализацией формата: что записать.

    `card` — узел карточки новой формы или `None` у существующей;
    `form_text` — текст описания; `module` — текст модуля новой формы
    или `None`; `handlers` — что должно появиться в модуле.
    """

    def __init__(self, edits, card, form_text, module, handlers, notes):
        self.edits = edits
        self.card = card
        self.form_text = form_text
        self.module = module
        self.handlers = list(handlers)
        self.notes = list(notes)


def _compact(text, limit=60):
    """Значение свойства в одну строку — для отчёта «было → стало»."""
    if text is None:
        return "(нет)"
    short = " ".join(text.split())
    return short if len(short) <= limit else short[:limit - 1] + "…"


def _rename_in(pattern, text, new_name):
    """Заменить имя во всех обозначениях, оставив приставки на месте.

    Меняются ровно границы группы `name`, а не первое вхождение строки:
    у объекта с именем `Document` первым вхождением будет приставка обозначения,
    и `cfg:DocumentRef.Document` превратился бы в `cfg:НовоеRef.Document` —
    ссылку на несуществующий вид, которую платформа не примет.
    """
    return pattern.sub(
        lambda found: (text[found.start():found.start("name")] + new_name
                       + text[found.end("name"):found.end()]), text)


def _remove_empty_folders(paths):
    """После удаления файлов-спутников пустые каталоги оставлять незачем."""
    for path in paths:
        folder = os.path.dirname(path)
        while folder and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
            folder = os.path.dirname(folder)


def _read_text(path):
    """Файл выгрузки -> текст без BOM и с едиными переводами строк."""
    return open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")


def _read_bytes(path):
    with open(path, "rb") as fn:
        return fn.read()


def _write_bytes(path, raw):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    tmp = path + ".tmp-meta"
    with open(tmp, "wb") as fn:
        fn.write(raw)
    os.replace(tmp, path)


class Repository(Configuration):
    """Выгрузка конфигурации по пути `root`."""

    # Платформа пишет CRLF во всех файлах выгрузки — и в карточках, и в модулях.
    # После загрузки и обратной выгрузки на пустой базе содержимое совпадает
    # узел в узел, отличаются только переводы строк. LF в рабочей копии —
    # не формат, а след git: при `core.autocrlf=true` LF лежит у всего,
    # что платформа не переписывала.
    EOL = "\r\n"

    def __init__(self, root, eol=EOL, tree=None):
        self.root = os.path.abspath(root)
        self.eol = eol
        # Единственное место, где выбирается реализация договора `CardTree`.
        # Заменить библиотеку XML — значит передать сюда другой разборщик.
        # Слушают её все операции, включая создание объекта: иначе подмена
        # дала бы полуподменённый репозиторий — правка по новой реализации,
        # создание по старой, и ничто бы не упало. Гард
        # `test_third_party_is_locked_in_its_layer` такого не видит: он смотрит
        # импорты, а обе реализации внутри `infra`.
        self.tree = tree or LxmlCardTree()
        # Какие макеты несут схему компоновки. Считается по требованию и живёт
        # до записи: пачка спрашивает источники ссылок по разу на объект.
        self._schemas = {}
        if not os.path.isdir(self.root):
            raise Refuse(f"каталога «{self.root}» не существует")
        if not os.path.isfile(os.path.join(self.root, "Configuration.xml")):
            raise Refuse(f"в «{self.root}» нет Configuration.xml — "
                         "это не выгрузка конфигурации")

    # --- крючки формата: что подменяет площадка другого формата ---------------

    def registry_path(self):
        """Файл реестра конфигурации."""
        return os.path.join(self.root, "Configuration.xml")

    def _read_text(self, path):
        """Текст файла, переводы строк приведены к `\n`. Площадка другого формата
        отдаёт здесь карточку в форме выгрузки — дальше её читает та же логика."""
        return _read_text(path)

    def _rights_path(self, role):
        """Файл прав роли."""
        return os.path.join(self.root, "Roles", role, "Ext", "Rights.xml")

    def _source_text(self, path, data):
        """Байты файла-источника ссылок -> текст в форме выгрузки."""
        return data.decode("utf-8-sig", "replace").replace("\r\n", "\n")

    # --- чтение: порт домена -------------------------------------------------

    def _module_path(self, name):
        return os.path.join(self.root, "CommonModules", name, "Ext", "Module.bsl")

    def common_module_exists(self, name):
        return os.path.isfile(self._module_path(name))

    def common_module_flags(self, name):
        """Читается тем же чтением, что и просмотр: спецификацией по схеме вида."""
        try:
            spec, _ = self.read_spec([("ОбщийМодуль", name)])
        except Refuse:
            return None
        return {флаг: bool(spec.get(флаг)) for флаг in REGISTRY["ОбщийМодуль"].CONTEXT_FLAGS}

    def common_module_lines(self, name):
        path = self._module_path(name)
        if not os.path.isfile(path):
            return None
        return re.split(r"\r\n|\n|\r", open(path, encoding="utf-8-sig", errors="replace").read())

    def roles_named(self, pattern):
        """Права ролей, чьи имена подходят под шаблон: {имя роли: выдачи} —
        только объекты, на которые выдано хоть одно право.

        Только каталоги этих ролей и их `Rights.xml`: сотни файлов вместо поиска
        по всей выгрузке.
        """
        папка = os.path.join(self.root, "Roles")
        if not os.path.isdir(папка):
            return {}
        шаблон = re.compile(pattern)
        найдено = {}
        for имя in sorted(os.listdir(папка)):
            права = self._rights_path(имя)
            if шаблон.fullmatch(имя) and os.path.isfile(права):
                with open(права, encoding="utf-8-sig", errors="replace") as файл:
                    текст = файл.read().replace("\r\n", "\n")
                найдено[имя] = mapping.granted_rights(self.tree.granted(self.tree.parse(текст)))
        return найдено

    def method_is_exported(self, module, method):
        path = self._module_path(module)
        if not os.path.isfile(path):
            return None
        text = open(path, encoding="utf-8-sig", errors="replace").read()
        start = re.search(
            rf"(?im)^[ \t]*(?:Процедура|Функция|Procedure|Function)[ \t]+{re.escape(method)}[ \t]*\(", text)
        if start is None:
            return False
        # Список параметров бывает многострочным, поэтому идём до парной скобки,
        # а не до конца строки.
        depth, i = 0, start.end() - 1
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        tail = text[i:i + 40]
        return re.match(r"\)\s*(Экспорт|Export)\b", tail, re.I) is not None

    def object_exists(self, kind, name):
        path = self.object_path(kind, name)
        if path is None:
            return None                     # вид без своего каталога — не судим
        return os.path.isfile(path)

    def object_path(self, kind, name):
        """Путь к карточке объекта по виду и имени. `None` — вид без каталога.

        Не путать с `card_path(card)`: тот берёт путь у готовой к записи
        карточки, а этот — у объекта, который уже лежит в выгрузке.

        Каталог спрашивается у схемы, а не у `FOLDERS`: та перечисляет виды,
        у которых бывают реквизиты, и общего модуля с подпиской в ней нет.
        """
        try:
            folder = mapping.container_of(kind)
        except Refuse:
            folder = vocabulary.FOLDERS.get(kind)
        if folder is None:
            return None
        return os.path.join(self.root, folder, name + ".xml")

    def read_card(self, kind, name):
        """Карточку -> дерево. `None`, если её нет или вид без каталога.

        Читает через `CardTree`, а не разбирает сам: побайтный круг доказан
        у реализации договора, и дублировать разбор здесь значит завести
        второе понимание формата, которое разойдётся с первым.
        """
        path = self.object_path(kind, name)
        if path is None or not os.path.isfile(path):
            return None
        text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
        return self.tree.parse(text)

    def read_spec(self, path):
        """Адрес -> спецификация. Читает то же, чем писала: схему видов."""
        file_path, document, rest = self.resolve(path)
        kind, element = path[0][0], document
        if rest:
            # Вложенная сущность адресуется тем же спуском, что и правка.
            element = self.tree.find(document, mapping.steps_of(rest))
            if element is None:
                адрес = ".".join(f"{k}.{n}" for k, n in path)
                raise Refuse(f"по адресу «{адрес}» ничего нет")
            kind = rest[-1][0]
        node = self.tree.to_node(element)
        spec = mapping.spec_from_node(kind, node)
        if not rest:
            формы = mapping.forms_from_node(node)
            if формы:
                spec.fields["формы"] = формы
        if kind == "Роль" and not rest:
            # Права роли — в своём файле рядом с карточкой; без него роль
            # показывалась бы пустой.
            rights = self._rights_path(path[0][1])
            if os.path.isfile(rights):
                text = open(rights, encoding="utf-8-sig").read().replace("\r\n", "\n")
                spec.fields.update(mapping.rights_from_node(self.tree.to_node(self.tree.parse(text))))
        return spec, file_path

    def taken_names(self, path):
        """Какие имена внутри хозяина уже заняты — объекта или его табличной части.

        Собирается разбором, а не регуляркой по отступу в три табуляции:
        регулярка держалась бы на том, что файл отформатирован ровно так.

        Адрес берётся целиком, а не первой парой: имя реквизита табличной
        части занято внутри неё, и спрашивать про объект бессмысленно —
        повтор внутри табличной части так не найти.

        Спрашивается про всех детей, а не про реквизиты: у платформы имена
        детей объекта — одно пространство. Счёт по тегу пропустил бы регистр
        с измерением «Организация» и ресурсом «Организация», а конфигурация
        с таким регистром не грузится.
        """
        host = self._host_at(path)
        return None if host is None else self.tree.child_names(host)

    def data_sources(self, path):
        """Имена источников данных схемы, внутри которой лежит адрес.

        Схема адресуется шагом «Макет», как и при записи, — поэтому спуск
        общий с занятостью имён. Спуск по карточке объекта привёл бы адрес
        внутрь схемы не туда: имена наборов данных лежат в файле макета, а не
        в карточке.
        """
        _, document, _ = self._resolve_quietly(path)
        if document is None or self.tree.document(document) != "DataCompositionSchema":
            return None
        return self.tree.child_names(document, "dataSource")

    def _resolve_quietly(self, path):
        """`resolve`, но молча: порт чтения на отсутствие отвечает `None`."""
        try:
            return self.resolve(path)
        except Refuse:
            return None, None, None

    def _host_at(self, path):
        """Узел, внутри которого живут дети по этому адресу. `None` — не нашли."""
        _, document, rest = self._resolve_quietly(path)
        if document is None:
            return None
        if not rest:
            return document
        return self.tree.find(document, mapping.steps_of(rest))

    def handler_arity(self, module, method):
        """Сколько параметров у метода общего модуля. `None` — метода нет."""
        path = self._module_path(module)
        if not os.path.isfile(path):
            return None
        text = open(path, encoding="utf-8-sig", errors="replace").read()
        found = re.search(
            rf"(?im)^[ \t]*(?:Процедура|Функция|Procedure|Function)[ \t]+"
            rf"{re.escape(method)}[ \t]*\(([^)]*)\)", text)
        if found is None:
            return None
        return len([p for p in found.group(1).split(",") if p.strip()])

    def configuration_name(self):
        """`<Name>` из свойств конфигурации — первое имя в реестре.

        Читается регуляркой по шапке, а не разбором: у реальной выгрузки
        крупной типовой конфигурации в файле 22 285 записей, а имя стоит в
        первых строках.
        """
        path = os.path.join(self.root, "Configuration.xml")
        try:
            with open(path, encoding="utf-8-sig") as source:
                head = source.read(self.EOL_HEAD)
        except OSError:
            return None
        found = re.search(r"<Name>([^<]+)</Name>", head)
        return found.group(1) if found else None

    #: Версия формата — атрибут корня `Configuration.xml`, а не объявления XML:
    #: у того свой `version="1.0"`.
    VERSION = re.compile(r'<MetaDataObject\b[^>]*?\sversion="([^"]+)"')

    def format_version(self):
        """Версия формата выгрузки из шапки `Configuration.xml`; `None` — не названа.

        Выгрузка конфигуратора называет её всегда; без неё бывают только
        выгрузки, собранные руками, и о них судить нечем.
        """
        path = os.path.join(self.root, "Configuration.xml")
        try:
            with open(path, encoding="utf-8-sig") as source:
                head = source.read(self.EOL_HEAD)
        except OSError:
            return None
        found = self.VERSION.search(head)
        return found.group(1) if found else None

    def _writable(self):
        """Писать можно только в выгрузку того формата, который инструмент пишет.

        Карточки формата 2.21, записанные в выгрузку платформы 8.3.27 (формат
        2.20), платформа не загружает: «Неизвестная версия формата 2.21
        загружаемого файла». Совместимость форматов не замерена, а запись «как
        получится» перекладывает проверку на загрузку в базу. Читать такую
        выгрузку можно; код модулей от формата не зависит, и его правка
        вставками этим отказом не затрагивается.
        """
        version = self.format_version()
        if version is not None and version != FORMAT_VERSION:
            raise Refuse(f"выгрузка формата {version}, а инструмент пишет формат {FORMAT_VERSION}: "
                         "файлы другого формата платформа может не принять (8.3.27 на 2.21 "
                         "отвечает «Неизвестная версия формата») — ничего не записано. "
                         "Правка кода вставками от формата не зависит")

    def register_write_mode(self, name):
        """Читается тем же чтением, что и просмотр: спецификацией по схеме вида."""
        try:
            spec, _ = self.read_spec([("РегистрСведений", name)])
        except Refuse:
            return None
        return spec.get("режимЗаписи") or None

    def defined_type_facets(self, name):
        path = os.path.join(self.root, "DefinedTypes", name + ".xml")
        if not os.path.isfile(path):
            return None
        text = open(path, encoding="utf-8-sig").read()
        body = re.search(r"<Type>(.*?)</Type>", text, re.S)
        if body is None:
            return None
        facets = []
        for is_set, notation in re.findall(
                r"<v8:(Type|TypeSet)>(cfg:[^<]*)</v8:\1>", body.group(1)):
            vtype = mapping.parse_type_notation(notation, is_set == "TypeSet")
            if vtype.facet and vtype.facet not in facets:
                facets.append(vtype.facet)
        return facets or None

    # --- запись --------------------------------------------------------------

    def card_path(self, card):
        return os.path.join(self.root, card.container, card.name + ".xml")

    #: Сколько байт файла хватает, чтобы увидеть его перевод строки.
    #: Первая строка выгрузки — объявление XML, дальше корень: если в этом
    #: куске `\r\n` не встретился, его в файле нет.
    EOL_HEAD = 4096

    def _encode(self, text, path=None):
        """Текст -> байты файла выгрузки: BOM и переводы строк.

        У существующего файла берутся его собственные переводы строк.
        Иначе правка одного свойства переписала бы файл целиком: конфигуратор
        пишет CRLF (это видно по эталонам выгрузки платформы), а карточки
        реальной выгрузки бывают с LF — 17 из 17 в выборке по пяти каталогам.
        Обещание «меняются ровно названные строки» на диске не выполнялось бы,
        и человек, переносящий правку в базу, видел бы diff во весь файл.
        Сравнение приведённых текстов этого не ловит.

        У нового файла — переводы строк площадки: так пишет конфигуратор,
        и таковы эталоны, с которыми сверяется побайтная проверка.

        Приведение всё равно нужно: текст модуля приходит от человека или
        из задания и может нести любые переводы строк.
        """
        unified = text.replace("\r\n", "\n")
        return (serializer.BOM + unified.replace("\n", self._eol_of(path))
                ).encode("utf-8")

    def _eol_of(self, path):
        """Перевод строки, которым записан файл. Нового файла — площадки."""
        if path is None:
            return self.eol
        try:
            with open(path, "rb") as source:
                head = source.read(self.EOL_HEAD)
        except OSError:
            return self.eol
        return "\r\n" if b"\r\n" in head else "\n"

    def prepare(self, cards):
        """Plan на создание объектов: карточки + записи в реестре.

        Ничего не пишет. Отказывается, если объект уже есть: перезапись
        существующего — другая операция, и делать её молча нельзя.

        Пачка обрабатывается одним планом, а записи в реестр копятся в одном
        разобранном дереве. Иначе задание из двух объектов дало бы два
        независимых изменения `Configuration.xml`, и второе затёрло бы первое.
        """
        self._writable()
        plan = Plan()
        taken = set()
        registry_path = self.registry_path()
        registry = self.tree.parse(self._read_text(registry_path))
        for card in cards:
            path = self.card_path(card)
            # Два разных случая с разными правками, и объяснять их одинаково
            # нельзя: человек пойдёт смотреть каталог, не найдёт там файла
            # и перестанет верить остальным сообщениям.
            if path in taken:
                # У карточки нет доменного вида (`card.kind` нет) — есть имя
                # элемента выгрузки; обратная таблица переводит его человеку.
                вид = mapping.ROOTS_BACK.get(card.element, card.element)
                raise Refuse(f"«{вид}.{card.name}» создаётся этим "
                             "заданием дважды")
            if os.path.exists(path):
                raise Refuse(f"карточка уже существует: {path}")
            taken.add(path)
            plan.add(path, self._encode(
                serializer.card_to_text(card, self.tree), path), True)
            for rel_path, content in card.satellites:
                satellite = os.path.join(self.root, card.container, card.name,
                                       *rel_path.split("/"))
                if os.path.exists(satellite):
                    raise Refuse(f"файл уже существует: {satellite}")
                # Спутник бывает и текстом (модуль), и деревом (файл прав роли):
                # собрать дерево в байты — здешнее дело, перекладка про файлы
                # не знает и отдаёт описание.
                text = (content if isinstance(content, str)
                        else self.tree.serialize(self.tree.build(content)))
                plan.add(satellite, self._encode(text, satellite), True)
            self._register(registry, card)
        plan.add(registry_path,
                 self._encode(self.tree.serialize(registry), registry_path),
                 False)
        return plan

    # --- формы -----------------------------------------------------------------

    def form_paths(self, owner, name):
        """Пути карточки формы, её описания и модуля."""
        if owner is None:
            base = os.path.join(self.root, "CommonForms")
        else:
            base = os.path.join(self.root, mapping.container_of(owner[0]), owner[1], "Forms")
        return (os.path.join(base, name + ".xml"),
                os.path.join(base, name, "Ext", "Form.xml"),
                os.path.join(base, name, "Ext", "Form", "Module.bsl"))

    def form_files(self, owner, name):
        """(файл описания формы, файл модуля или `None`, если модуля нет)."""
        _, form_path, module_path = self.form_paths(owner, name)
        return form_path, module_path if os.path.isfile(module_path) else None

    def read_form_text(self, owner, name):
        """Текст `Form.xml` формы (переводы строк приведены к `\\n`); `None` — нет."""
        try:
            _, form_path, _ = self.form_paths(owner, name)
        except Refuse:
            return None
        if not os.path.isfile(form_path):
            return None
        return self._read_text(form_path)

    def form_module_exists(self, owner, name):
        _, _, module_path = self.form_paths(owner, name)
        return os.path.isfile(module_path)

    def form_module_lines(self, owner, name):
        _, _, module_path = self.form_paths(owner, name)
        if not os.path.isfile(module_path):
            return None
        return re.split(r"\r\n|\n|\r", _read_text(module_path))

    def prepare_form_files(self, prepared):
        """Plan по подготовленным формам: новая — карточка, описание, модуль
        и запись у хозяина (или в реестре у общей формы); существующая —
        переписанное описание, в котором нетронутое осталось как было.
        Ничего не пишет.

        Карточка хозяина открывается один раз на всю пачку: две формы одного
        документа в одном задании — одна правка его карточки, а не две,
        затирающие друг друга.
        """
        self._writable()
        plan = Plan()
        opened = OrderedDict()
        registry = None
        registry_path = self.registry_path()
        taken = set()
        for item in prepared:
            edits = item.edits
            card_path, form_path, module_path = self.form_paths(edits.owner, edits.name)
            if form_path in taken:
                raise Refuse(f"форма «{edits.address}» правится этим заданием дважды")
            taken.add(form_path)
            for note in item.notes:
                plan.note(note)
            if item.card is None:
                plan.add(form_path, self._encode(item.form_text, form_path), False)
                if item.module is not None:
                    plan.add(module_path, self._encode(item.module, module_path), True)
                continue
            for path in (card_path, form_path):
                if os.path.exists(path):
                    raise Refuse(f"файл уже существует: {path}")
            plan.add(card_path, self._encode(
                self.tree.serialize(self.tree.build(item.card)), card_path), True)
            plan.add(form_path, self._encode(item.form_text, form_path), True)
            if item.module is not None:
                plan.add(module_path, self._encode(item.module, module_path), True)
            if edits.owner is None:
                if registry is None:
                    registry = self.tree.parse(self._read_text(registry_path))
                if edits.name in self.tree.child_names(registry, "CommonForm"):
                    raise Refuse(f"общая форма «{edits.name}» уже есть в Configuration.xml")
                tags = self.tree.child_elements(registry)
                self.tree.insert_child(registry, self._place(tags, "CommonForm",
                                                              vocabulary.GROUP_ORDER),
                                       mapping.Node("CommonForm", text=edits.name))
                plan.note(f"общая форма «{edits.name}» — в реестр конфигурации")
                continue
            self._attach_form(plan, opened, edits.create)
        for file_path, (document, _) in opened.items():
            plan.add(file_path, self._encode(self.tree.serialize(document), file_path), False)
        if registry is not None:
            plan.add(registry_path,
                     self._encode(self.tree.serialize(registry), registry_path), False)
        return plan

    def _attach_form(self, plan, opened, form):
        """`<Form>Имя</Form>` в детях хозяина и слот основной формы."""
        address = [(form.owner_kind, form.owner_name)]
        file_path, document, _ = self.resolve(address)
        if file_path not in opened:
            opened[file_path] = (document, self.tree.find(document, []))
        document, host = opened[file_path]
        if form.name in self.tree.child_names(document, "Form"):
            raise Refuse(f"у {form.owner_kind}.{form.owner_name} уже есть форма «{form.name}»")
        # Дети объекта верхнего уровня — тем же путём, что и реквизит при
        # создании: в конец группы своего вида, новая группа — по `CARD_ORDER`.
        order = vocabulary.CARD_ORDER.get(vocabulary.FOLDERS.get(form.owner_kind))
        if order is None:
            raise Refuse(f"порядок детей у «{form.owner_kind}» не замерен — "
                         "куда вставлять форму, из файлов не выводится")
        tags = self.tree.child_elements(document)
        self.tree.insert_child(document, self._place(tags, "Form", order),
                               mapping.Node("Form", text=form.name))
        plan.note(f"форма «{form.name}» — в состав {form.owner_kind}.{form.owner_name}")
        if form.default and form.default_slot:
            notation = mapping.object_notation(
                f"{form.owner_kind}.{form.owner_name}.Форма.{form.name}")
            described = mapping.translate_field(form.owner_kind, form.default_slot, notation)
            before = self.tree.set_property(host, described.tag, described)
            plan.note(f"{form.default_slot} у {form.owner_kind}.{form.owner_name}: "
                      f"«{before}» -> «{notation}»")

    # --- адресация -----------------------------------------------------------

    #: Шаг адреса, переводящий разговор в другой файл: схема компоновки живёт
    #: не в карточке объекта, а в макете рядом с ней.
    TEMPLATE_STEP = "Макет"

    def template_path(self, kind, name, template):
        """Путь к содержимому макета: `<вид>/<объект>/Templates/<макет>/Ext/Template.xml`."""
        card = self.object_path(kind, name)
        if card is None:
            return None
        return os.path.join(os.path.dirname(card), name, "Templates", template,
                            "Ext", "Template.xml")

    def resolve(self, path):
        """Адрес -> (путь к файлу, разобранное дерево, оставшиеся шаги).

        Адрес читается парами и может пересечь границу файла: шаг «Макет»
        переводит разговор из карточки объекта в её макет. Дальше всё
        одинаково — форма документа разбирается сама.
        """
        object_kind, object_name = path[0]
        rest = path[1:]
        # Сообщение цитирует то, что написал человек, а внутреннее устройство
        # приписывает следом. Одно «карточки „…\\Catalogs\\Имя.xml“ нет» при
        # опечатке в **виде** уводит в сторону — объект существует, просто
        # лежит в `Documents`, а человеку показывают отсутствие файла в
        # `Catalogs`.
        адрес = ".".join(f"{kind}.{name}" for kind, name in path)
        if rest and rest[0][0] == self.TEMPLATE_STEP:
            file_path = self.template_path(object_kind, object_name, rest[0][1])
            rest = rest[1:]
            if file_path is None:
                raise Refuse(f"в адресе «{адрес}» не знаю, где лежат объекты "
                             f"вида «{object_kind}»")
            if not os.path.isfile(file_path):
                raise Refuse(f"по адресу «{адрес}» макета нет "
                             f"(искали {file_path})")
        else:
            file_path = self.object_path(object_kind, object_name)
            if file_path is None:
                raise Refuse(f"в адресе «{адрес}» не знаю, где лежат объекты "
                             f"вида «{object_kind}»")
            if not os.path.isfile(file_path):
                raise Refuse(f"по адресу «{адрес}» объекта нет "
                             f"(искали {file_path})")
        return file_path, self.tree.parse(self._read_text(file_path)), rest

    # --- обратный поиск ------------------------------------------------------

    #: Каталоги, которые обход не открывает. `Forms` в выгрузке крупной типовой
    #: конфигурации — 23 443 файла (415 МБ мелочью), читаются две минуты, а
    #: ссылок в нашем смысле не несут. Код
    #: BSL инструмент не разбирает вовсе, и о непроверенном инвариант удаления
    #: говорит вслух — молчать об этом хуже, чем отказаться проверять.
    SKIP_FOLDERS = ("Forms",)

    #: Корень документа, по которому макет опознаётся как схема компоновки.
    #: Тот же признак, по которому разбор выбирает форму документа.
    SCHEMA_ROOT = b"DataCompositionSchema"

    #: Сколько байт хватает, чтобы увидеть корень документа.
    HEAD = 400

    def _reference_sources(self):
        """Все файлы выгрузки, где бывают ссылки на объект.

        Обход идёт вглубь, а не на один уровень. Плоское перечисление
        пропустило бы подчинённые подсистемы — `Subsystems/<Родитель>/Subsystems/
        <Дочерняя>.xml`, — а в реальной выгрузке это 1257 карточек и 19 208
        ссылок вида `<xr:Item>Catalog.Имя</xr:Item>`. Удаление такого объекта
        прошло бы с вердиктом «ссылок нет», и получилась бы конфигурация,
        которую платформа не принимает: ровно то, ради чего инвариант и заведён.
        """
        # Раскладка знает все каталоги объектов — и тех видов, которых
        # инструмент не создаёт: функциональная опция, общий реквизит, критерий
        # отбора держат ссылки, и без слова вида держатель назывался бы
        # каталогом выгрузки (`FunctionalOptions.Имя`).
        back = {folder: kind for folder, (kind, _) in OBJECT_FOLDERS.items()}
        back.update({folder: kind for kind, folder in vocabulary.FOLDERS.items()})
        # Схема знает контейнеры видов, которых нет в `FOLDERS` (подписка,
        # общий модуль): без этого ссылка называлась бы каталогом выгрузки.
        back.update({schema.container: kind for kind, schema in SCHEMA.items()
                     if schema.container})
        for folder, subfolders, names in os.walk(self.root):
            relative = os.path.relpath(folder, self.root)
            subfolders[:] = [d for d in subfolders if d not in self.SKIP_FOLDERS]
            if relative == ".":
                # Реестр конфигурации ссылки несёт, и настоящие: основные роли,
                # хранилище вариантов отчётов, общие формы, язык — восемь штук
                # вне раздела детей. Исключить файл целиком как «сам себе не
                # ссылка» нельзя: про раздел детей это верно, про всё
                # остальное — нет, и роль удалялась бы с вердиктом «ссылок нет».
                # Сами записи раздела детей под обозначение не подходят: точки
                # в имени нет ни у одной из 22 285 записей замеренной выгрузки.
                #
                # `ConfigDumpInfo.xml` не берётся намеренно: в крупной выгрузке
                # это 41 МБ и 87 134 обозначения — там названы все объекты
                # подряд, и по нему ссылка нашлась бы на что угодно. Платформа
                # его пересобирает при загрузке, инструмент его не трогает вовсе.
                yield ReferenceSource(os.path.join(folder, "Configuration.xml"),
                                      "Конфигурация", "Конфигурация", None)
                continue
            parts = relative.split(os.sep)
            kind = back.get(parts[0], parts[0])
            inside_ext = "Ext" in parts
            for name in sorted(names):
                if inside_ext:
                    # Из `Ext` берутся права и схемы компоновки. Модули — код
                    # BSL, его инструмент не разбирает; справка, картинки и
                    # прочие макеты ссылок в нашем смысле не несут.
                    if name == "Rights.xml":
                        yield ReferenceSource(os.path.join(folder, name),
                                              f"{kind}.{parts[-2]} (права)",
                                              None, kind)
                    elif name == "Template.xml":
                        path = os.path.join(folder, name)
                        if self._is_schema(path):
                            yield ReferenceSource(
                                path, f"{kind}.{parts[1]} (макет {parts[-2]})",
                                f"{kind}.{parts[1]}.{self.TEMPLATE_STEP}.{parts[-2]}",
                                None)
                    continue
                if name.endswith(".xml"):
                    # Каталог в середине пути называется словом вида, как
                    # в полном имени платформы: подчинённая подсистема из
                    # `Subsystems/Родитель/Subsystems/` — это
                    # «Подсистема.Родитель.Подсистема.Дочерняя».
                    inner = [back.get(part, part) if position % 2 else part
                             for position, part in enumerate(parts[1:])]
                    owner = ".".join([kind, *inner, name[:-4]])
                    yield ReferenceSource(os.path.join(folder, name), owner,
                                          owner, kind)

    def _note_query_mentions(self, plan, path, что):
        """Сказать про схемы, где объект назван в запросе. Их мы не правим."""
        mentions = self._query_mentions(path)
        if not mentions:
            return
        plan.note("{}: в текстах запросов назван ещё в {} — имя там "
                  "не переписывается, поправьте запрос в конфигураторе"
                  .format(что, ", ".join(mentions[:5])
                          + (f" и ещё {len(mentions) - 5}"
                             if len(mentions) > 5 else "")))

    def _query_mentions(self, path):
        """Схемы, где объект назван в тексте запроса.

        Переименование и удаление ищут английское обозначение —
        `d4p1:CatalogRef.Имя` в типе параметра, `Catalog.Имя` в правах и
        составе подсистемы. В тексте запроса объект назван по-русски
        («ИЗ Документ.мой_Проба»), и под это обозначение не подходит.

        Молчать об этом нельзя: из 926 схем реальной выгрузки в 608 хотя бы
        один объект назван **только** в запросе. Там переименование честно
        ответило бы «ссылок — 0» и оставило бы отчёт сломанным. Инструмент
        текст запроса не правит (это язык запросов, а не выгрузка) — он о нём
        предупреждает.
        """
        kind, name = path[0]
        if len(path) != 1 or kind not in vocabulary.QUERY_DESIGNATION:
            return []
        needle = name.encode("utf-8")
        pattern = re.compile(r"(?<![\w.])" + kind + r"\." + re.escape(name)
                             + r"(?![\w])")
        found = []
        for source in self._reference_sources():
            if os.path.basename(source.path) != "Template.xml":
                continue
            try:
                with open(source.path, "rb") as file:
                    data = file.read()
            except OSError:
                continue
            if needle not in data:
                continue
            if pattern.search(data.decode("utf-8-sig", "replace")):
                found.append(source.owner)
        return found

    def _is_schema(self, path):
        """Лежит ли в макете схема компоновки данных.

        Читать все макеты нельзя: в крупной выгрузке их 14 447 на 3,4 ГБ — в
        восемь раз дороже форм, которые исключены осознанно. Схем среди них
        926 на 86 МБ, то есть дешевле уже читаемых карточек. Отбор идёт по
        корню документа —
        по тому же признаку, по которому разбор выбирает форму документа.

        Ответ запоминается на весь экземпляр: пачка переименований спрашивает
        источники по разу на объект, а 14 447 открытий стоят 4,8 с каждый раз.
        Кеш живёт до записи — после неё экземпляр не переиспользуется.
        """
        known = self._schemas.get(path)
        if known is None:
            try:
                with open(path, "rb") as source:
                    known = self.SCHEMA_ROOT in source.read(self.HEAD)
            except OSError:
                known = False
            self._schemas[path] = known
        return known

    def references_to(self, path):
        """Где ссылаются на объект или его часть: держатель и место в нём.

        «Документ.мой_Заявка.ТабличнаяЧасть.Товары.Реквизит.Склад (тип)» —
        кто держит и что именно править: тип реквизита, запись прав и пункт
        состава подсистемы правятся по-разному, и открывать ради этого каждую
        карточку — работа, которую поиск уже сделал. Где места не назвать
        (права роли; совпадение не в тексте узла), назван держатель целиком.

        Сначала дешёвый отсев поиском имени по байтам, потом точная проверка
        обозначением — иначе на каждое удаление уходило бы полсотни секунд
        только на раскодирование 1,4 ГБ, из которых имя встречается в сотнях.
        Разбирается деревом только то, что отсев прошло.

        У адреса внутри схемы компоновки внешних ссылок не бывает: набор
        данных, параметр и пункт настроек снаружи никак не назвать — обозначение
        строится от объекта метаданных. Это не «не смогли проверить», а «нечему
        ссылаться»; о том, что связи внутри самой схемы не проверяются, говорит
        отдельное предупреждение.
        """
        if any(kind == self.TEMPLATE_STEP for kind, _ in path):
            return []
        pattern = mapping.reference_pattern(path)
        found = []
        for _, source, text in self._referencing(path):
            for place in self._places(source, text, pattern):
                if place not in found:
                    found.append(place)
        return found

    def _places(self, source, text, pattern):
        """Места ссылок в одном файле; держатель целиком, когда места не назвать."""
        if source.address is None:
            return [source.owner]
        try:
            places = self.tree.reference_places(self.tree.parse(text), pattern)
        except Refuse:
            return [source.owner]
        return [mapping.reference_place(source.address, source.kind, steps, prop)
                for steps, prop in places] or [source.owner]

    def _referencing(self, path, skip_own=True, texts=None, moved=None, skip=()):
        """(путь к файлу, источник, текст) для каждого файла со ссылкой на цель.

        Сначала дешёвый отсев поиском имени по байтам, потом точная проверка
        обозначением — иначе на каждое удаление уходило бы полсотни секунд
        только на раскодирование 1,4 ГБ, из которых имя встречается в сотнях.
        """
        pattern = mapping.reference_pattern(path)
        needle = path[-1][1].encode("utf-8")
        own = self.object_path(*path[0])
        for source in self._reference_sources():
            source_path = file_path = source.path
            if skip_own and file_path == own:
                continue                      # сам себя объект не держит
            if file_path in skip:
                continue                      # у этого файла есть свой хозяин
            # Карточка, переехавшая в этой же пачке, на диске лежит под прежним
            # именем; править надо тот текст, который пойдёт в новый файл, и
            # под новым же путём его возвращать.
            if moved and file_path in moved:
                file_path = moved[file_path]
            # Текст, уже поправленный в этой же пачке, берётся из памяти:
            # на диске он ещё старый, и перечитывание потеряло бы правку.
            text = None if texts is None else texts.get(file_path)
            if text is None:
                try:
                    with open(source_path, "rb") as file:
                        data = file.read()
                except OSError:
                    continue
                if needle not in data:
                    continue
                text = self._source_text(source_path, data)
            elif needle.decode("utf-8") not in text:
                continue
            if pattern.search(text):
                yield file_path, source, text

    # --- удаление ------------------------------------------------------------

    def prepare_deletion(self, paths):
        """Plan на удаление объектов и вложенных сущностей. Ничего не пишет."""
        self._writable()
        plan = Plan()
        opened = OrderedDict()
        removed_objects = []
        # Что удаляется целиком, известно до начала работы: проверка только
        # назад по уже собранному списку пропустила бы то же задание с двумя
        # переставленными строками. План вышел бы самопротиворечивым — файл
        # сначала переписывался бы с вырезанным реквизитом, потом удалялся, —
        # а инвариант, который зависит от порядка набора строк, инвариантом
        # не является.
        целиком = {tuple(path[0]) for path in paths if len(path) == 1}
        собранные = Собранные("не нашлось")
        for path in paths:
            object_kind, object_name = path[0]
            if len(path) == 1:
                # Своя ветка: объект целиком удаляется не спуском по дереву,
                # а снятием файлов. Отказы здесь копятся наравне с прочими
                # и называют адрес, как в соседней ветке про вложенные: работа
                # не рвётся на первом же ненайденном объекте.
                file_path = self.object_path(object_kind, object_name)
                if file_path is None:
                    собранные.добавить(
                        f"в адресе «{object_kind}.{object_name}» не знаю, "
                        f"где лежат объекты вида «{object_kind}»")
                    continue
                if not os.path.isfile(file_path):
                    собранные.добавить(
                        f"по адресу «{object_kind}.{object_name}» объекта нет "
                        f"(искали {file_path})")
                    continue
                removed_objects.append((path[0], file_path))
                continue
            # Вид входит в сравнение: `Справочник.Заявка` и `Документ.Заявка`
            # — разные объекты, и удаление первого целиком не мешает удалить
            # реквизит второго тем же заданием.
            if (object_kind, object_name) in целиком:
                raise Refuse(f"объект «{object_kind}.{object_name}» удаляется "
                             "целиком — удалять его часть отдельно незачем")
            # Адрес читается общей адресацией, как у правки и добавления:
            # шаг «Макет» переводит разговор в схему компоновки. Своя копия
            # спуска умела бы только карточку объекта, и убрать добавленный
            # набор данных или отбор было бы нечем.
            try:
                file_path, document, rest = self.resolve(path)
            except Refuse as отказ:
                собранные.добавить(str(отказ))
                continue
            document = opened.setdefault(file_path, document)
            steps = mapping.steps_of(rest)
            if not self.tree.remove_child(document, steps):
                собранные.добавить("в «{}» нет «{}»".format(
                    os.path.basename(file_path),
                    ".".join(f"{kind}.{name}" for kind, name in rest)))
                continue
            plan.note("удалить {}".format(
                ".".join(f"{kind}.{name}" for kind, name in path)))
        собранные.предъявить()
        for file_path, document in opened.items():
            plan.add(file_path,
                     self._encode(self.tree.serialize(document), file_path),
                     False)
        if removed_objects:
            self._erase_objects(plan, removed_objects)
        return plan

    def _erase_objects(self, plan, removed):
        """Карточка, файлы-спутники и запись в реестре — за один план."""
        registry_path = self.registry_path()
        registry = self.tree.parse(self._read_text(registry_path))
        for (kind, name), file_path in removed:
            plan.note(f"удалить {kind}.{name} целиком")
            self._note_query_mentions(plan, [(kind, name)], f"{kind}.{name}")
            plan.erase(file_path)
            folder = os.path.join(os.path.dirname(file_path), name)
            for inside, _, names in os.walk(folder):
                for satellite in sorted(names):
                    plan.erase(os.path.join(inside, satellite))
            tag = mapping.registry_tag_of(kind)
            if not self.tree.remove_child(registry, [(tag, name)]):
                raise Refuse(f"объекта «{name}» нет в Configuration.xml")
        plan.add(registry_path,
                 self._encode(self.tree.serialize(registry), registry_path),
                 False)

    def prepare_rename(self, renames):
        """Plan на переименование объектов. Ничего не пишет.

        Имя объекта живёт в четырёх местах сразу, и переименование — это
        не правка поля, а согласованная замена во всех: в собственной карточке
        (`<Name>`, имена порождаемых типов, ввод по строке), в имени файла
        и каталога-спутника, в записи реестра конфигурации и в каждой чужой
        карточке, которая на объект ссылается.

        Замена идёт тем же обозначением, которым ищутся ссылки: одно правило
        на все формы записи — от `cfg:CatalogRef.Имя` до
        `DocumentTabularSection.Имя.ТЧ`.
        """
        self._writable()
        plan = Plan()
        registry_path = self.registry_path()
        registry = self.tree.parse(self._read_text(registry_path))
        # Один текст на файл на всю пачку. Без этого второе переименование
        # перечитало бы ссылающуюся карточку с диска и затёрло бы правку
        # первого: в плане оказались бы две записи на один путь, выиграла бы
        # последняя, а старый файл к тому времени уже удалён — осталась бы
        # висячая ссылка, и конфигурация не загрузилась бы. Соседние операции
        # держат одно дерево на файл по той же причине.
        touched = OrderedDict()
        # Куда переехала карточка внутри этой же пачки. На диске она лежит под
        # прежним именем, и без этой таблицы следующее переименование нашло бы
        # её по старому пути, поправило прочитанный с диска текст — то есть
        # потеряло бы первое переименование — и положило результат в файл,
        # который тот же план удаляет.
        moved = OrderedDict()
        # Пути, занятые пачкой. Проверять только диск нельзя: на диске новой
        # карточки ещё нет, и два переименования в одно имя прошли бы молча —
        # один объект исчез бы совсем, а в реестре остались бы две записи.
        claimed = {}
        # Обозначения всей пачки: реестр правится один раз в конце, и по нему
        # проходят все замены разом.
        patterns = []
        for path, new_name in renames:
            kind, old_name = path[0]
            old_path = self.object_path(kind, old_name)
            if old_path is None:
                raise Refuse(f"не знаю, где лежат объекты вида «{kind}»")
            if old_path in moved:
                raise Refuse(f"«{kind}.{old_name}» уже переименован в этом "
                             "задании — дважды переименовать нельзя")
            if not os.path.isfile(old_path):
                raise Refuse(f"карточки «{old_path}» нет")
            new_path = self.object_path(kind, new_name)
            if os.path.exists(new_path):
                raise Refuse(f"карточка «{new_path}» уже существует")
            if new_path in claimed:
                raise Refuse(f"имя «{kind}.{new_name}» в этом задании уже занято "
                             f"переименованием «{claimed[new_path]}»")
            claimed[new_path] = f"{kind}.{old_name}"

            pattern = mapping.reference_pattern(path)
            patterns.append((pattern, new_name))
            count = 0
            # Реестр пропускается: его правит дерево ниже, и два писателя
            # в один файл дали бы две записи в плане — выиграла бы последняя.
            for file_path, _, text in self._referencing(
                    path, texts=touched, moved=moved, skip={registry_path}):
                touched[file_path] = _rename_in(pattern, text, new_name)
                count += 1

            own = touched.pop(old_path, None)
            if own is None:
                own = self._read_text(old_path)
            card = self.tree.parse(_rename_in(pattern, own, new_name))
            self.tree.set_property(self.tree.find(card, []), "Name",
                                   mapping.Node("Name", text=new_name))
            # Своя карточка идёт в общий свод, а не прямо в план: следующее
            # переименование пачки может сослаться на неё, и текст должен быть
            # один — тот, что уже поправлен.
            touched[new_path] = self.tree.serialize(card)
            moved[old_path] = new_path
            plan.erase(old_path)
            self._move_satellites(plan, old_path, old_name, new_name)

            # Запись переименовывается на месте, а не снимается и дописывается
            # в конец своей группы: иначе справочник, стоявший шестым из семи,
            # стал бы седьмым, а в реальной выгрузке уехал бы на дно списка из
            # 1184. Порядок в реестре — это порядок
            # дерева метаданных в конфигураторе, а не вычисляемая величина,
            # и переставлять его переименование не просило.
            tag = mapping.registry_tag_of(kind)
            entry = self.tree.find(registry, [(tag, old_name)])
            if entry is None:
                raise Refuse(f"объекта «{old_name}» нет в Configuration.xml")
            self.tree.set_text(entry, new_name)
            plan.note(f"переименовать {kind}.{old_name} в {new_name}: "
                      f"карточка, реестр и ссылок в других карточках — {count}")
            self._note_query_mentions(plan, [(kind, old_name)],
                                      f"{kind}.{old_name}")
        for file_path, text in touched.items():
            plan.add(file_path, self._encode(text, file_path),
                     file_path in claimed)
        # Запись раздела детей уже переставлена в дереве; здесь переписываются
        # ссылки вне него — основные роли, хранилище вариантов отчётов, общие
        # формы. Записи раздела детей замена не задевает: обозначение требует
        # точки, а в именах её нет ни у одной из 22 285 в замеренной выгрузке.
        registry_text = self.tree.serialize(registry)
        for pattern, new_name in patterns:
            registry_text = _rename_in(pattern, registry_text, new_name)
        plan.add(registry_path, self._encode(registry_text, registry_path), False)
        return plan

    def _move_satellites(self, plan, old_path, old_name, new_name):
        """Каталог-спутник переезжает вместе с объектом: модуль, права, макеты."""
        container = os.path.dirname(old_path)
        old_folder = os.path.join(container, old_name)
        if not os.path.isdir(old_folder):
            return
        for inside, _, names in os.walk(old_folder):
            for name in sorted(names):
                source = os.path.join(inside, name)
                target = os.path.join(container, new_name,
                                      os.path.relpath(source, old_folder))
                plan.add(target, _read_bytes(source), True)
                plan.erase(source)

    def prepare_addition(self, additions):
        """Plan на добавление вложенной сущности по адресу. Ничего не пишет.

        Адрес указывает хозяина — объект, его табличную часть или схему
        компоновки в макете, — а вид ребёнка задаётся отдельно. Так измерение,
        ресурс и табличную часть можно добавить в существующий объект, а не
        только вместе с его созданием.
        """
        self._writable()
        plan = Plan()
        opened = OrderedDict()
        собранные = Собранные("не нашлось")
        for path, node, name, kind, shown in additions:
            try:
                file_path, document, rest = self.resolve(path)
            except Refuse as отказ:
                собранные.добавить(str(отказ))
                continue
            document = opened.setdefault(file_path, document)
            steps = mapping.steps_of(rest)
            host = self.tree.find(document, steps)
            if host is None:
                raise Refuse("в «{}» нет «{}»".format(
                    os.path.basename(file_path),
                    ".".join(f"{kind}.{name_}" for kind, name_ in rest)))
            host = self._descend(document, host, mapping.containers_of(kind),
                                 path[0][0])
            # Спрашивается тот узел, куда ребёнок и ляжет, а не хозяин выше:
            # пункт настроек живёт не в варианте, а в своём контейнере внутри
            # него, и проверка в варианте не нашла бы ничего никогда.
            #
            # Срабатывает она там, где у ребёнка есть имя. У пунктов настроек
            # его нет, и это не упущение: повторы в них законны — 38 повторов
            # ключа на 18 113 выбираемых полей в 926 схемах реальной выгрузки.
            # Запрет противоречил бы типовым отчётам.
            if name and name in self.tree.child_names(host, node.tag):
                raise Refuse("«{}» уже есть в «{}»".format(
                    name, ".".join(f"{k}.{n}" for k, n in path)))
            index = self._child_index(document, host, path[0][0], node.tag)
            self.tree.insert_child_of(host, index, node)
            plan.note("добавить «{}» ({}) в {}".format(
                shown, kind,
                ".".join(f"{kind_}.{name_}" for kind_, name_ in path)))
        собранные.предъявить()
        for file_path, document in opened.items():
            plan.add(file_path,
                     self._encode(self.tree.serialize(document), file_path),
                     False)
        return plan

    def _descend(self, document, host, containers, kind):
        """Спуститься в контейнеры внутри хозяина, заведя недостающие.

        У свежей схемы настройки пусты — `<dcsset:settings/>` без содержимого.
        Контейнер заводится на своём месте по замеренному порядку, а не в конец:
        иначе отбор оказался бы после структуры, и это уже другие настройки.
        """
        for tag in containers:
            found = self.tree.child_by_tag(host, tag)
            if found is None:
                index = self._child_index(document, host, kind, tag)
                self.tree.insert_child_of(host, index, mapping.Node(tag))
                found = self.tree.child_by_tag(host, tag)
            host = found
        return host

    def prepare_changes(self, changes):
        """Plan на правку свойств. Ничего не пишет.

        Карточка каждого объекта разбирается один раз: две правки одного файла
        обязаны лечь в одно изменение, иначе вторая затрёт первую.
        """
        self._writable()
        plan = Plan()
        opened = OrderedDict()
        собранные = Собранные("не нашлось")
        for path, fields in changes:
            try:
                file_path, card, rest = self.resolve(path)
            except Refuse as отказ:
                собранные.добавить(str(отказ))
                continue
            if file_path in opened:
                card = opened[file_path]          # два изменения одного файла —
            else:                                  # одно дерево, иначе второе
                opened[file_path] = card           # затрёт первое
            steps = mapping.steps_of(rest)
            node = self.tree.find(card, steps)
            if node is None:
                собранные.добавить("в «{}» нет «{}»".format(
                    os.path.basename(file_path),
                    ".".join(f"{kind}.{name}" for kind, name in rest)))
                continue
            target_kind = path[-1][0]
            host = path[-2][0] if len(path) > 1 else None
            for field, value in fields.items():
                described = mapping.translate_field(target_kind, field, value, host)
                before = self.tree.set_property(node, described.tag, described)
                after = self.tree.property_text(node, described.tag)
                # Значение печатается и как в задании, и как ляжет в файл:
                # задание пишется по-русски, а «было Contains стало BeginsWith»
                # заставляет переводить обратно в голове, чтобы убедиться,
                # что просил именно это.
                # Русская половина печатается только тогда, когда она
                # действительно другая и действительно русская: иначе у булева
                # получилось бы «было true стало False (false)» — слева
                # написание выгрузки, справа питоновское.
                как_в_файле = _compact(after)
                как_задано = _compact(str(value))
                показать_обе = (isinstance(value, str)
                                and как_задано != как_в_файле)
                стало = (f"{как_задано} ({как_в_файле})" if показать_обе
                         else как_в_файле)
                plan.note("{}: {} было {} стало {}".format(
                    ".".join(f"{kind}.{name}" for kind, name in path),
                    field, _compact(before), стало))
        собранные.предъявить()
        for file_path, card in opened.items():
            plan.add(file_path,
                     self._encode(self.tree.serialize(card), file_path),
                     False)
        return plan

    def _child_index(self, document, host, kind, tag):
        """Куда встаёт новый ребёнок объекта.

        В конец своей группы, а новая группа — по замеренному порядку.
        Платформа переставляет группы в свой порядок, значит порядок
        канонический, и его можно не угадывать (скажем, по тому, что
        `Attribute` идёт первым в 96 % карточек), а знать.
        """
        шапка = self.tree.document(document)
        # Порядок ищется сперва у самого хозяина: у контейнера настроек он свой,
        # у схемы — один на документ, у карточки — свой на каждый вид.
        order = (vocabulary.CONTAINER_ORDER.get(self.tree.tag_of(host))
                 or (vocabulary.DOCUMENT_ORDER.get(шапка)
                     if шапка != "MetaDataObject"
                     else vocabulary.CARD_ORDER.get(vocabulary.FOLDERS.get(kind))))
        if order is None:
            raise Refuse(f"порядок детей у «{kind}» не замерен — "
                         "куда вставлять ребёнка, из файлов не выводится")
        # Внутри табличной части бывает один вид детей — реквизит, — и порядок
        # там не из чего выводить. Порядок карточки объекта сошёлся бы здесь
        # именно поэтому, а не потому, что он там верен. Появится
        # второй вид — ошибка будет тихой, и потому проверяется здесь.
        if self.tree.tag_of(host) == "TabularSection":
            присутствуют = {self.tree.local_name(t)
                            for t in self.tree.child_elements_of(host)}
            присутствуют.add(self.tree.local_name(tag))
            if присутствуют - {"Attribute"}:
                raise Refuse(
                    "порядок детей внутри табличной части не замерен, "
                    f"а их тут больше одного вида: {', '.join(sorted(присутствуют))}")
        # Теги сравниваются без приставки пространства имён: в порядке они
        # записаны разобранными именами, а у схемы компоновки почти всё
        # с приставкой. Приводит их сам разбор — здесь имя уже разобранное.
        return self._place(self.tree.child_elements_of(host),
                           self.tree.local_name(tag), order)

    def _register(self, registry, card):
        """Врезка `<Тег>Имя</Тег>` в `<ChildObjects>` файла Configuration.xml.

        Место — в конец группы своего вида. Порядок внутри группы произволен
        (в выгрузке он не алфавитный), на поведение не влияет, поэтому выбрано
        одно предсказуемое правило.

        Если объект заводится первым в своём виде, группы в файле ещё нет,
        и она ставится по `vocabulary.GROUP_ORDER` — перед ближайшей следующей
        из существующих. Порядок групп, в отличие от порядка внутри группы,
        не произволен: конфигуратор пишет его всегда одинаково.
        """
        tag = card.registry_tag
        if card.name in self.tree.child_names(registry, tag):
            raise Refuse(f"объект «{card.name}» уже зарегистрирован в Configuration.xml")
        tags = self.tree.child_elements(registry)
        self.tree.insert_child(registry, self._place(tags, tag, vocabulary.GROUP_ORDER),
                               mapping.Node(tag, text=card.name))

    @staticmethod
    def _place(tags, tag, order):
        """Место новой записи среди детей: в конец своей группы, иначе по порядку.

        Один механизм на два случая — дети объекта и записи в `Configuration.xml`.
        Раздел детей у конфигурации устроен так же, как у объекта, и порядок
        групп в обоих канонический; разные у них только таблицы порядка.
        """
        if tag in tags:                                  # группа есть — в её конец
            return len(tags) - tags[::-1].index(tag)
        if tag not in order:
            raise Refuse(f"вид «{tag}» не значится в порядке групп")
        position = order.index(tag)
        for following in order[position + 1:]:           # перед следующей группой
            if following in tags:
                return tags.index(following)
        for previous in reversed(order[:position]):      # или после предыдущей
            if previous in tags:
                return len(tags) - tags[::-1].index(previous)
        return len(tags)
