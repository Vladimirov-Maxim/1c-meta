"""Длинные тексты в ответах — сводкой, целиком — по просьбе.

Текст модуля в ответе `metadata_apply` (до 58 КБ) и запрос набора данных в
показе (тысячи токенов) съедали контекст агента. Многострочное значение
длиннее порога печатается счётчиками, контрольной суммой и началом;
`verbose` (`--подробно`) — целиком.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.domain.model import Spec  # noqa: E402
from meta.report.objects import НАЧАЛО_СВОДКИ, СВОДКА_ОТ_СТРОК, describe  # noqa: E402

ТЕКСТ = "\n".join(f"Процедура П{i}() Экспорт\nКонецПроцедуры" for i in range(20))


def модуль():
    return Spec("ОбщийМодуль", {"имя": "мой_Длинный", "текст": ТЕКСТ})


def test_a_long_text_is_shown_as_a_summary_by_default():
    текст = "\n".join(describe(модуль()))
    assert f"{ТЕКСТ.count(chr(10)) + 1} строк, {len(ТЕКСТ)} знаков, sha1 " in текст, текст
    assert "Процедура П0() Экспорт" in текст and "Процедура П19()" not in текст
    assert текст.count("│") == НАЧАЛО_СВОДКИ + 1


def test_verbose_shows_the_long_text_whole():
    текст = "\n".join(describe(модуль(), подробно=True))
    assert "Процедура П19() Экспорт" in текст and "sha1" not in текст


def test_a_short_text_is_shown_whole():
    короткий = "\n".join(["А = 1;"] * (СВОДКА_ОТ_СТРОК - 1))
    текст = "\n".join(describe(Spec("ОбщийМодуль", {"имя": "мой_Короткий", "текст": короткий})))
    assert "sha1" not in текст
