"""Проверка правок задачи — правила домена, без диска и без git.

Каждое правило и ловит, и молчит на исправном: проверка, которая отчитывается
зелёным по чужому множеству строк, хуже отсутствующей. Кейсы: правка
вендорского модуля без метки, новый метод в своём модуле прошлой задачи, «Ё» и
отсутствие даты в метке, незакрытая вставка, вставка вокруг метода, закрытая
отдельной строкой, файл без BOM и в чужих переводах строк, строка, заменённая
на себя же с другими пробелами, новый объект без своей роли.

Главный кейс — последний: что записала правка вставками, проверка принимает
без находок по меткам. Запись и проверка — одно знание.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.domain import verification as v  # noqa: E402
from meta.domain.changes import (  # noqa: E402
    Hunk,
    changed_lines,
    hunks_between,
    pairs_by_content,
    pairs_by_position,
    whole_file,
)
from meta.domain.conventions import Conventions  # noqa: E402
from meta.domain.edits import Edit, Signature, edit_module  # noqa: E402

COMMAND = Conventions(prefix="мой_", other_prefixes=("ОМ_мой_",))
VENDOR = ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)", "\tЗначение = 1;",
          "КонецПроцедуры"]


def codes(findings):
    return sorted(f.code for f in findings)


def markers(old, new, task=None, path="Documents/Вендорский/Ext/ObjectModule.bsl"):
    return v.marker_findings(path, old, new, hunks_between(old, new), task)


# --- участки различий ---------------------------------------------------------------


def test_hunks_look_like_git_unified_zero():
    old = ["а", "б", "в"]
    assert hunks_between(old, ["а", "Б", "в"]) == [Hunk(2, 1, 2, 1)]
    assert hunks_between(old, ["а", "б", "x", "в"]) == [Hunk(2, 0, 3, 1)]
    assert hunks_between(old, ["а", "в"]) == [Hunk(2, 1, 1, 0)]
    assert whole_file(["а", "б"]) == [Hunk(0, 0, 1, 2)]


def test_a_line_with_the_same_text_is_not_a_change():
    """Так git показывает строку, у которой изменился лишь перевод строки в
    конце файла: «-#КонецЕсли / +#КонецЕсли»."""
    added, removed = changed_lines([Hunk(3, 1, 3, 1)], ["а", "б", "#КонецЕсли"], ["а", "б", "#КонецЕсли"])
    assert added == [] and removed == []


def test_pairs_by_position_and_by_content():
    assert pairs_by_position([Hunk(2, 2, 2, 2), Hunk(5, 1, 5, 0)]) == [(2, 2), (3, 3)]
    assert pairs_by_content(["а  ", "б"], ["x", "а", "б"]) == [(1, 2), (2, 3)]


# --- приставка ---------------------------------------------------------------------------


def test_a_new_object_without_the_team_prefix_is_found():
    found = v.prefix_findings([("CommonModules/ОМ_мой_Новый.xml", "ОбщийМодуль", "ОМ_мой_Новый"),
                               ("CommonModules/мой_Новый.xml", "ОбщийМодуль", "мой_Новый"),
                               ("CommonModules/ЧужойМодуль.xml", "ОбщийМодуль", "ЧужойМодуль")], COMMAND)
    assert [(f.code, f.path) for f in found] == [("МД-ПРЕФИКС", "CommonModules/ЧужойМодуль.xml")]
    assert "«ОбщийМодуль.ЧужойМодуль» без приставки «мой_»" in found[0].message


def test_without_a_prefix_convention_there_is_nothing_to_check():
    assert v.prefix_findings([("CommonModules/Любой.xml", "ОбщийМодуль", "Любой")], Conventions()) == []


# --- метки вставок ----------------------------------------------------------------------


def test_a_vendor_edit_without_a_marker_is_found():
    found = markers(VENDOR, [VENDOR[0], "\tЗначение = 42;", VENDOR[2]])
    assert codes(found) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]
    assert "добавленных вне вставок: 1 (стр. 2)" in found[0].message
    assert "удалённых без комментария в своей вставке: 1 (стр. 2 прежней версии)" in found[0].message
    assert found[0].line is None


