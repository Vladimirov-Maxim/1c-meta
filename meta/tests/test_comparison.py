"""Формат выгрузки, подписка, кнопки и колонки новой формы — каждый случай со своей фикстурой.

Выгрузку чужого формата инструмент не пишет вовсе. Правка подписки проверяет
сигнатуру обработчика, а источник, заданный одной строкой, проверяется, а не
роняет проверку трассировкой. Кнопка встаёт в командную панель формы или
таблицы, которые заводит то же задание. Колонка, названная с именем таблицы
впереди, получает предупреждение, а не двойное имя молча.
"""

import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны", "формы")
DOCUMENT = "мой_ПробаСДвижениями"


def dump_dir(tmp_path, version=None):
    """Выгрузка конфигуратора с двумя документами; `версия` — подменить формат."""
    root = tmp_path / "cf"
    for name, reference_node in (("Configuration.xml", "Configuration.xml"),
                        (f"Documents/{DOCUMENT}.xml", f"{DOCUMENT}.до.xml"),
                        ("Documents/мой_ПробаНепроводимый.xml", "мой_ПробаНепроводимый.до.xml")):
        path = root.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(GOLDEN, reference_node), path)
    if version:
        registry = root / "Configuration.xml"
        raw_material = registry.read_bytes()
        assert b'version="2.21"' in raw_material
        registry.write_bytes(raw_material.replace(b'version="2.21"', f'version="{version}"'.encode(), 1))
    return root


