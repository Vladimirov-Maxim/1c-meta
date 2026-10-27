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

from .test_verify import ПРОФИЛЬ, check, git, выгрузка, зафиксировать, коды, написать  # noqa: E402

МОДУЛЬ = "CommonModules/Чужой/Ext/Module.bsl"
ЧУЖАЯ = "Процедура Б() Экспорт // {[+](фрагмент ДОБАВЛЕН), 01.01.2025, #TEAM Иванов #TASK-0"
СВОЯ = "// {[+](фрагмент ДОБАВЛЕН), 31.08.2026, #TEAM Автор #TASK-1"
СВОЯ_КОНЕЦ = "// } Автор, 31.08.2026"
БЫЛО = [ЧУЖАЯ, "\tЧ();", "\tЕсли А Тогда", "\t\tЧ();", "\tКонецЕсли;", "КонецПроцедуры", "",
        "Процедура В()", "КонецПроцедуры"]
СТАЛО = БЫЛО[:5] + ["\t" + СВОЯ, "\tЧ();", "\t" + СВОЯ_КОНЕЦ, "КонецПроцедуры", "",
                    СВОЯ, "Процедура Н()", "\tЧ();", "КонецПроцедуры", СВОЯ_КОНЕЦ] + БЫЛО[6:]


@pytest.fixture
def профиль(tmp_path):
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_a_new_method_after_a_nested_insertion_is_not_an_edit_inside_another_tasks_insertion(
        tmp_path, профиль, capsys):
    root = выгрузка(tmp_path)
    git(root, "config", "diff.algorithm", "myers")          # настройка репозитория не мешает
    написать(root, МОДУЛЬ, БЫЛО)
    зафиксировать(root, "чужой метод")
    написать(root, МОДУЛЬ, СТАЛО)
    _, text, data = check(capsys, профиль, root, "--задача", "TASK-1")
    assert "ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ" not in коды(data), text
