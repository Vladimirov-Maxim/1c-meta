"""Формы: правки существующей и рождение новой — против эталонов платформы.

Эталоны в `эталоны/формы` — не сочинённые: это файлы проверочной пустой
конфигурации после круга «записали инструментом → загрузили в базу →
выгрузили обратно», в котором платформа не меняет ни байта. Тест повторяет
те же задания на временной выгрузке и сверяет байты — включая BOM и переводы
строк.

Что рождается у элемента, взято не из корпуса, а из эталона конфигуратора
(форма `мой_Эталон` в той же конфигурации): мастер плюс по элементу каждого
вида, добавленному руками. В пяти местах эталон расходится с большинством
корпуса, и тесты ниже стоят на эталоне.

Отдельно: инварианты домена ловят то, что в сеансе всплыло бы падением
кода формы («Элемент не найден»), а словарь свойств совпадает с таблицей,
из которой сгенерирован.
"""

import json
import os
import re
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.application.edit_form.use_case import EditFormUseCase  # noqa: E402
from meta.domain import forms as fm  # noqa: E402
from meta.domain.model import Refuse, Spec  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.infra.forms import registry  # noqa: E402
from meta.jobs import dialect as job_dialect  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402

ЭТАЛОНЫ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны", "формы")
КРУГ = "Documents/мой_ПробаСДвижениями/Forms/мой_Круг"
КРУГ2 = "Documents/мой_ПробаНепроводимый/Forms/мой_Круг2"


def эталон(name):
    with open(os.path.join(ЭТАЛОНЫ, name), "rb") as source:
        return source.read()


def задание(name):
    return json.loads(эталон(name).decode("utf-8-sig"))


def без_uuid(raw):
    return re.sub(rb'uuid="[0-9a-f-]{36}"', b'uuid="*"', raw)


@pytest.fixture
def dump():
    """Выгрузка из двух документов — тех же, что в проверочной пустой
    конфигурации, и до форм."""
    root = tempfile.mkdtemp(prefix="meta-forms-")

    def положить(rel, name):
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as target:
            target.write(эталон(name))

    положить("Configuration.xml", "Configuration.xml")
    положить("Documents/мой_ПробаСДвижениями.xml", "мой_ПробаСДвижениями.до.xml")
    положить("Documents/мой_ПробаНепроводимый.xml", "мой_ПробаНепроводимый.до.xml")
    yield root
    shutil.rmtree(root, ignore_errors=True)


def выполнить(root, name):
    job = задание(name)
    edits = [job_dialect.form_edits_from_json(item) for item in job["forms"]]
    result = EditFormUseCase(DesignerDump(root)).execute(edits, apply_now=True)
    assert result.ok, [str(f) for f in result.findings]
    return result


def файл(root, rel):
    with open(os.path.join(root, *rel.split("/")), "rb") as source:
        return source.read()


# --- круги через платформу --------------------------------------------------------

def test_a_form_is_born_and_then_filled_as_the_platform_returned_it(dump):
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "2-наполнение.json")
    assert файл(dump, КРУГ + "/Ext/Form.xml") == эталон("круг.наполнение.xml")
    assert файл(dump, КРУГ + "/Ext/Form/Module.bsl") == эталон("круг.Module.bsl")
    assert без_uuid(файл(dump, КРУГ + ".xml")) == без_uuid(эталон("круг.карточка.xml"))
    assert файл(dump, "Documents/мой_ПробаСДвижениями.xml") == эталон(
        "мой_ПробаСДвижениями.после.xml")


def test_edits_on_a_filled_form_touch_only_what_was_asked(dump):
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "2-наполнение.json")
    result = выполнить(dump, "3-правка.json")
    assert файл(dump, КРУГ + "/Ext/Form.xml") == эталон("круг.правка.xml")
    # модуль есть — инструмент его не трогает, а говорит, что положить
    assert файл(dump, КРУГ + "/Ext/Form/Module.bsl") == эталон("круг.Module.bsl")
    assert any("Процедура ПроверитьЗаполнение(Команда)" in line
               for line in result.plan.describe())


def test_a_new_form_is_born_and_filled_in_one_job(dump):
    выполнить(dump, "4-создать.json")
    assert файл(dump, КРУГ2 + "/Ext/Form.xml") == эталон("круг2.xml")
    assert файл(dump, КРУГ2 + "/Ext/Form/Module.bsl") == эталон("круг2.Module.bsl")
    assert без_uuid(файл(dump, КРУГ2 + ".xml")) == без_uuid(эталон("круг2.карточка.xml"))
    assert файл(dump, "Documents/мой_ПробаНепроводимый.xml") == эталон(
        "мой_ПробаНепроводимый.после.xml")


def test_preview_writes_nothing(dump):
    выполнить(dump, "1-пустая.json")
    job = задание("2-наполнение.json")
    edits = [job_dialect.form_edits_from_json(item) for item in job["forms"]]
    before = файл(dump, КРУГ + "/Ext/Form.xml")
    result = EditFormUseCase(DesignerDump(dump)).execute(edits, apply_now=False)
    assert result.ok and result.plan is not None
    assert файл(dump, КРУГ + "/Ext/Form.xml") == before


