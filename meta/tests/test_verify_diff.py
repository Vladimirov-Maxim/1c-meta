"""Участки правок для проверок вставок — алгоритмом histogram.

Алгоритм git по умолчанию (myers) в одном частом случае ошибается: за
вложенной вставкой в конце чужого метода-вставки следует новый метод, и
неизменённый `КонецПроцедуры` чужого метода попадает в добавленные — правка
«внутри чужой вставки» находится там, где её нет. Histogram (и patience)
сопоставляет строки верно.
"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from .test_verify import PROFILE, check, codes, commit, dump_dir, git, write_file  # noqa: E402

MODULE = "CommonModules/Чужой/Ext/Module.bsl"
FOREIGN = "Процедура Б() Экспорт // {[+](фрагмент ДОБАВЛЕН), 01.01.2025, #TEAM Иванов #TASK-0"
OWN = "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1"
OWN_END = "// } Автор, 31.08.2026"
BEFORE = [FOREIGN, "\tЧ();", "\tЕсли А Тогда", "\t\tЧ();", "\tКонецЕсли;", "КонецПроцедуры", "",
        "Процедура В()", "КонецПроцедуры"]
AFTER = BEFORE[:5] + ["\t" + OWN, "\tЧ();", "\t" + OWN_END, "КонецПроцедуры", "",
                    OWN, "Процедура Н()", "\tЧ();", "КонецПроцедуры", OWN_END] + BEFORE[6:]


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_a_new_method_after_a_nested_insertion_is_not_an_edit_inside_another_tasks_insertion(
        tmp_path, profile, capsys):
    root = dump_dir(tmp_path)
    git(root, "config", "diff.algorithm", "myers")          # настройка репозитория не мешает
    write_file(root, MODULE, BEFORE)
    commit(root, "чужой метод")
    write_file(root, MODULE, AFTER)
    _, text, data = check(capsys, profile, root, "--задача", "TASK-1")
    assert "ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ" not in codes(data), text
