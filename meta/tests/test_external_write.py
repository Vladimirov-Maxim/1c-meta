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
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            found[os.path.relpath(path, root).replace(os.sep, "/")] = path
    return found


def apply(repo, tmp_path, before_=None):
    """Задания по порядку; `до` — имя задания, на котором остановиться."""
    for name in sorted(os.listdir(ЗАДАНИЯ)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(ЗАДАНИЯ, name), encoding="utf-8") as f:
            задание = json.loads(f.read().replace("{repo}", str(repo).replace("\\", "/")))
        path = tmp_path / "задание.json"
        path.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
        assert main([str(path), "--apply", "--профиль", ПРОФИЛЬ]) == 0, name
        if name == before_:
            return


@pytest.fixture
def directory(tmp_path, monkeypatch):
    repo = tmp_path / "внешние"
    repo.mkdir()
    rng = random.Random(ORACLE_SEED)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    return repo


def test_external_objects_are_written_as_the_configurator_dumps_them(directory, tmp_path):
    """Обработка с модулем, реквизитом, табличной частью и формой (создание,
    наполнение, правка), правка модуля вставкой, отчёт со схемой и формой
    отчёта — каждый файл байт в байт как выгрузка конфигуратора."""
    apply(directory, tmp_path)
    записано, reference_node = files(directory), files(ОЖИДАНИЕ)
    assert sorted(записано) == sorted(reference_node)
    разные = [pt for pt in reference_node
              if open(записано[pt], "rb").read() != open(reference_node[pt], "rb").read()]
    assert разные == []


def test_an_external_object_cannot_be_created_in_a_configuration_dump(tmp_path):
    """Внешней обработке в выгрузке конфигурации места нет — отказ, а не
    карточка в каталоге, которого конфигуратор не знает."""
    from meta.infra.repository import Repository
    (tmp_path / "Configuration.xml").write_text("<x/>", encoding="utf-8")
    with pytest.raises(Refuse, match="живут в своей выгрузке"):
        Repository(str(tmp_path)).object_path("ВнешняяОбработка", "мой_Обработка")


def test_a_configuration_object_cannot_be_created_in_an_external_dump(directory, tmp_path):
    """И наоборот: справочнику во внешней выгрузке места нет."""
    path = tmp_path / "задание.json"
    path.write_text(json.dumps({"repo": str(directory), "objects": [
        {"вид": "Справочник", "поля": {"имя": "мой_Спр", "синоним": "Спр"}}]},
        ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Refuse, match="в выгрузке внешней обработки объектов вида «Справочник» нет"):
        main([str(path), "--apply", "--профиль", ПРОФИЛЬ])
    assert os.listdir(directory) == []


def test_an_external_dump_has_no_common_forms(directory, tmp_path):
    path = tmp_path / "задание.json"
    path.write_text(json.dumps({"repo": str(directory), "forms": [
        {"форма": "ОбщаяФорма.мой_Вопрос", "создать": {"синоним": "Вопрос"}}]},
        ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Refuse, match="общих форм не бывает"):
        main([str(path), "--apply", "--профиль", ПРОФИЛЬ])
    assert os.listdir(directory) == []


def test_the_plan_of_an_external_dump_is_refused_not_reported_as_not_done(tmp_path):
    """Сверки плана для внешней обработки нет: отказ, а не ложное «объект не
    сделан» по пустому факту."""
    import asyncio
    import shutil

    from meta.composition import mcp_server

    reference_node, copy_ = tmp_path / "эталон", tmp_path / "копия"
    reference_node.mkdir()
    shutil.copytree(os.path.join(ВНЕШНИЕ, "ожидание"), copy_)
    сервер = mcp_server(roots=[str(tmp_path)])
    for инструмент, arguments in (("plan_emit", {}),
                                  ("plan_check", {"objects": [{"вид": "Обработка", "имя": "мой_Обработка",
                                                               "действие": "создать"}]})):
        ответ = asyncio.run(сервер.call_tool(инструмент, {"baseline": str(reference_node), "target": str(copy_),
                                                          **arguments}))
        text = "\n".join(block.text for block in (ответ[0] if isinstance(ответ, tuple) else ответ))
        assert "сверки плана" in text and "ПЛАН-ОБЪЕКТ-НЕ-СДЕЛАН" not in text, text