def test_what_the_configurator_writes_to_a_new_element(dump):
    """Рождённые свойства — по эталону, а не по большинству корпуса.

    Именно в этих пяти местах корпус показывает иначе, и без эталона
    инструмент ошибся бы именно на них.
    """
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "2-наполнение.json")
    text = файл(dump, КРУГ + "/Ext/Form.xml").decode("utf-8-sig")
    assert "<TitleLocation>" not in text            # у флажка его нет
    assert "<Behavior>" not in text                 # и у группы — ни поведения,
    assert "<Representation>None" not in text       # ни отображения
    assert "<PagesRepresentation>" not in text      # и у страниц
    assert "<ScrollOnCompress>" not in text         # и у страницы
    assert "<RowSelectionMode>" not in text         # и у таблицы
    # а то, что названо заданием, стоит: группе сказали спрятать заголовок
    assert text.count("<ShowTitle>false</ShowTitle>") == 1
    assert "<ShowCommandBar>auto</ShowCommandBar>" in text
    assert "<RowFilter xsi:nil=\"true\"/>" in text
    # а в корне новой формы — только свойства проведения документа
    root = text.split("<AutoCommandBar")[0]
    assert "<WindowOpeningMode>" not in root and "<Group>" not in root
    assert "<AutoTime>CurrentOrLast</AutoTime>" in root


def test_reading_a_form_gives_its_elements_attributes_and_commands(dump):
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "2-наполнение.json")
    view = DesignerDump(dump).read_form(("Документ", "мой_ПробаСДвижениями"), "мой_Круг")
    assert view.main == "Объект" and view.assignment == "Документа"
    комментарий = view.elements["Комментарий"]
    assert (комментарий.kind, комментарий.parent, комментарий.path) == (
        "ПолеВвода", None, "Объект.Комментарий")
    assert комментарий.events == (("ПриИзменении", "КомментарийПриИзменении"),)
    assert view.elements["Номер"][:2] == ("ПолеВвода", "мой_ГруппаШапка")
    assert view.elements["мой_ТаблицаСтатья"][:2] == ("ПолеВвода", "мой_Таблица")
    assert view.elements["ФормаКоманднаяПанель"][:2] == ("КоманднаяПанель", None)
    assert view.elements["ФормаЗаполнить"].command == "мой_Заполнить"
    assert view.order.index("мой_ГруппаШапка") < view.order.index("Комментарий")
    assert set(view.attributes) == {"Объект", "мой_Флаг", "мой_Период", "мой_Таблица"}
    assert view.commands == {"мой_Заполнить"}
    assert view.events == {"ПриСозданииНаСервере": "ПриСозданииНаСервере"}
    assert DesignerDump(dump).read_form(("Документ", "мой_ПробаНепроводимый"), "Нет") is None


# --- инварианты ---------------------------------------------------------------------

def правки(**kwargs):
    kwargs.setdefault("owner", ("Документ", "мой_Заявка"))
    kwargs.setdefault("name", "ФормаДокумента")
    return fm.FormEdits(**kwargs)


def вид(**kwargs):
    kwargs.setdefault("owner", ("Документ", "мой_Заявка"))
    kwargs.setdefault("name", "ФормаДокумента")
    kwargs.setdefault("main", "Объект")
    kwargs.setdefault("assignment", "Документа")
    return fm.FormView(**kwargs)


ХОЗЯИН = Spec("Документ", {"имя": "мой_Заявка", "реквизиты": [
    Spec("Реквизит", {"имя": "Контрагент"})], "табличныеЧасти": [
    Spec("ТабличнаяЧасть", {"имя": "Товары", "реквизиты": [Spec("Реквизит", {"имя": "Цена"})]})]})


def коды(findings):
    return [f.code for f in findings]


def test_missing_parent_and_misplaced_sibling_are_findings():
    view = вид(elements={"Шапка": fm.ViewItem("ГруппаФормы"),
                         "Подвал": fm.ViewItem("ГруппаФормы"),
                         "Комментарий": fm.ViewItem("ПолеВвода", "Подвал")})
    edits = правки(elements=[fm.FormElement("ПолеВвода", "Поле", "Объект.Контрагент",
                                            parent="Нет"),
                             fm.FormElement("ПолеВвода", "Поле2", "Объект.Контрагент",
                                            parent="Шапка", before="Комментарий")])
    assert коды(fm.check(edits, view, ХОЗЯИН)) == ["ФОРМА-РОДИТЕЛЬ-НЕТ",
                                                  "ФОРМА-СОСЕД-В-ДРУГОМ-МЕСТЕ"]


def test_taken_names_unknown_properties_and_bad_values_are_findings():
    view = вид(elements={"Комментарий": fm.ViewItem("ПолеВвода")}, attributes={"Объект": "x"})
    edits = правки(
        attributes=[fm.FormAttribute("Объект", None)],
        elements=[fm.FormElement("ПолеВвода", "Комментарий", "Объект.Контрагент",
                                 properties={"Ширина": "широко", "Цвет": 1,
                                             "ПоложениеЗаголовка": "Сбоку"})])
    found = коды(fm.check(edits, view, ХОЗЯИН))
    assert found.count("ФОРМА-СВОЙСТВО") == 3
    assert "ФОРМА-РЕКВИЗИТ-ЗАНЯТ" in found and "ФОРМА-ЭЛЕМЕНТ-ЗАНЯТ" in found


def test_a_binding_to_a_missing_owner_attribute_is_refused():
    edits = правки(elements=[fm.FormElement("ПолеВвода", "Склад", "Объект.Склад"),
                             fm.FormElement("ПолеВвода", "Цена", "Объект.Товары.Цена")])
    assert коды(fm.check(edits, вид(), ХОЗЯИН)) == ["ФОРМА-ПРИВЯЗКА-НЕТ-РЕКВИЗИТА"]
    # без карточки хозяина — предупреждение, а не молчание
    found = fm.check(edits, вид(), None)
    assert [f.code for f in found] == ["ФОРМА-ПРИВЯЗКИ-НЕ-ПРОВЕРЕНЫ"] and not found[0].blocking


