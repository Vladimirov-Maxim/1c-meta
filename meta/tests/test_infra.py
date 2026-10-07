"""Проверка инфраструктуры: сериализация, запись, реестр, чтение конфигурации.

Три опоры, от слабой к сильной:

1. `test_all_subscription_cards_bytewise` и `test_all_modules_bytewise` — 639 подписок
   и 4100 общих модулей из корпуса разбираются и собираются обратно. Много
   эталонов, которые никто не подгонял, но переводы строк там сглажены git;
2. `test_matches_platform_dump` — эталон выгружен самой платформой: модуль,
   записанный инструментом в пустую выгрузку, конфигуратор загружает в базу
   и выгружает обратно. Сверка побайтная, включая переводы строк;
3. остальное — поведение записи: атомарность, отказы, место группы в реестре.

Запись проверяется на игрушечной выгрузке во временном каталоге; настоящая
выгрузка (корпус) в этих тестах только читается.
"""

import collections
import os
import re
import shutil
import sys
import tempfile
from collections import OrderedDict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping, schema, vocabulary  # noqa: E402
from meta.application import ports
from meta.application.add_child.use_case import AddChildUseCase  # noqa: E402
from meta.application.add_object.use_case import AddObjectUseCase  # noqa: E402
from meta.application.change_property.use_case import ChangePropertyUseCase  # noqa: E402
from meta.application.delete.use_case import DeleteUseCase  # noqa: E402
from meta.application.rename.use_case import RenameUseCase  # noqa: E402
from meta.domain.model import Refuse, Spec, TypeRef  # noqa: E402
from meta.infra import serializer  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.infra.repository import (
    Plan,  # noqa: E402
    Repository,  # noqa: E402
)
from meta.jobs import dialect as job_dialect  # noqa: E402
from meta.tests import corpus  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402
from meta.tests.corpus import CORPUS as SOURCES  # noqa: E402

SUBSCRIPTIONS = os.path.join(SOURCES, "EventSubscriptions")

REFERENCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны")

# Сверка с корпусом идёт без учёта переводов строк, и вот почему. Платформа
# пишет CRLF (доказано загрузкой и обратной выгрузкой на пустой базе), а git
# при `core.autocrlf=true` сворачивает их в индексе, поэтому в рабочем каталоге
# LF у всего, что пришло из git, а не из свежей выгрузки. Переводы строк
# проверяются отдельно и строго — на эталоне, выгруженном самой платформой.


# --- разбор настоящей карточки (только для тестов) ---------------------------

def spec_from_file(path):
    """Файл выгрузки -> (uuid, спецификация на языке домена).

    Разбор построчный: выгрузка форматирована табами, узел на строку. Обратная
    перекладка берётся из `mapping`, чтобы словарь выгрузки был описан один раз.
    """
    text = open(path, encoding="utf-8-sig").read()
    uuid = re.search(r'<\w+ uuid="([^"]+)"', text).group(1)
    properties = re.search(r"<Properties>(.*?)</Properties>", text, re.S).group(1)
    synonym = re.findall(
        r"<v8:lang>(.*?)</v8:lang>\s*<v8:content>(.*?)</v8:content>", properties, re.S)
    comment = re.search(r"<Comment>(.*?)</Comment>", properties, re.S)
    source = [mapping.parse_type_notation(item, tag == "TypeSet")
                for tag, item in re.findall(
                    r"<v8:(Type|TypeSet)>(cfg:.*?)</v8:\1>", properties)]
    event = re.search(r"<Event>(.*?)</Event>", properties).group(1)
    return uuid, Spec("ПодпискаНаСобытие", {
        "имя": re.search(r"<Name>(.*?)</Name>", properties).group(1),
        "синоним": OrderedDict(synonym) if synonym else "",
        "комментарий": comment.group(1) if comment else "",
        "источник": source,
        "событие": vocabulary.EVENTS_BACK[event],
        "обработчик": re.search(
            r"<Handler>CommonModule\.(.*?)</Handler>", properties).group(1),
    })


def build_bytes(uuid, spec):
    card = mapping.translate(spec, uuid)
    lines = serializer.card_to_lines(card)
    return (serializer.BOM + "\n".join(lines)).encode("utf-8")


# --- игрушечная выгрузка -----------------------------------------------------

