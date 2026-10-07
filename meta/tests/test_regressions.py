"""Регрессии языка заданий — каждая со своей фикстурой: задание проходит
целиком, через язык заданий и инварианты. Правило без фикстуры живёт до
первого рефакторинга.

Два первых случая показательны: первый не виден тесту, который зовёт
перекладку напрямую, мимо инвариантов; второй живёт там, где других
проверок нет.
"""

import ast
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping  # noqa: E402
from meta.domain import model as dm  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Host, Refuse, Spec  # noqa: E402
from meta.jobs import dialect as job  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402


class World:
    """Конфигурация-заглушка: отвечает на вопросы порта, диска не трогает."""

    def __init__(self, objects=("мой_Эталон",)):
        self.objects = objects

    def object_exists(self, kind, name):
        return name in self.objects

    def taken_names(self, path):
        return []


def test_string_attribute_in_tabular_section_is_accepted():
    """Строковая колонка табличной части — самый частый случай, и он проходит.

    `fill` смотрит на хозяина: подставь он строковому реквизиту значение
    заполнения вслепую, `check` отверг бы это же значение как недопустимое
    для табличной части — инструмент отказал бы из-за того, что сочинил сам.
    """
    spec = Spec("Справочник", {
        "имя": "мой_Проба", "синоним": "Проба",
        "табличныеЧасти": [Spec("ТабличнаяЧасть", {
            "имя": "Строки", "синоним": "Строки",
            "реквизиты": [Spec("Реквизит", {"имя": "Статья", "синоним": "Статья",
                                            "тип": dm.StringType(100)})]})]})
    kind = kind_of("Справочник")
    findings = kind.check(kind.fill(spec), World())
    assert not [f for f in findings if f.blocking], [str(f) for f in findings]


def test_fill_keeps_the_property_where_the_host_has_it():
    """Само правило при этом действует: у реквизита справочника оно есть."""
    attribute = kind_of("Реквизит")
    spec = attribute.fill(Spec("Реквизит", {"имя": "Комментарий", "синоним": "К",
                                            "тип": dm.StringType(50)}),
                          ("Справочник", "мой_Эталон"))
    assert spec.get("значениеЗаполнения") == ""
    in_section = attribute.fill(Spec("Реквизит", {"имя": "Комментарий", "синоним": "К",
                                                  "тип": dm.StringType(50)}),
                                ("ТабличнаяЧасть", None))
    assert "значениеЗаполнения" not in in_section.fields


@pytest.mark.parametrize("described, wrong", [
    ({"вид": "Число", "длина": 15, "точность": 2}, "длина"),
    ({"вид": "Дата", "составДаты": "Дата"}, "составДаты"),
    ({"вид": "Строка", "разрядность": 20}, "разрядность"),
    ({"вид": "Справочник", "имя": "мой_Эталон", "грани": "Ссылка"}, "грани"),
])
def test_unknown_type_key_is_refused(described, wrong):
    """Лишний ключ в описании типа — отказ, а не молчаливое умолчание.

    «длина»/«точность» вместо «разрядность»/«дробнаяЧасть» у числа — частая
    ошибка по аналогии со строкой, у которой ключ «длина». Замени инструмент
    лишний ключ умолчанием, просмотр ответил бы «замечаний нет» и выдал план,
    побайтно совпадающий с планом правильного задания: записалось бы
    Число(10.0) вместо Число(15.2).
    """
    with pytest.raises(Refuse) as refusal:
        job.value_type_from_json(described)
    assert wrong in str(refusal.value)
    assert "допустимы" in str(refusal.value)


def test_known_type_keys_still_work():
    assert str(job.value_type_from_json(
        {"вид": "Число", "разрядность": 15, "дробнаяЧасть": 2})) == "Число(15,2)"
    assert str(job.value_type_from_json({"вид": "Дата", "состав": "Дата"})) == "Дата"


def test_number_where_text_expected_is_refused_not_crashed():
    """`"длинаКода": 9` — отказ с адресом поля, а не трейсбек из недр перекладки."""
    spec = kind_of("Справочник").fill(
        Spec("Справочник", {"имя": "мой_Проба", "синоним": "П", "длинаКода": 9}))
    with pytest.raises(Refuse) as refusal:
        mapping.translate(spec, "x", new_id=lambda: "id")
    text = str(refusal.value)
    assert "длинаКода" in text and '"9"' in text, text


def test_missing_reference_type_is_reported():
    """Ссылка на несуществующий объект.

    Поиск — файловая операция, домену не принадлежит: он спрашивает через порт
    `Configuration.object_exists`, а отвечает инфраструктура. Здесь порт
    подменён заглушкой, и именно поэтому проверка обходится без диска.
    """
    attribute = kind_of("Реквизит")
    context = ("Справочник", "мой_Эталон")
    spec = attribute.fill(Spec("Реквизит", {
        "имя": "Ссылка", "синоним": "С",
        "тип": dm.TypeRef("Справочник", "мой_Нету", "Ссылка")}), context)
    codes = [f.code for f in attribute.check(spec, World(), context)]
    assert "ТИП-НЕТ" in codes, codes

    ok = attribute.fill(Spec("Реквизит", {
        "имя": "Ссылка", "синоним": "С",
        "тип": dm.TypeRef("Справочник", "мой_Эталон", "Ссылка")}), context)
    assert "ТИП-НЕТ" not in [f.code for f in attribute.check(ok, World(), context)]


def test_child_findings_carry_the_path_to_the_child():
    """Замечание по ребёнку печатается с его именем: детей у объекта десяток."""
    spec = Spec("Справочник", {
        "имя": "мой_Проба", "синоним": "П",
        "реквизиты": [Spec("Реквизит", {"имя": "БезСинонима",
                                        "тип": dm.StringType(10)})]})
    kind = kind_of("Справочник")
    where = [f.field for f in kind.check(kind.fill(spec), World())
             if f.code == "МД-БЕЗ-СИНОНИМА"]
    assert where == ["реквизиты[БезСинонима].синоним"], where


@pytest.mark.parametrize("kind_name, host", [
    ("Реквизит", "РегистрСведений"),
    ("Измерение", "РегистрСведений"),
    ("Ресурс", "РегистрСведений"),
])
def test_synonym_is_asked_of_every_nested_kind(kind_name, host):
    """Синоним спрашивается у каждого вложенного вида, а не только у реквизита."""
    kind = kind_of(kind_name)
    spec = kind.fill(Spec(kind_name, {"имя": "Проба", "тип": dm.StringType(10)}),
                     (host, None))
    codes = [f.code for f in kind.check(spec, World(), (host, None))]
    assert "МД-БЕЗ-СИНОНИМА" in codes, codes


def test_child_prefix_follows_the_object_not_the_nearest_parent():
    """Префикс ребёнка судится по имени объекта, а не ближайшего родителя.

    Детям создаваемого объекта передаётся имя хозяина — иначе правило
    префикса до них не доходит вовсе и держится на рассуждении «объект
    создаётся, значит он свой». И передаётся именно имя объекта: реквизит
    внутри «мой_Проба.Строки» живёт в своём объекте, хотя табличная часть
    зовётся «Строки» и префикса не несёт.
    """
    def catalog(name):
        return Spec("Справочник", {
            "имя": name, "синоним": "П",
            "реквизиты": [Spec("Реквизит", {"имя": "Поле", "синоним": "П",
                                            "тип": dm.StringType(10)})],
            "табличныеЧасти": [Spec("ТабличнаяЧасть", {
                "имя": "Строки", "синоним": "С",
                "реквизиты": [Spec("Реквизит", {"имя": "Статья", "синоним": "С",
                                                "тип": dm.StringType(100)})]})]})

    kind = kind_of("Справочник", ТЕСТ)
    ours = [f.field for f in kind.check(kind.fill(catalog("мой_Проба")), World())
            if f.code == "МД-ПРЕФИКС"]
    assert ours == [], ours

    # Имя объекта без префикса делает его «типовым» в глазах правила, и
    # тогда префикса можно было бы потребовать и от детей — четыре ошибки
    # на одну опечатку. Но объект здесь **создаётся**, а создать вендорский
    # нельзя: три ошибки из четырёх были бы следствием первой, и, исправив
    # все, человек получил бы `мой_Тестовый` с реквизитом `мой_Поле`, чего
    # правило не требует. Поэтому называется только корень.
    foreign = [f.field for f in kind.check(kind.fill(catalog("Тестовый")), World())
               if f.code == "МД-ПРЕФИКС"]
    assert foreign == ["имя"], foreign

    # Но там, где хозяин действительно вендорский и уже лежит на диске,
    # правило работает в полную силу: ребёнок обязан нести префикс.
    реквизит = kind_of("Реквизит", ТЕСТ)
    в_чужой = [f.code for f in реквизит.check(
        реквизит.fill(Spec("Реквизит", {"имя": "Поле", "синоним": "П",
                                        "тип": dm.StringType(10)})),
        World(), Host("Справочник", "Контрагенты"))]
    assert "МД-ПРЕФИКС" in в_чужой, в_чужой


def test_new_host_is_not_searched_on_disk():
    """Имя хозяина известно — но искать его на диске нельзя.

    Признак «существует» отделён от имени именно за этим: карточки объекта,
    который создаётся этим же заданием, на диске ещё нет, и проверки
    «объект есть» и «имя занято» к нему неприменимы.
    """
    class Empty:
        def object_exists(self, kind, name):
            return False                      # на диске нет ничего

        def taken_names(self, path):
            return None

    spec = Spec("Справочник", {
        "имя": "мой_Проба", "синоним": "П",
        "реквизиты": [Spec("Реквизит", {"имя": "Поле", "синоним": "П",
                                        "тип": dm.StringType(10)})]})
    kind = kind_of("Справочник")
    codes = [f.code for f in kind.check(kind.fill(spec), Empty())]
    assert "РЕКВИЗИТ-ХОЗЯИНА-НЕТ" not in codes, codes
    assert "РЕКВИЗИТ-СОСТАВ-НЕПРОВЕРЕН" not in codes, codes


def test_finding_codes_are_written_in_russian():
    """Гард против порчи данных переименованием: коды находок пишутся по-русски.

    Механическая замена идентификаторов на английские задевает и строки:
    коды находок становятся `MODULE_BSL-БЕЗ-СЕРВЕРА`, `ПОДПИСКА-MODULE_BSL-НЕТ`.
    Проверок это не ломает — код находки сравнивается сам с собой, — и
    заметно только человеку, который читает сообщение.
    """
    latin = []
    scanned = []
    # Обход вглубь, а не перечисление верхнего уровня: сценарии лежат по папке
    # на каждый (`application/add_object/use_case.py`), и плоский список не
    # увидел бы ни одного — гард сторожил бы слой, где находок почти нет.
    for folder in ("domain", "acl", "application", "jobs"):
        for where, _, names in os.walk(os.path.join(ROOT, "meta", folder)):
            for name in sorted(names):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(where, name)
                scanned.append(path)
                tree = ast.parse(open(path, encoding="utf-8-sig").read())
                for node in ast.walk(tree):
                    if not (isinstance(node, ast.Call)
                            and getattr(node.func, "id", None) == "Finding"):
                        continue
                    first = node.args[0] if node.args else None
                    if (isinstance(first, ast.Constant)
                            and isinstance(first.value, str)
                            and re.search("[A-Za-z]", first.value)):
                        latin.append(f"{os.path.relpath(path, ROOT)}: {first.value}")
    assert any(p.endswith("use_case.py") for p in scanned), \
        "обход не дошёл до сценариев — он плоский"
    assert not latin, "коды находок пишутся по-русски:\n" + "\n".join(latin)