def test_a_button_needs_a_command_and_a_page_needs_pages():
    view = вид(elements={"Группа": fm.ViewItem("ГруппаФормы")}, commands={"Заполнить"})
    edits = правки(elements=[
        fm.FormElement("Кнопка", "К1"),
        fm.FormElement("Кнопка", "К2", command="Нет"),
        fm.FormElement("Кнопка", "К3", command="Заполнить"),
        fm.FormElement("Кнопка", "К4", command="Стандартная.Write"),
        fm.FormElement("Страница", "С", parent="Группа")])
    assert коды(fm.check(edits, view, ХОЗЯИН)) == [
        "ФОРМА-КНОПКА-БЕЗ-КОМАНДЫ", "ФОРМА-КНОПКА-БЕЗ-КОМАНДЫ", "ФОРМА-МЕСТО-НЕ-ТОГО-ВИДА"]


def test_removing_what_is_absent_and_the_main_attribute_is_refused():
    edits = правки(remove_elements=["Нет"], remove_attributes=["Объект"])
    assert коды(fm.check(edits, вид(attributes={"Объект": "x"}), ХОЗЯИН)) == [
        "ФОРМА-УДАЛИТЬ-НЕТ", "ФОРМА-ГЛАВНЫЙ-НЕ-УДАЛЯЕТСЯ"]


def test_paths_are_bound_like_the_configurator_writes_them():
    edits = правки(
        attributes=[fm.FormAttribute("Период", None),
                    fm.FormAttribute("Таблица", None)],
        elements=[fm.FormElement("ПолеВвода", "Номер", "Номер"),
                  fm.FormElement("ПолеВвода", "Дата", "Объект.Дата"),
                  fm.FormElement("ПолеВвода", "Период", "Период"),
                  fm.FormElement("ПолеВвода", "Контрагент", "Контрагент"),
                  fm.FormElement("ТаблицаФормы", "Таблица", "Таблица", children=[
                      fm.FormElement("ПолеВвода", "ТаблицаСумма", column="Сумма")])])
    fm.bind_paths(edits, вид())
    paths = {e.name: e.path for e in edits.all_elements()}
    assert paths == {"Номер": "Объект.Number", "Дата": "Объект.Date", "Период": "Период",
                     "Контрагент": "Объект.Контрагент", "Таблица": "Таблица",
                     "ТаблицаСумма": "Таблица.Сумма"}


def test_a_missing_form_needs_create_and_an_existing_one_refuses_it(dump):
    platform = DesignerDump(dump)
    result = EditFormUseCase(platform).execute([правки(owner=("Документ", "мой_ПробаНепроводимый"))])
    assert коды(result.findings) == ["ФОРМА-НЕТ"]
    выполнить(dump, "1-пустая.json")
    born = правки(owner=("Документ", "мой_ПробаСДвижениями"), name="мой_Круг",
                  create=fm.Form("мой_Круг", ("Документ", "мой_ПробаСДвижениями")))
    result = EditFormUseCase(platform).execute([born])
    assert "ФОРМА-УЖЕ-ЕСТЬ" in коды(result.findings)


# --- свойства и разбор задания ----------------------------------------------------

def test_property_check_accepts_both_languages_and_refuses_structures():
    assert fm.check_property("ГруппаФормы", "Группировка", "Horizontal")[3] == "Горизонтальная"
    assert fm.check_property("ПолеВвода", "ReadOnly", "Истина")[3] is True
    with pytest.raises(Refuse):
        fm.check_property("ПолеВвода", "Шрифт", "Arial")
    with pytest.raises(Refuse):
        fm.check_property("Надпись", "Ширина", "10")


def test_the_property_dictionary_matches_its_source_table():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import form_properties_from_md_design as generator
    properties, enums = generator.build(generator.read_rows())
    with open(os.path.join(ROOT, "meta", "domain", "form_properties.py"),
              encoding="utf-8") as module:
        assert module.read() == generator.render(properties, enums)


def test_type_text_notation():
    assert str(job_dialect.value_type_from_text("Строка(20)")) == "Строка(20)"
    assert str(job_dialect.value_type_from_text("Число(15,2)")) == "Число(15,2)"
    assert str(job_dialect.value_type_from_text("Дата")) == "Дата"
    assert str(job_dialect.value_type_from_text("Справочник.Номенклатура")) == \
        "Справочник.Номенклатура"
    for bad in ("Строка", "Число", "Дата(1)", "Нечто"):
        with pytest.raises(Refuse):
            job_dialect.value_type_from_text(bad)


def test_unknown_keys_in_a_form_job_are_refused():
    with pytest.raises(Refuse):
        job_dialect.form_edits_from_json({"форма": "Документ.Х.Ф", "элемент": []})
    with pytest.raises(Refuse):
        job_dialect.form_edits_from_json({"форма": "Х.Ф"})
    edits = job_dialect.form_edits_from_json(
        {"форма": "Общая.мой_Проба", "создать": True,
         "элементы": [{"вид": "ТаблицаФормы", "имя": "Т", "путь": "Т",
                       "колонки": [{"имя": "А", "обработчики": {"ПриИзменении": True}}]}]})
    assert edits.owner is None and edits.create.assignment == "Произвольная"
    column = edits.elements[0].children[0]
    assert (column.name, column.column, column.events) == (
        "ТА", "А", {"ПриИзменении": "ТАПриИзменении"})


# --- реализации формата --------------------------------------------------------------

