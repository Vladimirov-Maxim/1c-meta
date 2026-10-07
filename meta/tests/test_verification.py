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
from meta.domain.conventions import Соглашения  # noqa: E402
from meta.domain.edits import Edit, Signature, edit_module  # noqa: E402

КОМАНДА = Соглашения(приставка="мой_", другие_приставки=("ОМ_мой_",))
ВЕНДОР = ["Процедура ПередЗаписью(Отказ, РежимЗаписи, РежимПроведения)", "\tЗначение = 1;",
          "КонецПроцедуры"]


def коды(находки):
    return sorted(f.code for f in находки)


def метки(old, new, task=None, path="Documents/Вендорский/Ext/ObjectModule.bsl"):
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
                               ("CommonModules/ЧужойМодуль.xml", "ОбщийМодуль", "ЧужойМодуль")], КОМАНДА)
    assert [(f.code, f.path) for f in found] == [("МД-ПРЕФИКС", "CommonModules/ЧужойМодуль.xml")]
    assert "«ОбщийМодуль.ЧужойМодуль» без приставки «мой_»" in found[0].message


def test_without_a_prefix_convention_there_is_nothing_to_check():
    assert v.prefix_findings([("CommonModules/Любой.xml", "ОбщийМодуль", "Любой")], Соглашения()) == []


# --- метки вставок ----------------------------------------------------------------------


def test_a_vendor_edit_without_a_marker_is_found():
    found = метки(ВЕНДОР, [ВЕНДОР[0], "\tЗначение = 42;", ВЕНДОР[2]])
    assert коды(found) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]
    assert "добавленных вне вставок: 1 (стр. 2)" in found[0].message
    assert "удалённых вне вставок: 1 (стр. 2 прежней версии)" in found[0].message
    assert found[0].line is None


def test_a_wrapped_edit_and_its_marker_are_accepted():
    new = [ВЕНДОР[0], "\t// {[*](фрагмент ИЗМЕНЕН), 31.08.2026, #TEAM Автор #TASK-1", "\t",
           "\t//Значение = 1;", "\t", "\tЗначение = 2;", "\t", "\t// } Автор, 31.08.2026", ВЕНДОР[2]]
    assert метки(ВЕНДОР, new, task="TASK-1") == []


def test_a_marker_with_yo_or_without_date_is_found():
    def с_меткой(метка):
        return [ВЕНДОР[0], метка, "\tЗначение = 2;", "\t// } Автор", ВЕНДОР[1], ВЕНДОР[2]]

    ё = метки(ВЕНДОР, с_меткой("\t// {[*](фрагмент ИЗМЕНЁН), 31.08.2026, #TEAM Автор #TASK-1"))
    assert коды(ё) == ["ВСТАВКА-БУКВА-Ё"] and ё[0].line == 2
    без_даты = метки(ВЕНДОР, с_меткой("\t// {[+](фрагмент ДОБАВЛЕН), #TEAM Автор #TASK-1"))
    assert коды(без_даты) == ["ВСТАВКА-БЕЗ-ДАТЫ"]
    без_задачи = метки(ВЕНДОР, с_меткой("\t// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор"))
    assert коды(без_задачи) == ["ВСТАВКА-БЕЗ-ЗАДАЧИ"]
    без_типа = метки(ВЕНДОР, с_меткой("\t// {[+](фрагмент), 31.08.2026, Автор #TASK-1"))
    assert коды(без_типа) == ["ВСТАВКА-БЕЗ-ТИПА"]


def test_a_new_method_in_a_module_of_a_past_task_needs_a_marker():
    """Принадлежность модуля основанием не является: новый метод в своём модуле
    прошлой задачи оборачивается на общих основаниях."""
    old = ["Процедура ОбработкаПроведения(Отказ, РежимПроведения)", "\tЗначение = 1;", "КонецПроцедуры"]
    голый = old + ["", "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;", "КонецПроцедуры"]
    assert коды(метки(old, голый, path="Documents/мой_Наш/Ext/ObjectModule.bsl")) == ["ПРАВКА-ВНЕ-ВСТАВКИ"]
    обёрнут = old + ["", "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1",
                     "Процедура ПриЗаписи(Отказ)", "\tЗначение = 2;",
                     "КонецПроцедуры // } Автор, 31.08.2026"]
    assert метки(old, обёрнут, path="Documents/мой_Наш/Ext/ObjectModule.bsl") == []