def test_value_types_describe_themselves_in_russian():
    """Та же порча в том, что видит пользователь: `StringType(20)` вместо «Строка(20)».

    Представления типов печатаются в просмотре — по ним человек и проверяет,
    то ли разобрано из задания.
    """
    samples = [dm.StringType(20), dm.NumberType(15, 2), dm.DateType("Дата"),
               dm.BooleanType(), dm.AnyType(), dm.ValueStorageType()]
    latin = [str(t) for t in samples if re.search("[A-Za-z]", str(t))]
    assert not latin, latin
    assert str(dm.StringType(20)) == "Строка(20)"
    assert str(dm.NumberType(15, 2, True)) == "Число(15,2, неотрицательное)"


def test_a_composite_type_of_a_child_is_shown_by_names(capsys):
    """Составной тип измерения печатается именами, а не адресами в памяти.

    Просмотр без `--apply` — единственная точка, где состав и порядок типов
    сверяют до записи. Печатай он `[<meta.domain.model.TypeRef object at 0x…>]`
    вместо ссылок на документы, для составных типов он был бы бесполезен:
    сверять пришлось бы уже по записанному XML.
    """
    from meta.report.objects import describe

    измерение = Spec("Измерение", {
        "имя": "ДокументВыдачи",
        "тип": [dm.TypeRef("Документ", "Заявка", "Ссылка"),
                dm.TypeRef("Документ", "Акт", "Ссылка")]})
    напечатано = "\n".join(describe(Spec("РегистрСведений",
                                          {"имя": "мой_Проба", "измерения": [измерение]})))
    assert "Документ.Заявка | Документ.Акт" in напечатано, напечатано
    assert "object at 0x" not in напечатано
    # и сам список типов, где бы его ни печатали, — именами, а не адресами
    assert "object at" not in repr([dm.TypeRef("Документ", "Акт")])


def test_unknown_field_message_names_the_known_ones():
    """Сообщение называет и неизвестные поля, и известные."""
    kind = kind_of("Перечисление")
    findings = [f for f in kind.check(kind.fill(Spec("Перечисление", {
        "имя": "мой_Проба", "синоним": "П", "элементы": []})), World())
        if f.code == "МД-ПОЛЕ-НЕИЗВЕСТНО"]
    assert findings, "поле «элементы» должно быть отвергнуто"
    assert "известны" in findings[0].message and "значения" in findings[0].message


def test_register_warning_does_not_claim_the_platform_refuses():
    """Текст не утверждает «платформа не принимает» — платформа принимает.

    Опыт на пустой конфигурации: регистр без измерений загружается,
    собирается и выгружается обратно как есть. В замеренной конфигурации
    таких 49 из 1809. Предупреждение остаётся — но как «проверьте, что
    намеренно», а не как выдуманный запрет, которого у платформы нет.
    """
    kind = kind_of("РегистрСведений")
    warning = [f for f in kind.check(kind.fill(Spec("РегистрСведений", {
        "имя": "мой_Проба", "синоним": "П"})), World())
        if f.code == "РЕГИСТР-БЕЗ-ИЗМЕРЕНИЙ"]
    assert warning, "предупреждение должно остаться"
    сказано = warning[0].message
    assert "платформа не принимает" not in сказано, сказано
    assert "49 из 1809" in сказано, сказано
    assert not warning[0].blocking, "это предупреждение, а не запрет"


def test_dimension_can_be_added_to_an_existing_register(tmp_path):
    """Измерение, ресурс и табличная часть добавляются в существующий объект.

    Врезка — это «добавить ребёнка по адресу», а не только реквизит в объект:
    иначе всё прочее задавалось бы только вместе с созданием объекта, и
    предупреждение «регистр без измерений» оказалось бы тупиком — добавить
    измерение потом было бы нечем. Один механизм служит и метаданным, и
    схеме компоновки.
    """
    from meta.application.add_child.use_case import AddChildUseCase
    from meta.infra.designer import DesignerDump
    from meta.jobs import dialect as job_dialect

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects>\n"
        "\t\t\t<InformationRegister>мой_Лимиты</InformationRegister>\n"
        "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")
    os.makedirs(os.path.join(root, "InformationRegisters"))
    open(os.path.join(root, "InformationRegisters", "мой_Лимиты.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"'
        ' xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">\n'
        '\t<InformationRegister uuid="r1">\n'
        "\t\t<Properties>\n\t\t\t<Name>мой_Лимиты</Name>\n\t\t</Properties>\n"
        "\t\t<ChildObjects/>\n"
        "\t</InformationRegister>\n</MetaDataObject>")

    AddChildUseCase(DesignerDump(root), ТЕСТ).execute(
        [job_dialect.addition_job_from_json({
            "путь": "РегистрСведений.мой_Лимиты", "вид": "Измерение",
            "поля": {"имя": "Организация", "синоним": "Организация",
                     "тип": {"вид": "Строка", "длина": 20}}})],
        apply_now=True)
    card = open(os.path.join(root, "InformationRegisters", "мой_Лимиты.xml"),
                encoding="utf-8-sig").read()
    assert "<Dimension uuid=" in card
    assert "<Name>Организация</Name>" in card
    assert "<ChildObjects/>" not in card        # раздел развернулся


def _catalog_with_a_tabular_section(root):
    """Выгрузка из одной карточки `мой_Проба` с пустой табличной частью."""
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects>\n"
        "\t\t\t<Catalog>мой_Проба</Catalog>\n"
        "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")
    os.makedirs(os.path.join(root, "Catalogs"), exist_ok=True)
    open(os.path.join(root, "Catalogs", "мой_Проба.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"'
        ' xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">\n'
        '\t<Catalog uuid="c1">\n'
        "\t\t<Properties>\n\t\t\t<Name>мой_Проба</Name>\n\t\t</Properties>\n"
        "\t\t<ChildObjects>\n"
        '\t\t\t<TabularSection uuid="t1">\n'
        "\t\t\t\t<Properties>\n\t\t\t\t\t<Name>Строки</Name>\n"
        "\t\t\t\t</Properties>\n\t\t\t\t<ChildObjects/>\n"
        "\t\t\t</TabularSection>\n\t\t</ChildObjects>\n"
        "\t</Catalog>\n</MetaDataObject>")
    return root


def _add_to_the_tabular_section(root, name, apply_now=False):
    from meta.application.add_child.use_case import AddChildUseCase
    from meta.infra.designer import DesignerDump
    from meta.jobs import dialect as job_dialect

    return AddChildUseCase(DesignerDump(root), ТЕСТ).execute(
        [job_dialect.addition_job_from_json({
            "путь": "Справочник.мой_Проба.ТабличнаяЧасть.Строки",
            "вид": "Реквизит",
            "поля": {"имя": name, "синоним": name,
                     "тип": {"вид": "Строка", "длина": 10}}})],
        apply_now=apply_now)


def test_prefix_asks_the_object_not_the_tabular_section(tmp_path):
    """Реквизит в табличной части своего объекта префикса не требует.

    Три вопроса о хозяине разные: состав свойств — по виду ближайшего
    родителя, префикс — по имени объекта, занятость имени — по всему адресу.
    Возьми сценарий на все три последнюю пару адреса, добавление реквизита
    в «мой_Проба.Строки» упёрлось бы в требование префикса у «Строки» —
    а это тот вид работы, ради которого инструмент и сделан.
    """
    root = _catalog_with_a_tabular_section(str(tmp_path))
    result = _add_to_the_tabular_section(root, "Сумма")
    assert [f.code for f in result.errors] == []


def test_name_taken_is_looked_up_inside_the_tabular_section(tmp_path):
    """Занятость имени спрашивается у табличной части, а не у объекта.

    Ответь порт на вопрос про объект, повтор внутри табличной части остался
    бы незамеченным: вместо отказа вышло бы предупреждение «состав не проверен».
    """
    root = _catalog_with_a_tabular_section(str(tmp_path))
    _add_to_the_tabular_section(root, "Сумма", apply_now=True)
    result = _add_to_the_tabular_section(root, "Сумма")
    assert [f.code for f in result.errors] == ["РЕКВИЗИТ-ИМЯ-ЗАНЯТО"]
    assert "ТабличнаяЧасть.Строки" in result.errors[0].message


def _empty_dump(root):
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects/>\n"
        "\t</Configuration>\n</MetaDataObject>")
    return root


СТРОКА = {"вид": "Строка", "длина": 20}


