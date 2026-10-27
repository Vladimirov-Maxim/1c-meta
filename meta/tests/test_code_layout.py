# ruff: noqa: F811 — фикстура `репо` взята из test_code и принимается параметром
"""Раскладка вставок там, где шаблон с пустыми строками неуместен.

Текст запроса: метки — строки-комментарии
BSL вплотную к строкам литерала, пустая строка без `|` внутри литерала
недопустима — ни снаружи меток, ни внутри ИЗМЕНЕН.

Смена сигнатуры: ИЗМЕНЕН оборачивает только объявление —
метка вплотную под описанием метода (пустая строка отрывала бы описание),
внутри вставки и под закрывающей меткой пустых строк нет (они оказались
бы в теле метода). Проверка правок записанное принимает без находок.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta import add  # noqa: E402

from .test_code import VENDOR_MODULE, edit_job, read_file, repo_dir, run, single_one  # noqa: E402,F401

OPENED = "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Петров Петр #TASK-1"
CHANGED = "// {[*](фрагмент ИЗМЕНЕН), 31.08.2026, #TEAM Петров Петр #TASK-1"
CLOSED = "// } Петров Петр, 31.08.2026"

QUERY = ["Функция Данные()", "\tЗапрос = Новый Запрос;", "\tЗапрос.Текст =", "\t\"ВЫБРАТЬ",
          "\t|\tТ.Номер,", "\t|\tТ.Сумма", "\t|ИЗ", "\t|\tДокумент.Т КАК Т\";", "\tВозврат Запрос;",
          "КонецФункции"]

SIGNATURE_TEXT = ["// Выгружает данные.", "//", "// Параметры:", "//  Каталог - Строка - куда.", "//",
             "Функция Выгрузить(Каталог) Экспорт", "\t", "\tВозврат Каталог;", "", "КонецФункции"]


def findings(root):
    answer = os.path.join(os.path.dirname(root), "ответ.json")
    add.main(["--проверить", root, "--задача", "TASK-1", "--json", answer])
    return [f["код"] for f in json.load(open(answer, encoding="utf-8"))["находки"]]


def test_an_added_query_line_has_no_blank_lines_around_its_markers(repo_dir):
    root = repo_dir(QUERY)
    code, text = run(root, path=VENDOR_MODULE, edits=[edit_job(6, code="\t|\tТ.Дата,")])
    assert code == 0, text
    lines = read_file(root, VENDOR_MODULE)[0]
    assert lines[3:9] == ["\t\"ВЫБРАТЬ", "\t|\tТ.Номер,", "\t" + OPENED, "\t|\tТ.Дата,", "\t" + CLOSED,
                           "\t|\tТ.Сумма"]


def test_a_changed_query_line_has_no_blank_lines_inside_the_insertion(repo_dir):
    root = repo_dir(QUERY)
    code, text = run(root, path=VENDOR_MODULE, edits=[single_one("\t|\tТ.Сумма", "\t|\tТ.Сумма КАК Итого") | {"line": 6}])
    assert code == 0, text
    lines = read_file(root, VENDOR_MODULE)[0]
    assert lines[4:10] == ["\t|\tТ.Номер,", "\t" + CHANGED, "\t//|\tТ.Сумма", "\t|\tТ.Сумма КАК Итого",
                            "\t" + CLOSED, "\t|ИЗ"]


def test_a_signature_change_wraps_only_the_declaration_under_its_description(repo_dir):
    root = repo_dir(SIGNATURE_TEXT)
    code, text = run(root, path=VENDOR_MODULE, edits=[
        single_one("Функция Выгрузить(Каталог) Экспорт", "Функция Выгрузить(Каталог, Период = Неопределено) Экспорт")
        | {"line": 6}])
    assert code == 0, text
    lines = read_file(root, VENDOR_MODULE)[0]
    assert lines[4:10] == ["//", CHANGED, "//Функция Выгрузить(Каталог) Экспорт",
                            "Функция Выгрузить(Каталог, Период = Неопределено) Экспорт", CLOSED, "\t"]
    assert findings(root) == []


def test_a_continued_expression_does_not_warn_about_a_lost_tab():
    """Вызов с продолжением на следующих строках отступает глубже начала — это
    не потерянный таб; блок, начатый и законченный на разных уровнях, — да."""
    from meta.domain.edits import indent_warning
    assert indent_warning(["\tЗначение = ?(Строка = Неопределено,", "\t\tСтр.Статья,",
                           "\t\tСтрока.Статья);"], "\t") == ""
    assert "разных отступах" in indent_warning(["\tА = 1;", "\t\tБ = 2;"], "\t")
    assert indent_warning(["\tА = \"(\";  // (", "\t\tБ = 2;"], "\t")    # скобки в литерале не в счёт


def test_a_placeholder_in_a_comment_is_not_refused():
    from meta.domain.edits import placeholder
    assert placeholder("// Заменяет <ИмяНастройки> именем настройки.") is None
    assert placeholder("Вызвать(<Модуль>);") == "<Модуль>"


def test_a_new_method_without_markers_is_separated_from_its_neighbours(repo_dir):
    """Модуль, созданный задачей: метки не ставятся, но новый метод перед
    `#КонецОбласти`, стоящим вплотную к `КонецПроцедуры`, отделяется пустыми
    строками с обеих сторон."""
    import subprocess

    root = repo_dir(["#Область Служебные", "Процедура Старая()", "КонецПроцедуры", "#КонецОбласти"])
    # модуль «создан задачей»: в базовой ревизии его нет
    subprocess.run(["git", "-C", root, "rm", "-q", "--cached", VENDOR_MODULE], check=True)
    subprocess.run(["git", "-C", root, "commit", "-q", "-m", "без модуля"], check=True)
    code, text = run(root, path=VENDOR_MODULE, edits=[edit_job(4, code="Процедура Новая()\nКонецПроцедуры")])
    assert code == 0, text
    assert read_file(root, VENDOR_MODULE)[0] == ["#Область Служебные", "Процедура Старая()", "КонецПроцедуры", "",
                                               "Процедура Новая()", "КонецПроцедуры", "", "#КонецОбласти"]



def test_every_problem_of_one_edit_comes_at_once(repo_dir):
    """Беды одной правки — одним отказом: неверная последняя строка якоря и
    ёлочки в коде видны сразу, а не по кругу на каждую."""
    root = repo_dir(["Процедура Тест()", "\tЗначение = 1;", "\tДругое = 2;", "КонецПроцедуры"])
    code, text = run(root, apply=False, path=VENDOR_MODULE, edits=[
        edit_job(2, 2, "\tЗначение = 1;", "\tДругое = 3;", "\tА = «б»;")])
    assert code == 1 and "в правке бед 2" in text, text
    assert "кавычки-ёлочки" in text and "ожидалось" in text


ONE = "\t// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Петров Петр #TASK-1"
END = "\t// } Петров Петр, 31.08.2026"
TWO = ["Процедура Тест()", "\tЗначение = 1;", "", ONE, "\tЖурнал();", END, "", "\tДругое = 2;", "",
       ONE, "\tОстаётся();", END, "", "КонецПроцедуры"]


def test_one_own_insertion_is_reverted_by_its_line(repo_dir):
    """Требование сменилось: одна вставка задачи из двух снимается откатом по
    номеру её строки — вместе с разделителями, другая остаётся."""
    from .test_code import write_file
    root = repo_dir(["Процедура Тест()", "	Значение = 1;", "	Другое = 2;", "КонецПроцедуры"])
    write_file(root, VENDOR_MODULE, TWO)                    # обе вставки — правки задачи поверх базы
    code, text = run(root, path=VENDOR_MODULE, revert=5)
    assert code == 0, text
    assert read_file(root, VENDOR_MODULE)[0] == ["Процедура Тест()", "\tЗначение = 1;", "\tДругое = 2;", "",
                                               ONE, "\tОстаётся();", END, "", "КонецПроцедуры"]


def test_a_line_outside_own_insertions_is_refused_for_a_single_revert(repo_dir):
    root = repo_dir(TWO)
    code, text = run(root, path=VENDOR_MODULE, revert=8)
    assert code != 0 and "своей вставки задачи TASK-1 здесь нет" in text, text


def test_an_edit_touching_an_own_marker_is_refused(repo_dir):
    """Удаление своей вставки правкой с захватом соседней пустой строки дало бы
    блок УДАЛЕН с закомментированными своими метками — отказ с подсказкой."""
    root = repo_dir(TWO)
    code, text = run(root, apply=False, path=VENDOR_MODULE, edits=[
        edit_job(3, 4, "", END, "")])
    assert code != 0 and "задевает метку своей вставки" in text and "revert" in text, text