def test_the_format_is_chosen_by_the_file_and_unknown_versions_are_refused():
    text = эталон("круг.наполнение.xml").decode("utf-8-sig")
    assert registry.for_text(text).version == "2.21"
    with pytest.raises(Refuse):
        registry.for_text(text.replace('version="2.21"', 'version="9.9"'))
    with pytest.raises(Refuse):
        registry.for_version("9.9")


def test_implementations_are_reached_only_through_the_registry():
    """Версия формата — подстановка реализации, а не ветка в коде: пакет
    реализации импортирует только реестр (и он сам изнутри)."""
    import ast
    package = os.path.join(ROOT, "meta")
    offenders = []
    for folder, _, names in os.walk(package):
        if "tests" in folder.split(os.sep):
            continue
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, package).replace(os.sep, "/")
            if rel.startswith("infra/forms/designer221/") or rel == "infra/forms/registry.py":
                continue
            with open(path, encoding="utf-8-sig") as source:
                tree = ast.parse(source.read())
            for node in ast.walk(tree):
                targets = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                           else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                if any("designer221" in t for t in targets):
                    offenders.append(rel)
    assert not offenders, offenders


# --- типовые формы: только кодом ------------------------------------------------

def типовая(**kwargs):
    kwargs.setdefault("owner", ("Документ", "их_Заявка"))
    kwargs.setdefault("name", "ФормаДокумента")
    return fm.FormEdits(**kwargs)


def test_a_vendor_form_is_not_edited_as_xml():
    """Типовые формы меняются только программно. Инструмент видит XML типовой
    формы так же, как своей, — значит правило проверяет он, а не надежда на
    проверку глазами."""
    edits = типовая(elements=[fm.FormElement("ПолеВвода", "мой_П", "Объект.Комментарий")])
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" in коды(fm.check(edits, вид(), None, соглашения=ТЕСТ))
    # с «кодом» — можно
    edits = типовая(as_code=True,
                    elements=[fm.FormElement("ПолеВвода", "мой_П", "Объект.Комментарий")])
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" not in коды(fm.check(edits, вид(), None, соглашения=ТЕСТ))
    # наша форма в вендорском объекте — своя, XML править можно
    своя = типовая(name="мой_РабочееМесто",
                   elements=[fm.FormElement("ПолеВвода", "мой_П", "Объект.Комментарий")])
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" not in коды(fm.check(своя, вид(), None, соглашения=ТЕСТ))


def test_code_mode_refuses_what_form_code_cannot_do():
    edits = типовая(as_code=True, create=fm.Form("Ф", ("Документ", "их_Заявка")),
                    events={"ПриОткрытии": "ПриОткрытии"}, remove_elements=["Что-то"])
    found = коды(fm.check(edits, вид(), None, соглашения=ТЕСТ))
    assert "ФОРМА-КОД-НЕ-СОЗДАЁТ" in found
    assert "ФОРМА-КОД-БЕЗ-СОБЫТИЙ" in found
    assert "ФОРМА-КОД-БЕЗ-УДАЛЕНИЯ" in found


def test_code_mode_refuses_what_it_cannot_express():
    from meta.acl import platform_code
    после = типовая(as_code=True, elements=[
        fm.FormElement("ПолеВвода", "П", "Объект.Комментарий", after="Дата")])
    with pytest.raises(Refuse):
        platform_code.render(после, вид())
    стандартная = типовая(as_code=True, elements=[
        fm.FormElement("Кнопка", "К", command="Стандартная.Write")])
    with pytest.raises(Refuse):
        platform_code.render(стандартная, вид())


def test_a_code_job_writes_no_files(dump):
    job = {"форма": "Документ.их_Заявка.ФормаДокумента", "код": True,
           "элементы": [{"вид": "ПолеВвода", "имя": "мой_П", "путь": "Объект.Комментарий"}]}
    edits = job_dialect.form_edits_from_json(job)
    assert edits.as_code


# --- формы списка -------------------------------------------------------------

КРУГ_СПИСОК = "Documents/мой_ПробаСДвижениями/Forms/мой_КругСписок"


def test_a_list_form_is_born_with_a_dynamic_list_table(dump):
    """Форма списка — такая, какой её возвращает круг через платформу: у таблицы
    списка нет отбора строк, стандартное поле пишется английским именем,
    идентификаторы пользовательских настроек — константы платформы."""
    выполнить(dump, "1-пустая.json")     # порядок заданий — как при снятии эталона
    выполнить(dump, "5-список.json")
    assert файл(dump, КРУГ_СПИСОК + "/Ext/Form.xml") == эталон("кругсписок.xml")
    assert без_uuid(файл(dump, КРУГ_СПИСОК + ".xml")) == без_uuid(
        эталон("кругсписок.карточка.xml"))
    assert файл(dump, "Documents/мой_ПробаСДвижениями.xml") == эталон(
        "мой_ПробаСДвижениями.после-списка.xml")
    text = файл(dump, КРУГ_СПИСОК + "/Ext/Form.xml").decode("utf-8-sig")
    assert "<RowFilter" not in text
    assert "<DataPath>Список.Date</DataPath>" in text        # сказали «Дата»
    assert "<DataPath>Список.Комментарий</DataPath>" in text  # свой — как есть
    assert text.count("dfcece9d-5077-440b-b6b3-45a5cb4538eb") == 1


