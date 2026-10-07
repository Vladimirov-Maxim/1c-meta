"""Шов между доменом и схемой: состав полей назван дважды и сверяется.

Отдельный файл, потому что вопрос общий для всех видов: в тест про один вид
человек, добавляющий другой, не заглянет — а падать будет именно у него.

Что сверяется, перечислено в `mapping.check_layers`; каждая из проверок
срабатывает на подстроенное расхождение.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping  # noqa: E402


def test_layers_agree():
    mismatches = mapping.check_layers()
    assert not mismatches, mismatches