def test_child_names_are_one_namespace_at_creation(tmp_path):
    """Измерение и ресурс с одним именем — отказ, а не молчаливая запись.

    Занятость среди своих считается по всем детям объекта, а не по полю
    задания: со своим множеством на «измерения» и своим на «ресурсы» регистр
    с измерением «Организация» и ресурсом «Организация» писался бы без
    единого замечания, а конфигурацию с таким регистром платформа не грузит.
    Столкновений между видами детей в замеренной конфигурации нет ни одного
    на 7035 объектов — это и есть основание.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump
    from meta.jobs import dialect as job_dialect

    root = _empty_dump(str(tmp_path))
    result = AddObjectUseCase(DesignerDump(root)).execute(
        [job_dialect.spec_from_json({"вид": "РегистрСведений", "поля": {
            "имя": "мой_Проба", "синоним": "Проба",
            "измерения": [{"имя": "Организация", "синоним": "О", "тип": СТРОКА}],
            "ресурсы": [{"имя": "Организация", "синоним": "О", "тип": СТРОКА}]}})],
        apply_now=False)
    assert [f.code for f in result.errors] == ["ДЕТИ-ИМЯ-ПОВТОРЯЕТСЯ"]


def test_an_attribute_and_a_tabular_section_cannot_share_a_name(tmp_path):
    """Тот же случай у справочника: реквизит «Строки» и табличная часть «Строки»."""
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump
    from meta.jobs import dialect as job_dialect

    root = _empty_dump(str(tmp_path))
    result = AddObjectUseCase(DesignerDump(root)).execute(
        [job_dialect.spec_from_json({"вид": "Справочник", "поля": {
            "имя": "мой_Проба", "синоним": "Проба",
            "реквизиты": [{"имя": "Строки", "синоним": "С", "тип": СТРОКА}],
            "табличныеЧасти": [{"имя": "Строки", "синоним": "С"}]}})],
        apply_now=False)
    assert [f.code for f in result.errors] == ["ДЕТИ-ИМЯ-ПОВТОРЯЕТСЯ"]


def test_occupancy_reaches_every_nested_kind(tmp_path):
    """Занятость имени проверяется не только у реквизита.

    Проверка общая для всех вложенных видов: живи она в
    `AttributeKind.own_findings`, измерение, ресурс, табличная часть и
    значение перечисления её не получали бы вовсе — ресурс с именем
    существующего измерения добавлялся бы в регистр без замечаний.
    """
    from meta.application.add_child.use_case import AddChildUseCase
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump
    from meta.jobs import dialect as job_dialect

    root = _empty_dump(str(tmp_path))
    AddObjectUseCase(DesignerDump(root)).execute(
        [job_dialect.spec_from_json({"вид": "РегистрСведений", "поля": {
            "имя": "мой_Проба", "синоним": "Проба",
            "измерения": [{"имя": "Организация", "синоним": "О",
                           "тип": СТРОКА}]}})], apply_now=True)

    def добавить(kind, name):
        return AddChildUseCase(DesignerDump(root), ТЕСТ).execute(
            [job_dialect.addition_job_from_json({
                "путь": "РегистрСведений.мой_Проба", "вид": kind,
                "поля": {"имя": name, "синоним": name, "тип": СТРОКА}})],
            apply_now=False)

    assert [f.code for f in добавить("Ресурс", "Организация").errors] == [
        "ВЛОЖЕННОЕ-ИМЯ-ЗАНЯТО"]
    assert [f.code for f in добавить("Измерение", "Организация").errors] == [
        "ВЛОЖЕННОЕ-ИМЯ-ЗАНЯТО"]
    assert not добавить("Ресурс", "Сумма").errors


def test_no_nested_kind_writes_its_own_set_of_common_findings():
    """Общие инварианты вложенного вида берутся из базы, а не переписываются.

    Правило объявлено в описании модуля: точка входа одна, подклассы её
    не переопределяют, иначе общее теряется молча. Перечисли подкласс общие
    проверки заново — следующая, добавленная в базу, до него бы не дошла.
    Гард смотрит на исходники, а не на поведение: поведение при таком
    нарушении совпадает.
    """
    import ast
    import inspect

    from meta.domain import kinds as module

    tree = ast.parse(inspect.getsource(module))
    nested = {"NestedKind"}
    culprits = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        if not bases & nested and node.name not in nested:
            continue
        nested.add(node.name)
        for item in node.body:
            if not (isinstance(item, ast.FunctionDef)
                    and item.name == "own_findings" and node.name != "NestedKind"):
                continue
            calls = [c for c in ast.walk(item) if isinstance(c, ast.Call)]
            if not any(isinstance(c.func, ast.Attribute)
                       and c.func.attr == "own_findings" for c in calls):
                culprits.append(node.name)
    assert not culprits, (
        "переопределяют own_findings, не вызвав базовую: " + ", ".join(culprits))


def test_every_kind_describes_itself():
    """У каждого вида есть описание — там живут замеры.

    Описание вида — не украшение: в нём записано, откуда взяты умолчания
    и что именно замерено. Теряется оно молча: атрибут класса, вписанный
    перед строкой описания, превращает её в выражение, и `__doc__`
    становится пустым — без этого гарда ни один другой тест не заметит.
    """
    from meta.domain.kinds import REGISTRY

    silent = [name for name, kind in REGISTRY.items()
              if not (type(kind).__doc__ or "").strip()]
    assert not silent, "виды без описания: " + ", ".join(sorted(silent))


# --- форма записи, типы, права и подсказки отказов ------------------------

def test_a_dataset_declares_its_kind():
    """Набор данных без `xsi:type` платформа не примет.

    Элемент `dataSet` абстрактный, и атрибут — то, чем платформа выбирает
    класс. Голых в замеренной конфигурации нет ни одного из 1275: запрос 893,
    объект 273, объединение 109. Голый набор ушёл бы в файл с вердиктом
    «замечаний нет».
    """
    from meta.acl import mapping
    from meta.jobs import dialect as job_dialect

    node = mapping.translate_node(job_dialect.child_spec_from_json(
        "НаборДанных", {"имя": "Основной", "источникДанных": "И",
                        "запрос": "ВЫБРАТЬ 1"}), "u1")
    assert node.attrs.get("xsi:type") == "DataSetQuery"


def test_a_shorthand_type_is_refused_where_it_would_lose_the_qualifier():
    """`"тип": "Строка"` — не строка, а строка неограниченной длины.

    Три соседние небрежности инструмент отвергает, и эта не уходит на диск
    молча: README объявляет для описания типа политику — молчаливое
    умолчание здесь незаметно и в задании, и в результате.
    """
    from meta.domain.model import Refuse
    from meta.jobs import dialect as job_dialect

    for краткий in ("Строка", "Число"):
        with pytest.raises(Refuse) as refusal:
            job_dialect.child_spec_from_json("Реквизит", {"имя": "П", "тип": краткий})
        assert "нужен квалификатор" in str(refusal.value)
        assert "(" in str(refusal.value)          # и как написать кратко
    # А там, где квалификатора нет, краткая запись остаётся удобством
    assert job_dialect.child_spec_from_json(
        "Реквизит", {"имя": "П", "тип": "Булево"}).get("тип") is not None


def test_the_metadata_job_takes_the_type_the_way_show_prints_it():
    """Что выдал просмотр, то и вставляется в задание.

    Просмотр печатает тип той же краткой записью («Строка(50)»,
    «Справочник.Контрагенты»), что принимают и задание на формы, и задание
    на метаданные — наряду с объектной. Печатай он свою, третью запись
    (`Число(10.0)`, `Дата(ДатаВремя)`, `Справочник.X (Ссылка)`), тип,
    скопированный из `show`, получал бы отказ. У даты состав и есть запись:
    «Дата» — только дата, как и в задании на формы.
    """
    from meta.domain import model as dm
    from meta.jobs import dialect as job_dialect

    образцы = [dm.StringType(50), dm.StringType(9, True), dm.NumberType(15, 2),
               dm.NumberType(10, 0, True), dm.DateType("Дата"), dm.DateType("ДатаВремя"),
               dm.DateType("Время"), dm.BooleanType(), dm.PlatformType("ХранилищеЗначения"),
               dm.TypeRef("Справочник", "Контрагенты", "Ссылка"),
               dm.TypeRef.defined("ДенежнаяСумма"),
               dm.TypeRef("Характеристика", "ВидыСубконто", None, is_set=True),
               dm.TypeRef("ЛюбаяСсылка", None, None, is_set=True),
               dm.TypeRef.of_kind("Документ", "Ссылка"),
               dm.TypeRef("Документ", "Заявка", "Объект")]
    for тип in образцы:
        запись = dm.запись_типа(тип)
        разобрано = job_dialect.value_type_from_json(запись)
        assert dm.запись_типа(разобрано) == запись, запись
        assert type(разобрано) is type(тип), запись
        assert getattr(разобрано, "is_set", None) == getattr(тип, "is_set", None), запись
    составной = [dm.StringType(10), dm.TypeRef("Справочник", "Склады", "Ссылка")]
    запись = dm.запись_типа(составной)
    assert запись == "Строка(10) | Справочник.Склады"
    assert dm.запись_типа(job_dialect.value_type_from_json(запись)) == запись
    # и задание на формы понимает ту же запись
    assert dm.запись_типа(job_dialect.value_type_from_text(запись)) == запись
    точка = dm.TypeRef("ТочкаМаршрутаБизнесПроцесса", None, None)
    assert dm.запись_типа(job_dialect.value_type_from_json(str(точка))) == str(точка)


def test_every_attribute_type_of_the_corpus_is_read_and_reads_back():
    """Каждый реквизит справочников и документов конфигурации читается не
    «Произвольным» и печатается записью, которую задание разбирает обратно
    в тот же тип. Потерю TypeSet при чтении — 1597 определяемых типов в
    замеренной конфигурации — сверка записи не видит: проверять надо чтение."""
    from meta.infra.designer import DesignerDump
    from meta.tests import corpus

    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    root = corpus.CORPUS
    дамп = DesignerDump(root)
    плохие, всего = [], 0

    def обойти(spec, где):
        nonlocal всего
        for реквизит in spec.get("реквизиты") or []:
            всего += 1
            тип = реквизит.get("тип")
            запись = dm.запись_типа(тип)
            if isinstance(тип, dm.AnyType) or "object at" in запись:
                плохие.append(f"{где}.{реквизит.get('имя')}: {запись}")
                continue
            try:
                обратно = dm.запись_типа(job.value_type_from_json(запись))
            except Refuse as отказ:
                обратно = f"отказ: {отказ}"
            if обратно != запись:
                плохие.append(f"{где}.{реквизит.get('имя')}: {запись} -> {обратно}")
        for часть in spec.get("табличныеЧасти") or []:
            обойти(часть, f"{где}.{часть.get('имя')}")

    for вид, каталог in (("Справочник", "Catalogs"), ("Документ", "Documents")):
        for файл in sorted(os.listdir(os.path.join(root, каталог))):
            if файл.endswith(".xml"):
                spec, _ = дамп.read_spec([(вид, файл[:-4])])
                обойти(spec, f"{вид}.{файл[:-4]}")
    assert всего > 40000, всего
    assert not плохие, плохие[:10]


def test_an_object_reference_is_written_the_way_the_platform_writes_it():
    """Обозначение объекта в свойстве переводится, а не пишется дословно.

    Основная схема отчёта записана как `Report.Имя.Template.Макет` во всех
    417 отчётах замеренной конфигурации. Будь поле текстом, туда ложилось бы
    что дали — и русская форма, и английская, обе с вердиктом «замечаний нет».
    """
    from meta.acl import mapping
    from meta.domain.model import Refuse

    # Через поле, а не только через функцию: функция может стоять на месте,
    # а поле — быть объявлено текстом, и тогда до перевода дело не дойдёт.
    from meta.infra import serializer
    from meta.jobs import dialect as job_dialect

    карточка = serializer.card_to_text(mapping.translate(
        job_dialect.spec_from_json({"вид": "Отчет", "поля": {
            "имя": "мой_Реестр", "синоним": "Р",
            "основнаяСхема": "Отчет.мой_Реестр.Макет.Схема"}}), "u1",
        new_id=lambda: "id"))
    assert ("<MainDataCompositionSchema>Report.мой_Реестр.Template.Схема"
            "</MainDataCompositionSchema>") in карточка

    with pytest.raises(Refuse) as refusal:
        mapping.object_notation("Отчет.мой_Реестр.НетТакогоШага.Схема")
    assert "не знаю вида" in str(refusal.value)


def test_a_standard_attribute_name_is_taken_by_the_platform():
    """Стандартный реквизит вида занимает имя, а среди детей его нет.

    Платформа заводит стандартные реквизиты сама и в выгрузку их не
    выписывает, пока не настроят руками, — спросить про них состав детей
    нельзя, и без этой проверки измерение «Период» в периодическом регистре
    проходило бы со словами «замечаний нет». Ни у одного из 1809 регистров
    замеренной конфигурации ребёнка «Период» нет.
    """
    from meta.domain.kinds import kind_of
    from meta.domain.model import Host, Spec

    host = Host("РегистрСведений", "мой_Проба",
                path=(("РегистрСведений", "мой_Проба"),))

    class Мир:
        def object_exists(self, kind, name):
            return True

        def taken_names(self, path):
            return []

    коды = [f.code for f in kind_of("Измерение").check(
        Spec("Измерение", {"имя": "Период", "синоним": "П",
                           "тип": dm.StringType(10)}), Мир(), host)]
    assert "ВЛОЖЕННОЕ-ИМЯ-СТАНДАРТНОЕ" in коды
    коды = [f.code for f in kind_of("Измерение").check(
        Spec("Измерение", {"имя": "Организация", "синоним": "О",
                           "тип": dm.StringType(10)}), Мир(), host)]
    assert "ВЛОЖЕННОЕ-ИМЯ-СТАНДАРТНОЕ" not in коды


def test_a_right_is_checked_against_the_kind():
    """Проведение справочнику и ввод по строке регистру не пишутся молча.

    Таблица снята по 3,07 млн пар «объект — право» в 2709 ролях замеренной
    конфигурации: право, не встретившееся у вида ни разу, скорее всего этому
    виду не полагается.
    """
    from meta.domain.kinds import kind_of
    from meta.domain.model import Spec

    class Мир:
        def object_exists(self, kind, name):
            return True

    def права(объект, права_):
        return [f.code for f in kind_of("Роль").check(Spec("Роль", {
            "имя": "мой_Р", "синоним": "Р",
            "права": [{"объект": объект, "права": права_}]}), Мир())]

    assert "РОЛЬ-ПРАВО-НЕ-ДЛЯ-ВИДА" in права(
        "Справочник.мой_Ц", ["Чтение", "Проведение"])
    assert "РОЛЬ-ПРАВО-НЕ-ДЛЯ-ВИДА" not in права(
        "Справочник.мой_Ц", ["Чтение", "Просмотр", "ВводПоСтроке"])


def test_a_lookalike_prefix_names_the_substituted_character():
    """«мoй_» и «мой_» на глаз одинаковы: без подсказки отказ читался бы как поломка."""
    from meta.domain.kinds import kind_of
    from meta.domain.model import Spec

    сообщения = [f.message for f in kind_of("Справочник", ТЕСТ).check(
        Spec("Справочник", {"имя": "мoй_Хитрый", "синоним": "Х"}), None)
        if f.code == "МД-ПРЕФИКС"]
    assert сообщения and "латиница" in сообщения[0]
    # на обычном имени подсказки нет — иначе она превратится в шум
    сообщения = [f.message for f in kind_of("Справочник", ТЕСТ).check(
        Spec("Справочник", {"имя": "ПростоИмя", "синоним": "П"}), None)
        if f.code == "МД-ПРЕФИКС"]
    assert сообщения and "латиница" not in сообщения[0]


def test_a_name_longer_than_anything_measured_is_said_out_loud():
    """Имя длиннее 80 символов (#std474 п. 2.3) — ошибка, а не «замечаний нет»."""
    from meta.domain.kinds import kind_of
    from meta.domain.model import Spec

    коды = [f.code for f in kind_of("Справочник", ТЕСТ).check(
        Spec("Справочник", {"имя": "мой_" + "Я" * 90, "синоним": "Д"}), None)]
    assert "МД-ИМЯ-ДЛИННОЕ" in коды

def test_all_unknown_values_are_named_at_once():
    """Три непонятых слова — три строки отказа, а не три круга запусков.

    Без этого отказ летел бы с первого же: человек правил бы одно слово,
    запускал снова и узнавал про второе.
    """
    with pytest.raises(Refuse) as отказ:
        mapping.translate(kind_of("Справочник").fill(Spec("Справочник", {
            "имя": "мой_Проба", "синоним": "П",
            "полнотекстовыйПоиск": "Нет такого",
            "созданиеПриВводе": "И такого",
            "историяДанных": "И этого"})), "uuid")
    сказано = str(отказ.value)
    for поле in ("полнотекстовыйПоиск", "созданиеПриВводе", "историяДанных"):
        assert поле in сказано, сказано


def test_a_reference_type_without_a_name_says_so():
    """Вид назван, имени нет — это «не хватает имени», а не «невнятно».

    Текст, пересказывающий весь формат типа заново, заставил бы искать в нём
    ошибку, которой человек не делал.
    """
    from meta.jobs import dialect as job_dialect

    with pytest.raises(Refuse) as отказ:
        job_dialect.child_spec_from_json(
            "Реквизит", {"имя": "Поле", "тип": {"вид": "Справочник"}})
    assert "не указано имя объекта" in str(отказ.value)


def test_an_unknown_right_lists_the_rights_of_that_kind():
    """Всех прав 70, у справочника — 25; читать нужно те самые."""
    with pytest.raises(Refuse) as отказ:
        mapping.render_rights(Spec("Роль", {"имя": "мой_Роль", "права": [
            {"объект": "Справочник.Валюты", "права": ["Чтенее"]}]}))
    сказано = str(отказ.value)
    assert "у вида «Справочник» бывают" in сказано, сказано
    assert "Проведение" not in сказано, "право документа справочнику не показываем"

# --- проверки, без которых запись прошла бы молча ----------------------------

def _находки(вид, поля, мир=None, хозяин=None):
    """Задание собирается диалектом: дети должны стать `Spec`, а типы — типами."""
    from meta.jobs import dialect as job_dialect

    kind = kind_of(вид)
    spec = job_dialect.spec_from_json({"вид": вид, "поля": поля})
    return kind.check(kind.fill(spec), мир, хозяин)


def test_a_dimension_type_is_checked_like_an_attribute_type():
    """Опечатка в имени справочника не проходит молча у измерения и ресурса.

    Проверка «тип указывает на живой объект» общая для вложенных видов, а не
    только у реквизита: у измерения тип точно такой же, и иначе `{"вид":
    "Справочник", "имя": "мой_ЭталонНесуществующий"}` получал бы «замечаний нет».
    """
    for поле, вложенный in (("измерения", "Измерение"), ("ресурсы", "Ресурс")):
        находки = _находки("РегистрСведений", {
            "имя": "мой_Проба", "синоним": "П",
            поле: [{"имя": "Поле", "синоним": "П",
                    "тип": {"вид": "Справочник",
                            "имя": "мой_НетТакого"}}]}, World())
        коды = [f.code for f in находки]
        assert "ТИП-НЕТ" in коды, (вложенный, коды)


def test_qualifier_numbers_are_bounded_by_what_the_platform_does():
    """Платформа их не отвергает, а молча подменяет — потому и проверяем.

    Опыт на пустой конфигурации: разрядность 39 становится 38, дробная часть
    5 при разрядности 0 — нулём, длина −5 читается как 4294967291. Загрузка
    при этом проходит, то есть человек уверен, что записал заказанное.
    """
    случаи = [
        ({"вид": "Число", "разрядность": 0, "дробнаяЧасть": 5}, "ТИП-ДРОБНАЯ"),
        ({"вид": "Число", "разрядность": 999, "дробнаяЧасть": 2},
         "ТИП-РАЗРЯДНОСТЬ"),
        ({"вид": "Строка", "длина": -5}, "ТИП-ДЛИНА"),
    ]
    for тип, код in случаи:
        находки = _находки("Справочник", {
            "имя": "мой_Проба", "синоним": "П",
            "реквизиты": [{"имя": "Поле", "синоним": "П", "тип": тип}]}, World())
        коды = [f.code for f in находки]
        assert код in коды, (тип, коды)
    # а годное — молчит
    ладно = _находки("Справочник", {
        "имя": "мой_Проба", "синоним": "П",
        "реквизиты": [{"имя": "Поле", "синоним": "П",
                       "тип": {"вид": "Число", "разрядность": 38,
                               "дробнаяЧасть": 38}}]}, World())
    assert not [f for f in ладно if f.code.startswith("ТИП-")], ладно


def test_code_length_beyond_the_platform_limit_is_refused():
    """`длинаКода: "9999"` — отказ: платформа отвергает на ней всю загрузку.

    Дословно: «Длина кода превышает максимально допустимое значение - 50».
    Длина наименования 200 при этом проходит загрузку и остаётся 200, поэтому
    предел по корпусному максимуму 150 не выдумывается.
    """
    коды = [f.code for f in _находки("Справочник", {
        "имя": "мой_Проба", "синоним": "П", "длинаКода": "9999"})]
    assert "ДЛИНА-БОЛЬШЕ-ПРЕДЕЛА" in коды, коды
    коды = [f.code for f in _находки("Справочник", {
        "имя": "мой_Проба", "синоним": "П", "длинаНаименования": "-10"})]
    assert "ДЛИНА-ОТРИЦАТЕЛЬНА" in коды, коды
    # 50 — предел, а не запрет; 200 у наименования платформа принимает
    спокойно = _находки("Справочник", {
        "имя": "мой_Проба", "синоним": "П", "длинаКода": "50",
        "длинаНаименования": "200"})
    assert not [f for f in спокойно if f.code.startswith("ДЛИНА")], спокойно


@pytest.mark.parametrize("имя, ожидается, повтор", [
    ("мой_Заявки", ("сервер", "внешнееСоединение", "клиентОбычноеПриложение"), "НеИспользовать"),
    ("мой_ЗаявкиСервер", ("сервер", "внешнееСоединение", "клиентОбычноеПриложение"), "НеИспользовать"),
    ("мой_ЗаявкиВызовСервера", ("сервер", "вызовСервера"), "НеИспользовать"),
    ("мой_ЗаявкиКлиент", ("клиентУправляемоеПриложение", "клиентОбычноеПриложение"), "НеИспользовать"),
    ("мой_ЗаявкиКлиентСервер", ("клиентУправляемоеПриложение", "сервер", "внешнееСоединение",
                               "клиентОбычноеПриложение"), "НеИспользовать"),
    ("мой_ЗаявкиГлобальный", ("глобальный", "клиентУправляемоеПриложение",
                             "клиентОбычноеПриложение"), "НеИспользовать"),
    ("мой_ЗаявкиПовтИсп", ("сервер", "внешнееСоединение", "клиентОбычноеПриложение"), "НаВремяСеанса"),
    ("мой_ЗаявкиКлиентПовтИсп", ("клиентУправляемоеПриложение", "клиентОбычноеПриложение"), "НаВремяСеанса"),
    ("мой_ЗаявкиВызовСервераПовтИсп", ("сервер", "вызовСервера"), "НаВремяСеанса"),
    ("мой_ЗаявкиСлужебныйПолныеПрава", ("сервер", "внешнееСоединение", "клиентОбычноеПриложение",
                                       "привилегированный"), "НеИспользовать"),
    ("мой_ЗаявкиКлиентПереопределяемый", ("клиентУправляемоеПриложение",
                                         "клиентОбычноеПриложение"), "НеИспользовать"),
])
def test_module_context_follows_the_name_postfix(имя, ожидается, повтор):
    """Стандарт #469: постфикс имени задаёт контекст, и умолчания выводятся из него.

    Замер по 4103 модулям замеренной конфигурации: `ВызовСервера` → «сервер +
    вызов» у 439 из 455, `КлиентСервер` → все четыре у 466 из 475, `Клиент` →
    оба клиента у 631 из 636, `Глобальный` → клиент + глобальный у 56 из 58,
    `ПовтИсп` → «на время сеанса» у 205 из 222. С одними умолчаниями
    серверного модуля на всех три `false` приходилось бы писать руками,
    а без них выходил бы модуль с вызовом сервера и внешним соединением.
    """
    kind = kind_of("ОбщийМодуль")
    spec = kind.fill(Spec("ОбщийМодуль", {"имя": имя, "синоним": "П"}))
    флаги = ("глобальный", "клиентУправляемоеПриложение", "сервер", "внешнееСоединение",
             "клиентОбычноеПриложение", "вызовСервера", "привилегированный")
    assert tuple(f for f in флаги if spec.get(f)) == ожидается
    assert spec.get("повторноеИспользование") == повтор
    assert not [f for f in kind.check(spec, None) if f.code.startswith("МОДУЛЬ-")], \
        [f.code for f in kind.check(spec, None)]


@pytest.mark.parametrize("поля, код, блокирует", [
    ({"имя": "мой_Заявки", "вызовСервера": True}, "МОДУЛЬ-ВЫЗОВ-БЕЗ-ПОСТФИКСА", True),
    ({"имя": "мой_ЗаявкиВызовСервера", "вызовСервера": False}, "МОДУЛЬ-ИМЯ-ВЫЗОВ-СЕРВЕРА", True),
    ({"имя": "мой_Заявки", "глобальный": True, "клиентУправляемоеПриложение": True},
     "МОДУЛЬ-ГЛОБАЛЬНЫЙ-БЕЗ-ПОСТФИКСА", True),
    ({"имя": "мой_ЗаявкиКлиент", "клиентУправляемоеПриложение": False}, "МОДУЛЬ-КЛИЕНТ-БЕЗ-КЛИЕНТА", True),
    ({"имя": "мой_ЗаявкиКлиент", "сервер": True}, "МОДУЛЬ-КЛИЕНТ-С-СЕРВЕРОМ", True),
    ({"имя": "мой_ЗаявкиВызовСервера", "внешнееСоединение": True}, "МОДУЛЬ-КОНТЕКСТ-НЕ-ПО-СТАНДАРТУ", False),
    ({"имя": "мой_ЗаявкиПовтИсп", "повторноеИспользование": "НеИспользовать"}, "МОДУЛЬ-ПОВТИСП-БЕЗ-ФЛАГА", False),
    ({"имя": "мой_Заявки", "повторноеИспользование": "НаВремяСеанса"}, "МОДУЛЬ-ПОВТИСП-БЕЗ-ПОСТФИКСА", False),
    ({"имя": "мой_Заявки", "привилегированный": True}, "МОДУЛЬ-ПРИВИЛЕГИРОВАННЫЙ-БЕЗ-ПОСТФИКСА", False),
])
def test_module_name_and_flags_must_agree(поля, код, блокирует):
    """Имя и флаги сходятся: отказ там, где стандарт говорит «обязательно».

    «Обязательно» у #469 — постфикс `ВызовСервера` (п. 2.2) и `Глобальный`
    (п. 3.2.1); клиентское имя без клиентского контекста и `Клиент` с сервером —
    просто другой вид модуля. Остальное — рекомендации, и на них предупреждение:
    состав контекстов, `ПовтИсп`, `ПолныеПрава` (последний в замеренной
    конфигурации почти не используют — 45 привилегированных из 47 без него).
    """
    находки = _находки("ОбщийМодуль", dict(поля, синоним="П"))
    свои = [f for f in находки if f.code == код]
    assert свои, [f.code for f in находки]
    assert свои[0].blocking is блокирует
    assert "469" in свои[0].message or код == "МОДУЛЬ-ИМЯ-ВЫЗОВ-СЕРВЕРА"


def test_explicit_flags_are_never_overwritten_by_the_name():
    """Названное человеком не трогается — умолчания правят только пропуски."""
    kind = kind_of("ОбщийМодуль")
    spec = kind.fill(Spec("ОбщийМодуль", {"имя": "мой_ЗаявкиВызовСервера",
                                          "внешнееСоединение": True}))
    assert spec.get("внешнееСоединение") is True
    assert spec.get("вызовСервера") is True          # остальное — по постфиксу
    assert spec.get("клиентОбычноеПриложение") is False


class _Мир:
    """Конфигурация, в которой есть ровно названные объекты."""

    def __init__(self, *есть, режимы=None):
        self.есть = set(есть)
        self.режимы = dict(режимы or {})

    def object_exists(self, kind, name):
        return (kind, name) in self.есть

    def register_write_mode(self, name):
        return self.режимы.get(name)

    def __getattr__(self, имя):
        return lambda *a, **k: None


@pytest.mark.parametrize("поля, код, блокирует", [
    ({"движения": ["РегистрНакопления.мой_НетТакого"]}, "ДОКУМЕНТ-ДВИЖЕНИЯ-НЕТ", True),
    ({"движения": ["Справочник.мой_Остатки"]}, "ДОКУМЕНТ-ДВИЖЕНИЯ-НЕ-РЕГИСТР", True),
    ({"движения": ["мой_Остатки"]}, "ДОКУМЕНТ-ДВИЖЕНИЯ-ФОРМА", True),
    ({"движения": ["РегистрНакопления.мой_Остатки"], "проведение": "Запретить"},
     "ДОКУМЕНТ-ДВИЖЕНИЯ-БЕЗ-ПРОВЕДЕНИЯ", False),
    ({"основание": ["Документ.мой_НетТакого"]}, "ДОКУМЕНТ-ОСНОВАНИЕ-НЕТ", True),
])
def test_document_movements_are_checked(поля, код, блокирует):
    """Движения — только по регистрам, только по существующим, и не без проведения.

    Без проверок справочник в движениях и несуществующий регистр проходили бы
    с «замечаний нет». Замер по 634 документам замеренной конфигурации: 4191
    движение, не-регистров ноль; движения при запрете проведения — 7 из 383,
    все «операции», поэтому это предупреждение.
    """
    находки = _находки("Документ", dict(поля, имя="мой_Проба", синоним="П"),
                       мир=_Мир(("РегистрНакопления", "мой_Остатки")))
    свои = [f for f in находки if f.code == код]
    assert свои, [f.code for f in находки]
    assert свои[0].blocking is блокирует


def test_document_movements_by_existing_registers_pass():
    мир = _Мир(("РегистрНакопления", "мой_Остатки"), ("РегистрСведений", "мой_Факты"),
               режимы={"мой_Факты": "ПодчинениеРегистратору"})
    находки = _находки("Документ", {
        "имя": "мой_Проба", "синоним": "П",
        "движения": ["РегистрНакопления.мой_Остатки", "РегистрСведений.мой_Факты"]},
        мир=мир)
    assert not [f for f in находки if f.code.startswith("ДОКУМЕНТ-")], \
        [f.code for f in находки]


def test_an_independent_information_register_cannot_take_movements():
    """Движения по регистру сведений — только подчинённому регистратору.

    В замеренной конфигурации 986 регистров сведений названы в движениях, и
    все 986 подчинены регистратору; конфигуратор независимый и не предложит.
    Без этой проверки инструмент записал бы его молча.
    """
    мир = _Мир(("РегистрСведений", "мой_Настройки"),
               режимы={"мой_Настройки": "Независимо"})
    находки = _находки("Документ", {"имя": "мой_Проба", "синоним": "П",
                                    "движения": ["РегистрСведений.мой_Настройки"]}, мир=мир)
    свои = [f for f in находки if f.code == "ДОКУМЕНТ-ДВИЖЕНИЯ-НЕЗАВИСИМЫЙ-РЕГИСТР"]
    assert свои and свои[0].blocking, [f.code for f in находки]
    # режим не прочитан — предупреждение, а не обвинение
    мир = _Мир(("РегистрСведений", "мой_Настройки"))
    находки = _находки("Документ", {"имя": "мой_Проба", "синоним": "П",
                                    "движения": ["РегистрСведений.мой_Настройки"]}, мир=мир)
    assert [f for f in находки if f.code == "ДОКУМЕНТ-ДВИЖЕНИЯ-РЕЖИМ-НЕПРОВЕРЕН"
            and not f.blocking]


def test_a_designation_may_be_given_as_an_object():
    """Обозначение — строкой «Вид.Имя» или объектом, как тип. Лишний ключ — отказ.

    Объект в движениях разбирается в обозначение ещё при чтении задания —
    иначе он ронял бы инструмент трассировкой из недр перекладки, а не
    отказом с адресом поля.
    """
    from meta.jobs import dialect as job_dialect

    spec = job_dialect.spec_from_json({"вид": "Документ", "поля": {
        "имя": "мой_Проба",
        "движения": [{"вид": "РегистрНакопления", "имя": "мой_Остатки"},
                     "РегистрСведений.мой_Факты"]}})
    assert spec.get("движения") == ["РегистрНакопления.мой_Остатки",
                                    "РегистрСведений.мой_Факты"]
    with pytest.raises(Refuse) as отказ:
        job_dialect.spec_from_json({"вид": "Документ", "поля": {
            "имя": "мой_Проба",
            "движения": [{"вид": "РегистрНакопления", "имя": "мой_Остатки", "лишнее": 1}]}})
    assert "движения" in str(отказ.value) and "лишнее" in str(отказ.value)
    # состав подсистемы — тот же приём
    spec = job_dialect.spec_from_json({"вид": "Подсистема", "поля": {
        "имя": "мой_Проба", "состав": [{"вид": "Справочник", "имя": "Организации"}]}})
    assert spec.get("состав") == ["Справочник.Организации"]


def test_the_preview_shows_what_was_asked_even_when_it_equals_the_default():
    """Просмотр отвечает на «то ли я заказал», а не только на «что тут необычного».

    Заданный «видИерархии: ГруппыИЭлементы» совпадает с умолчанием и без этого
    исчез бы из вывода: отличить «принято» от «не разобрано» было бы нельзя.
    Спецификация помнит, что назвал человек, и `fill` это знание не теряет.
    """
    kind = kind_of("Справочник")
    задано = {"имя": "мой_Проба", "синоним": "П",
              "видИерархии": "ГруппыИЭлементы"}
    готово = kind.fill(job.spec_from_json({"вид": "Справочник", "поля": задано}))
    assert готово.asked == frozenset(задано), готово.asked
    assert готово.get("видИерархии") == "ГруппыИЭлементы"
    # умолчания подставлены, но в «названном» их нет
    assert "иерархический" in готово.fields
    assert "иерархический" not in готово.asked


def test_a_qualifier_is_required_in_the_object_form_too():
    """`{"вид": "Строка"}` — отказ, а не молчаливая строка нулевой длины.

    Краткая запись («тип»: «Строка») и объектная отвергаются по одной
    причине. У даты это ещё и выбор: `ДатаВремя` у 2884 реквизитов
    замеренной конфигурации, `Дата` у 2653 — почти поровну, угадывать нечего.
    """
    for вид, ключ in (("Строка", "длина"), ("Число", "разрядность"),
                      ("Дата", "состав")):
        with pytest.raises(Refuse) as отказ:
            job.value_type_from_json({"вид": вид})
        assert ключ in str(отказ.value), (вид, str(отказ.value))
    # а с квалификатором — молча и правильно
    assert str(job.value_type_from_json({"вид": "Дата", "состав": "Дата"})) \
        == "Дата"


def test_a_bad_name_says_what_is_wrong_with_it():
    """Отказ говорит, что не так с именем: «не является именем» не объясняет ничего."""
    находки = [f for f in _находки("Справочник", {
        "имя": "мой_Лимиты Тест-2024", "синоним": "П"})
        if f.code == "МД-ИМЯ-НЕДОПУСТИМО"]
    assert находки, "имя должно быть отвергнуто"
    сказано = находки[0].message
    assert "пробел" in сказано and "дефис" in сказано, сказано


def test_a_typo_in_a_field_name_gets_a_suggestion():
    """На опечатку — подсказка, а не все 55 имён полей одной строкой."""
    находки = [f for f in _находки("Справочник", {
        "имя": "мой_Проба", "синоним": "П", "иерархичный": True})
        if f.code == "МД-ПОЛЕ-НЕИЗВЕСТНО"]
    assert находки
    сказано = находки[0].message
    assert "возможно, иерархический" in сказано, сказано
    assert "их 55, перечень" in сказано, сказано


def test_an_unknown_field_silences_its_own_consequences():
    """Одна ошибка — одна находка, иначе чинить тянуло бы все три.

    Значение перечисления, написанное как объект, — незнакомые поля, пустое
    имя и отсутствующий синоним. Две последние только следствия первой.
    """
    kind = kind_of("ЗначениеПеречисления")
    коды = [f.code for f in kind.check(
        kind.fill(Spec("ЗначениеПеречисления",
                       {"вид": "ЗначениеПеречисления", "поля": {}})), World())]
    assert коды == ["МД-ПОЛЕ-НЕИЗВЕСТНО"], коды


def test_an_attribute_job_without_the_address_key_names_the_key():
    """Отказ называет недостающий ключ, а не печатает `получено «»`, которого человек не писал."""
    with pytest.raises(Refuse) as отказ:
        job.attribute_job_from_json({"путь": "Справочник.мой_Эталон",
                                     "поля": {"имя": "Поле"}})
    сказано = str(отказ.value)
    assert "«объект»" in сказано and "additions" in сказано, сказано

# --- план, просмотр и разбор задания ------------------------------------------

def test_the_plan_keeps_the_size_it_had_before_writing(tmp_path):
    """План печатается ПОСЛЕ записи, и «было» помнит размер до неё.

    Читай план «было» с диска уже после записи, выходило бы «станет 12251 Б,
    было 12251 Б» — строка, отрицающая только что произошедшее и наводящая
    на мысль, что просмотр пишет на диск вопреки обещанию.

    Фикстура выполняет `apply` и смотрит на текст плана после него, а не до.
    """
    from meta.infra.repository import Plan

    файл = os.path.join(str(tmp_path), "карточка.xml")
    open(файл, "wb").write(b"x" * 100)
    plan = Plan()
    plan.add(файл, b"y" * 250, False)
    до_записи = "\n".join(plan.describe())
    plan.apply()
    после = "\n".join(plan.describe())
    assert "станет 250 Б, было 100 Б" in до_записи, до_записи
    assert после == до_записи, после
    assert os.path.getsize(файл) == 250          # запись действительно была


def test_a_typo_in_a_type_kind_is_not_taken_for_a_reference():
    """«Строчка» — опечатка в виде, а не ссылочный тип без имени.

    Правило «вид назван, имени нет — значит ссылочный тип» без этого
    проглатывало бы опечатки в примитивных типах: инструмент предложил бы
    достроить `{"вид": "Строчка", "имя": "Контрагенты"}`.
    """
    with pytest.raises(Refuse) as отказ:
        job.value_type_from_json({"вид": "Строчка", "длина": 20})
    сказано = str(отказ.value)
    assert "возможно, Строка" in сказано, сказано
    assert "имя объекта" not in сказано, сказано
    # настоящий ссылочный тип без имени по-прежнему говорит про имя
    with pytest.raises(Refuse) as отказ:
        job.value_type_from_json({"вид": "Справочник"})
    assert "не указано имя объекта" in str(отказ.value)


def test_the_date_parts_are_checked_while_the_job_is_read():
    """Состав даты проверяется при разборе задания, а не в перекладке.

    Перекладка — на ступень позже инвариантов: проверка там не показала бы
    неверный состав вместе с любой другой ошибкой, а в разборе печаталось бы
    `Дата(ТолькоДата)`, будто значение принято.
    """
    with pytest.raises(Refuse) as отказ:
        job.value_type_from_json({"вид": "Дата", "состав": "ТолькоДата"})
    сказано = str(отказ.value)
    assert "допустимо: Дата, Время, ДатаВремя" in сказано, сказано
    assert "возможно, Дата" in сказано, сказано


def test_the_domain_and_the_dump_agree_on_the_date_parts():
    """Слова состава объявляет домен, перекладка держит только перевод."""
    from meta.acl.vocabulary import DATE_PARTS

    assert set(DATE_PARTS) == set(dm.DateType.PARTS)


def test_a_child_synonym_is_shown_even_when_it_repeats_the_name(capsys):
    """Синоним показывается и тогда, когда повторяет имя.

    Пряча совпадающий синоним, просмотр делал бы «задан» и «забыт»
    одинаковыми: строка выходила бы побайтно одна и та же у карточек,
    различающихся на 401 байт.
    """
    from meta.report.objects import describe

    kind = kind_of("Перечисление")
    spec = kind.fill(job.spec_from_json({"вид": "Перечисление", "поля": {
        "имя": "мой_Проба", "синоним": "П",
        "значения": [{"имя": "Черновик", "синоним": "Черновик"},
                     {"имя": "НаСогласовании", "синоним": "На согласовании"}]}}))
    сказано = "\n".join(describe(spec))
    assert "Черновик «Черновик»" in сказано, сказано
    assert "НаСогласовании «На согласовании»" in сказано, сказано


def test_the_default_count_agrees_with_the_word_after_it(capsys):
    """«ещё 1 полей» — по-русски так не говорят."""
    from meta.report.objects import describe

    kind = kind_of("ОбщийМодуль")
    задано = dict.fromkeys(
        [п for п in kind.fields if п != "текст"], "")
    задано.update({"имя": "мой_Проба", "синоним": "П"})
    spec = kind.fill(job.spec_from_json({"вид": "ОбщийМодуль", "поля": задано}))
    сказано = "\n".join(describe(spec))
    assert "ещё 1 поле не названо в задании —" in сказано, сказано


def test_asking_for_help_is_not_a_failure():
    """`--help` печатает справку и возвращает 0: код 2 в скрипте — падение."""
    import meta.add as cli

    assert cli.main(["--help"]) == 0

# --- дефекты подачи: отказы копятся, а не рвут работу на первом --------------

def test_every_value_the_dump_cannot_take_is_named_at_once():
    """Два поля-длины числом — один отказ с обоими, а не два запуска.

    Словарные значения и остальные отказы укладки копятся одинаково: иначе
    внутри одного запуска было бы два разных характера поведения, и
    предсказать, какой достанется, было бы нельзя.
    """
    with pytest.raises(Refuse) as отказ:
        mapping.translate(kind_of("Справочник").fill(job.spec_from_json({
            "вид": "Справочник", "поля": {
                "имя": "мой_Проба", "синоним": "П",
                "длинаКода": 9, "длинаНаименования": 100}})), "uuid")
    сказано = str(отказ.value)
    assert "длинаКода" in сказано and "длинаНаименования" in сказано, сказано
    assert "(2)" in сказано, сказано


def test_every_broken_type_is_named_at_once_with_its_address():
    """Четыре беды в описании типов — один отказ, а не четыре запуска по одной."""
    with pytest.raises(Refuse) as отказ:
        job.spec_from_json({"вид": "Справочник", "поля": {
            "имя": "мой_Проба", "синоним": "П", "реквизиты": [
                {"имя": "А", "синоним": "А",
                 "тип": {"вид": "Строчка", "длина": 5}},
                {"имя": "Б", "синоним": "Б",
                 "тип": {"вид": "Дата", "состав": "ТолькоДата"}},
                {"имя": "В", "синоним": "В",
                 "тип": {"вид": "Число", "длина": 5}},
                {"имя": "Г", "синоним": "Г", "тип": {"вид": "Строка"}}]}})
    сказано = str(отказ.value)
    assert "(4)" in сказано, сказано
    for адрес in ("реквизиты[А].тип", "реквизиты[Б].тип",
                  "реквизиты[В].тип", "реквизиты[Г].тип"):
        assert адрес in сказано, (адрес, сказано)


def test_a_broken_type_inside_a_tabular_section_is_addressed_in_full():
    """Адрес складывается по дороге вглубь, а не теряется на первом уровне."""
    with pytest.raises(Refuse) as отказ:
        job.spec_from_json({"вид": "Справочник", "поля": {
            "имя": "мой_Проба", "синоним": "П", "табличныеЧасти": [
                {"имя": "Строки", "синоним": "С", "реквизиты": [
                    {"имя": "Сумма", "синоним": "С",
                     "тип": {"вид": "Число", "точность": 2}}]}]}})
    assert "табличныеЧасти[Строки].реквизиты[Сумма].тип" in str(отказ.value)


def test_one_collector_serves_every_layer():
    """Сборщик один на три слоя — он живёт в домене, а не в инфраструктуре."""
    from meta.acl import mapping as acl_mapping
    from meta.infra import repository
    from meta.jobs import dialect as dialect

    assert repository.Собранные is dm.Собранные
    assert acl_mapping.Собранные is dm.Собранные
    assert dialect.Собранные is dm.Собранные

# --- обратное чтение --------------------------------------------------------

ПУСТАЯ_ВЫГРУЗКА = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
                   "\t<Configuration>\n\t\t<ChildObjects/>\n"
                   "\t</Configuration>\n</MetaDataObject>")