def job_spec(tmp_path, data, name="job.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def snapshot(root):
    return {path: open(path, "rb").read()
            for path in (os.path.join(folder, name) for folder, _, names in os.walk(root)
                         for name in names)}


# --- запись не своего формата -----------------------------------------------


@pytest.mark.parametrize("operation", [
    {"objects": [{"вид": "Справочник", "поля": {"имя": "мой_Проба", "синоним": "Проба"}}]},
    {"forms": [{"форма": f"Документ.{DOCUMENT}.мой_Проба",
                "создать": {"назначение": "Документа", "синоним": "Проба"}}]},
    {"changes": [{"путь": f"Документ.{DOCUMENT}", "поля": {"комментарий": "проба"}}]},
])
def test_a_dump_of_another_format_is_not_written(tmp_path, operation):
    """Карточки 2.21 в выгрузке 8.3.27 (формат 2.20) платформа не загрузит:
    «Неизвестная версия формата 2.21». Поэтому — отказ до записи, и на диске
    не меняется ни байта."""
    root = dump_dir(tmp_path, "2.20")
    before_ = snapshot(root)
    with pytest.raises(Refuse, match="выгрузка формата 2.20, а инструмент пишет формат 2.21"):
        main(["--apply", job_spec(tmp_path, dict(operation, repo=str(root)))])
    assert snapshot(root) == before_


def test_the_own_format_is_written(tmp_path):
    """Тот же отказ не должен задевать свой формат: эталон — 2.21."""
    root = dump_dir(tmp_path)
    data = {"repo": str(root), "objects": [
        {"вид": "Справочник", "поля": {"имя": "мой_Проба", "синоним": "Проба"}}]}
    assert main(["--apply", job_spec(tmp_path, data)]) == 0
    assert (root / "Catalogs" / "мой_Проба.xml").is_file()


def test_the_version_is_the_roots_not_the_declarations(tmp_path):
    """У объявления XML свой `version="1.0"`: версия формата — атрибут корня."""
    from meta.infra.designer import DesignerDump

    assert DesignerDump(str(dump_dir(tmp_path))).format_version() == "2.21"
    assert DesignerDump(str(dump_dir(tmp_path / "старая", "2.20"))).format_version() == "2.20"


def test_code_is_edited_in_a_dump_of_any_format(tmp_path):
    """Текст модуля от формата выгрузки не зависит — правка вставками идёт."""
    root = dump_dir(tmp_path, "2.20")
    module = root / "Documents" / DOCUMENT / "Ext" / "ObjectModule.bsl"
    module.parent.mkdir(parents=True)
    module.write_bytes("﻿Процедура Проба()\r\n\tВозврат;\r\nКонецПроцедуры\r\n".encode())
    data = {"repo": str(root), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
              "modules": [{"модуль": f"Документ.{DOCUMENT}.МодульОбъекта",
                           "edits": [{"line": 2, "lines": 0, "code": "\tА = 1;"}]}]}
    assert main(["--apply", job_spec(tmp_path, data)]) == 0
    assert "\tА = 1;" in module.read_text(encoding="utf-8-sig")


# --- подписка: сигнатура обработчика --------------------------------------------


def with_subscription(tmp_path):
    """Справочник, модуль с обработчиком документа (четыре параметра) и
    подписка документа на него — исправная, без замечаний."""
    root = dump_dir(tmp_path)
    objects = {"repo": str(root), "objects": [
        {"вид": "Справочник", "поля": {"имя": "мой_Партнеры", "синоним": "Партнеры"}},
        {"вид": "ОбщийМодуль", "поля": {
            "имя": "мой_ЗаявкиСервер", "синоним": "Заявки, сервер",
            "текст": "Процедура ЗаявкаПередЗаписью(Источник, Отказ, РежимЗаписи, РежимПроведения) "
                     "Экспорт\nКонецПроцедуры"}}]}
    assert main(["--apply", job_spec(tmp_path, objects, "1.json")]) == 0
    subscription = {"repo": str(root), "objects": [{"вид": "ПодпискаНаСобытие", "поля": {
        "имя": "мой_ЗаявкаПередЗаписью", "синоним": "Заявка перед записью",
        "источник": [{"вид": "Документ", "имя": DOCUMENT}], "событие": "ПередЗаписью",
        "обработчик": "мой_ЗаявкиСервер.ЗаявкаПередЗаписью"}}]}
    assert main(["--apply", job_spec(tmp_path, subscription, "2.json")]) == 0
    return root


def test_moving_the_source_checks_the_handler_signature(tmp_path, capsys):
    """Источник, переставленный с документа на справочник при обработчике с
    четырьмя параметрами, не проходит «замечаний нет»: правка проверяется
    вместе с событием и обработчиком, которые у подписки уже записаны."""
    root = with_subscription(tmp_path)
    capsys.readouterr()
    edit_job = {"repo": str(root), "changes": [{"путь": "ПодпискаНаСобытие.мой_ЗаявкаПередЗаписью",
                                              "поля": {"источник": "Справочник.мой_Партнеры"}}]}
    assert main([job_spec(tmp_path, edit_job, "3.json")]) == 0
    output = capsys.readouterr().out
    assert "ПОДПИСКА-СИГНАТУРА" in output and "параметров 4" in output and "принимает 2" in output


def test_a_change_of_unrelated_field_does_not_ask_about_the_rest(tmp_path, capsys):
    """Правка комментария об источнике и обработчике не спрашивает."""
    root = with_subscription(tmp_path)
    capsys.readouterr()
    edit_job = {"repo": str(root), "changes": [{"путь": "ПодпискаНаСобытие.мой_ЗаявкаПередЗаписью",
                                              "поля": {"комментарий": "проба"}}]}
    assert main([job_spec(tmp_path, edit_job, "3.json")]) == 0
    assert "ПОДПИСКА-" not in capsys.readouterr().out


@pytest.mark.parametrize("source", ["Справочник.мой_Партнеры", "Справочник.мой_Партнеры (Объект)"])
def test_a_single_source_without_a_list_is_checked_not_crashed(tmp_path, capsys, source):
    """Одно обозначение строкой — так источник печатает показ — проверяется,
    как и список, а не падает с `TypeError: object of type 'TypeRef' has no len()`."""
    root = with_subscription(tmp_path)
    capsys.readouterr()
    data = {"repo": str(root), "objects": [{"вид": "ПодпискаНаСобытие", "поля": {
        "имя": "мой_ПартнерыПередЗаписью", "синоним": "Партнеры перед записью",
        "источник": source, "событие": "ПередЗаписью",
        "обработчик": "мой_ЗаявкиСервер.ЗаявкаПередЗаписью"}}]}
    assert main([job_spec(tmp_path, data, "3.json")]) == 0
    output = capsys.readouterr().out
    assert "ПОДПИСКА-СИГНАТУРА" in output and "Справочник.мой_Партнеры (Объект)" in output


# --- форма: кнопки в командных панелях, рождённых тем же заданием -------------


def test_buttons_go_to_the_command_bars_born_by_the_same_job(tmp_path, capsys):
    """Кнопка в «ФормаКоманднаяПанель» прямо в задании, которое форму создаёт
    (так её показывает README), встаёт на место, а не получает «родителя нет».
    Так же и кнопка в панели таблицы, заводимой тем же заданием."""
    root = dump_dir(tmp_path)
    data = {"repo": str(root), "forms": [{
        "форма": f"Документ.{DOCUMENT}.мой_Проба",
        "создать": {"назначение": "Документа", "синоним": "Проба"},
        "реквизиты": [{"имя": "мой_Строки", "тип": "ТаблицаЗначений",
                       "колонки": [{"имя": "Статья", "тип": "Строка(100)"}]}],
        "команды": [{"имя": "мой_Заполнить", "заголовок": "Заполнить"}],
        "элементы": [
            {"вид": "ТаблицаФормы", "имя": "мой_Строки", "путь": "мой_Строки",
             "колонки": [{"имя": "Статья"}]},
            {"вид": "Кнопка", "имя": "ФормаЗаполнить", "команда": "мой_Заполнить",
             "родитель": "ФормаКоманднаяПанель"},
            {"вид": "Кнопка", "имя": "мой_СтрокиЗаполнить", "команда": "мой_Заполнить",
             "родитель": "мой_СтрокиКоманднаяПанель"}]}]}
    assert main(["--apply", job_spec(tmp_path, data)]) == 0
    assert "ФОРМА-РОДИТЕЛЬ-НЕТ" not in capsys.readouterr().out
    form = (root / "Documents" / DOCUMENT / "Forms" / "мой_Проба" / "Ext" / "Form.xml").read_text(
        encoding="utf-8-sig")
    form_bar = form[form.index('<AutoCommandBar name="ФормаКоманднаяПанель"'):]
    assert form_bar.index('<Button name="ФормаЗаполнить"') < form_bar.index("</AutoCommandBar>")
    table_bar = form[form.index('<AutoCommandBar name="мой_СтрокиКоманднаяПанель"'):]
    assert (table_bar.index('<Button name="мой_СтрокиЗаполнить"')
            < table_bar.index("</AutoCommandBar>"))


def test_a_column_named_with_its_table_is_warned_about(tmp_path, capsys):
    """«имя» колонки — поле строки; полное имя элемента дало бы двойное имя молча."""
    root = dump_dir(tmp_path)
    data = {"repo": str(root), "forms": [{
        "форма": f"Документ.{DOCUMENT}.мой_Проба",
        "создать": {"назначение": "Документа", "синоним": "Проба"},
        "реквизиты": [{"имя": "мой_Строки", "тип": "ТаблицаЗначений",
                       "колонки": [{"имя": "Статья", "тип": "Строка(100)"}]}],
        "элементы": [{"вид": "ТаблицаФормы", "имя": "мой_Строки", "путь": "мой_Строки",
                      "колонки": [{"имя": "мой_СтрокиСтатья"}]}]}]}
    assert main([job_spec(tmp_path, data)]) == 0
    output = capsys.readouterr().out
    assert "ФОРМА-КОЛОНКА-ИМЯ" in output and "«Статья»" in output and "мой_Строкимой_СтрокиСтатья" in output


def test_the_button_reference_names_where_buttons_go():
    """Справка по кнопке называет, куда её класть: панель формы и панель таблицы."""
    from meta.report.forms import element_properties

    text = "\n".join(element_properties("Кнопка"))
    assert "«ФормаКоманднаяПанель»" in text and "«<Таблица>КоманднаяПанель»" in text
