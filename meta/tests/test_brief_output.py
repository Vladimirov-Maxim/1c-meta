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
from meta.report.objects import SUMMARY_FROM_LINES, SUMMARY_START, describe  # noqa: E402

ТЕКСТ = "\n".join(f"Процедура П{i}() Экспорт\nКонецПроцедуры" for i in range(20))


def module():
    return Spec("ОбщийМодуль", {"имя": "мой_Длинный", "текст": ТЕКСТ})


def test_a_long_text_is_shown_as_a_summary_by_default():
    text = "\n".join(describe(module()))
    assert f"{ТЕКСТ.count(chr(10)) + 1} строк, {len(ТЕКСТ)} знаков, sha1 " in text, text
    assert "Процедура П0() Экспорт" in text and "Процедура П19()" not in text
    assert text.count("│") == SUMMARY_START + 1


def test_verbose_shows_the_long_text_whole():
    text = "\n".join(describe(module(), detailed=True))
    assert "Процедура П19() Экспорт" in text and "sha1" not in text


def test_a_short_text_is_shown_whole():
    короткий = "\n".join(["А = 1;"] * (SUMMARY_FROM_LINES - 1))
    text = "\n".join(describe(Spec("ОбщийМодуль", {"имя": "мой_Короткий", "текст": короткий})))
    assert "sha1" not in text