def test_a_removed_line_kept_as_a_comment_is_not_lost():
    new = [ВЕНДОР[0], "\t// {[-](фрагмент УДАЛЕН), 31.08.2026, Автор #TASK-1", "\t//Значение = 1;",
           "\t// } Автор, 31.08.2026", ВЕНДОР[2]]
    assert метки(ВЕНДОР, new) == []


def test_region_directives_and_blank_lines_need_no_marker():
    new = [ВЕНДОР[0], "", ВЕНДОР[1], ВЕНДОР[2], "", "#Область Новая", "#КонецОбласти"]
    assert метки(ВЕНДОР, new) == []


def test_an_edit_inside_another_tasks_insertion_is_a_warning_with_the_task_given():
    old = [ВЕНДОР[0], "\t// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, Автор #OLD-7", "\tА = 1;",
           "\t// } Автор, 01.01.2025", ВЕНДОР[2]]
    new = old[:3] + ["\tБ = 2;"] + old[3:]
    assert метки(old, new) == []                       # без ИД задачи правило не проверяется
    found = метки(old, new, task="TASK-1")
    assert коды(found) == ["ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ"] and found[0].level == "предупреждение"
    assert "(OLD-7)" in found[0].message
    поверх = old[:3] + ["\t// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, Автор #TASK-1", "\tБ = 2;",
                        "\t// } Автор, 31.08.2026"] + old[3:]
    assert метки(old, поверх, task="TASK-1") == []


# --- незакрытая вставка и вставка вокруг метода ----------------------------------------------


def структура(new, old=ВЕНДОР):
    added, _ = changed_lines(hunks_between(old, new), old, new)
    return v.structure_findings("Documents/Вендорский/Ext/ObjectModule.bsl", new, added)


def test_an_unclosed_insertion_and_a_method_closed_on_its_own_line_are_found():
    new = ВЕНДОР + ["",
                    "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
                    "Процедура мой_Первый()", "\tЗначение = 2;", "КонецПроцедуры",
                    "// } Тест, 26.09.2026",
                    "",
                    "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
                    "Процедура мой_Второй()", "\tЗначение = 3;", "КонецПроцедуры"]
    found = структура(new)
    assert [(f.code, f.line) for f in found] == [("ВСТАВКА-НЕ-ЗАКРЫТА", 11),
                                                 ("ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ", 8)]
    assert "мой_Первый (метка на строке 5)" in found[1].message


def test_a_method_closed_on_its_end_is_accepted():
    new = ВЕНДОР + ["", "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1",
                    "Процедура мой_Первый()", "\tЗначение = 2;", "КонецПроцедуры // } Тест, 26.09.2026"]
    assert структура(new) == []


def test_a_compilation_directive_belongs_to_the_method():
    """Подъём от объявления к метке не останавливается на директиве: иначе
    метод формы с меткой на отдельной строке прошёл бы незамеченным."""
    old = ["&НаСервере", "Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)",
           "\tЗначение = 1;", "КонецПроцедуры"]
    new = old + ["", "// {[+](фрагмент ДОБАВЛЕН), 26.09.2026, #TEAM Тест #TASK-1", "&НаКлиенте",
                 "Процедура мой_Третий(Команда)", "\tЗначение = 3;", "КонецПроцедуры",
                 "// } Тест, 26.09.2026"]
    found = структура(new, old)
    assert коды(found) == ["ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ"] and "мой_Третий" in found[0].message


def test_someone_elses_unclosed_marker_is_not_the_tasks():
    old = ВЕНДОР + ["// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, Автор #OLD-7", "А = 1;"]
    new = old + ["Б = 2;"]
    assert структура(new, old) == []


# --- состав и формат --------------------------------------------------------------------------


def test_a_service_file_is_named():
    found = v.service_findings(["ConfigDumpInfo.xml"])
    assert коды(found) == ["ВЫГРУЗКА-СЛУЖЕБНЫЙ-ФАЙЛ"] and found[0].path == "ConfigDumpInfo.xml"


def test_bom_and_line_endings():
    crlf = "﻿А\r\nБ\r\n".encode()
    assert v.format_findings("a.bsl", crlf, "CRLF") == []
    assert коды(v.format_findings("a.bsl", "А\r\nБ\r\n".encode(), "CRLF")) == ["ФАЙЛ-БЕЗ-BOM"]
    чужие = v.format_findings("a.bsl", "﻿А\nБ\n".encode(), "CRLF")
    assert коды(чужие) == ["ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"] and "LF, в репозитории приняты CRLF" in чужие[0].message
    assert v.format_findings("a.bsl", "﻿А\nБ\n".encode(), None) == []
    смесь = v.format_findings("a.bsl", "﻿А\r\nБ\n".encode(), "CRLF")
    assert коды(смесь) == ["ФАЙЛ-ПЕРЕВОДЫ-СМЕШАНЫ"] and смесь[0].level == "предупреждение"