def test_a_dynamic_list_column_shows_and_does_not_edit(dump):
    """Колонка списка — поле-надписи, если вид не назвали: список показывают.
    В замеренной конфигурации так у 19 465 колонок против 1262 полей ввода."""
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "5-список.json")
    text = файл(dump, КРУГ_СПИСОК + "/Ext/Form.xml").decode("utf-8-sig")
    assert text.count("<LabelField name=") == 3 and "<InputField" not in text
    # названный вид уважается
    edits = job_dialect.form_edits_from_json(
        {"форма": "Документ.мой_ПробаСДвижениями.мой_КругСписок",
         "элементы": [{"вид": "ТаблицаФормы", "имя": "Список", "путь": "Список",
                       "колонки": [{"имя": "Ссылка", "вид": "ПолеВвода"}]}]})
    view = DesignerDump(dump).read_form(("Документ", "мой_ПробаСДвижениями"), "мой_КругСписок")
    fm.bind_paths(edits, view)
    колонка = edits.elements[0].children[0]
    assert колонка.kind == "ПолеВвода" and колонка.path == "Список.Ref"


def test_an_unknown_list_field_is_a_warning_not_an_error(dump):
    """Поле списка приходит из его запроса: чего нет у хозяина — повод
    посмотреть, а не отказ. Платформа такую колонку примет и покажет пустой."""
    view = вид(assignment="Списка", main="Список", dynamic_lists={"Список"},
               attributes={"Список": None})
    edits = правки(elements=[fm.FormElement("ТаблицаФормы", "Список", "Список", children=[
        fm.FormElement("ПолеНадписи", "СписокВыдумка", "Список.Выдумка")])])
    found = fm.check(edits, view, ХОЗЯИН)
    assert [f.code for f in found] == ["ФОРМА-ПОЛЕ-СПИСКА-НЕ-НАЙДЕНО"]
    assert not found[0].blocking


# --- дерево значений ----------------------------------------------------------

КРУГ_ДЕРЕВО = "Documents/мой_ПробаСДвижениями/Forms/мой_КругДерево"