REGISTRY_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\r\n'
    '<MetaDataObject>\r\n'
    '\t<Configuration>\r\n'
    '\t\t<ChildObjects>\r\n'
    '\t\t\t<CommonModule>мой_Тест</CommonModule>\r\n'
    '\t\t\t<EventSubscription>СтараяПодписка</EventSubscription>\r\n'
    '\t\t\t<ScheduledJob>Регламент</ScheduledJob>\r\n'
    '\t\t</ChildObjects>\r\n'
    '\t</Configuration>\r\n'
    '</MetaDataObject>'
)

MODULE_BSL = (
    "Процедура мой_ЗаявкаПередЗаписьюОбработчик(Источник, Отказ) Экспорт\n"
    "\tВозврат;\n"
    "КонецПроцедуры\n"
    "\n"
    "Процедура НеЭкспортный(Источник, Отказ)\n"
    "КонецПроцедуры\n"
)


def sandbox():
    root = tempfile.mkdtemp(prefix="meta-")
    open(os.path.join(root, "Configuration.xml"), "w",
            encoding="utf-8-sig", newline="").write(REGISTRY_XML)
    module = os.path.join(root, "CommonModules", "мой_Тест", "Ext")
    os.makedirs(module)
    open(os.path.join(module, "Module.bsl"), "w",
            encoding="utf-8-sig", newline="").write(MODULE_BSL)
    os.makedirs(os.path.join(root, "EventSubscriptions"))
    # Источник подписки должен существовать — инвариант проверяет это по файлу
    os.makedirs(os.path.join(root, "Documents"))
    open(os.path.join(root, "Documents", "РеализацияТоваровУслуг.xml"), "w",
            encoding="utf-8-sig", newline="").write("<Document/>")
    return root


def subscription_spec(name="мой_ЗаявкаПередЗаписью"):
    return Spec("ПодпискаНаСобытие", {
        "имя": name,
        "синоним": "(Мой) Заявка перед записью",
        "комментарий": "#ЗАДАЧА-1",
        "источник": [TypeRef("Документ", "РеализацияТоваровУслуг", "Объект")],
        "событие": "ПередЗаписью",
        "обработчик": "мой_Тест.мой_ЗаявкаПередЗаписьюОбработчик",
    })


# --- тесты: сериализация -----------------------------------------------------

def test_header_matches_configuration():
    """Шапка карточки совпадает с той, что пишет платформа.

    Спрашивается тот, кто её и пишет, — сборка карточки целиком: отдельная
    функция, собирающая шапку из тех же таблиц, подтвердила бы таблицы, но
    не то, что в файл попадёт именно это.
    """
    files = sorted(os.listdir(SUBSCRIPTIONS)) if os.path.isdir(SUBSCRIPTIONS) else []
    if not files:
        pytest.skip(f"пропущен: нет {SUBSCRIPTIONS}")
    line = open(os.path.join(SUBSCRIPTIONS, files[0]),
                encoding="utf-8-sig").read().split("\n")[1]
    ours = serializer.card_to_text(mapping.translate(subscription_spec(), "u1")).split("\n")[1]
    assert ours == line, f"\nсборка: {ours[:120]}\nфайл:   {line[:120]}"


def test_all_subscription_cards_bytewise():
    if not os.path.isdir(SUBSCRIPTIONS):
        pytest.skip(f"пропущен: нет {SUBSCRIPTIONS}")
    total = mismatched = 0
    first = None
    for filename in sorted(os.listdir(SUBSCRIPTIONS)):
        path = os.path.join(SUBSCRIPTIONS, filename)
        reference = open(path, "rb").read()
        uuid, spec = spec_from_file(path)
        total += 1
        if build_bytes(uuid, spec) != reference.replace(b"\r\n", b"\n"):
            mismatched += 1
            first = first or filename
    assert mismatched == 0, f"разошлось {mismatched} из {total}, первое: {first}"
    print(f"{total} карточек")


