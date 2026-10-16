"""Фильтр проверки правок: `only` (коды правил) и `paths` (файлы правок).

Фильтр сужает ответ, а не прячет ошибку входа: неизвестный код правила и
отбор, под который не подошёл ни один файл, — отказ, а не «чисто». Ответ
повторяет фильтр, и «чисто» при нём — «чисто по фильтру». Сотни находок в
одном файле не вытесняют остальные: сводка по файлам и предел на файл.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.application.dto import VerifyResult  # noqa: E402
from meta.domain import verification as rules  # noqa: E402
from meta.report.verify import НА_ФАЙЛ, verify_lines  # noqa: E402

from .test_verify import ПРОФИЛЬ, выгрузка, коды, написать, проверить  # noqa: E402,F401

БЕЗ_BOM = "CommonModules/мой_А/Ext/Module.bsl"
С_BOM = "CommonModules/мой_Б/Ext/Module.bsl"


@pytest.fixture
def профиль(tmp_path):
    import json
    путь = tmp_path / "профиль.json"
    путь.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(путь)


@pytest.fixture
def правки(tmp_path):
    """Два новых модуля: один без BOM (находка), другой в норме."""
    root = выгрузка(tmp_path)
    написать(root, БЕЗ_BOM, ["Процедура А() Экспорт", "КонецПроцедуры"], bom=False)
    написать(root, С_BOM, ["Процедура Б() Экспорт", "КонецПроцедуры"])
    return root


@pytest.mark.parametrize("код, подсказка", [
    ("НЕТ-ТАКОГО", ""),
    ("2.5", "номера пунктов регламента"),
    ("[9.1]", "номера пунктов регламента"),
    ("2.1–2.6", "номера пунктов регламента"),
])
def test_an_unknown_rule_code_is_refused_not_clean(правки, профиль, capsys, код, подсказка):
    результат, текст, _ = проверить(capsys, профиль, правки, "--только", код)
    assert результат == 2 and "ОТКАЗ" in текст and "неизвестные коды правил" in текст, текст
    assert подсказка in текст and rules.БЕЗ_BOM in текст
    assert "ЧИСТО" not in текст


def test_the_filter_is_echoed_and_clean_is_clean_only_by_it(правки, профиль, capsys):
    результат, текст, данные = проверить(capsys, профиль, правки, "--только", rules.ВНЕ_ВСТАВКИ)
    assert результат == 0 and коды(данные) == []
    assert f"Фильтр: правила {rules.ВНЕ_ВСТАВКИ}" in текст
    assert "ЧИСТО ПО ФИЛЬТРУ" in текст and "проверены все правила" not in текст, текст
    assert данные["фильтр"] == {"правила": [rules.ВНЕ_ВСТАВКИ], "файлы": []}

    результат, текст, данные = проверить(capsys, профиль, правки, "--только", rules.БЕЗ_BOM)
    assert результат == 1 and коды(данные) == [rules.БЕЗ_BOM], текст


def test_paths_narrow_the_files_checked(правки, профиль, capsys):
    результат, текст, данные = проверить(capsys, профиль, правки, "--файлы", "CommonModules/мой_Б",
                                            "--задача", "TASK-1")
    assert результат == 0 and коды(данные) == [], текст
    assert "Файлов задачи: 1 (по отбору paths)" in текст and "ЧИСТО ПО ФИЛЬТРУ" in текст
    assert данные["фильтр"]["файлы"] == ["CommonModules/мой_Б"]

    _, _, данные = проверить(capsys, профиль, правки, "--файлы", "CommonModules/*/Ext/Module.bsl")
    assert коды(данные) == [rules.БЕЗ_BOM]


def test_paths_matching_no_file_are_refused(правки, профиль, capsys):
    результат, текст, _ = проверить(capsys, профиль, правки, "--файлы", "Catalogs/мой_Нет")
    assert результат == 2 and "ни один файл правок не подходит под paths" in текст, текст


def test_many_findings_start_with_a_summary_and_are_limited_per_file():
    находки = ([rules.FileFinding(rules.ТОЛЬКО_ПРОБЕЛЫ, "только пробелы", "Чужой.mdo", i) for i in range(1, 80)]
               + [rules.FileFinding(rules.БЕЗ_BOM, "файл без BOM", "Свой.bsl")])
    строки = verify_lines(VerifyResult("проба", [], находки))
    текст = "\n".join(строки)
    assert "Находок 80 в 2 файлах — сводка" in текст
    assert текст.index("Чужой.mdo") < текст.index("[ФАЙЛ-БЕЗ-BOM]")      # сводка — в начале
    assert len([с for с in строки if "[ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ]" in с]) == НА_ФАЙЛ
    assert f"… ещё {79 - НА_ФАЙЛ} в Чужой.mdo" in текст
    assert "Свой.bsl — файл без BOM" in текст                                 # свой файл не вытеснен
