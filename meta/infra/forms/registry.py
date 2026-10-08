"""Реестр реализаций формата форм: версия -> реализация.

Единственное место, где перечислены реализации. Новая версия формата — новый
пакет рядом с `designer221` и одна строка здесь; сценарии, порт и домен
не меняются. Незнакомая версия — отказ, а не «возьмём ближайшую»: форма,
записанная не тем форматом, всплывает только при загрузке в базу.
"""

from ...domain.model import Refuse
from .designer221 import Format221
from .edt import FormatEdt

FORMATS = (Format221(), FormatEdt())


def for_version(version):
    for candidate in FORMATS:
        if candidate.version == version:
            return candidate
    raise Refuse(f"формы формата «{version}» писать не умею; умею: "
                 + ", ".join(f.version for f in FORMATS))


def for_text(text):
    """Реализация по самому файлу формы — по его корню и версии."""
    for candidate in FORMATS:
        if candidate.matches(text):
            return candidate
    raise Refuse("не узнаю формат файла формы; умею: "
                 + ", ".join(f.version for f in FORMATS))