def module_spec_from_file(path):
    """Карточка общего модуля -> (uuid, спецификация). Только для тестов."""
    text = open(path, encoding="utf-8-sig").read()
    uuid = re.search(r'<\w+ uuid="([^"]+)"', text).group(1)
    properties = re.search(r"<Properties>(.*?)</Properties>", text, re.S).group(1)
    values = dict(re.findall(r"^\t{3}<(\w+)>(.*?)</\1>", properties, re.M))
    synonym = re.findall(
        r"<v8:lang>(.*?)</v8:lang>\s*<v8:content>(.*?)</v8:content>", properties, re.S)
    fields = {"имя": values["Name"],
            "синоним": OrderedDict(synonym) if synonym else "",
            "комментарий": values.get("Comment", ""),
            "повторноеИспользование": {v: k for k, v in vocabulary.RETURN_REUSE.items()}[
                values["ReturnValuesReuse"]]}
    for field in schema.SCHEMA["ОбщийМодуль"].fields:
        if field.value_kind == vocabulary.BOOLEAN:
            fields[field.domain] = values.get(field.tag) == "true"
    return uuid, Spec("ОбщийМодуль", fields)


def test_all_modules_bytewise():
    """4100 карточек общих модулей: разобрать, собрать, сверить байты.

    Модуль — вторая структурная форма («карточка + спутник»), и проверяется
    она тем же способом, что подписка: против того, что написала платформа.
    """
    folder = os.path.join(SOURCES, "CommonModules")
    if not os.path.isdir(folder):
        pytest.skip(f"пропущен: нет {folder}")
    total = mismatched = 0
    first = None
    for filename in sorted(os.listdir(folder)):
        if not filename.endswith(".xml"):
            continue
        path = os.path.join(folder, filename)
        reference = open(path, "rb").read()
        uuid, spec = module_spec_from_file(path)
        card = mapping.translate(spec, uuid)
        built = (serializer.BOM + "\n".join(
            serializer.card_to_lines(card))).encode("utf-8")
        total += 1
        if built != reference.replace(b"\r\n", b"\n"):
            mismatched += 1
            first = first or filename
    assert mismatched == 0, f"разошлось {mismatched} из {total}, первое: {first}"
    print(f"{total} карточек")


def test_escaping():
    node = mapping.Node("Comment", text="а < б & в > г")
    assert serializer.node_to_lines(node) == ["<Comment>а &lt; б &amp; в &gt; г</Comment>"]


def test_empty_value_self_closing_tag():
    assert serializer.node_to_lines(mapping.Node("Comment", text="")) == ["<Comment/>"]


# --- тесты: запись -----------------------------------------------------------

def test_create_subscription():
    root = sandbox()
    try:
        platform = DesignerDump(root)
        result = AddObjectUseCase(platform).execute(subscription_spec(),
                                   uuids=["11111111-2222-3333-4444-555555555555"],
                                   apply_now=True)
        assert result.ok, [str(f) for f in result.errors]
        card = os.path.join(root, "EventSubscriptions",
                                "мой_ЗаявкаПередЗаписью.xml")
        raw = open(card, "rb").read()
        assert raw[:3] == b"\xef\xbb\xbf", "нет BOM"
        assert b"\r\n" in raw, "платформа пишет CRLF, а мы нет"
        assert not raw.endswith(b"\n"), "лишний перевод строки в конце"
        text = raw.decode("utf-8-sig")
        assert '<EventSubscription uuid="11111111-2222-3333-4444-555555555555">' in text
        assert "<Event>BeforeWrite</Event>" in text
        assert ("<Handler>CommonModule.мой_Тест."
                "мой_ЗаявкаПередЗаписьюОбработчик</Handler>") in text
        assert "<v8:Type>cfg:DocumentObject.РеализацияТоваровУслуг</v8:Type>" in text
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _groups(root):
    text = open(os.path.join(root, "Configuration.xml"),
                    encoding="utf-8-sig", newline="").read()
    tags = re.findall(r"\t\t\t<(\w+)>[^<]*</\1>", text)
    order = []
    for tag in tags:
        if not order or order[-1] != tag:
            order.append(tag)
    return order