def test_a_wrapped_edit_and_its_marker_are_accepted():
    new = [VENDOR[0], "\t// {[*](фрагмент ИЗМЕНЕН), 31.08.2026, #TEAM Автор #TASK-1", "\t",
           "\t//Значение = 1;", "\t", "\tЗначение = 2;", "\t", "\t// } Автор, 31.08.2026", VENDOR[2]]
    assert markers(VENDOR, new, task="TASK-1") == []


OWN = "\t// {[*](фрагмент ИЗМЕНЕН), 31.08.2026, #TEAM Автор #TASK-1"
OWN_END = "\t// } Автор, 31.08.2026"
FOREIGN = "\t// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, #TEAM Иванов #TASK-0"
FOREIGN_END = "\t// } Иванов, 01.01.2025"


def test_old_code_removed_inside_an_own_insertion_without_a_comment_is_found():
    """ИЗМЕНЕН с новым кодом, а прежняя строка удалена, не закомментирована.
    Такой же комментарий в другом методе её не сохраняет."""
    old = ["Процедура А()", "\tПроверить(Запись);", "\tЗначение = 1;", "КонецПроцедуры", "",
           "Процедура Б()", "\t//Проверить(Запись);", "КонецПроцедуры"]
    new = ["Процедура А()", OWN, "\tНовое();", OWN_END, "\tЗначение = 1;", "КонецПроцедуры", "",
           "Процедура Б()", "\t//Проверить(Запись);", "КонецПроцедуры"]
    found = markers(old, new, task="TASK-1")
    assert codes(found) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]
    assert "удалённых без комментария в своей вставке: 1 (стр. 2 прежней версии)" in found[0].message

    saved = new[:3] + ["\t//Проверить(Запись);"] + new[3:]
    assert markers(old, saved, task="TASK-1") == []


def test_old_code_moved_under_an_own_marker_with_another_indent_is_not_kept():
    """Под своей ИЗМЕНЕН прежняя строка перенесена внутрь нового условия с
    другим отступом, а не закомментирована, — следа правки нет."""
    old = ["Процедура А()", "\tШаг();", "КонецПроцедуры"]
    new = ["Процедура А()", OWN, "\tЕсли Условие Тогда", "\t\tШаг();", "\tКонецЕсли;", OWN_END,
           "КонецПроцедуры"]
    assert codes(markers(old, new, task="TASK-1")) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]


def test_a_whole_file_hunk_with_an_own_marker_does_not_remove_unchanged_lines():
    """Сменились переводы строк — git показывает весь файл одним участком; в
    нём и своя вставка. Строки, вернувшиеся тем же текстом, не удалены."""
    old = ["Процедура А()", FOREIGN, "\tЧужое();", FOREIGN_END, "\tШаг();", "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, "\tЧужое();", FOREIGN_END, OWN, "\t//Шаг();", "\tНовое();", OWN_END,
           "КонецПроцедуры"]
    from meta.domain.changes import Hunk as H
    found = v.marker_findings("М.bsl", old, new, [H(1, len(old), 1, len(new))], "TASK-1")
    assert not any("удалённых" in f.message for f in found), found


def test_a_removal_hunk_separated_from_its_insertion_by_a_blank_line_is_kept():
    """diff отдаёт удалённое объявление отдельным участком, а вставка с его
    комментарием начинается через пустую строку."""
    from meta.domain.changes import Hunk as H
    old = ["// Описание.", "Функция Ф(А) Экспорт", "\tВозврат А;", "КонецФункции"]
    new = ["// Описание.", "", OWN, "//Функция Ф(А) Экспорт", "Функция Ф(А, Б) Экспорт", OWN_END, "\tВозврат А;",
           "КонецФункции"]
    found = v.marker_findings("М.bsl", old, new, [H(2, 1, 1, 0), H(3, 0, 2, 5)], "TASK-1")
    assert not any("удалённых" in f.message for f in found), found