def _выгрузка(tmp_path):
    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(ПУСТАЯ_ВЫГРУЗКА)
    return root


ЗАДАНИЯ = [
    {"вид": "Справочник", "поля": {
        "имя": "мой_Круг", "синоним": "(Мой) Круг", "иерархический": True,
        "видИерархии": "ГруппыИЭлементы", "типКода": "Число",
        "длинаКода": "9", "длинаНаименования": "100",
        "реквизиты": [{"имя": "Дата", "синоним": "Дата",
                       "тип": {"вид": "Дата", "состав": "Дата"}},
                      {"имя": "Сумма", "синоним": "Сумма",
                       "тип": {"вид": "Число", "разрядность": 15,
                               "дробнаяЧасть": 2}}],
        "табличныеЧасти": [{"имя": "Строки", "синоним": "Строки",
                            "реквизиты": [
                                {"имя": "Текст", "синоним": "Текст",
                                 "тип": {"вид": "Строка", "длина": 200}}]}]}},
    {"вид": "Перечисление", "поля": {
        "имя": "мой_КругСтатусы", "синоним": "(Мой) Круг, статусы",
        "значения": [{"имя": "Черновик", "синоним": "Черновик"},
                     {"имя": "Готово", "синоним": "Готово к работе"}]}},
    # Имя с постфиксом: «вызов сервера» без «ВызовСервера» — отказ
    # по стандарту #469, и такой модуль просто не записался бы.
    {"вид": "ОбщийМодуль", "поля": {
        "имя": "мой_КругВызовСервера", "синоним": "(Мой) Круг, вызов сервера",
        "комментарий": "#КРУГ-1", "сервер": True, "вызовСервера": True,
        "внешнееСоединение": False, "клиентОбычноеПриложение": False}},
]


