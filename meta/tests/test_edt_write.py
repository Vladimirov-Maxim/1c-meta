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

from meta.acl import edt_model as _edt_model  # noqa: E402
from meta.add import main  # noqa: E402

#: Таблица метамодели EDT не хранится в репозитории — без неё эти тесты не о чем.
pytestmark = pytest.mark.skipif(not _edt_model.available(), reason="таблица метамодели EDT не сгенерирована: "
                                "py -3 tools/edt_model_from_xcore.py")

EDT = os.path.join(ROOT, "meta", "tests", "эталоны", "edt")
ЗАДАНИЯ = os.path.join(EDT, "задания")
ORACLE_SEED = 20261007
ПРОФИЛЬ = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")


def files(root):
    found = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            found[os.path.relpath(path, root).replace(os.sep, "/")] = path
    return found


@pytest.fixture
def проект(tmp_path, monkeypatch):
    """Копия базового проекта EDT и воспроизводимые uuid."""
    src = tmp_path / "src"
    shutil.copytree(os.path.join(EDT, "база"), src)
    rng = random.Random(ORACLE_SEED)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    return src


def apply(src, tmp_path, forms=False):
    """Задания по порядку: без форм (эталон `ожидание`) или все (`ожидание-формы`)."""
    for name in sorted(os.listdir(ЗАДАНИЯ)):
        if not name.endswith(".json") or ("-форма-" in name and not forms):
            continue
        with open(os.path.join(ЗАДАНИЯ, name), encoding="utf-8") as f:
            задание = json.loads(f.read().replace("{repo}", str(src).replace("\\", "/")))
        path = tmp_path / name
        path.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
        assert main([str(path), "--apply", "--профиль", ПРОФИЛЬ]) == 0, name


def test_new_objects_of_every_kind_are_written_as_edt_writes_them(проект, tmp_path):
    apply(проект, tmp_path)
    ожидание, after_ = files(os.path.join(EDT, "ожидание")), files(проект)
    assert sorted(after_) == sorted(ожидание)
    разошлись = [path for path in ожидание
                 if open(ожидание[path], "rb").read() != open(after_[path], "rb").read()]
    assert разошлись == []


def test_forms_are_written_as_edt_writes_them(проект, tmp_path):
    """Формы: новая форма объекта (запись в карточке хозяина, описание, модуль,
    настройки динамического списка) и правка существующей — те же байты, что у
    EDT после импорта выгрузки, в которой те же задания записал писатель выгрузки."""
    apply(проект, tmp_path, forms=True)
    ожидание, after_ = files(os.path.join(EDT, "ожидание-формы")), files(проект)
    assert sorted(after_) == sorted(ожидание)
    разошлись = [path for path in ожидание
                 if open(ожидание[path], "rb").read() != open(after_[path], "rb").read()]
    assert разошлись == []


def test_a_new_file_is_utf8_without_bom_and_lf(проект, tmp_path):
    apply(проект, tmp_path)
    for path in files(проект).values():
        data = open(path, "rb").read()
        assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data, path


def test_what_the_edt_platform_writes_verify_accepts(проект, tmp_path):
    """Записанное площадкой EDT проверка правок принимает: формат файлов
    (BOM, переводы строк) и приставка — без находок; права названы только у
    объектов, у которых их в заданиях нет."""
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(проект), *args], check=True, capture_output=True)

    git("init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git("config", key, value)
    git("add", "-A")
    git("commit", "-q", "-m", "база")
    apply(проект, tmp_path)
    ответ = tmp_path / "ответ.json"
    main(["--проверить", str(проект), "--задача", "ОРАКУЛ-1", "--профиль", ПРОФИЛЬ, "--json", str(ответ)])
    data = json.loads(ответ.read_text(encoding="utf-8"))
    коды = {f["код"] for f in data["находки"]}
    assert коды <= {"ПРАВА-НЕ-ВЫДАНЫ"}, data["находки"]
    assert data["источник"].startswith("проект EDT")


def test_a_form_read_from_edt_is_the_same_form_as_in_the_dump(tmp_path, monkeypatch):
    """Каждая форма оракула, прочитанная из `Form.form` проекта EDT, показывает
    то же, что та же форма из `Form.xml` выгрузки: элементы с видами,
    родителями, путями, командами и событиями, реквизиты, команды, события."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import edt_oracle

    from meta.infra.forms.registry import for_text

    rng = random.Random(ORACLE_SEED)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    cf = tmp_path / "cf"
    edt_oracle.base_dump(str(cf))
    edt_oracle.apply_jobs(str(cf), main)
    forms = os.path.join(EDT, "ожидание-формы", "Documents", "мой_Заявка", "Forms")
    сверено = 0
    for name in sorted(os.listdir(forms)):
        edt_text = open(os.path.join(forms, name, "Form.form"), encoding="utf-8").read()
        xml = open(cf / "Documents" / "мой_Заявка" / "Forms" / name / "Ext" / "Form.xml",
                   encoding="utf-8-sig").read().replace("\r\n", "\n")
        owner = ("Документ", "мой_Заявка")
        выгрузка = for_text(xml).view(for_text(xml).load(xml), owner, name)
        edt = for_text(edt_text).view(for_text(edt_text).load(edt_text), owner, name)
        for field in ("elements", "commands", "events", "main", "assignment",
                     "dynamic_lists", "commands_actions"):
            assert getattr(edt, field) == getattr(выгрузка, field), (name, field)
        # типы домена сравниваются записью: равенства по значению у них нет
        assert {k: str(v) for k, v in edt.attributes.items()}             == {k: str(v) for k, v in выгрузка.attributes.items()}, name
        сверено += 1
    assert сверено >= 5