def test_an_insertion_starting_with_the_lines_that_follow_it_is_not_an_edit_outside():
    """Вставка в тексте запроса начинается парой разделителей, та же исходная
    пара стоит сразу за ней, а следом — своя ИЗМЕНЕН: diff относит исходную
    пару к добавленным вне вставки. Сняв свои вставки, получаем базу — правка
    вне вставок не найдена; настоящая правка вне вставки находится."""
    from meta.domain.changes import Hunk as H
    is_added = "\t// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1"
    old = ["\tТекст = \"", "\t|ВЫБРАТЬ 1", "\t|", "\t|////", "\t|ВЫБРАТЬ 2\";"]
    new = ["\tТекст = \"", "\t|ВЫБРАТЬ 1", is_added, "\t|", "\t|////", "\t|ВЫБРАТЬ 3", OWN_END,
           "\t|", "\t|////", OWN, "\t//|ВЫБРАТЬ 2\";", "\t|ВЫБРАТЬ 22\";", OWN_END]
    # так их сопоставил diff: исходная пара 3-4 — с первой парой вставки
    hunks = [H(2, 0, 3, 1), H(4, 0, 6, 4), H(5, 1, 10, 4)]
    assert "ПРАВКА-ВНЕ-ВСТАВКИ" not in codes(v.marker_findings("М.bsl", old, new, hunks, "TASK-1"))

    edited = [new[0], "\t|ВЫБРАТЬ 11"] + new[2:]
    hunks = [H(2, 1, 2, 2), H(4, 0, 6, 4), H(5, 1, 10, 4)]
    assert "ПРАВКА-ВНЕ-ВСТАВКИ" in codes(v.marker_findings("М.bsl", old, edited, hunks, "TASK-1"))


def test_another_tasks_insertion_removed_whole_is_an_edit_outside():
    """Чужая вставка удалена целиком вместе с метками, своей вставки УДАЛЕН нет:
    след прошлой задачи пропадает — ошибка, а не молчание."""
    old = ["Процедура А()", FOREIGN, "\tЧужое();", FOREIGN_END, "\tШаг();", "КонецПроцедуры"]
    new = ["Процедура А()", "\tШаг();", "КонецПроцедуры"]
    found = markers(old, new, task="TASK-1")
    assert codes(found) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]
    assert "удалена вставка другой задачи TASK-0 (стр. 2–4 прежней версии)" in found[0].message


