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
from meta.tests.test_verify import commit, dump_dir, write_file  # noqa: E402

NEW = "CommonModules/мой_Новый/Ext/Module.bsl"
TEST = "CommonModules/мой_Тест/Ext/Module.bsl"


def read_file(root, rel):
    raw = open(os.path.join(str(root), *rel.split("/")), "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = (raw[3:] if bom else raw).decode("utf-8")
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    body = text[:-1].rstrip("\r") if text.endswith("\n") else text
    lines = [s[:-1] if s.endswith("\r") else s for s in body.split("\n")] if body else []
    return lines, bom, crlf, lf, text.endswith("\n")


def normalize(capsys, *arguments):
    capsys.readouterr()
    code = main(["--нормализовать", *map(str, arguments)])
    return code, capsys.readouterr().out


def test_bom_is_returned_to_a_new_file(tmp_path, capsys):
    root = dump_dir(tmp_path)
    write_file(root, NEW, ["Процедура Б() Экспорт", "\tВозврат;", "КонецПроцедуры"], bom=False)
    code, text = normalize(capsys, root)
    assert code == 1 and f"[к правке] {NEW}: BOM" in text and not read_file(root, NEW)[1]
    code, text = normalize(capsys, root, "--apply")
    assert code == 0 and read_file(root, NEW)[1] and "ИСПРАВЛЕНО: файлов 1" in text


def test_line_endings_follow_the_repository(tmp_path, capsys):
    root = dump_dir(tmp_path)
    write_file(root, NEW, ["Процедура Б() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    _, text = normalize(capsys, root, "--apply")
    _, _, crlf, lf, _ = read_file(root, NEW)
    assert crlf == 3 and lf == 0, text


def test_blank_lines_in_methods_get_their_indent(tmp_path, capsys):
    root = dump_dir(tmp_path)
    write_file(root, NEW, ["Процедура А() Экспорт", "", "\tЕсли Условие Тогда", "", "\t\tБ = 1;", "",
                           "\tКонецЕсли;", "", "КонецПроцедуры", "", "Процедура В() Экспорт",
                           "\tВозврат;", "КонецПроцедуры"])
    normalize(capsys, root, "--apply")
    lines = read_file(root, NEW)[0]
    assert lines[1] == "\t"            # после заголовка процедуры
    assert lines[3] == "\t\t"          # внутри Если
    assert lines[5] == "\t\t"          # перед КонецЕсли — ещё внутри блока
    assert lines[7] == "\t"            # перед КонецПроцедуры
    assert lines[9] == ""              # между процедурами отступ не ставится


def test_an_added_blank_line_gets_the_exact_indent_even_with_whitespace(tmp_path, capsys):
    """Пустая строка перед `КонецЦикла` вложенного цикла с потерянной
    табуляцией (одна вместо трёх) — отступ по уровню, а не «пробел уже есть»."""
    root = dump_dir(tmp_path)
    write_file(root, TEST, ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"])
    commit(root)
    for indent in ("", "\t", "\t\t", "\t\t\t\t"):
        write_file(root, TEST, ["Процедура А() Экспорт", "\tДля Каждого А Из Массив Цикл",
                              "\t\tДля Каждого Б Из А Цикл", "\t\t\tСделать(Б);", indent,
                              "\t\tКонецЦикла;", "\tКонецЦикла;", "КонецПроцедуры"])
        normalize(capsys, root, "--apply")
        assert read_file(root, TEST)[0][4] == "\t\t\t", repr(indent)


def test_a_foreign_line_with_whitespace_is_left_alone(tmp_path, capsys):
    """Переоформлять существующий отступ значило бы самой нормализации дать
    косметическую правку чужого кода."""
    root = dump_dir(tmp_path)
    write_file(root, TEST, ["Процедура А() Экспорт", "\t\t", "\tБ = 1;", "КонецПроцедуры"])
    commit(root)
    code, text = normalize(capsys, root)
    assert code == 0 and "ФОРМАТ В НОРМЕ" in text


def test_a_cut_trailing_space_comes_back_from_the_base(tmp_path, capsys):
    """Инструмент записи срезает хвостовые пробелы у любой записываемой строки —
    правка чужого кода сверх объёма задачи."""
    root = dump_dir(tmp_path)
    write_file(root, TEST, ["Процедура А() Экспорт", "\tВендорская = 1;   ", "\tДругая = 2;", "КонецПроцедуры"])
    commit(root)
    write_file(root, TEST, ["Процедура А() Экспорт", "\tВендорская = 1;", "\tДругая = 3;", "КонецПроцедуры"])
    _, text = normalize(capsys, root, "--apply")
    lines = read_file(root, TEST)[0]
    assert lines[1] == "\tВендорская = 1;   " and lines[2] == "\tДругая = 3;", text
    assert "хвостовые пробелы: 1 строк" in text


def test_where_git_normalizes_line_endings_the_file_is_not_rewritten(tmp_path, capsys):
    """В выгрузке с core.autocrlf=true git нормализует переводы строк сам —
    состояние рабочей копии на коммит не влияет, переписывать файлы незачем."""
    root = dump_dir(tmp_path, autocrlf=True)
    write_file(root, NEW, ["Процедура А() Экспорт", "\tВозврат;", "КонецПроцедуры"], eol="\n")
    code, text = normalize(capsys, root)
    assert "переводы строк LF ->" not in text and "core.autocrlf" in text and code == 0


def test_foreign_blank_lines_stay_and_own_get_indented(tmp_path, capsys):
    root = dump_dir(tmp_path)
    write_file(root, TEST, ["Процедура Старая() Экспорт", "", "\tЗначение = 1;", "КонецПроцедуры"])
    commit(root)
    write_file(root, TEST, ["Процедура Старая() Экспорт", "", "\tЗначение = 1;", "КонецПроцедуры", "",
                          "Процедура Новая() Экспорт", "", "\tЗначение = 2;", "КонецПроцедуры"])
    normalize(capsys, root, "--apply")
    lines = read_file(root, TEST)[0]
    assert lines[1] == "" and lines[6] == "\t"


def test_the_final_line_ending_is_as_in_the_base(tmp_path, capsys):
    root = dump_dir(tmp_path)
    write_file(root, TEST, ["Процедура А() Экспорт", "\tБ = 1;", "КонецПроцедуры"], final=False)
    commit(root)
    write_file(root, TEST, ["Процедура А() Экспорт", "\tБ = 2;", "КонецПроцедуры"], final=True)
    _, text = normalize(capsys, root, "--apply")
    assert not read_file(root, TEST)[4] and "снять завершающий перевод строки" in text


def test_it_is_an_operation_not_an_event(tmp_path, capsys):
    """Разовая правка живёт до следующей перезаписи файла: нормализация
    запускается перед каждым показом и коммитом, и второй запуск чист."""
    root = dump_dir(tmp_path)
    write_file(root, NEW, ["Процедура А() Экспорт", "", "\tБ = 1;", "", "КонецПроцедуры"], eol="\n",
             bom=False)
    code, text = normalize(capsys, root, "--apply")
    assert code == 0 and "ИСПРАВЛЕНО" in text
    code, text = normalize(capsys, root)
    assert code == 0 and "ФОРМАТ В НОРМЕ" in text


def test_a_directory_pair_takes_the_format_of_the_baseline(tmp_path, capsys):
    """Обработка вне репозитория: BOM и переводы строк — как у эталона,
    хвостовые пробелы — по совпадению строк без них."""
    reference_node, copy_ = tmp_path / "эталон", tmp_path / "копия"
    write_file(reference_node, "Обработка/Ext/ObjectModule.bsl",
             ["Процедура Сформировать()", "\tЗначение = 1;  ", "\tДругое = 2;", "КонецПроцедуры"])
    write_file(copy_, "Обработка/Ext/ObjectModule.bsl",
             ["Процедура Сформировать()", "\tЗначение = 1;", "\tДругое = 3;", "КонецПроцедуры"],
             eol="\n", bom=False)
    code, text = normalize(capsys, "--эталон", reference_node, "--копия", copy_, "--apply")
    lines, bom, crlf, lf, _ = read_file(copy_, "Обработка/Ext/ObjectModule.bsl")
    assert code == 0 and bom and crlf == 4 and lf == 0, text
    assert lines[1] == "\tЗначение = 1;  " and lines[2] == "\tДругое = 3;"
    assert read_file(reference_node, "Обработка/Ext/ObjectModule.bsl")[1]          # эталон не тронут
    code, text = normalize(capsys, "--эталон", reference_node, "--копия", copy_)
    assert code == 0 and "ФОРМАТ В НОРМЕ" in text


def test_the_agent_normalizes_only_allowed_dumps(tmp_path):
    import asyncio

    from meta.composition import mcp_server

    root = dump_dir(tmp_path)
    write_file(root, NEW, ["Процедура Б() Экспорт", "\tВозврат;", "КонецПроцедуры"], bom=False)
    server = mcp_server(roots=[str(root)])

    def call_tool(tool, **arguments):
        answer = asyncio.run(server.call_tool(tool, arguments))
        if isinstance(answer, tuple):
            answer = answer[0]
        return "\n".join(block.text for block in answer)

    assert "вызовите normalize_apply" in call_tool("normalize_check", repo=str(root))
    assert not read_file(root, NEW)[1]
    assert "ИСПРАВЛЕНО" in call_tool("normalize_apply", repo=str(root)) and read_file(root, NEW)[1]
    assert call_tool("normalize_apply", repo=str(tmp_path)).startswith("ОТКАЗ: выгрузка")


def test_with_a_base_older_than_head_files_of_other_tasks_are_not_touched(tmp_path, capsys):
    """База сверки — старая ветка: между ней и HEAD другая задача добавила в свой
    модуль пустую строку без отступа. Нормализация задачи её не трогает — чужой
    модуль не попадает в правки — и говорит об этом примечанием."""
    import subprocess

    root = dump_dir(tmp_path)
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    write_file(root, TEST, ["Процедура Старая() Экспорт", "", "\tЗначение = 1;", "КонецПроцедуры"])
    commit(root, "другая задача")
    foreign_item = read_file(root, TEST)
    write_file(root, NEW, ["Процедура Б() Экспорт", "", "\tВозврат;", "КонецПроцедуры"])
    code, text = normalize(capsys, root, "--база", base, "--apply")
    assert read_file(root, TEST) == foreign_item, text
    assert "база сверки — не HEAD" in text and "1, они не трогаются" in text
    assert read_file(root, NEW)[0][1] == "\t"              # свой файл нормализован
