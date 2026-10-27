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
JOBS = os.path.join(EDT, "задания")
ORACLE_SEED = 20261007
PROFILE = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")


def files(root):
    found = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            found[os.path.relpath(path, root).replace(os.sep, "/")] = path
    return found


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Копия базового проекта EDT и воспроизводимые uuid."""
    src = tmp_path / "src"
    shutil.copytree(os.path.join(EDT, "база"), src)
    rng = random.Random(ORACLE_SEED)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=rng.getrandbits(128), version=4))
    return src


def apply(src, tmp_path, forms=False):
    """Задания по порядку: без форм (эталон `ожидание`) или все (`ожидание-формы`)."""
    for name in sorted(os.listdir(JOBS)):
        if not name.endswith(".json") or ("-форма-" in name and not forms):
            continue
        with open(os.path.join(JOBS, name), encoding="utf-8") as f:
            job_spec = json.loads(f.read().replace("{repo}", str(src).replace("\\", "/")))
        path = tmp_path / name
        path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
        assert main([str(path), "--apply", "--профиль", PROFILE]) == 0, name


def test_new_objects_of_every_kind_are_written_as_edt_writes_them(project, tmp_path):
    apply(project, tmp_path)
    expectation, after_ = files(os.path.join(EDT, "ожидание")), files(project)
    assert sorted(after_) == sorted(expectation)
    diverged = [path for path in expectation
                 if open(expectation[path], "rb").read() != open(after_[path], "rb").read()]
    assert diverged == []


def test_forms_are_written_as_edt_writes_them(project, tmp_path):
    """Формы: новая форма объекта (запись в карточке хозяина, описание, модуль,
    настройки динамического списка) и правка существующей — те же байты, что у
    EDT после импорта выгрузки, в которой те же задания записал писатель выгрузки."""
    apply(project, tmp_path, forms=True)
    expectation, after_ = files(os.path.join(EDT, "ожидание-формы")), files(project)
    assert sorted(after_) == sorted(expectation)
    diverged = [path for path in expectation
                 if open(expectation[path], "rb").read() != open(after_[path], "rb").read()]
    assert diverged == []


def test_a_new_file_is_utf8_without_bom_and_lf(project, tmp_path):
    apply(project, tmp_path)
    for path in files(project).values():
        data = open(path, "rb").read()
        assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data, path


def test_what_the_edt_platform_writes_verify_accepts(project, tmp_path):
    """Записанное площадкой EDT проверка правок принимает: формат файлов
    (BOM, переводы строк) и приставка — без находок; права названы только у
    объектов, у которых их в заданиях нет."""
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)

    git("init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git("config", key, value)
    git("add", "-A")
    git("commit", "-q", "-m", "база")
    apply(project, tmp_path)
    answer = tmp_path / "ответ.json"
    main(["--проверить", str(project), "--задача", "ОРАКУЛ-1", "--профиль", PROFILE, "--json", str(answer)])
    data = json.loads(answer.read_text(encoding="utf-8"))
    codes = {f["код"] for f in data["находки"]}
    assert codes <= {"ПРАВА-НЕ-ВЫДАНЫ"}, data["находки"]
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
    reconciled = 0
    for name in sorted(os.listdir(forms)):
        edt_text = open(os.path.join(forms, name, "Form.form"), encoding="utf-8").read()
        xml = open(cf / "Documents" / "мой_Заявка" / "Forms" / name / "Ext" / "Form.xml",
                   encoding="utf-8-sig").read().replace("\r\n", "\n")
        owner = ("Документ", "мой_Заявка")
        dump_dir = for_text(xml).view(for_text(xml).load(xml), owner, name)
        edt = for_text(edt_text).view(for_text(edt_text).load(edt_text), owner, name)
        for field in ("elements", "commands", "events", "main", "assignment",
                     "dynamic_lists", "commands_actions"):
            assert getattr(edt, field) == getattr(dump_dir, field), (name, field)
        # типы домена сравниваются записью: равенства по значению у них нет
        assert {k: str(v) for k, v in edt.attributes.items()}             == {k: str(v) for k, v in dump_dir.attributes.items()}, name
        reconciled += 1
    assert reconciled >= 5


# --- форма, испорченная правкой в обход EDT ----------------------------------

ROUND_FORM = os.path.join(os.path.dirname(__file__), "эталоны", "edt", "ожидание-формы",
                          "Documents", "мой_Заявка", "Forms", "мой_Круг", "Form.form")


def _designer_text(text):
    from meta.domain.model import Refuse
    from meta.infra.forms.edt import designer_text
    try:
        return designer_text(text), None
    except Refuse as refusal:
        return None, str(refusal)


def test_a_form_written_by_edt_is_read():
    """Обратная сторона: форма, какой её пишет EDT, перекладывается без отказа."""
    text, refusal = _designer_text(open(ROUND_FORM, encoding="utf-8").read())
    assert refusal is None and text


def test_an_event_named_in_russian_is_named_in_the_refusal():
    """`<event>ПриСозданииНаСервере</event>` вместо `OnCreateAtServer` EDT не
    узнаёт — обработчик не вызывается. Отказ называет само событие и слово EDT,
    а не элемент, на котором круг перекладки не сошёлся первым."""
    text = open(ROUND_FORM, encoding="utf-8").read().replace(
        "<event>OnCreateAtServer</event>", "<event>ПриСозданииНаСервере</event>")
    _, refusal = _designer_text(text)
    assert "форма: событие «ПриСозданииНаСервере» — в EDT оно называется «OnCreateAtServer»" in refusal


def test_an_element_event_named_in_russian_names_the_element():
    text = open(ROUND_FORM, encoding="utf-8").read().replace(
        "<event>OnChange</event>", "<event>ПриИзменении</event>", 1)
    _, refusal = _designer_text(text)
    assert "элемент «Комментарий»: событие «ПриИзменении» — в EDT оно называется «OnChange»" in refusal


@pytest.mark.skipif(not _edt_model.available(), reason="нет таблицы метамодели EDT")
def test_a_block_written_out_of_edt_order_is_named():
    """Блок обработчиков формы, дописанный в конец файла: EDT так не пишет, и
    отказ называет свойство не на месте, а не «не проходит круг»."""
    text = open(ROUND_FORM, encoding="utf-8").read()
    start = text.index("  <handlers>\n    <event>OnCreateAtServer")
    end = text.index("  </handlers>\n", start) + len("  </handlers>\n")
    block = text[start:end]
    text = text[:start] + text[end:]
    text = text.replace("</form:Form>", block + "</form:Form>")
    _, refusal = _designer_text(text)
    assert "«handlers» стоит после «extInfo»" in refusal, refusal