@pytest.mark.parametrize("задание", ЗАДАНИЯ,
                         ids=[з["вид"] for з in ЗАДАНИЯ])
def test_what_was_written_reads_back_the_same(tmp_path, задание):
    """Записали — прочитали — сверили, без всякой платформы.

    Чтение ходит по той же схеме видов, что и запись, поэтому круг проверяет
    обе стороны разом: разъехаться незаметно они не могут. Это же и есть
    ответ на «то ли записалось» — без чтения XML глазами.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(задание)], apply_now=True)

    прочитано, файл = DesignerDump(root).read_spec(
        [(задание["вид"], задание["поля"]["имя"])])
    assert os.path.isfile(файл)
    for поле, ожидалось in задание["поля"].items():
        если_дети = isinstance(ожидалось, list) and ожидалось and isinstance(
            ожидалось[0], dict)
        стало = прочитано.get(поле)
        if если_дети:
            assert [c.get("имя") for c in стало] == [
                c["имя"] for c in ожидалось], поле
            assert [c.get("синоним") for c in стало] == [
                c["синоним"] for c in ожидалось], поле
        elif isinstance(ожидалось, dict):        # тип
            assert стало is not None, поле
        else:
            assert стало == ожидалось, (поле, стало, ожидалось)


def test_a_written_type_reads_back_as_the_same_type(tmp_path):
    """Тип — то место, где чтение и запись разъехались бы незаметнее всего."""
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(ЗАДАНИЯ[0])], apply_now=True)
    прочитано, _ = DesignerDump(root).read_spec([("Справочник", "мой_Круг")])
    типы = {c.get("имя"): str(c.get("тип")) for c in прочитано.get("реквизиты")}
    assert типы == {"Дата": "Дата", "Сумма": "Число(15,2)"}, типы
    строки = прочитано.get("табличныеЧасти")[0]
    assert str(строки.get("реквизиты")[0].get("тип")) == "Строка(200)"


def test_a_nested_entity_is_read_by_its_own_address(tmp_path):
    """Адрес тот же, что у правки: спуск один на всё."""
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(ЗАДАНИЯ[0])], apply_now=True)
    реквизит, _ = DesignerDump(root).read_spec(
        [("Справочник", "мой_Круг"), ("Реквизит", "Сумма")])
    assert реквизит.kind == "Реквизит"
    assert реквизит.get("синоним") == "Сумма"
    assert str(реквизит.get("тип")) == "Число(15,2)"


def test_showing_a_missing_object_is_refused(tmp_path):
    """Отказ говорит адресом, а не внутренним устройством."""
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    with pytest.raises(Refuse) as отказ:
        DesignerDump(root).read_spec([("Справочник", "мой_НетТакого")])
    assert "мой_НетТакого" in str(отказ.value)

# --- вендорский хозяин и принятые предупреждения -----------------------------

ВЕНДОРСКАЯ_КАРТОЧКА = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
    'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.21">\n'
    '\t<Catalog uuid="11111111-1111-1111-1111-111111111111">\n'
    "\t\t<Properties>\n\t\t\t<Name>Контрагенты</Name>\n"
    "\t\t</Properties>\n\t\t<ChildObjects/>\n\t</Catalog>\n"
    "</MetaDataObject>")

ВЕНДОРСКИЙ_РЕЕСТР = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
    "\t<Configuration>\n\t\t<ChildObjects>\n"
    "\t\t\t<Catalog>Контрагенты</Catalog>\n"
    "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")


def test_a_child_of_a_vendor_object_must_carry_the_prefix(tmp_path):
    """Главный случай правила префиксов: реквизит в вендорском объекте.

    В выгрузке, где все объекты свои (`мой_*`), этот случай не проверить.
    Здесь вендорский объект заведён руками — создать его инструментом нельзя,
    он же и не даст.
    """
    from meta.application.add_child.use_case import AddChildUseCase
    from meta.infra.designer import DesignerDump

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(ВЕНДОРСКИЙ_РЕЕСТР)
    os.makedirs(os.path.join(root, "Catalogs"))
    open(os.path.join(root, "Catalogs", "Контрагенты.xml"), "w",
         encoding="utf-8-sig", newline="").write(ВЕНДОРСКАЯ_КАРТОЧКА)

    итог = AddChildUseCase(DesignerDump(root), ТЕСТ).execute(
        [job.attribute_job_from_json({
            "объект": "Справочник.Контрагенты",
            "поля": {"имя": "КодПодразделения", "синоним": "Код",
                     "тип": {"вид": "Строка", "длина": 20}}})],
        apply_now=False)
    коды = [f.code for f in итог.findings]
    assert "МД-ПРЕФИКС" in коды, коды

    # а с префиксом — молча
    итог = AddChildUseCase(DesignerDump(root), ТЕСТ).execute(
        [job.attribute_job_from_json({
            "объект": "Справочник.Контрагенты",
            "поля": {"имя": "мой_КодПодразделения", "синоним": "Код",
                     "тип": {"вид": "Строка", "длина": 20}}})],
        apply_now=False)
    assert "МД-ПРЕФИКС" not in [f.code for f in итог.findings]


def test_an_accepted_warning_is_marked_accepted(capsys, tmp_path):
    """Принятое предупреждение не повторяется вперемешку с новыми.

    Подписка на собственный объект — то, что задание требует, а отступить
    от предупреждения нельзя. Печатайся оно на каждом запуске, человек
    каждый раз перечитывал бы, не стало ли оно ошибкой.
    """
    import json

    import meta.add as cli

    root = _выгрузка(tmp_path)
    путь = os.path.join(str(tmp_path), "job.json")
    json.dump({"repo": root, "принято": ["РЕГИСТР-БЕЗ-ИЗМЕРЕНИЙ"],
               "objects": [{"вид": "РегистрСведений", "поля": {
                   "имя": "мой_Проба", "синоним": "П",
                   "ресурсы": [{"имя": "Сумма", "синоним": "Сумма",
                                "тип": {"вид": "Число", "разрядность": 15,
                                        "дробнаяЧасть": 2}}]}}]},
              open(путь, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False)
    assert cli.main([путь]) == 0
    сказано = capsys.readouterr().out
    assert "принято        [РЕГИСТР-БЕЗ-ИЗМЕРЕНИЙ]" in сказано, сказано
    assert "предупреждение [РЕГИСТР-БЕЗ-ИЗМЕРЕНИЙ]" not in сказано, сказано


def test_an_error_cannot_be_accepted(capsys, tmp_path):
    """Ошибку принять нельзя: она про то, что платформа не возьмёт."""
    import json

    import meta.add as cli

    root = _выгрузка(tmp_path)
    путь = os.path.join(str(tmp_path), "job.json")
    json.dump({"repo": root, "принято": ["МД-ПРЕФИКС"],
               "objects": [{"вид": "Справочник", "поля": {
                   "имя": "ЛимитыТест", "синоним": "П"}}]},
              open(путь, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False)
    assert cli.main([путь]) == 1
    сказано = capsys.readouterr().out
    assert "ошибка         [МД-ПРЕФИКС]" in сказано, сказано
    assert сказано.split("\n")[1].startswith("ОТКАЗ: ошибок 1"), сказано


def test_the_detailed_preview_names_what_was_decided_for_you(capsys, tmp_path):
    """За строкой «ещё N полей» прячутся не пустоты, а решения: подробный просмотр их называет.

    У регистра сведений это периодичность и режим записи — они задают
    структуру таблицы и меняются потом только с потерей данных.
    """
    import json

    import meta.add as cli

    root = _выгрузка(tmp_path)
    путь = os.path.join(str(tmp_path), "job.json")
    json.dump({"repo": root, "objects": [{"вид": "РегистрСведений", "поля": {
        "имя": "мой_Проба", "синоним": "П",
        "ресурсы": [{"имя": "Сумма", "синоним": "Сумма",
                     "тип": {"вид": "Число", "разрядность": 15,
                             "дробнаяЧасть": 2}}]}}]},
              open(путь, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False)
    assert cli.main([путь, "--подробно"]) == 0
    сказано = capsys.readouterr().out
    assert "периодичность: Непериодический" in сказано, сказано
    assert "режимЗаписи: Независимо" in сказано, сказано

# --- обработка --------------------------------------------------------------

ОБРАБОТКА = {"вид": "Обработка", "поля": {
    "имя": "мой_ПробаОбработка", "синоним": "(Мой) Проба обработка",
    "комментарий": "#КРУГ-6", "стандартныеКоманды": True,
    "включатьСправкуВСодержание": False,
    "реквизиты": [{"имя": "Период", "синоним": "Период",
                   "тип": {"вид": "Дата", "состав": "Дата"}}],
    "табличныеЧасти": [{"имя": "Строки", "синоним": "Строки", "реквизиты": [
        {"имя": "Сумма", "синоним": "Сумма",
         "тип": {"вид": "Число", "разрядность": 15, "дробнаяЧасть": 2}},
        {"имя": "Текст", "синоним": "Текст",
         "тип": {"вид": "Строка", "длина": 100}}]}]}}


def test_a_data_processor_is_written_and_reads_back(tmp_path):
    """Обработка: состав снят со всех 613 карточек замеренной конфигурации, вариант один.

    Круг записи и чтения проверяет обе стороны разом.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    итог = AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(ОБРАБОТКА)], apply_now=True)
    assert [f.code for f in итог.findings] == [], [f.code for f in итог.findings]
    assert os.path.isfile(os.path.join(root, "DataProcessors",
                                       "мой_ПробаОбработка.xml"))
    прочитано, _ = DesignerDump(root).read_spec(
        [("Обработка", "мой_ПробаОбработка")])
    assert прочитано.get("синоним") == "(Мой) Проба обработка"
    assert прочитано.get("стандартныеКоманды") is True
    строки = прочитано.get("табличныеЧасти")[0]
    assert [c.get("имя") for c in строки.get("реквизиты")] == ["Сумма", "Текст"]
    assert str(строки.get("реквизиты")[0].get("тип")) == "Число(15,2)"