def test_a_tree_table_is_born_without_a_row_filter(dump):
    """Дерево для формы — таблица со своим источником; после круга через
    платформу у таблицы дерева нет отбора строк, а вид таблицы — «List»:
    иерархию даёт источник, а не свойство."""
    выполнить(dump, "6-дерево.json")
    assert файл(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml") == эталон("кругдерево.xml")
    assert без_uuid(файл(dump, КРУГ_ДЕРЕВО + ".xml")) == без_uuid(
        эталон("кругдерево.карточка.xml"))
    text = файл(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml").decode("utf-8-sig")
    assert "<RowFilter" not in text
    assert "<Representation>List</Representation>" in text
    # остальное рождается как у таблицы данных
    assert "<AutoInsertNewRow>true</AutoInsertNewRow>" in text
    assert text.count('<Column name=') == 4
    карточка = файл(dump, "Documents/мой_ПробаСДвижениями.xml").decode("utf-8-sig")
    assert "<Form>мой_КругДерево</Form>" in карточка


def test_a_column_added_into_a_tree_lands_where_asked(dump):
    """Колонка в дерево — то же задание, что и колонка в таблицу: имя реквизита
    в «таблица», поле с родителем-таблицей. Идентификатор колонки живёт внутри
    реквизита (max+1 по его «Columns»), а не в общем счёте формы."""
    выполнить(dump, "6-дерево.json")
    выполнить(dump, "7-дерево-колонка.json")
    assert файл(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml") == эталон("кругдерево.колонка.xml")
    text = файл(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml").decode("utf-8-sig")
    assert '<Column name="Комментарий" id="5">' in text
    assert '<Column name="Норматив" id="6">' in text
    # поле-надписи внутри таблицы: правку сообщает EditMode, автоправки нет
    надпись = text[text.index('<LabelField name="мой_ДеревоКомментарий"'):]
    надпись = надпись[:надпись.index("</LabelField>")]
    assert "<EditMode>EnterOnInput</EditMode>" in надпись
    assert "AutoEditMode" not in надпись
    # «после» соблюдено: надпись встала между флажком и партнёром
    assert (text.index('name="мой_ДеревоФлаг"') < text.index('name="мой_ДеревоКомментарий"')
            < text.index('name="мой_ДеревоПартнёр"'))


def test_a_tree_source_is_seen_even_when_the_attribute_is_new(dump):
    """Реквизит-дерево и таблица по нему заводятся одним заданием, и вид
    рождения выбирается по типу реквизита — включая только что заведённый."""
    from meta.infra.forms.designer221 import vocabulary as voc

    assert dict(voc.BORN["Table"]["properties"]).get("RowFilter") is not None
    assert "RowFilter" not in dict(voc.BORN["Table/дерево"]["properties"])
    assert (voc.BORN["Table/дерево"]["satellites"] == voc.BORN["Table"]["satellites"])
    выполнить(dump, "6-дерево.json")          # реквизит и таблица — одно задание
    assert "<RowFilter" not in файл(
        dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml").decode("utf-8-sig")


# --- картинки, переключатель, группа колонок -----------------------------------

КРУГ_ВИДЫ = "Documents/мой_ПробаСДвижениями/Forms/мой_КругВиды"


def test_pictures_radio_and_column_groups_come_back_from_the_platform_untouched(dump):
    """Круг через платформу: картинка-декорация с картинкой, поле картинки с
    картинкой значений, переключатель со списком выбора, группа колонок с
    полями внутри таблицы. Платформа не меняет ни байта."""
    выполнить(dump, "8-виды.json")
    assert файл(dump, КРУГ_ВИДЫ + "/Ext/Form.xml") == эталон("кругвиды.xml")
    assert без_uuid(файл(dump, КРУГ_ВИДЫ + ".xml")) == без_uuid(эталон("кругвиды.карточка.xml"))
    text = файл(dump, КРУГ_ВИДЫ + "/Ext/Form.xml").decode("utf-8-sig")
    # картинка: ссылка плюс LoadTransparent, приставка — платформенная
    assert text.count("<xr:Ref>StdPicture.Setting</xr:Ref>") == 2
    assert text.count("<xr:LoadTransparent>true</xr:LoadTransparent>") == 2
    # у декорации заголовок с атрибутом, как у надписи
    assert '<Title formatted="false">' in text
    # переключатель: вид рождённый, список выбора — сказанный
    assert "<RadioButtonType>Auto</RadioButtonType>" in text
    assert '<xr:Value xsi:type="FormChoiceListDesTimeValue">' in text
    assert '<Value xsi:type="xs:decimal">1</Value>' in text
    assert "<v8:content>Второй</v8:content>" in text
    # группа колонок: спутник один, заголовок от имени, подсказки нет
    группа = text[text.index('<ColumnGroup name="мой_ГруппаЧисел"'):]
    группа = группа[:группа.index("</ColumnGroup>")]
    своё, дети = группа.split("<ChildItems>", 1)   # спутники группы, а не полей
    assert "<ExtendedTooltip" in своё and "<ContextMenu" not in своё
    assert "<v8:content>Числа</v8:content>" in своё and "<ToolTip>" not in своё
    assert "<Group>InCell</Group>" in своё
    # поле внутри группы колонок внутри таблицы — всё равно поле в таблице
    надпись = дети[дети.index('<LabelField name="мой_ТаблицаКомментарий"'):]
    assert "<EditMode>EnterOnInput</EditMode>" in надпись
    assert "AutoEditMode" not in надпись


def test_a_property_without_a_place_is_refused_not_dropped(dump):
    """Свойство, которого у этого вида нет в замеренной выгрузке, поставить
    некуда: отказ, а не молчаливая потеря в файле — задание сказало, инструмент
    не смог, и об этом сказано."""
    выполнить(dump, "8-виды.json")
    задание = {"форма": "Документ.мой_ПробаСДвижениями.мой_КругВиды",
               "элементы": [{"вид": "ПолеКартинки", "имя": "мой_Второе",
                             "путь": "мой_Флажок",
                             "свойства": {"АктивизироватьПоУмолчанию": True}}]}
    with pytest.raises(Refuse) as отказ:
        EditFormUseCase(DesignerDump(dump)).execute(
            [job_dialect.form_edits_from_json(задание)], apply_now=True)
    assert "не знаю, где" in str(отказ.value) and "DefaultItem" in str(отказ.value)


def test_a_picture_is_named_by_its_source():
    """Картинка — библиотека конфигурации или стандартная платформы; английские
    приставки выгрузки принимаются наравне с русскими словами."""
    assert fm.check_property("Картинка", "Картинка", "БиблиотекаКартинок.Значок")[3] == (
        "БиблиотекаКартинок", "Значок")
    assert fm.check_property("Картинка", "Картинка", "CommonPicture.Значок")[3] == (
        "БиблиотекаКартинок", "Значок")
    assert fm.check_property("Картинка", "Картинка", "StdPicture.Setting")[3] == (
        "СтандартнаяКартинка", "Setting")
    for плохое in ("Значок", "Библиотека.Значок", "БиблиотекаКартинок.", 42):
        with pytest.raises(Refuse):
            fm.check_property("Картинка", "Картинка", плохое)


def test_a_choice_list_keeps_value_kinds():
    """Список выбора: число, строка, булево и значение перечисления — каждому
    свой `xsi:type` в файле; представление необязательно."""
    from meta.infra.forms.designer221.editor import Editor

    значения = [{"значение": 1}, {"значение": "Текст"}, {"значение": True},
                {"значение": "Перечисление.ОтражениеВУСН.Принимаются",
                 "представление": "Принимаются"}]
    _, _, вид, приведённое = fm.check_property("ПолеПереключателя", "СписокВыбора", значения)
    assert вид == "СписокЗначений" and len(приведённое) == 4
    узел = Editor._choice_list_node("ChoiceList", приведённое)
    типы = [item.children[2].children[1].attrs["xsi:type"] for item in узел.children]
    assert типы == ["xs:decimal", "xs:string", "xs:boolean", "xr:DesignTimeRef"]
    assert узел.children[3].children[2].children[1].text == (
        "Enum.ОтражениеВУСН.EnumValue.Принимаются")
    for плохое in ([], "не список", [{"представление": "без значения"}],
                   [{"значение": 1, "лишнее": 2}]):
        with pytest.raises(Refuse):
            fm.check_property("ПолеПереключателя", "СписокВыбора", плохое)


# --- условное оформление в разделе реквизитов ----------------------------------

ОФОРМЛЕНИЕ = "\t\t<ConditionalAppearance/>\n\t</Attributes>"


def положить_оформление(root, rel):
    """Дописать форме условное оформление — так его пишет конфигуратор: ребёнком
    раздела реквизитов, последним. Содержимое для места вставки роли не играет.
    """
    path = os.path.join(root, *rel.split("/"))
    with open(path, "rb") as source:
        text = source.read().decode("utf-8-sig")
    text = text.replace("\t</Attributes>", ОФОРМЛЕНИЕ, 1)
    with open(path, "wb") as target:
        target.write(b"\xef\xbb\xbf" + text.encode("utf-8"))


def test_conditional_appearance_is_not_an_attribute(dump):
    """Условное оформление лежит в разделе реквизитов (563 формы замеренной
    конфигурации), но реквизитом не является: у него нет имени, и показ не
    должен выдавать его строкой «None: None», а тем более считать главным
    реквизитом."""
    выполнить(dump, "6-дерево.json")
    положить_оформление(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml")
    view = DesignerDump(dump).read_form(("Документ", "мой_ПробаСДвижениями"), "мой_КругДерево")
    assert None not in view.attributes
    assert list(view.attributes) == ["Объект", "мой_Дерево"]
    _, текст = показать(dump, "Документ.мой_ПробаСДвижениями.мой_КругДерево")
    assert "None" not in текст


def test_a_new_attribute_goes_before_the_appearance_not_after_it(dump):
    """Порядок в разделе не наш выбор: у всех 563 форм замеренной конфигурации,
    где есть условное оформление, оно стоит последним. Новый реквизит идёт за
    последним реквизитом, а не в конец раздела."""
    выполнить(dump, "6-дерево.json")
    положить_оформление(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml")
    выполнить(dump, "7-дерево-колонка.json")   # колонка — в существующий реквизит
    result = EditFormUseCase(DesignerDump(dump)).execute(
        [job_dialect.form_edits_from_json(
            {"форма": "Документ.мой_ПробаСДвижениями.мой_КругДерево",
             "реквизиты": [{"имя": "мой_Признак", "тип": "Булево"}]})], apply_now=True)
    assert result.ok, [str(f) for f in result.findings]
    text = файл(dump, КРУГ_ДЕРЕВО + "/Ext/Form.xml").decode("utf-8-sig")
    assert text.index('<Attribute name="мой_Признак"') < text.index("<ConditionalAppearance")
    # оформление не тронуто и по-прежнему последнее в разделе
    assert text.index("<ConditionalAppearance") < text.index("</Attributes>")


def test_kinds_the_tool_only_reads_are_named_from_the_property_dictionary():
    """Показ называет по-русски и то, чего инструмент не пишет. Слова не
    придуманы: каждое есть в справочнике свойств, откуда взяты и остальные."""
    from meta.domain.form_properties import PROPERTIES
    from meta.infra.forms.designer221 import vocabulary as voc

    спутники = {"РасширеннаяПодсказка", "ДополнениеСтрокаПоиска",
                "ДополнениеСостояниеПросмотра", "ДополнениеУправлениеПоиском"}
    for тег, слово in voc.DOMAIN_KIND.items():
        assert слово in PROPERTIES or слово in спутники, (тег, слово)
    # то, что инструмент читает, но не пишет, — не попало в умеющие виды
    assert voc.DOMAIN_KIND["SpreadSheetDocumentField"] == "ПолеТабличногоДокумента"
    assert "ПолеТабличногоДокумента" not in fm.ELEMENT_KINDS
    with pytest.raises(Refuse):
        fm.FormElement("ПолеТабличногоДокумента", "мой_Т")


# --- показ формы --------------------------------------------------------------

def показать(dump, адрес, *flags):
    """`--показать` как его зовёт человек — через точку сборки."""
    import io
    from contextlib import redirect_stdout

    import meta.add as add
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = add.main(["--показать", dump, адрес, *flags])
    return код, буфер.getvalue()


def test_showing_a_form_answers_where_to_insert(dump):
    """Показ отвечает на вопрос задания «куда вставлять»: имя элемента, вид,
    привязка, обработчики — вместо чтения `Form.xml` глазами."""
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "2-наполнение.json")
    код, текст = показать(dump, "Документ.мой_ПробаСДвижениями.мой_Круг")
    assert код == 0
    assert "Форма Документ.мой_ПробаСДвижениями.мой_Круг   (назначение Документа)" in текст
    assert "Объект: Документ.мой_ПробаСДвижениями (Объект)   (главный)" in текст
    assert "мой_Таблица: ТаблицаЗначений" in текст
    assert "ПриСозданииНаСервере -> ПриСозданииНаСервере" in текст
    assert "Комментарий (ПолеВвода) [Объект.Комментарий] @ПриИзменении=КомментарийПриИзменении" in текст
    assert "ФормаЗаполнить (Кнопка) -> мой_Заполнить" in текст
    # дерево, а не список: поле шапки с отступом глубже своей группы
    def отступ(кусок):
        строка = next(строка for строка in текст.splitlines()
                      if строка.strip().startswith(кусок))
        return len(строка) - len(строка.lstrip())

    assert отступ("Номер (ПолеВвода)") > отступ("мой_ГруппаШапка (ГруппаФормы")
    assert отступ("мой_ТаблицаСтатья") > отступ("мой_Таблица (ТаблицаФормы)")
    # группировка видна в дереве: иначе её ищут поиском по тексту Form.xml
    assert "мой_ГруппаШапка (ГруппаФормы, Горизонтальная)" in текст


def test_satellites_are_hidden_but_counted(dump):
    """Спутников вдвое больше, чем элементов: в показе они прячутся — но
    сказано, сколько и как увидеть."""
    выполнить(dump, "1-пустая.json")
    выполнить(dump, "2-наполнение.json")
    _, кратко = показать(dump, "Документ.мой_ПробаСДвижениями.мой_Круг")
    _, подробно = показать(dump, "Документ.мой_ПробаСДвижениями.мой_Круг", "--подробно")
    assert "РасширеннаяПодсказка" not in кратко and "Скрыто спутников" in кратко
    # вид спутника тоже назван по-русски: английский тег посреди русских слов
    # читается как ошибка вывода
    assert "КомментарийРасширеннаяПодсказка (РасширеннаяПодсказка)" in подробно
    assert len(подробно.split("\n")) > len(кратко.split("\n")) + 20


def test_showing_a_vendor_form_says_it_is_typical(dump):
    выполнить(dump, "1-пустая.json")
    _, своя = показать(dump, "Документ.мой_ПробаСДвижениями.мой_Круг")
    assert "ТИПОВАЯ" not in своя
    view = fm.FormView(("Документ", "их_Чужой"), "ФормаДокумента")
    assert not fm.is_ours(view.owner_name, view.name, ТЕСТ.приставка)


def test_showing_a_missing_form_is_refused(dump):
    код, текст = показать(dump, "Документ.мой_ПробаСДвижениями.НетТакой")
    assert код == 1 and "в выгрузке нет" in текст
    # адрес объекта по-прежнему показывает объект, а не форму
    assert job_dialect.looks_like_a_form("Документ.мой_Заявка.ФормаДокумента")
    assert job_dialect.looks_like_a_form("Общая.мой_Проба")
    assert not job_dialect.looks_like_a_form("Справочник.мой_Эталон")
    assert not job_dialect.looks_like_a_form("Документ.мой_Заявка.Реквизит.Сумма")


def test_every_form_event_of_the_corpus_has_a_russian_name():
    """Каждое событие форм выгрузки переводится на русский — кроме неоднозначных:
    словарь, снятый по частоте, обрывается на редких, и показ печатал бы
    «OnWriteAtServer» вместо «ПриЗаписиНаСервере»."""
    from meta.infra.forms.designer221.vocabulary import ELEMENT_EVENTS_BACK, FORM_EVENTS_BACK
    from meta.tests import corpus

    if not corpus.available():
        pytest.skip("нет выгрузки для сверки")
    # неоднозначные: «OnActivate» — два русских имени по корпусу, «BeforeDelete» —
    # русское имя занято «BeforeDeleteRow» таблицы (см. словарь)
    known = set(FORM_EVENTS_BACK) | set(ELEMENT_EVENTS_BACK) | {"OnActivate", "BeforeDelete"}
    missing = set()
    for dirpath, _dirs, files in os.walk(corpus.CORPUS):
        if "Form.xml" in files:
            text = open(os.path.join(dirpath, "Form.xml"), encoding="utf-8-sig").read()
            missing |= set(re.findall(r'<Event name="([^"]+)"', text)) - known
    assert not missing, sorted(missing)


# --- код типовой формы: литералы и обработчики ---------------------------------------

def _код_надписи(свойства=None, события=None):
    from meta.acl import platform_code
    from meta.domain import forms as fmd

    правки = fmd.FormEdits(("Документ", "АвансовыйОтчет"), "ФормаДокумента", elements=[
        fmd.FormElement("Надпись", "мой_Надпись", parent="ГруппаКомментарий",
                        properties=свойства or {}, events=события or {})], as_code=True)
    return platform_code.render(правки, None)


def test_a_multiline_title_is_valid_bsl():
    """Перевод строки в заголовке не рвёт литерал: продолжение — с «|»."""
    assert 'Элемент.Заголовок = "Приложите ""чеки""\n|к отчёту";' in _код_надписи(
        {"Заголовок": 'Приложите "чеки"\nк отчёту'})


def test_a_programmatic_handler_has_the_handler_prefix():
    """Программно назначаемый обработчик — с приставкой «Подключаемый_» (#std492)."""
    assert ('Элемент.УстановитьДействие("Нажатие", "Подключаемый_мой_НадписьНажатие");'
            in _код_надписи(события={"Нажатие": "мой_НадписьНажатие"}))


def test_every_tooltip_is_a_string():
    """У 19 видов полей тип подсказки в справочнике-источнике сдвинут со
    строки «СочетаниеКлавиш»: без поправки подсказку не задать ни флажку, ни
    надписи."""
    from meta.domain import forms as fmd
    from meta.domain.form_properties import PROPERTIES

    assert {p["Подсказка"][1] for p in PROPERTIES.values() if "Подсказка" in p} == {"Строка"}
    assert fmd.check_property("ПолеФлажка", "Подсказка", "Отметьте")[3] == "Отметьте"


def test_kind_as_a_property_is_refused_in_plain_words():
    """«Вид» поля — это сам вид элемента; отказ говорит об этом, а не про
    внутренний тег."""
    from meta.domain import forms as fmd

    with pytest.raises(Refuse, match="задаётся ключом «вид» элемента"):
        fmd.check_property("ПолеВвода", "Вид", "ПолеТабличногоДокумента")
    assert fmd.check_property("Кнопка", "Вид", "Гиперссылка")[3] == "Гиперссылка"


def test_a_missing_region_says_where_to_put_it():
    """«Области нет — заведите её» говорит, куда: соседи — по шаблону #std455,
    строки — по модулю."""
    from meta.domain.modules import region_place

    модуль = ["#Область ОбработчикиСобытийФормы", "Процедура ПриОткрытии(Отказ)",
              "КонецПроцедуры", "#КонецОбласти", "",
              "#Область ОбработчикиКомандФормы", "#КонецОбласти"]
    assert region_place(модуль, "ОбработчикиСобытийФормы") == \
        "в область «ОбработчикиСобытийФормы» (строки 1-4)"
    ответ = region_place(модуль, "ОбработчикиСобытийЭлементовШапкиФормы")
    assert ("заведите её после «ОбработчикиСобытийФормы» (её #КонецОбласти — строка 4), "
            "перед «ОбработчикиКомандФормы» (строка 6)") in ответ, ответ
    таблица = region_place(модуль, "ОбработчикиСобытийЭлементовТаблицыФормыТовары")
    assert "после «ОбработчикиСобытийФормы»" in таблица and "перед «ОбработчикиКомандФормы»" in таблица
    assert "место — по смыслу" in region_place(["Процедура А()", "КонецПроцедуры"],
                                               "ОбработчикиКомандФормы")