def test_trailing_whitespace_lost_against_the_baseline():
    assert v.trailing_findings("a.bsl", b"\xd0\x90  \r\n\xd0\x91\r\n", b"\xd0\x90\r\n\xd0\x91\r\n") \
        and v.trailing_findings("a.bsl", b"\xd0\x90\r\n", b"\xd0\x90\r\n") == []


def test_a_line_replaced_by_itself_with_other_whitespace():
    old = ["Процедура А()", "\tЗначение = 1;  ", "\tДругое = 2;", "", "КонецПроцедуры"]
    new = ["Процедура А()", "\tЗначение = 1;", "\tДругое = 3;", "\t", "КонецПроцедуры"]
    found = v.cosmetic_findings("a.bsl", old, new, hunks_between(old, new))
    assert [(f.code, f.line) for f in found] == [("ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ", 2)]
    assert "«Значение=1;»" in found[0].message


# --- права на новые объекты ------------------------------------------------------------------


def test_rights_on_new_objects():
    объекты = [("ОбщаяКоманда", "мой_А"), ("РегистрСведений", "мой_Б"), ("Отчет", "мой_В"),
               ("Обработка", "мой_Г")]
    роли = {("ОбщаяКоманда", "мой_А"): [("мой_атом_А", True)],
            ("РегистрСведений", "мой_Б"): [("мой_атом_Выключено", False)],
            ("Отчет", "мой_В"): [("ПолныеПрава", True)]}
    found = v.rights_findings(объекты, роли, КОМАНДА)
    assert [(f.code, f.message.split(" ")[0]) for f in found] == [
        ("ПРАВА-НЕ-ВЫДАНЫ", "РегистрСведений.мой_Б"),
        ("ПРАВА-ТОЛЬКО-В-ЧУЖОЙ-РОЛИ", "Отчет.мой_В"),
        ("ПРАВА-НЕ-ВЫДАНЫ", "Обработка.мой_Г")]
    assert "(ПолныеПрава)" in found[1].message


def test_without_a_prefix_any_role_with_a_right_counts():
    assert v.rights_findings([("Отчет", "В")], {("Отчет", "В"): [("ПолныеПрава", True)]}, Соглашения()) == []


def test_the_profile_changes_the_level_and_keeps_the_place():
    команда = Соглашения(приставка="мой_", правила=(("ПРАВКА-ВНЕ-ВСТАВКИ", "предупреждение"),
                                                     ("ВСТАВКА-БЕЗ-ДАТЫ", "выкл")))
    found = команда.применить([v.FileFinding("ПРАВКА-ВНЕ-ВСТАВКИ", "текст", "a.bsl", 3),
                               v.FileFinding("ВСТАВКА-БЕЗ-ДАТЫ", "текст", "a.bsl", 4)])
    assert [(f.code, f.level, f.path, f.line) for f in found] == [
        ("ПРАВКА-ВНЕ-ВСТАВКИ", "предупреждение", "a.bsl", 3)]


# --- главный кейс: записанное правкой вставками проверка принимает ---------------------------


ПОДПИСЬ = Signature("TASK-1", "06.10.2026", "Автор", "#TEAM")
МОДУЛЬ = ["#Область ПрограммныйИнтерфейс", "",
          "Процедура Тест() Экспорт", "\tЗначение = 1;", "\tВозврат;", "КонецПроцедуры", "",
          "#КонецОбласти", "",
          "// {[+](фрагмент ДОБАВЛЕН), 01.01.2025, Автор #OLD-7",
          "Процедура Старая()", "\tА = 1;", "\tБ = 2;", "\tВ = 3;", "КонецПроцедуры",
          "// } Автор, 01.01.2025"]


def записано(edits):
    new, _ = edit_module(list(МОДУЛЬ), edits, ПОДПИСЬ, new_module=False)
    return new


def test_what_code_editing_writes_verification_accepts():
    правки = {
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
    for что, edits in правки.items():
        new = записано(edits)
        hunks = hunks_between(МОДУЛЬ, new)
        added, _ = changed_lines(hunks, МОДУЛЬ, new)
        found = (v.marker_findings("CommonModules/X/Ext/Module.bsl", МОДУЛЬ, new, hunks, "TASK-1")
                 + v.structure_findings("CommonModules/X/Ext/Module.bsl", new, added))
        assert found == [], f"{что}: {found}\n" + "\n".join(new)