def test_a_tabular_attribute_knows_whose_section_it_is(tmp_path):
    """Состав реквизита табличной части зависит от того, хранится ли объект.

    У справочника и документа — индексирование, полнотекстовый поиск и
    история и **без** заполнения (6698 и 14 280 реквизитов замеренной
    конфигурации); у обработки и отчёта наоборот: заполнение есть,
    остального нет (3829 и 582).
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(ОБРАБОТКА)], apply_now=True)
    текст = open(os.path.join(root, "DataProcessors", "мой_ПробаОбработка.xml"),
                 encoding="utf-8-sig").read()
    внутри = текст.split("<TabularSection", 1)[1]
    assert "<FillValue" in внутри, "у нехранимой ТЧ заполнение есть"
    for чего_нет in ("<Indexing>", "<FullTextSearch>", "<DataHistory>"):
        assert чего_нет not in внутри, чего_нет

    # а у справочника — ровно наоборот
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json({"вид": "Справочник", "поля": {
            "имя": "мой_Хранимый", "синоним": "П",
            "табличныеЧасти": [{"имя": "Строки", "синоним": "С", "реквизиты": [
                {"имя": "Сумма", "синоним": "С",
                 "тип": {"вид": "Число", "разрядность": 10,
                         "дробнаяЧасть": 2}}]}]}})], apply_now=True)
    текст = open(os.path.join(root, "Catalogs", "мой_Хранимый.xml"),
                 encoding="utf-8-sig").read()
    внутри = текст.split("<TabularSection", 1)[1]
    assert "<FillValue" not in внутри, "у хранимой ТЧ заполнения нет"
    for что_есть in ("<Indexing>", "<FullTextSearch>", "<DataHistory>"):
        assert что_есть in внутри, что_есть

# --- константа, определяемый тип, подсистема ---------------------------------

def _записать(tmp_path, задание):
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    итог = AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(задание)], apply_now=True)
    assert [f.code for f in итог.findings] == [], [f.code for f in итог.findings]
    return root, DesignerDump(root)


def test_a_constant_is_written_and_reads_back(tmp_path):
    """Константа: 30 свойств, один вариант на 905 карточек замеренной конфигурации."""
    задание = {"вид": "Константа", "поля": {
        "имя": "мой_Проба", "синоним": "(Мой) Проба", "комментарий": "#К-1",
        "стандартныеКоманды": True,
        "тип": {"вид": "Число", "разрядность": 15, "дробнаяЧасть": 2}}}
    root, дамп = _записать(tmp_path, задание)
    прочитано, _ = дамп.read_spec([("Константа", "мой_Проба")])
    assert str(прочитано.get("тип")) == "Число(15,2)"
    assert прочитано.get("стандартныеКоманды") is True
    assert прочитано.get("комментарий") == "#К-1"
    # умолчания из корпуса на месте
    assert прочитано.get("выборГруппИЭлементов") == "Элементы"
    assert прочитано.get("быстрыйВыбор") == "Авто"
    assert прочитано.get("режимУправленияБлокировкой") == "Управляемый"


def test_a_defined_type_may_hold_several_types(tmp_path):
    """Определяемый тип: четыре свойства, и состав бывает набором."""
    задание = {"вид": "ОпределяемыйТип", "поля": {
        "имя": "мой_ПробаТип", "синоним": "(Мой) Проба тип",
        "тип": [{"вид": "Строка", "длина": 100},
                {"вид": "Число", "разрядность": 10, "дробнаяЧасть": 0}]}}
    root, дамп = _записать(tmp_path, задание)
    прочитано, _ = дамп.read_spec([("ОпределяемыйТип", "мой_ПробаТип")])
    assert [str(x) for x in прочитано.get("тип")] == ["Строка(100)", "Число(10,0)"]


def test_a_subsystem_content_is_written_as_notation(tmp_path):
    """Состав подсистемы — обозначения объектов, а не текст.

    Задание пишет «Справочник.Имя», в файл идёт «Catalog.Имя» с типом
    элемента `xr:MDObjectRef` — он один и тот же на все 25 458 элементов
    состава в замеренной конфигурации.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json({"вид": "Справочник", "поля": {
            "имя": "мой_Цель", "синоним": "Ц"}})], apply_now=True)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json({"вид": "Подсистема", "поля": {
            "имя": "мой_ПробаПодсистема", "синоним": "(Мой) Проба",
            "включатьСправкуВСодержание": True,
            "включатьВКомандныйИнтерфейс": True,
            "состав": ["Справочник.мой_Цель"]}})], apply_now=True)
    текст = open(os.path.join(root, "Subsystems", "мой_ПробаПодсистема.xml"),
                 encoding="utf-8-sig").read()
    assert ('<xr:Item xsi:type="xr:MDObjectRef">Catalog.мой_Цель</xr:Item>'
            in текст), текст
    assert "<ChildObjects/>" in текст, "пустой раздел детей пишется всегда"
    прочитано, _ = DesignerDump(root).read_spec(
        [("Подсистема", "мой_ПробаПодсистема")])
    assert прочитано.get("состав") == ["Справочник.мой_Цель"]


