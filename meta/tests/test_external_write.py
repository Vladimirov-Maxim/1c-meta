"""Внешние обработка и отчёт — против того, что выгружает сам конфигуратор.

Эталоны снимает `tools/epf_oracle.py`: задания `эталоны/внешние/задания`
пишутся инструментом в пустой каталог, каждая карточка загружается
конфигуратором в файл и выгружается обратно — выгрузка и есть эталон
(`эталоны/внешние/ожидание`). Здесь те же задания применяются к пустому
каталогу и каждый файл сверяется с эталоном побайтно. uuid воспроизводимы:
то же зерно, что у оракула.
"""

import json
import os
import random
import sys
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402

ВНЕШНИЕ = os.path.join(ROOT, "meta", "tests", "эталоны", "внешние")
ЗАДАНИЯ = os.path.join(ВНЕШНИЕ, "задания")
ОЖИДАНИЕ = os.path.join(ВНЕШНИЕ, "ожидание")
ПРОФИЛЬ = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")
ORACLE_SEED = 20261008


def files(root):
    found = {}
    for папка, _, имена in os.walk(root):
        for имя in имена:
            путь = os.path.join(папка, имя)
            found[os.path.relpath(путь, root).replace(os.sep, "/")] = путь
    return found


def применить(repo, tmp_path, до=None):
    """Задания по порядку; `до` — имя задания, на котором остановиться."""
    for имя in sorted(os.listdir(ЗАДАНИЯ)):
        if not имя.endswith(".json"):
            continue
        with open(os.path.join(ЗАДАНИЯ, имя), encoding="utf-8") as f:
            задание = json.loads(f.read().replace("{repo}", str(repo).replace("\\", "/")))
        путь = tmp_path / "задание.json"
        путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
        assert main([str(путь), "--apply", "--профиль", ПРОФИЛЬ]) == 0, имя
        if имя == до:
            return


@pytest.fixture
def каталог(tmp_path, monkeypatch):
    repo = tmp_path / "внешние"
    repo.mkdir()
    rng = random.Random(ORACLE_SEED)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    return repo


def test_external_objects_are_written_as_the_configurator_dumps_them(каталог, tmp_path):
    """Обработка с модулем, реквизитом, табличной частью и формой (создание,
    наполнение, правка), правка модуля вставкой, отчёт со схемой и формой
    отчёта — каждый файл байт в байт как выгрузка конфигуратора."""
    применить(каталог, tmp_path)
    записано, эталон = files(каталог), files(ОЖИДАНИЕ)
    assert sorted(записано) == sorted(эталон)
    разные = [п for п in эталон
              if open(записано[п], "rb").read() != open(эталон[п], "rb").read()]
    assert разные == []


def test_an_external_object_cannot_be_created_in_a_configuration_dump(tmp_path):
    """Внешней обработке в выгрузке конфигурации места нет — отказ, а не
    карточка в каталоге, которого конфигуратор не знает."""
    from meta.infra.repository import Repository
    (tmp_path / "Configuration.xml").write_text("<x/>", encoding="utf-8")
    with pytest.raises(Refuse, match="живут в своей выгрузке"):
        Repository(str(tmp_path)).object_path("ВнешняяОбработка", "мой_Обработка")


def test_a_configuration_object_cannot_be_created_in_an_external_dump(каталог, tmp_path):
    """И наоборот: справочнику во внешней выгрузке места нет."""
    путь = tmp_path / "задание.json"
    путь.write_text(json.dumps({"repo": str(каталог), "objects": [
        {"вид": "Справочник", "поля": {"имя": "мой_Спр", "синоним": "Спр"}}]},
        ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Refuse, match="в выгрузке внешней обработки объектов вида «Справочник» нет"):
        main([str(путь), "--apply", "--профиль", ПРОФИЛЬ])
    assert os.listdir(каталог) == []


def test_an_external_dump_has_no_common_forms(каталог, tmp_path):
    путь = tmp_path / "задание.json"
    путь.write_text(json.dumps({"repo": str(каталог), "forms": [
        {"форма": "ОбщаяФорма.мой_Вопрос", "создать": {"синоним": "Вопрос"}}]},
        ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Refuse, match="общих форм не бывает"):
        main([str(путь), "--apply", "--профиль", ПРОФИЛЬ])
    assert os.listdir(каталог) == []
