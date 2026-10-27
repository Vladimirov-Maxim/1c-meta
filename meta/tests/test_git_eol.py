"""Переводы строк, которые задаёт git: `core.autocrlf`, `core.safecrlf`, атрибуты.

Рабочая копия проекта с `core.autocrlf=true` бывает смешанной: файлы, взятые
до включения настройки, лежат с LF, тронутые после — с CRLF. При
`core.safecrlf=true` git не принимает файл не в тех переводах строк, какими
сам кладёт его в рабочую копию («LF would be replaced by CRLF»), — и коммит
не проходит. Поэтому инструмент пишет файлы так, как их кладёт git, проверка
правок находит файл, который `git add` не примет, а нормализация его
приводит. В ревизии git переводы строк уже не сводит: файл, целиком
закоммиченный в CRLF при LF в базе, — одна находка, а не тишина.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import edt_model  # noqa: E402
from meta.add import main  # noqa: E402
from meta.infra import git as infra_git  # noqa: E402

from .test_edt import PROFILE, card, read_file, write_file  # noqa: E402


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], check=check, capture_output=True)


def configure(repo, **settings):
    for key, value in settings.items():
        git(repo, "config", key.replace("_", "."), value)


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def mixed(tmp_path):
    """Проект EDT, взятый до включения настройки: в индексе и в рабочей копии LF (до
    `core.autocrlf`), теперь `core.autocrlf=true` и `core.safecrlf=true`."""
    repo = tmp_path / "repo"
    src = repo / "project" / "src"
    src.mkdir(parents=True)
    git(repo, "init", "-q")
    configure(repo, user_email="t@example.local", user_name="Фикстуры", core_quotepath="false",
              core_autocrlf="false", core_safecrlf="false")
    write_file(src, "Configuration/Configuration.mdo", card("Configuration", "Конфигурация"))
    write_file(src, "CommonModules/ВендорскийМодуль/ВендорскийМодуль.mdo",
             card("CommonModule", "ВендорскийМодуль"))
    write_file(src, "CommonModules/ВендорскийМодуль/Module.bsl",
             ["#Область ПрограммныйИнтерфейс", "Функция Публичный() Экспорт", "\tВозврат 1;", "КонецФункции",
              "#КонецОбласти"])
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "база")
    configure(repo, core_autocrlf="true", core_safecrlf="true")
    return repo, src


def crlf_only(data):
    return b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")


def git_accepts(repo, *paths):
    """Примет ли git файлы: только названные — файлы фикстуры записаны в ту же
    секунду, что и коммит, и git перепроверил бы их все («racy git»)."""
    done = git(repo, "add", "--", *("project/src/" + path for path in paths), check=False)
    return done.returncode == 0, done.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("settings, xml_attrs, expectation", [
    ({"core_autocrlf": "true"}, "", "CRLF"),
    ({"core_autocrlf": "input"}, "", "LF"),
    ({"core_autocrlf": "false"}, "", None),                      # git переводы строк не трогает
    ({"core_autocrlf": "true"}, "* -text\n", None),              # расширение тестов: как лежит
    ({"core_autocrlf": "true"}, "*.bsl eol=lf\n", "LF"),
    ({"core_autocrlf": "false", "core_eol": "crlf"}, "* text=auto\n", "CRLF"),
])
def test_checkout_line_endings_are_those_git_writes(tmp_path, settings, xml_attrs, expectation):
    git(tmp_path, "init", "-q")
    configure(tmp_path, **settings)
    if xml_attrs:
        (tmp_path / ".gitattributes").write_text(xml_attrs, encoding="utf-8")
    assert infra_git.checkout_eol(str(tmp_path), "CommonModules/Модуль/Module.bsl") == expectation


def test_checkout_line_endings_outside_git_are_unknown(tmp_path):
    assert infra_git.checkout_eol(str(tmp_path), "Module.bsl") is None


@pytest.mark.skipif(not edt_model.available(), reason="таблица метамодели EDT не сгенерирована")
def test_a_new_object_is_written_as_git_checks_it_out_and_git_accepts_it(mixed, tmp_path, profile):
    """Новый общий модуль среди карточек с LF: карточка, модуль и реестр — CRLF,
    как кладёт git; `git add` проходит, в индексе реестр не переписан целиком."""
    repo, src = mixed
    job_spec = {"repo": str(src), "objects": [{"вид": "ОбщийМодуль", "поля": {
        "имя": "мой_Новый", "синоним": "Новый", "сервер": True, "текст": "Процедура А() Экспорт\nКонецПроцедуры\n"}}]}
    path = tmp_path / "задание.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    assert main([str(path), "--apply", "--профиль", profile]) == 0
    written_items = ("CommonModules/мой_Новый/мой_Новый.mdo", "CommonModules/мой_Новый/Module.bsl",
                  "Configuration/Configuration.mdo")
    for rel in written_items:
        assert crlf_only(read_file(src, rel)), rel
    accepted, why = git_accepts(repo, *written_items)
    assert accepted, why
    registry = git(repo, "diff", "--cached", "--numstat", "--", "project/src/Configuration/Configuration.mdo")
    added_count, deleted_item = map(int, registry.stdout.decode().split()[:2])
    assert added_count <= 2 and deleted_item <= 1          # не весь файл: в индексе переводы сведены


def test_code_apply_rewrites_an_lf_module_as_git_checks_it_out(mixed, tmp_path, profile, capsys):
    """Модуль с LF на диске: правка пишет его в CRLF (в индексе изменится одна
    строка) и говорит об этом, а не «так и останется»."""
    repo, src = mixed
    job_spec = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "ОбщийМодуль.ВендорскийМодуль", "edits": [
                   {"line": 5, "lines": 0, "first_line": "#КонецОбласти",
                    "code": "Функция Новая() Экспорт\n\tВозврат 2;\nКонецФункции"}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(job_spec, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["--apply", str(path), "--профиль", profile]) == 0
    text = capsys.readouterr().out
    assert "файл LF, без BOM — станет CRLF" in text and "так и останется" not in text, text
    assert crlf_only(read_file(src, "CommonModules/ВендорскийМодуль/Module.bsl"))
    accepted, why = git_accepts(repo, "CommonModules/ВендорскийМодуль/Module.bsl")
    assert accepted, why
    deleted_item = git(repo, "diff", "--cached", "--numstat").stdout.decode().split()[1]
    assert deleted_item == "0"


def test_verify_finds_a_file_git_add_refuses_and_normalize_fixes_it(mixed, profile, capsys):
    repo, src = mixed
    write_file(src, "CommonModules/мой_Прямой/мой_Прямой.mdo", card("CommonModule", "мой_Прямой"), eol="\r\n")
    write_file(src, "CommonModules/мой_Прямой/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"])
    answer = os.path.join(os.path.dirname(profile), "ответ.json")
    capsys.readouterr()
    main(["--проверить", str(src), "--профиль", profile, "--json", answer])
    text = capsys.readouterr().out
    findings = json.load(open(answer, encoding="utf-8"))["находки"]
    assert [(f["код"], f["файл"]) for f in findings] == [
        ("ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ", "CommonModules/мой_Прямой/Module.bsl")], text
    assert "git add откажет" in findings[0]["текст"]
    module = "CommonModules/мой_Прямой/Module.bsl"
    assert not git_accepts(repo, module)[0]

    assert main(["--нормализовать", str(src), "--apply"]) == 0
    assert crlf_only(read_file(src, module))
    accepted, why = git_accepts(repo, module)
    assert accepted, why


def test_in_a_revision_a_file_committed_whole_in_crlf_is_one_finding(mixed, profile, capsys):
    """Ревизия: блоб с CRLF при LF в базе — одна находка на файл, и пояснения
    «git нормализует их сам» нет: в коммите git уже ничего не сводит."""
    repo, src = mixed
    configure(repo, core_autocrlf="false", core_safecrlf="false")
    write_file(src, "CommonModules/ВендорскийМодуль/Module.bsl",
             ["#Область ПрограммныйИнтерфейс", "Функция Публичный() Экспорт", "\tВозврат 1;", "КонецФункции",
              "#КонецОбласти"], eol="\r\n")
    git(repo, "commit", "-q", "-am", "переписан в CRLF")
    configure(repo, core_autocrlf="true", core_safecrlf="true")
    answer = os.path.join(os.path.dirname(profile), "ответ.json")
    capsys.readouterr()
    main(["--проверить", str(src), "--база", "HEAD~1", "--ревизия", "HEAD", "--профиль", profile, "--json", answer])
    text = capsys.readouterr().out
    findings = json.load(open(answer, encoding="utf-8"))["находки"]
    ours = [f for f in findings if f["код"] == "ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"]
    assert len(ours) == 1 and "в HEAD~1 файл с LF" in ours[0]["текст"], text
    assert "нормализует их сам" not in text
