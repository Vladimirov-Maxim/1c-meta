"""Пути из входных данных не выходят за корень выгрузки.

Белый список MCP (`META_ROOTS`) проверяет только корень. Имена объектов,
ролей, макетов и путь модуля приходят из задания агента и становятся частями
пути — без проверки «Справочник.C:/чужое» или «../Module.bsl» читали бы и
правили файл вне выгрузки.
"""

import os

from ..domain.model import Refuse

_SEPARATORS = ("/", "\\", ":")


def check_part(part):
    """Имя, из которого строится одна часть пути: без разделителей, диска и `..`."""
    if not part or part in (".", "..") or any(s in part for s in _SEPARATORS):
        raise Refuse(f"«{part}» не годится в имя: в нём разделитель пути или «..»")
    return part


def check_relative(path):
    """Относительный путь внутри выгрузки: не абсолютный и без `..`."""
    parts = path.replace("\\", "/").split("/")
    if os.path.isabs(path) or ":" in parts[0] or any(p == ".." for p in parts):
        raise Refuse(f"путь «{path}» должен быть относительным, внутри выгрузки")
    return path


def within(root, path):
    """`path`, если он лежит внутри `root`; иначе отказ."""
    base = os.path.normcase(os.path.normpath(os.path.abspath(root)))
    full = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    if full != base and not full.startswith(base.rstrip(os.sep) + os.sep):
        raise Refuse(f"путь «{path}» выходит за пределы выгрузки «{root}»")
    return path
