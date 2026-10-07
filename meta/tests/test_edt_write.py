"""Запись в проект EDT — против того, что пишет сам EDT.

Эталоны снимает `tools/edt_oracle.py`: те же задания записываются писателем
выгрузки, выгрузка импортируется командой EDT `import`, полученный проект —
`эталоны/edt/ожидание`; импорт базовой выгрузки (пустая конфигурация и язык)
— `эталоны/edt/база`. Здесь задания применяются к копии базового проекта EDT
и каждый файл сверяется с эталоном побайтно. uuid воспроизводимы: то же
зерно, что у оракула.
"""

import json
import os
import random
import shutil
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402

EDT = os.path.join(ROOT, "meta", "tests", "эталоны", "edt")
ЗАДАНИЯ = os.path.join(EDT, "задания")
ORACLE_SEED = 20261007


def files(root):
    found = {}
    for папка, _, имена in os.walk(root):
        for имя in имена:
            путь = os.path.join(папка, имя)
            found[os.path.relpath(путь, root).replace(os.sep, "/")] = путь
    return found


@pytest.fixture
def проект(tmp_path, monkeypatch):
    """Копия базового проекта EDT и воспроизводимые uuid."""
    src = tmp_path / "src"
    shutil.copytree(os.path.join(EDT, "база"), src)
    rng = random.Random(ORACLE_SEED)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    return src


def применить(src, tmp_path):
    for имя in sorted(os.listdir(ЗАДАНИЯ)):
        if not имя.endswith(".json"):
            continue
        with open(os.path.join(ЗАДАНИЯ, имя), encoding="utf-8") as f:
            задание = json.loads(f.read().replace("{repo}", str(src).replace("\\", "/")))
        путь = tmp_path / имя
        путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
        assert main([str(путь), "--apply"]) == 0, имя


def test_new_objects_of_every_kind_are_written_as_edt_writes_them(проект, tmp_path):
    применить(проект, tmp_path)
    ожидание, стало = files(os.path.join(EDT, "ожидание")), files(проект)
    assert sorted(стало) == sorted(ожидание)
    разошлись = [путь for путь in ожидание
                 if open(ожидание[путь], "rb").read() != open(стало[путь], "rb").read()]
    assert разошлись == []


def test_a_new_file_is_utf8_without_bom_and_lf(проект, tmp_path):
    применить(проект, tmp_path)
    for путь in files(проект).values():
        данные = open(путь, "rb").read()
        assert not данные.startswith(b"\xef\xbb\xbf") and b"\r\n" not in данные, путь