def test_lines_removed_inside_another_tasks_insertion_are_a_warning():
    old = ["Процедура А()", FOREIGN, "\tЧужое();", "\tЕщё();", FOREIGN_END, "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, "\tЕщё();", FOREIGN_END, "КонецПроцедуры"]
    found = markers(old, new, task="TASK-1")
    assert codes(found) == ["ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ"]
    assert "внутри вставки другой задачи (TASK-0): удалено строк 1 (стр. 3 прежней версии)" in found[0].message


def test_another_tasks_insertion_removed_under_an_own_removed_marker_is_accepted():
    """Удаление чужой вставки своей УДАЛЕН — по правилам: находок нет."""
    removed_one = "// {[-](фрагмент УДАЛЕН), 31.08.2026, #TEAM Автор #TASK-1"
    old = ["Процедура А()", FOREIGN, "\tЧужое();", "\tЕщё();", FOREIGN_END, "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, removed_one, "\t//Чужое();", OWN_END, "\tЕщё();", FOREIGN_END,
           "КонецПроцедуры"]
    assert markers(old, new, task="TASK-1") == []


def test_an_own_insertion_rewriting_most_of_another_one_needs_an_outer_wrapper():
    """Своя ИЗМЕНЕН внутри чужой [+] заменяет две строки кода из трёх — чужая
    вставка фактически переписана: по правилу записи нужна обёртка снаружи."""
    old = ["Процедура А()", FOREIGN, "\tА();", "\tБ();", "\tВ();", FOREIGN_END, "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, OWN, "\t//А();", "\t//Б();", "\tНовое();", OWN_END, "\tВ();",
           FOREIGN_END, "КонецПроцедуры"]
    found = markers(old, new, task="TASK-1")
    assert codes(found) == ["ВСТАВКА-НУЖНА-ОБЁРТКА"]
    assert "заменяют 2 строк кода из 3" in found[0].message

    single_one = ["Процедура А()", FOREIGN, OWN, "\t//А();", "\tНовое();", OWN_END, "\tБ();", "\tВ();",
            FOREIGN_END, "КонецПроцедуры"]
    assert markers(old, single_one, task="TASK-1") == []


def test_an_unclosed_own_marker_inside_another_insertion_with_an_undated_close_is_found():
    """Чужая вставка закрыта меткой без даты; своя открывающая внутри неё без
    закрывающей. Разбор отдаёт чужую закрывающую нашей метке — находка всё
    равно на нашей открывающей."""
    foreign_without_date = "\t// } Иванов"
    old = ["Процедура А()", FOREIGN, "\tЧужое();", foreign_without_date, "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, OWN, "\tНовое();", "\tЧужое();", foreign_without_date, "КонецПроцедуры"]
    from meta.domain.changes import changed_lines
    added_count, _ = changed_lines(hunks_between(old, new), old, new)
    found = v.structure_findings("М.bsl", new, added_count, "TASK-1")
    assert [(f.code, f.line) for f in found] == [("ВСТАВКА-НЕ-ЗАКРЫТА", 3)]


def test_each_removed_line_needs_its_own_commented_copy():
    old = ["Процедура А()", "\tШаг();", "\tШаг();", "КонецПроцедуры"]
    new = ["Процедура А()", OWN, "\t//Шаг();", "\tНовое();", OWN_END, "КонецПроцедуры"]
    found = markers(old, new, task="TASK-1")
    assert codes(found) == ["ПРАВКА-ВНЕ-ВСТАВКИ"] and "удалённых без комментария в своей вставке: 1" \
        in found[0].message


def test_code_removed_under_an_own_marker_inside_another_tasks_insertion_must_be_kept():
    """Своя ИЗМЕНЕН внутри чужой вставки, а прежняя строка удалена физически:
    задача назвала правку изменением — прежнее должно быть в ней комментарием.
    Свою прежнюю вставку задача правит свободно."""
    old = ["Процедура А()", FOREIGN, "\tЧужое();", "\tЕщё();", FOREIGN_END, "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, OWN, "\tНовое();", OWN_END, "\tЕщё();", FOREIGN_END, "КонецПроцедуры"]
    found = markers(old, new, task="TASK-1")
    assert "ПРАВКА-ВНЕ-ВСТАВКИ" in codes(found)
    assert "удалённых без комментария в своей вставке: 1 (стр. 3 прежней версии)" in \
        [f for f in found if f.code == "ПРАВКА-ВНЕ-ВСТАВКИ"][0].message
    assert "ПРАВКА-ВНЕ-ВСТАВКИ" not in codes(markers(old, new, task="TASK-0"))


def test_an_edit_inside_another_tasks_insertion_without_an_own_marker_stays_a_warning():
    """Без своей метки правка в чужой вставке — предупреждение
    `ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ`, не ошибка «удалено без комментария»."""
    old = ["Процедура А()", FOREIGN, "\tЧужое();", FOREIGN_END, "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, "\tЧужое(1);", FOREIGN_END, "КонецПроцедуры"]
    assert codes(markers(old, new, task="TASK-1")) == ["ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ"]


def test_a_line_inside_another_tasks_insertion_with_only_whitespace_changed_is_not_removed():
    """Срезанные хвостовые пробелы у метки чужой вставки — смена пробелов, а не
    удалённый код: о ней судит своё правило."""
    old = ["Процедура А()", FOREIGN, "	Чужое();", FOREIGN_END + "		", "КонецПроцедуры"]
    new = ["Процедура А()", FOREIGN, "	Чужое();", FOREIGN_END, "КонецПроцедуры"]
    assert "ПРАВКА-ВНЕ-ВСТАВКИ" not in codes(markers(old, new, task="TASK-1"))


def test_a_marker_with_yo_or_without_date_is_found():
    def with_marker(marker):
        return [VENDOR[0], marker, "\tЗначение = 2;", "\t// } Автор", VENDOR[1], VENDOR[2]]

    yo = markers(VENDOR, with_marker("\t// {[*](фрагмент ИЗМЕНЁН), 31.08.2026, #TEAM Автор #TASK-1"))
    assert codes(yo) == ["ВСТАВКА-БУКВА-Ё"] and yo[0].line == 2
    without_date = markers(VENDOR, with_marker("\t// {[+](фрагмент ДОБАВЛЕН), #TEAM Автор #TASK-1"))
    assert codes(without_date) == ["ВСТАВКА-БЕЗ-ДАТЫ"]
    without_task = markers(VENDOR, with_marker("\t// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор"))
    assert codes(without_task) == ["ВСТАВКА-БЕЗ-ЗАДАЧИ"]
    without_type = markers(VENDOR, with_marker("\t// {[+](фрагмент), 31.08.2026, Автор #TASK-1"))
    assert codes(without_type) == ["ВСТАВКА-БЕЗ-ТИПА"]


def test_a_new_method_in_a_module_of_a_past_task_needs_a_marker():
    """Принадлежность модуля основанием не является: новый метод в своём модуле
    прошлой задачи оборачивается на общих основаниях."""
    old = ["Процедура ОбработкаПроведения(Отказ, РежимПроведения)", "\tЗначение = 1;", "КонецПроцедуры"]
    bare = old + ["", "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;", "КонецПроцедуры"]
    assert codes(markers(old, bare, path="Documents/мой_Наш/Ext/ObjectModule.bsl")) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]
    wrapped = old + ["", "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1",
                     "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;",
                     "КонецПроцедуры // } Автор, 31.08.2026"]
    assert markers(old, wrapped, path="Documents/мой_Наш/Ext/ObjectModule.bsl") == []


def test_a_removed_line_kept_as_a_comment_is_not_lost():
    new = [VENDOR[0], "\t// {[-](фрагмент УДАЛЕН), 31.08.2026, Автор #TASK-1", "\t//Значение = 1;",
           "\t// } Автор, 31.08.2026", VENDOR[2]]
    assert markers(VENDOR, new) == []


def test_region_directives_and_blank_lines_need_no_marker():
    new = [VENDOR[0], "", VENDOR[1], VENDOR[2], "", "#Область Новая", "#КонецОбласти"]
    assert markers(VENDOR, new) == []


def test_an_edit_inside_another_tasks_insertion_is_a_warning_with_the_task_given():
    old = [VENDOR[0], "\t// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, Автор #OLD-7", "\tА = 1;",
           "\t// } Автор, 01.01.2025", VENDOR[2]]
    new = old[:3] + ["\tБ = 2;"] + old[3:]
    assert markers(old, new) == []                       # без ИД задачи правило не проверяется
    found = markers(old, new, task="TASK-1")
    assert codes(found) == ["ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ"] and found[0].level == "предупреждение"
    assert "(OLD-7)" in found[0].message
    on_top = old[:3] + ["\t// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, Автор #TASK-1", "\tБ = 2;",
                        "\t// } Автор, 31.08.2026"] + old[3:]
    assert markers(old, on_top, task="TASK-1") == []


# --- незакрытая вставка и вставка вокруг метода ----------------------------------------------


def structure(new, old=VENDOR):
    added, _ = changed_lines(hunks_between(old, new), old, new)
    return v.structure_findings("Documents/Вендорский/Ext/ObjectModule.bsl", new, added)


def test_an_unclosed_insertion_and_a_method_closed_on_its_own_line_are_found():
    new = VENDOR + ["",
                    "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
                    "Процедура мой_Первый()", "\tЗначение = 2;", "КонецПроцедуры",
                    "// } Тест, 26.09.2026",
                    "",
                    "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
                    "Процедура мой_Второй()", "\tЗначение = 3;", "КонецПроцедуры"]
    found = structure(new)
    assert [(f.code, f.line) for f in found] == [("ВСТАВКА-НЕ-ЗАКРЫТА", 11),
                                                 ("ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ", 8)]
    assert "мой_Первый (метка на строке 5)" in found[1].message


def test_a_method_closed_on_its_end_is_accepted():
    new = VENDOR + ["", "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
                    "Процедура мой_Первый()", "\tЗначение = 2;", "КонецПроцедуры // } Тест, 26.09.2026"]
    assert structure(new) == []


def test_a_compilation_directive_belongs_to_the_method():
    """Подъём от объявления к метке не останавливается на директиве: иначе
    метод формы с меткой на отдельной строке прошёл бы незамеченным."""
    old = ["&НаСервере", "Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)",
           "\tЗначение = 1;", "КонецПроцедуры"]
    new = old + ["", "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1", "&НаКлиенте",
                 "Процедура мой_Третий(Команда)", "\tЗначение = 3;", "КонецПроцедуры",
                 "// } Тест, 26.09.2026"]
    found = structure(new, old)
    assert codes(found) == ["ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ"] and "мой_Третий" in found[0].message


def test_someone_elses_unclosed_marker_is_not_the_tasks():
    old = VENDOR + ["// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, Автор #OLD-7", "А = 1;"]
    new = old + ["Б = 2;"]
    assert structure(new, old) == []


# --- состав и формат --------------------------------------------------------------------------


def test_a_service_file_is_named():
    found = v.service_findings(["ConfigDumpInfo.xml"])
    assert codes(found) == ["ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ"] and found[0].path == "ConfigDumpInfo.xml"


def test_bom_and_line_endings():
    crlf = "﻿А\r\nБ\r\n".encode()
    assert v.format_findings("a.bsl", crlf, "CRLF") == []
    assert codes(v.format_findings("a.bsl", "А\r\nБ\r\n".encode(), "CRLF")) == ["ФАЙЛ-БЕЗ-BOM"]
    foreign = v.format_findings("a.bsl", "﻿А\nБ\n".encode(), "CRLF")
    assert codes(foreign) == ["ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"] and "LF, в репозитории приняты CRLF" in foreign[0].message
    assert v.format_findings("a.bsl", "﻿А\nБ\n".encode(), None) == []
    mixture = v.format_findings("a.bsl", "﻿А\r\nБ\n".encode(), "CRLF")
    assert codes(mixture) == ["ФАЙЛ-ПЕРЕВОДЫ-СМЕШАНЫ"] and mixture[0].level == "предупреждение"


def test_a_marker_wrapping_only_the_declaration_is_not_a_method_insertion():
    """Смена сигнатуры: метка ИЗМЕНЕН над описанием-комментарием не нужна,
    старое объявление комментарием, новое, закрывающая метка сразу за ним —
    не вставка вокруг метода, закрывать её на КонецФункции не нужно."""
    new = ["// Описание метода.", "// {[*](фрагмент ИЗМЕНЕН), 31.08.2026, #TEAM Автор #TASK-1",
           "//Функция Ф(А) Экспорт", "Функция Ф(А, Б) Экспорт", "// } Автор, 31.08.2026", "\tВозврат А;",
           "КонецФункции"]
    assert v.structure_findings("a.bsl", new, [2, 3, 4, 5]) == []

    around = ["// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1", "Функция Ф(А) Экспорт",
              "\tВозврат А;", "КонецФункции", "// } Автор, 31.08.2026"]
    assert codes(v.structure_findings("a.bsl", around, [1, 2, 3, 4, 5])) == ["ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ"]


def test_trailing_whitespace_lost_against_the_baseline():
    assert v.trailing_findings("a.bsl", b"\xd0\x90  \r\n\xd0\x91\r\n", b"\xd0\x90\r\n\xd0\x91\r\n") \
        and v.trailing_findings("a.bsl", b"\xd0\x90\r\n", b"\xd0\x90\r\n") == []


def test_a_line_replaced_by_itself_with_other_whitespace():
    old = ["Процедура А()", "\tЗначение = 1;  ", "\tДругое = 2;", "", "КонецПроцедуры"]
    new = ["Процедура А()", "\tЗначение = 1;", "\tДругое = 3;", "\t", "КонецПроцедуры"]
    found = v.cosmetic_findings("a.bsl", old, new, hunks_between(old, new))
    assert [(f.code, f.line) for f in found] == [("ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ", 2)]
    assert "«Значение=1;»" in found[0].message


def test_a_line_moved_into_a_new_construct_of_an_own_insertion_is_not_whitespace_only():
    """Своя ИЗМЕНЕН: прежняя строка закомментирована, та же инструкция стоит
    глубже в ветке `Иначе` новой конструкции — отступ следует из правки."""
    old = ["Процедура А()", "\tИнициализировать(Макет);", "КонецПроцедуры"]
    new = ["Процедура А()", OWN, "\t//Инициализировать(Макет);", "\tЕсли Временные Тогда",
           "\t\tИнициализировать(Макет, Менеджер);", "\tИначе", "\t\tИнициализировать(Макет);",
           "\tКонецЕсли;", OWN_END, "КонецПроцедуры"]
    assert v.cosmetic_findings("a.bsl", old, new, hunks_between(old, new)) == []


def test_a_line_moved_into_a_subquery_is_not_whitespace_only():
    """Схема СКД: строка `ИЗ` уехала внутрь нового подзапроса — без меток, но
    участок меняет запрос по существу."""
    old = ["\tВЫБРАТЬ", "\t\tТ.Сумма", "\tИЗ", "\t\tВтРасчет КАК Т"]
    new = ["\tВЫБРАТЬ", "\t\tТ.Сумма", "\tИЗ", "\t\t(ВЫБРАТЬ", "\t\t\tВтРасчет.Сумма КАК Сумма", "\t\tИЗ",
           "\t\t\tВтРасчет КАК Т", "\t\t) КАК Т"]
    assert v.cosmetic_findings("Template.dcs", old, new, hunks_between(old, new)) == []


def test_an_indent_changed_without_a_change_of_meaning_is_still_found():
    old = ["Процедура А()", "\tЗначение = 1;", "\tДругое = 2;", "КонецПроцедуры"]
    new = ["Процедура А()", "\t\tЗначение = 1;", "\tДругое = 2;", "КонецПроцедуры"]
    assert codes(v.cosmetic_findings("a.bsl", old, new, hunks_between(old, new))) == ["ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ"]


def test_a_neighbouring_xml_block_is_not_whitespace_only():
    """Удалено поле верхнего уровня, в другом месте добавлено поле в группе:
    теги совпадают без пробелов, но это разные строки, а не смена отступа."""
    old = ["<fields>", "\t<field>", "\t\t<valueType>А</valueType>", "\t</field>", "\t<group>", "\t</group>",
           "</fields>"]
    new = ["<fields>", "\t<group>", "\t\t<field>", "\t\t\t<valueType>Б</valueType>", "\t\t</field>", "\t</group>",
           "</fields>"]
    assert v.cosmetic_findings("Template.dcs", old, new, hunks_between(old, new)) == []


def test_a_block_moved_to_another_hunk_is_not_whitespace_only():
    """Перенос кода в другое место модуля — не «та же строка с другими
    пробелами»: пара ищется внутри участка."""
    old = ["Процедура А()", "\tШаг();", "\tДругое();", "КонецПроцедуры", "", "Процедура Б()", "КонецПроцедуры"]
    new = ["Процедура А()", "\tДругое();", "КонецПроцедуры", "", "Процедура Б()", "\tЕсли Да Тогда",
           "\t\tШаг();", "\tКонецЕсли;", "КонецПроцедуры"]
    assert v.cosmetic_findings("a.bsl", old, new, hunks_between(old, new)) == []


def test_a_line_with_an_exact_copy_among_added_is_not_whitespace_only():
    """Весь файл одним участком (сменились переводы строк): строка, вернувшаяся
    тем же текстом, не изменилась."""
    old = ["Процедура А()", "\tКонецЕсли;", "\t\tКонецЕсли;", "КонецПроцедуры"]
    new = ["Процедура А()", "\t\tКонецЕсли;", "\tКонецЕсли;", "КонецПроцедуры"]
    from meta.domain.changes import Hunk as H
    assert v.cosmetic_findings("a.bsl", old, new, [H(1, 4, 1, 4)]) == []


# --- права на новые объекты ------------------------------------------------------------------


def test_rights_on_new_objects():
    objects = [("ОбщаяКоманда", "мой_А"), ("РегистрСведений", "мой_Б"), ("Отчет", "мой_В"),
               ("Обработка", "мой_Г")]
    roles = {("ОбщаяКоманда", "мой_А"): [("мой_атом_А", True)],
            ("РегистрСведений", "мой_Б"): [("мой_атом_Выключено", False)],
            ("Отчет", "мой_В"): [("ПолныеПрава", True)]}
    found = v.rights_findings(objects, roles, COMMAND)
    assert [(f.code, f.message.split(" ")[0]) for f in found] == [
        ("ПРАВА-НЕ-ВЫДАНЫ", "РегистрСведений.мой_Б"),
        ("ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ", "Отчет.мой_В"),
        ("ПРАВА-НЕ-ВЫДАНЫ", "Обработка.мой_Г")]
    assert "(ПолныеПрава)" in found[1].message


def test_without_a_prefix_any_role_with_a_right_counts():
    assert v.rights_findings([("Отчет", "В")], {("Отчет", "В"): [("ПолныеПрава", True)]}, Conventions()) == []


def test_the_profile_changes_the_level_and_keeps_the_place():
    command = Conventions(prefix="мой_", rules=(("ПРАВКА-ВНЕ-ВСТАВКИ", "предупреждение"),
                                                     ("ВСТАВКА-БЕЗ-ДАТЫ", "выкл")))
    found = command.apply([v.FileFinding("ПРАВКА-ВНЕ-ВСТАВКИ", "текст", "a.bsl", 3),
                               v.FileFinding("ВСТАВКА-БЕЗ-ДАТЫ", "текст", "a.bsl", 4)])
    assert [(f.code, f.level, f.path, f.line) for f in found] == [
        ("ПРАВКА-ВНЕ-ВСТАВКИ", "предупреждение", "a.bsl", 3)]


# --- главный кейс: записанное правкой вставками проверка принимает ---------------------------


SIGNATURE = Signature("TASK-1", "06.10.2026", "Автор", "#TEAM")
MODULE = ["#Область ПрограммныйИнтерфейс", "",
          "Процедура Тест() Экспорт", "\tЗначение = 1;", "\tВозврат;", "КонецПроцедуры", "",
          "#КонецОбласти", "",
          "// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, Автор #OLD-7",
          "Процедура Старая()", "\tА = 1;", "\tБ = 2;", "\tВ = 3;", "КонецПроцедуры",
          "// } Автор, 01.01.2025"]


def written_as(edits):
    new, _ = edit_module(list(MODULE), edits, SIGNATURE, new_module=False)
    return new


def test_what_code_editing_writes_verification_accepts():
    edit_jobs = {
        "вставка": [Edit(line=5, lines=0, first_line="\tВозврат;", code="\tПроверка();")],
        "замена": [Edit(line=4, lines=1, first_line="\tЗначение = 1;", last_line="\tЗначение = 1;",
                        code="\tЗначение = 99;")],
        "удаление": [Edit(line=4, lines=1, first_line="\tЗначение = 1;", last_line="\tЗначение = 1;",
                          code="")],
        "новый метод": [Edit(line=8, lines=0, first_line="#КонецОбласти",
                             code="Процедура Новая() Экспорт\n\tВозврат;\nКонецПроцедуры")],
        "внутри чужой — вложенная": [Edit(line=12, lines=1, first_line="\tА = 1;", last_line="\tА = 1;",
                                          code="\tА = 10;")],
        "внутри чужой — обёртка снаружи": [Edit(line=12, lines=3, first_line="\tА = 1;",
                                                last_line="\tВ = 3;", code="\tГ = 4;")],
    }
    for what, edits in edit_jobs.items():
        new = written_as(edits)
        hunks = hunks_between(MODULE, new)
        added, _ = changed_lines(hunks, MODULE, new)
        found = (v.marker_findings("CommonModules/X/Ext/Module.bsl", MODULE, new, hunks, "TASK-1")
                 + v.structure_findings("CommonModules/X/Ext/Module.bsl", new, added))
        assert found == [], f"{what}: {found}\n" + "\n".join(new)
