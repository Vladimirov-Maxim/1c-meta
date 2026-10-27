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
from meta.report.verify import PER_FILE, verify_lines  # noqa: E402

from .test_verify import PROFILE, check, codes, dump_dir, write_file  # noqa: E402,F401

NO_BOM = "CommonModules/мой_А/Ext/Module.bsl"
WITH_BOM = "CommonModules/мой_Б/Ext/Module.bsl"


@pytest.fixture
def profile(tmp_path):
    import json
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def edit_jobs(tmp_path):
    """Два новых модуля: один без BOM (находка), другой в норме."""
    root = dump_dir(tmp_path)
    write_file(root, NO_BOM, ["Процедура А() Экспорт", "КонецПроцедуры"], bom=False)
    write_file(root, WITH_BOM, ["Процедура Б() Экспорт", "КонецПроцедуры"])
    return root


@pytest.mark.parametrize("code, hint", [
    ("НЕТ-ТАКОГО", ""),
    ("2.5", "номера пунктов регламента"),
    ("[9.1]", "номера пунктов регламента"),
    ("2.1–2.6", "номера пунктов регламента"),
])
def test_an_unknown_rule_code_is_refused_not_clean(edit_jobs, profile, capsys, code, hint):
    outcome, text, _ = check(capsys, profile, edit_jobs, "--только", code)
    assert outcome == 2 and "ОТКАЗ" in text and "неизвестные коды правил" in text, text
    assert hint in text and rules.NO_BOM in text
    assert "ЧИСТО" not in text


def test_the_filter_is_echoed_and_clean_is_clean_only_by_it(edit_jobs, profile, capsys):
    outcome, text, data = check(capsys, profile, edit_jobs, "--только", rules.OUTSIDE_INSERTION)
    assert outcome == 0 and codes(data) == []
    assert f"Фильтр: правила {rules.OUTSIDE_INSERTION}" in text
    assert "ЧИСТО ПО ФИЛЬТРУ" in text and "проверены все правила" not in text, text
    assert data["фильтр"] == {"правила": [rules.OUTSIDE_INSERTION], "файлы": []}

    outcome, text, data = check(capsys, profile, edit_jobs, "--только", rules.NO_BOM)
    assert outcome == 1 and codes(data) == [rules.NO_BOM], text


def test_paths_narrow_the_files_checked(edit_jobs, profile, capsys):
    outcome, text, data = check(capsys, profile, edit_jobs, "--файлы", "CommonModules/мой_Б",
                                            "--задача", "TASK-1")
    assert outcome == 0 and codes(data) == [], text
    assert "Файлов задачи: 1 (по отбору paths)" in text and "ЧИСТО ПО ФИЛЬТРУ" in text
    assert data["фильтр"]["файлы"] == ["CommonModules/мой_Б"]

    _, _, data = check(capsys, profile, edit_jobs, "--файлы", "CommonModules/*/Ext/Module.bsl")
    assert codes(data) == [rules.NO_BOM]


def test_paths_matching_no_file_are_refused(edit_jobs, profile, capsys):
    outcome, text, _ = check(capsys, profile, edit_jobs, "--файлы", "Catalogs/мой_Нет")
    assert outcome == 2 and "ни один файл правок не подходит под paths" in text, text


def test_many_findings_start_with_a_summary_and_are_limited_per_file():
    findings = ([rules.FileFinding(rules.WHITESPACE_ONLY, "только пробелы", "Чужой.mdo", i) for i in range(1, 80)]
               + [rules.FileFinding(rules.NO_BOM, "файл без BOM", "Свой.bsl")])
    lines = verify_lines(VerifyResult("проба", [], findings))
    text = "\n".join(lines)
    assert "Находок 80 в 2 файлах — сводка" in text
    assert text.index("Чужой.mdo") < text.index("[ФАЙЛ-БЕЗ-BOM]")      # сводка — в начале
    assert len([ss for ss in lines if "[ПРАВКА-ТОЛЬКО-ПРОБЕЛЫ]" in ss]) == PER_FILE
    assert f"… ещё {79 - PER_FILE} в Чужой.mdo" in text
    assert "Свой.bsl — файл без BOM" in text                                 # свой файл не вытеснен