def test_a_subsystem_refuses_a_missing_object(tmp_path):
    """Сослаться в составе на несуществующий объект нельзя."""
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    итог = AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json({"вид": "Подсистема", "поля": {
            "имя": "мой_Проба", "синоним": "П",
            "включатьСправкуВСодержание": False,
            "включатьВКомандныйИнтерфейс": False,
            "состав": ["Справочник.мой_НетТакого", "безТочки"]}})],
        apply_now=False)
    коды = [f.code for f in итог.findings]
    assert "ПОДСИСТЕМА-СОСТАВ-НЕТ" in коды, коды
    assert "ПОДСИСТЕМА-СОСТАВ-ФОРМА" in коды, коды

# --- регистр накопления -----------------------------------------------------

РЕГИСТР_НАКОПЛЕНИЯ = {"вид": "РегистрНакопления", "поля": {
    "имя": "мой_ЭталонРН", "синоним": "Мой эталон РН", "видРегистра": "Остатки",
    "ресурсы": [{"имя": "Ресурс1", "синоним": "",
                 "тип": {"вид": "Число", "разрядность": 10,
                         "дробнаяЧасть": 0}}],
    "измерения": [{"имя": "Измерение1", "синоним": "",
                   "тип": {"вид": "Строка", "длина": 10}}]}}