def test_registry_changes_one_line():
    root = sandbox()
    try:
        AddObjectUseCase(DesignerDump(root)).execute(subscription_spec(),
                            apply_now=True)
        after = open(os.path.join(root, "Configuration.xml"),
                        encoding="utf-8-sig", newline="").read()
        before = REGISTRY_XML.split("\r\n")
        new_data = after.split("\r\n")
        assert len(new_data) == len(before) + 1, "изменилось строк больше одной"
        added = [s for s in new_data if s not in before]
        assert added == [
            "\t\t\t<EventSubscription>мой_ЗаявкаПередЗаписью</EventSubscription>"]
        # встала в конец своей группы, а не в конец файла
        assert new_data[new_data.index(added[0]) + 1].strip() == \
            "<ScheduledJob>Регламент</ScheduledJob>"
        assert [s for s in before if s not in new_data] == [], "что-то пропало"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_new_group_before_next():
    """Группы вида ещё нет: она обязана встать по порядку конфигуратора."""
    root = sandbox()
    try:
        registry = os.path.join(root, "Configuration.xml")
        text = open(registry, encoding="utf-8-sig", newline="").read()
        open(registry, "w", encoding="utf-8-sig", newline="").write(
            text.replace("\t\t\t<EventSubscription>СтараяПодписка"
                          "</EventSubscription>\r\n", ""))
        assert _groups(root) == ["CommonModule", "ScheduledJob"]
        AddObjectUseCase(DesignerDump(root)).execute(subscription_spec(),
                            apply_now=True)
        assert _groups(root) == ["CommonModule", "EventSubscription", "ScheduledJob"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_new_group_after_previous():
    """Следующих групп в файле нет — тогда после ближайшей предыдущей.

    Это в точности случай пустой конфигурации: в ней есть только Language,
    а всё, что идёт после EventSubscription, отсутствует.
    """
    root = sandbox()
    try:
        registry = os.path.join(root, "Configuration.xml")
        text = open(registry, encoding="utf-8-sig", newline="").read()
        text = (text
                 .replace("\t\t\t<EventSubscription>СтараяПодписка</EventSubscription>\r\n", "")
                 .replace("\t\t\t<ScheduledJob>Регламент</ScheduledJob>\r\n", "")
                 .replace("\t\t\t<CommonModule>мой_Тест</CommonModule>\r\n",
                          "\t\t\t<Language>Русский</Language>\r\n"
                          "\t\t\t<CommonModule>мой_Тест</CommonModule>\r\n"))
        open(registry, "w", encoding="utf-8-sig", newline="").write(text)
        AddObjectUseCase(DesignerDump(root)).execute(subscription_spec(),
                            apply_now=True)
        assert _groups(root) == ["Language", "CommonModule", "EventSubscription"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_group_order_matches_configuration():
    """Таблица порядка групп — не мнение, а снимок замеренной конфигурации."""
    filename = os.path.join(SOURCES, "Configuration.xml")
    if not os.path.isfile(filename):
        pytest.skip(f"пропущен: нет {filename}")
    text = open(filename, encoding="utf-8-sig").read()
    children = re.search(r"<ChildObjects>(.*)</ChildObjects>", text, re.S).group(1)
    order = []
    for tag in re.findall(r"<(\w+)>[^<]*</\1>", children):
        if not order or order[-1] != tag:
            order.append(tag)
    assert tuple(order) == vocabulary.GROUP_ORDER, (
        f"порядок разошёлся:\nфайл:    {order}\nтаблица: {vocabulary.GROUP_ORDER}")
    print(f"{len(order)} групп")


def test_refuse_if_card_exists():
    root = sandbox()
    try:
        platform = DesignerDump(root)
        AddObjectUseCase(platform).execute(subscription_spec(), apply_now=True)
        try:
            AddObjectUseCase(platform).execute(subscription_spec(), apply_now=True)
        except Refuse:
            return
        raise AssertionError("повторное создание не отвергнуто")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_batch_of_two_stacks_registry():
    root = sandbox()
    try:
        result = AddObjectUseCase(DesignerDump(root)).execute([subscription_spec("мой_ПерваяПодписка"), subscription_spec("мой_ВтораяПодписка")],
            apply_now=True)
        assert result.ok, [str(f) for f in result.errors]
        after = open(os.path.join(root, "Configuration.xml"),
                        encoding="utf-8-sig", newline="").read()
        assert after.count("<EventSubscription>") == 3, "записи затёрли друг друга"
        assert len(result.written) == 3, result.written
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_plan_rolls_back_entirely():
    root = sandbox()
    try:
        registry = os.path.join(root, "Configuration.xml")
        before = open(registry, "rb").read()
        new_path = os.path.join(root, "EventSubscriptions", "мой_Новая.xml")
        plan = Plan()
        plan.add(new_path, "карточка".encode(), True)
        plan.add(registry, "изменённый реестр".encode(), False)
        # третий файл в каталоге, которого не может быть: путь занят файлом
        plan.add(os.path.join(new_path, "невозможно.xml"), b"x", True)
        try:
            plan.apply()
        except Exception:
            pass
        else:
            raise AssertionError("план не упал, тест бессмысленный")
        assert not os.path.exists(new_path), "созданный файл не удалён при откате"
        assert open(registry, "rb").read() == before, "реестр не восстановлен"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_configdumpinfo_untouched():
    root = sandbox()
    try:
        result = AddObjectUseCase(DesignerDump(root)).execute(subscription_spec())
        paths = [p for p, _, _ in result.plan.files]
        assert not any("ConfigDumpInfo" in p for p in paths), paths
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_preview_writes_nothing():
    root = sandbox()
    try:
        before = open(os.path.join(root, "Configuration.xml"), "rb").read()
        result = AddObjectUseCase(DesignerDump(root)).execute(subscription_spec())
        assert result.written == []
        assert not os.path.exists(os.path.join(root, "EventSubscriptions",
                                               "мой_ЗаявкаПередЗаписью.xml"))
        assert open(os.path.join(root, "Configuration.xml"), "rb").read() == before
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_broken_invariant_never_reaches_disk():
    root = sandbox()
    try:
        fields = dict(subscription_spec().fields)
        fields["имя"] = "БезПрефикса"
        result = AddObjectUseCase(DesignerDump(root), ТЕСТ).execute(Spec("ПодпискаНаСобытие", fields), apply_now=True)
        assert not result.ok
        assert result.plan is None and result.written == []
        assert os.listdir(os.path.join(root, "EventSubscriptions")) == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_matches_platform_dump():
    """Сильнейшая проверка: эталоны выгружены платформой из того, что записал инструмент.

    Эталоны получены опытом на пустой конфигурации: инструмент создаёт в пустой
    выгрузке общий модуль, затем подписку с обработчиком в этом модуле;
    конфигуратор оба раза загружает выгрузку в базу и выгружает обратно,
    меняя ровно один файл — `ConfigDumpInfo.xml`, который инструмент
    намеренно не трогает. Сохранённые файлы и есть эталоны: их писала
    платформа, и сверяются они побайтно, включая переводы строк.

    Тест повторяет тот же порядок: сначала модуль, потом подписка на него.
    Порядок важен — без модуля инвариант подписки не пропустил бы обработчик.
    """
    references = {
        "модуль": os.path.join(REFERENCES, "ОбщийМодуль-платформа.xml"),
        "текст": os.path.join(REFERENCES, "ОбщийМодуль-платформа.bsl"),
        "подписка": os.path.join(REFERENCES, "ПодпискаНаСобытие-платформа.xml"),
    }
    missing = [p for p in references.values() if not os.path.isfile(p)]
    if missing:
        pytest.skip(f"пропущен: нет {missing[0]}")

    module_uuid, module_spec = module_spec_from_file(references["модуль"])
    module_spec.fields["текст"] = open(
        references["текст"], encoding="utf-8-sig", newline="").read()
    subscription_uuid, spec = spec_from_file(references["подписка"])

    root = sandbox()
    try:
        platform = DesignerDump(root)
        result = AddObjectUseCase(platform).execute([module_spec], uuids=[module_uuid],
                                   apply_now=True)
        assert result.ok, [str(f) for f in result.errors]
        result = AddObjectUseCase(platform).execute([spec], uuids=[subscription_uuid],
                                   apply_now=True)
        assert result.ok, [str(f) for f in result.errors]

        to_check = [
            (os.path.join(root, "CommonModules", "мой_ПесочницаСервер.xml"),
             references["модуль"]),
            (os.path.join(root, "CommonModules", "мой_ПесочницаСервер",
                          "Ext", "Module.bsl"), references["текст"]),
            (os.path.join(root, "EventSubscriptions",
                          "мой_ЛюбойДокументПередЗаписью.xml"), references["подписка"]),
        ]
        for ours, reference in to_check:
            assert open(ours, "rb").read() == open(reference, "rb").read(), \
                f"разошлось с выгрузкой платформы: {os.path.basename(ours)}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("модуль, его текст и подписка — побайтно")


def test_application_runs_on_foreign_platform():
    """Разворот зависимости — не на словах: сценарии отрабатывают целиком
    на площадке, которая ничего не знает ни про XML, ни про файлы.

    Проверяются пять сценариев, а не один. Гард направления зависимостей ловит
    ребро наружу по импортам; здесь ловится то, чего он не видит, — сценарий,
    который работает лишь потому, что `DesignerDump` вернул нечто похожее
    на дерево. Площадка ниже не возвращает ничего похожего ни на что.
    """
    записано = []

    class MemoryPlan(ports.Plan):
        def __init__(self, what):
            self.what = what

        def describe(self):
            return [f"в памяти: {self.what}"]

        def apply(self):
            записано.append(self.what)
            return [self.what]

    class MemoryPlatform(ports.Platform):
        # --- перекладка: возвращаем метки, а не узлы
        def translate_card(self, spec, uuid, new_id=None):
            card = type("Карточка", (), {})()
            card.name, card.uuid, card.kind = spec.get("имя"), uuid, spec.kind
            return card

        def translate_node_for(self, spec, uuid, host, owner=None, new_id=None):
            return f"узел {spec.kind}.{spec.get('имя')}"

        # --- планы: по одному на сценарий
        def prepare(self, cards):
            return MemoryPlan("создание " + ", ".join(c.name for c in cards))

        def prepare_embedding(self, groups):
            return MemoryPlan("врезка " + ", ".join(n for _, n, _ in groups))

        def prepare_addition(self, additions):
            # Пятёрки, а не четвёрки: договор называет и представление
            # сущности — у пункта настроек имени нет вовсе.
            return MemoryPlan("добавление " + ", ".join(
                shown for _, _, _, _, shown in additions))

        def prepare_changes(self, changes):
            return MemoryPlan("правка " + ", ".join(
                path[-1][1] for path, _ in changes))

        def prepare_deletion(self, paths):
            return MemoryPlan("удаление " + ", ".join(p[-1][1] for p in paths))

        def prepare_rename(self, renames):
            return MemoryPlan("переименование " + ", ".join(
                n for _, n in renames))

        # --- чтение конфигурации: домен спрашивает, площадка отвечает
        def common_module_exists(self, name):
            return True

        def handler_arity(self, module, method):
            return None

        def method_is_exported(self, module, method):
            return True

        #: Что на этой площадке «есть». Отвечать «есть» на всё нельзя:
        #: переименование тогда упирается в занятое имя, а создание — в своё.
        ЕСТЬ = {("Справочник", "мой_Проба"),
                ("Документ", "РеализацияТоваровУслуг")}

        def object_exists(self, kind, name):
            return (kind, name) in self.ЕСТЬ

        def taken_names(self, path):
            return []

        def references_to(self, path):
            return []

    площадка = MemoryPlatform()
    тип = {"вид": "Строка", "длина": 10}
    сценарии = [
        (AddObjectUseCase(площадка).execute, [subscription_spec()],
         "создание мой_ЗаявкаПередЗаписью"),
        (AddChildUseCase(площадка).execute,
         [([("Справочник", "мой_Проба")], job_dialect.spec_from_json(
             {"вид": "Реквизит", "поля": {"имя": "Поле", "синоним": "Поле",
                                          "тип": тип}}))],
         "добавление Поле"),
        (ChangePropertyUseCase(площадка).execute,
         [([("Справочник", "мой_Проба"), ("Реквизит", "Поле")],
           {"индексирование": "Индексировать"})],
         "правка Поле"),
        (DeleteUseCase(площадка).execute,
         [[("Справочник", "мой_Проба")]], "удаление мой_Проба"),
        (RenameUseCase(площадка).execute,
         [([("Справочник", "мой_Проба")], "мой_Новое")],
         "переименование мой_Новое"),
    ]
    for запустить, вход, ожидание in сценарии:
        итог = запустить(вход, apply_now=True)
        assert итог.ok, (ожидание, [str(f) for f in итог.errors])
        assert итог.plan.describe() == [f"в памяти: {ожидание}"], ожидание
    assert записано == [ожидание for _, _, ожидание in сценарии]


# --- тесты: чтение конфигурации (порт домена) --------------------------------

def test_port_exported_method():
    root = sandbox()
    try:
        repo = DesignerDump(root)
        assert repo.common_module_exists("мой_Тест") is True
        assert repo.common_module_exists("мой_Нет") is False
        assert repo.method_is_exported(
            "мой_Тест", "мой_ЗаявкаПередЗаписьюОбработчик") is True
        assert repo.method_is_exported("мой_Тест", "НеЭкспортный") is False
        assert repo.method_is_exported("мой_Тест", "Отсутствует") is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_port_on_real_configuration():
    if not os.path.isfile(os.path.join(SOURCES, "Configuration.xml")):
        pytest.skip(f"пропущен: нет выгрузки {SOURCES}")
    repo = DesignerDump(SOURCES)
    assert repo.common_module_exists("ОбщегоНазначения") is True
    assert repo.method_is_exported("ОбщегоНазначения", "ЗначениеРеквизитаОбъекта") is True
    assert repo.object_exists("Справочник", "БанковскиеСчета") is True
    assert repo.object_exists("Справочник", "мой_НетТакого") is False


def test_port_resolves_defined_type():
    folder = os.path.join(SOURCES, "DefinedTypes")
    if not os.path.isdir(folder):
        pytest.skip(f"пропущен: нет {folder}")
    repo = DesignerDump(SOURCES)
    # берём определяемый тип, который реально используется источником подписки
    for filename in sorted(os.listdir(SUBSCRIPTIONS)):
        text = open(os.path.join(SUBSCRIPTIONS, filename), encoding="utf-8-sig").read()
        m = re.search(r"<v8:TypeSet>cfg:DefinedType\.([^<]+)</v8:TypeSet>", text)
        if m:
            facets = repo.defined_type_facets(m.group(1))
            assert facets, f"определяемый тип «{m.group(1)}» не раскрылся"
            assert all(facet_one in vocabulary.FACETS for facet_one in facets), facets
            print(f"{m.group(1)} -> {', '.join(facets)}")
            return
    pytest.skip("пропущен: подписок с определяемым типом не нашлось")


def test_child_order_matches_the_configuration():
    """Порядок групп в таблице — это то, что написано в выгрузке, а не мнение.

    Порядок канонический: карточка, записанная с переставленными группами,
    после загрузки в базу и обратной выгрузки возвращается к порядку из этой
    таблицы. Поэтому новая группа ставится по таблице, а не в начало раздела,
    хотя `Attribute` идёт первым в 96 % карточек.

    Здесь таблица пересобирается по всей конфигурации заново: встречающиеся
    в карточках «разные варианты» обязаны оказаться подмножествами одного
    общего порядка, без единого противоречия.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    section = re.compile(r"^\t\t<ChildObjects>\n(.*?)^\t\t</ChildObjects>", re.M | re.S)
    group = re.compile(r"^\t{3}<(\w+)[ >]", re.M)
    checked = 0
    for folder, expected in sorted(vocabulary.CARD_ORDER.items()):
        path = os.path.join(corpus.CORPUS, folder)
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            if not name.endswith(".xml"):
                continue
            text = open(os.path.join(path, name),
                        encoding="utf-8-sig").read().replace("\r\n", "\n")
            found = section.search(text)
            if not found:
                continue
            seen = []
            for tag in group.findall(found.group(1)):
                if not seen or seen[-1] != tag:
                    seen.append(tag)
            assert seen == [t for t in expected if t in seen], (
                f"{folder}/{name}: порядок групп {seen} не ложится на {expected}")
            checked += 1
    print(f"порядок групп сверен на {checked} карточках")
    assert checked > 5000


def test_new_group_lands_by_the_canonical_order():
    """Новая группа встаёт по порядку вида, а не «в начало, потому что чаще так».

    Случай, на котором правило «в начало» ошибается: у документа формы идут
    между реквизитами и табличными частями. Табличная часть, добавленная
    в документ с реквизитами и формами, обязана встать после форм — правило
    «в начало» поставило бы её первой.
    """
    place = Repository._place
    document = vocabulary.CARD_ORDER["Documents"]
    assert place(["Attribute", "Form"], "TabularSection", document) == 2
    assert place(["Attribute", "Form"], "Command", document) == 2
    assert place(["Form", "TabularSection"], "Attribute", document) == 0
    assert place(["Attribute", "Attribute", "Form"], "Attribute", document) == 2

    catalog = vocabulary.CARD_ORDER["Catalogs"]
    assert place(["Attribute", "Form"], "TabularSection", catalog) == 1


def test_flags_are_read_in_any_position():
    """`add.py --apply job.json` — задание в файле, а не в ключе.

    Если считать файлом задания первый же аргумент, такой порядок слов даёт
    трассировку `FileNotFoundError: --apply` вместо разбора.
    """
    import json
    import tempfile

    from meta.add import main

    root = tempfile.mkdtemp(prefix="meta-cli-")
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n"
        "\t</Configuration>\n</MetaDataObject>")
    job = os.path.join(root, "job.json")
    open(job, "w", encoding="utf-8").write(json.dumps({
        "repo": root,
        "objects": [{"вид": "ОбщийМодуль",
                     "поля": {"имя": "мой_Проба", "синоним": "Проба"}}]}))
    assert main(["--apply", job]) == 0
    assert os.path.isfile(os.path.join(root, "CommonModules", "мой_Проба.xml"))


def test_an_unreadable_job_is_a_refusal_not_a_traceback():
    from meta.add import main
    from meta.domain.model import Refuse

    try:
        main(["ниоткуда.json"])
    except Refuse as refusal:
        assert "не читается" in str(refusal)
    else:
        raise AssertionError("отсутствие файла прошло молча")


def test_comparison_type_is_a_measured_dictionary():
    """Вид сравнения задаётся по-русски, как и остальные словарные поля."""
    from meta.acl import mapping
    from meta.domain.model import Refuse, Spec

    node = mapping.translate_node(Spec("Отбор", {
        "использование": True, "левое": "Организация",
        "видСравнения": "НеРавно", "правое": "Основная"}), "u1")
    assert any("NotEqual" in str(child.text) for child in node.children)
    try:
        mapping.translate_node(Spec("Отбор", {
            "использование": True, "левое": "Организация",
            "видСравнения": "NotEqual"}), "u1")
    except Refuse as refusal:
        assert "не знаю, как записать" in str(refusal)
    else:
        raise AssertionError("английское написание прошло молча")


#: Значения, которые платформа допускает, а конфигурация не использует.
#: Список закрытый и с причиной у каждого: иначе гард превращается
#: в «дописать сюда всё, что не сошлось».
НЕ_ВСТРЕЧАЮТСЯ = {
    ("ChoiceHistoryOnInput", "Use"):
        "история выбора включена явно — в конфигурации везде Авто или Не использовать",
    ("comparisonType", "Like"): "подобно — в схемах не встретилось, в модулях есть",
    ("comparisonType", "NotLike"): "не подобно — там же",
}


def test_every_dictionary_value_occurs_in_its_own_tag():
    """Каждое значение словаря должно стоять в конфигурации в своём теге.

    Это гард против выдуманного перечисления. Значение, которого платформа
    не знает, — например периодичность `PerDay` вместо `Day`, — в выгрузке
    не встречается ни разу, а загрузку с ним платформа отвергает словами
    «Неверное значение перечисления - PerDay». Непериодический регистр — умолчание,
    им создают чаще всего, поэтому ошибку в остальных значениях корпусные
    сверки пропускают: ловит её круг через платформу, а этот тест — то же
    самое дешевле.

    Сверка идёт по тегу, а не по тексту вообще: значение `Read` встречается
    в выгрузке всюду, а вопрос в том, бывает ли оно в `<name>` внутри права.
    Тег известен из схемы — там же, где объявлен словарь.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")

    ожидается = {}
    for вид, схема in schema.SCHEMA.items():
        for поле in схема.fields:
            if not поле.dictionary:
                continue
            тег = поле.tag.rpartition(":")[2]
            for значение in поле.dictionary.values():
                ожидается.setdefault((тег, значение), []).append(
                    f"{вид}.{поле.domain}")

    теги = sorted({тег for тег, _ in ожидается})
    образец = re.compile("<(?:[\\w]+:)?(" + "|".join(теги) + ")>([^<]*)</")
    встречено = collections.defaultdict(set)
    for каталог, папки, файлы in os.walk(corpus.CORPUS):
        папки[:] = [d for d in папки if d != "Forms"]
        for имя in файлы:
            if not имя.endswith(".xml"):
                continue
            текст = open(os.path.join(каталог, имя), encoding="utf-8-sig",
                         errors="replace").read()
            for тег, значение in образец.findall(текст):
                встречено[тег].add(значение)

    пропало = [
        f"<{тег}> не содержит «{значение}» (поля: {', '.join(поля)})"
        for (тег, значение), поля in sorted(ожидается.items())
        if встречено.get(тег) and значение not in встречено[тег]
        and (тег, значение) not in НЕ_ВСТРЕЧАЮТСЯ]
    assert not пропало, ("значения словарей, которых нет в конфигурации:\n   "
                         + "\n   ".join(пропало))
    print(f"значений словарей сверено {len(ожидается)} по {len(теги)} тегам")

