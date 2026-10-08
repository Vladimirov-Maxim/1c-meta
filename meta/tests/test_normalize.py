"""Нормализация формата файлов задачи — через терминал, на git и паре каталогов.

Кейсы: BOM, который инструмент записи не пишет; файл в переводах строк, чужих
репозиторию; пустые строки без отступа, которые первая же выгрузка из базы
превращает в правки; срезанный хвостовой пробел вендорской строки; git,
который нормализует переводы строк сам; чужие пустые строки, которых задача не
трогала. И главное свойство — операция, а не событие: второй запуск работы не
находит.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.tests.test_verify import выгрузка, зафиксировать, написать  # noqa: E402

НОВЫЙ = "CommonModules/мой_Новый/Ext/Module.bsl"
ТЕСТ = "CommonModules/мой_Тест/Ext/Module.bsl"


def прочитать(root, rel):
    сырое = open(os.path.join(str(root), *rel.split("/")), "rb").read()
    bom = сырое.startswith(b"\xef\xbb\xbf")
    текст = (сырое[3:] if bom else сырое).decode("utf-8")
    crlf = текст.count("\r\n")
    lf = текст.count("\n") - crlf
    тело = текст[:-1].rstrip("\r") if текст.endswith("\n") else текст
    строки = [s[:-1] if s.endswith("\r") else s for s in тело.split("\n")] if тело else []
    return строки, bom, crlf, lf, текст.endswith("\n")


def нормализовать(capsys, *аргументы):
    capsys.readouterr()
    код = main(["--нормализовать", *map(str, аргументы)])
    return код, capsys.readouterr().out


def test_bom_is_returned_to_a_new_file(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, НОВЫЙ, ["Процедура Б() Экспорт", "\tВозврат;", "КонецПроцедуры"], bom=False)
    код, текст = нормализовать(capsys, root)
    assert код == 1 and f"[к правке] {НОВЫЙ}: BOM" in текст and not прочитать(root, НОВЫЙ)[1]
    код, текст = нормализовать(capsys, root, "--apply")
    assert код == 0 and прочитать(root, НОВЫЙ)[1] and "ИСПРАВЛЕНО: файлов 1" in текст


def test_line_endings_follow_the_repository(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, НОВЫЙ, ["Процедура Б() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    _, текст = нормализовать(capsys, root, "--apply")
    _, _, crlf, lf, _ = прочитать(root, НОВЫЙ)
    assert crlf == 3 and lf == 0, текст


def test_blank_lines_in_methods_get_their_indent(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, НОВЫЙ, ["Процедура А() Экспорт", "", "\tЕсли Условие Тогда", "", "\t\tБ = 1;", "",
                           "\tКонецЕсли;", "", "КонецПроцедуры", "", "Процедура В() Экспорт",
                           "\tВозврат;", "КонецПроцедуры"])
    нормализовать(capsys, root, "--apply")
    строки = прочитать(root, НОВЫЙ)[0]
    assert строки[1] == "\t"            # после заголовка процедуры
    assert строки[3] == "\t\t"          # внутри Если
    assert строки[5] == "\t\t"          # перед КонецЕсли — ещё внутри блока
    assert строки[7] == "\t"            # перед КонецПроцедуры
    assert строки[9] == ""              # между процедурами отступ не ставится


def test_an_added_blank_line_gets_the_exact_indent_even_with_whitespace(tmp_path, capsys):
    """Пустая строка перед `КонецЦикла` вложенного цикла с потерянной
    табуляцией (одна вместо трёх) — отступ по уровню, а не «пробел уже есть»."""
    root = выгрузка(tmp_path)
    написать(root, ТЕСТ, ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"])
    зафиксировать(root)
    for отступ in ("", "\t", "\t\t", "\t\t\t\t"):
        написать(root, ТЕСТ, ["Процедура А() Экспорт", "\tДля Каждого А Из Массив Цикл",
                              "\t\tДля Каждого Б Из А Цикл", "\t\t\tСделать(Б);", отступ,
                              "\t\tКонецЦикла;", "\tКонецЦикла;", "КонецПроцедуры"])
        нормализовать(capsys, root, "--apply")
        assert прочитать(root, ТЕСТ)[0][4] == "\t\t\t", repr(отступ)


def test_a_foreign_line_with_whitespace_is_left_alone(tmp_path, capsys):
    """Переоформлять существующий отступ значило бы самой нормализации дать
    косметическую правку чужого кода."""
    root = выгрузка(tmp_path)
    написать(root, ТЕСТ, ["Процедура А() Экспорт", "\t\t", "\tБ = 1;", "КонецПроцедуры"])
    зафиксировать(root)
    код, текст = нормализовать(capsys, root)
    assert код == 0 and "ФОРМАТ В НОРМЕ" in текст


def test_a_cut_trailing_space_comes_back_from_the_base(tmp_path, capsys):
    """Инструмент записи срезает хвостовые пробелы у любой записываемой строки —
    правка чужого кода сверх объёма задачи."""
    root = выгрузка(tmp_path)
    написать(root, ТЕСТ, ["Процедура А() Экспорт", "\tВендорская = 1;   ", "\tДругая = 2;", "КонецПроцедуры"])
    зафиксировать(root)
    написать(root, ТЕСТ, ["Процедура А() Экспорт", "\tВендорская = 1;", "\tДругая = 3;", "КонецПроцедуры"])
    _, текст = нормализовать(capsys, root, "--apply")
    строки = прочитать(root, ТЕСТ)[0]
    assert строки[1] == "\tВендорская = 1;   " and строки[2] == "\tДругая = 3;", текст
    assert "хвостовые пробелы: 1 строк" in текст


def test_where_git_normalizes_line_endings_the_file_is_not_rewritten(tmp_path, capsys):
    """В выгрузке с core.autocrlf=true git нормализует переводы строк сам —
    состояние рабочей копии на коммит не влияет, переписывать файлы незачем."""
    root = выгрузка(tmp_path, autocrlf=True)
    написать(root, НОВЫЙ, ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    код, текст = нормализовать(capsys, root)
    assert "переводы строк LF ->" not in текст and "core.autocrlf" in текст and код == 0


def test_foreign_blank_lines_stay_and_own_get_indented(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, ТЕСТ, ["Процедура Старая() Экспорт", "", "\tЗначение = 1;", "КонецПроцедуры"])
    зафиксировать(root)
    написать(root, ТЕСТ, ["Процедура Старая() Экспорт", "", "\tЗначение = 1;", "КонецПроцедуры", "",
                          "Процедура Новая() Экспорт", "", "\tЗначение = 2;", "КонецПроцедуры"])
    нормализовать(capsys, root, "--apply")
    строки = прочитать(root, ТЕСТ)[0]
    assert строки[1] == "" and строки[6] == "\t"


def test_the_final_line_ending_is_as_in_the_base(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, ТЕСТ, ["Процедура А() Экспорт", "\tБ = 1;", "КонецПроцедуры"], final=False)
    зафиксировать(root)
    написать(root, ТЕСТ, ["Процедура А() Экспорт", "\tБ = 2;", "КонецПроцедуры"], final=True)
    _, текст = нормализовать(capsys, root, "--apply")
    assert not прочитать(root, ТЕСТ)[4] and "снять завершающий перевод строки" in текст


def test_it_is_an_operation_not_an_event(tmp_path, capsys):
    """Разовая правка живёт до следующей перезаписи файла: нормализация
    запускается перед каждым показом и коммитом, и второй запуск чист."""
    root = выгрузка(tmp_path)
    написать(root, НОВЫЙ, ["Процедура А() Экспорт", "", "\tБ = 1;", "", "КонецПроцедуры"], eol="\n",
             bom=False)
    код, текст = нормализовать(capsys, root, "--apply")
    assert код == 0 and "ИСПРАВЛЕНО" in текст
    код, текст = нормализовать(capsys, root)
    assert код == 0 and "ФОРМАТ В НОРМЕ" in текст


def test_a_directory_pair_takes_the_format_of_the_baseline(tmp_path, capsys):
    """Обработка вне репозитория: BOM и переводы строк — как у эталона,
    хвостовые пробелы — по совпадению строк без них."""
    эталон, копия = tmp_path / "эталон", tmp_path / "копия"
    написать(эталон, "Обработка/Ext/ObjectModule.bsl",
             ["Процедура Сформировать()", "\tЗначение = 1;  ", "\tДругое = 2;", "КонецПроцедуры"])
    написать(копия, "Обработка/Ext/ObjectModule.bsl",
             ["Процедура Сформировать()", "\tЗначение = 1;", "\tДругое = 3;", "КонецПроцедуры"],
             eol="\n", bom=False)
    код, текст = нормализовать(capsys, "--эталон", эталон, "--копия", копия, "--apply")
    строки, bom, crlf, lf, _ = прочитать(копия, "Обработка/Ext/ObjectModule.bsl")
    assert код == 0 and bom and crlf == 4 and lf == 0, текст
    assert строки[1] == "\tЗначение = 1;  " and строки[2] == "\tДругое = 3;"
    assert прочитать(эталон, "Обработка/Ext/ObjectModule.bsl")[1]          # эталон не тронут
    код, текст = нормализовать(capsys, "--эталон", эталон, "--копия", копия)
    assert код == 0 and "ФОРМАТ В НОРМЕ" in текст


def test_the_agent_normalizes_only_allowed_dumps(tmp_path):
    import asyncio

    from meta.composition import mcp_server

    root = выгрузка(tmp_path)
    написать(root, НОВЫЙ, ["Процедура Б() Экспорт", "\tВозврат;", "КонецПроцедуры"], bom=False)
    сервер = mcp_server(roots=[str(root)])

    def вызвать(инструмент, **аргументы):
        ответ = asyncio.run(сервер.call_tool(инструмент, аргументы))
        if isinstance(ответ, tuple):
            ответ = ответ[0]
        return "\n".join(блок.text for блок in ответ)

    assert "вызовите normalize_apply" in вызвать("normalize_check", repo=str(root))
    assert not прочитать(root, НОВЫЙ)[1]
    assert "ИСПРАВЛЕНО" in вызвать("normalize_apply", repo=str(root)) and прочитать(root, НОВЫЙ)[1]
    assert вызвать("normalize_apply", repo=str(tmp_path)).startswith("ОТКАЗ: выгрузка")