def test_the_register_matches_what_the_designer_wrote(tmp_path):
    """Сверка с карточкой, записанной конфигуратором.

    Эталон лежит в наборе целиком: это не пересказ, а тот самый файл.
    Умолчания у половины свойств по корпусу расходятся почти поровну —
    режим блокировки 94 против 79, — и вывести их неоткуда, кроме
    как из только что созданного объекта.

    Порядок детей в нём — ресурс, потом измерение; наивный порядок
    «как в задании» дал бы 70 расхождений на ровном месте.
    """
    import re

    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    итог = AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(РЕГИСТР_НАКОПЛЕНИЯ)], apply_now=True)
    assert not [f for f in итог.findings if f.blocking], [
        f.code for f in итог.findings]
    записано = open(os.path.join(root, "AccumulationRegisters", "мой_ЭталонРН.xml"),
                    encoding="utf-8-sig").read()
    эталон = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "эталоны", "РегистрНакопления-конфигуратор.xml"),
                  encoding="utf-8-sig").read()
    уид = re.compile(r'(uuid="|<xr:TypeId>|<xr:ValueId>)[0-9a-f-]{36}')

    def без_идентификаторов(текст):
        return уид.sub(r"\1…", текст).replace("\r\n", "\n").rstrip("\n")

    assert без_идентификаторов(записано) == без_идентификаторов(эталон)


def test_the_three_demands_of_an_accumulation_register_differ_in_severity():
    """Опыт на пустой конфигурации: три загрузки, три разных ответа платформы.

    Без ресурса отвергает («У регистра не определено ни одного ресурса»),
    без регистратора отвергает («Ни один из документов не является
    регистратором для регистра»), без измерения — принимает. Объявить
    последнее ошибкой значило бы выдумать запрет, которого у платформы нет.
    """
    kind = kind_of("РегистрНакопления")
    находки = kind.check(kind.fill(job.spec_from_json(
        {"вид": "РегистрНакопления", "поля": {
            "имя": "мой_Проба", "синоним": "П", "видРегистра": "Обороты"}})),
        World())
    по_коду = {f.code: f for f in находки}
    assert по_коду["РЕГИСТР-НАКОПЛЕНИЯ-БЕЗ-РЕСУРСА"].blocking
    assert not по_коду["РЕГИСТР-НАКОПЛЕНИЯ-БЕЗ-ИЗМЕРЕНИЯ"].blocking
    assert not по_коду["РЕГИСТР-НАКОПЛЕНИЯ-БЕЗ-РЕГИСТРАТОРА"].blocking
    # про регистратор говорится всегда: его в карточке регистра не видно
    полный = kind.check(kind.fill(job.spec_from_json(РЕГИСТР_НАКОПЛЕНИЯ)), World())
    коды = [f.code for f in полный if f.code != "МД-БЕЗ-СИНОНИМА"]
    assert коды == ["РЕГИСТР-НАКОПЛЕНИЯ-БЕЗ-РЕГИСТРАТОРА"], коды


def test_the_register_kind_is_asked_not_guessed():
    """Обороты и остатки расходятся по корпусу ровно пополам — 89 и 84."""
    kind = kind_of("РегистрНакопления")
    коды = [(f.code, f.field) for f in kind.check(kind.fill(job.spec_from_json(
        {"вид": "РегистрНакопления", "поля": {
            "имя": "мой_Проба", "синоним": "П"}})), World())]
    assert ("МД-ПОЛЕ-ПУСТО", "видРегистра") in коды, коды


def test_nested_composition_differs_between_the_two_registers(tmp_path):
    """У измерения накопления 27 свойств, у сведений 32 — и наоборот одно.

    Замер: 1145 измерений накопления против 4319 сведений, вариант состава
    у каждого вида один.
    """
    from meta.application.add_object.use_case import AddObjectUseCase
    from meta.infra.designer import DesignerDump

    root = _выгрузка(tmp_path)
    AddObjectUseCase(DesignerDump(root)).execute(
        [job.spec_from_json(РЕГИСТР_НАКОПЛЕНИЯ)], apply_now=True)
    текст = open(os.path.join(root, "AccumulationRegisters", "мой_ЭталонРН.xml"),
                 encoding="utf-8-sig").read()
    измерение = текст.split("<Dimension", 1)[1]
    assert "<UseInTotals>true</UseInTotals>" in измерение
    for чего_нет in ("<Master>", "<MainFilter>", "<DataHistory>",
                     "<TypeReductionMode>", "<FillValue"):
        assert чего_нет not in измерение, чего_нет
    ресурс = текст.split("<Resource", 1)[1].split("</Resource>", 1)[0]
    for чего_нет in ("<Indexing>", "<DataHistory>", "<FillValue"):
        assert чего_нет not in ресурс, чего_нет
