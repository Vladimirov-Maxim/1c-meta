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

from .test_edt import ПРОФИЛЬ, карточка, написать, прочитать  # noqa: E402


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], check=check, capture_output=True)


def настроить(repo, **настройки):
    for ключ, значение in настройки.items():
        git(repo, "config", ключ.replace("_", "."), значение)


@pytest.fixture
def профиль(tmp_path):
    путь = tmp_path / "профиль.json"
    путь.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(путь)


@pytest.fixture
def смешанный(tmp_path):
    """Проект EDT, взятый до включения настройки: в индексе и в рабочей копии LF (до
    `core.autocrlf`), теперь `core.autocrlf=true` и `core.safecrlf=true`."""
    repo = tmp_path / "repo"
    src = repo / "project" / "src"
    src.mkdir(parents=True)
    git(repo, "init", "-q")
    настроить(repo, user_email="t@example.local", user_name="Фикстуры", core_quotepath="false",
              core_autocrlf="false", core_safecrlf="false")
    написать(src, "Configuration/Configuration.mdo", карточка("Configuration", "Конфигурация"))
    написать(src, "CommonModules/ВендорскийМодуль/ВендорскийМодуль.mdo",
             карточка("CommonModule", "ВендорскийМодуль"))
    написать(src, "CommonModules/ВендорскийМодуль/Module.bsl",
             ["#Область ПрограммныйИнтерфейс", "Функция Публичный() Экспорт", "\tВозврат 1;", "КонецФункции",
              "#КонецОбласти"])
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "база")
    настроить(repo, core_autocrlf="true", core_safecrlf="true")
    return repo, src


def только_crlf(данные):
    return b"\r\n" in данные and b"\n" not in данные.replace(b"\r\n", b"")


def принимает_git(repo, *пути):
    """Примет ли git файлы: только названные — файлы фикстуры записаны в ту же
    секунду, что и коммит, и git перепроверил бы их все («racy git»)."""
    done = git(repo, "add", "--", *("project/src/" + путь for путь in пути), check=False)
    return done.returncode == 0, done.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("настройки, атрибуты, ожидание", [
    ({"core_autocrlf": "true"}, "", "CRLF"),
    ({"core_autocrlf": "input"}, "", "LF"),
    ({"core_autocrlf": "false"}, "", None),                      # git переводы строк не трогает
    ({"core_autocrlf": "true"}, "* -text\n", None),              # расширение тестов: как лежит
    ({"core_autocrlf": "true"}, "*.bsl eol=lf\n", "LF"),
    ({"core_autocrlf": "false", "core_eol": "crlf"}, "* text=auto\n", "CRLF"),
])
def test_checkout_line_endings_are_those_git_writes(tmp_path, настройки, атрибуты, ожидание):
    git(tmp_path, "init", "-q")
    настроить(tmp_path, **настройки)
    if атрибуты:
        (tmp_path / ".gitattributes").write_text(атрибуты, encoding="utf-8")
    assert infra_git.checkout_eol(str(tmp_path), "CommonModules/Модуль/Module.bsl") == ожидание


def test_checkout_line_endings_outside_git_are_unknown(tmp_path):
    assert infra_git.checkout_eol(str(tmp_path), "Module.bsl") is None


@pytest.mark.skipif(not edt_model.available(), reason="таблица метамодели EDT не сгенерирована")
def test_a_new_object_is_written_as_git_checks_it_out_and_git_accepts_it(смешанный, tmp_path, профиль):
    """Новый общий модуль среди карточек с LF: карточка, модуль и реестр — CRLF,
    как кладёт git; `git add` проходит, в индексе реестр не переписан целиком."""
    repo, src = смешанный
    задание = {"repo": str(src), "objects": [{"вид": "ОбщийМодуль", "поля": {
        "имя": "мой_Новый", "синоним": "Новый", "сервер": True, "текст": "Процедура А() Экспорт\nКонецПроцедуры\n"}}]}
    путь = tmp_path / "задание.json"
    путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    assert main([str(путь), "--apply", "--профиль", профиль]) == 0
    записанные = ("CommonModules/мой_Новый/мой_Новый.mdo", "CommonModules/мой_Новый/Module.bsl",
                  "Configuration/Configuration.mdo")
    for rel in записанные:
        assert только_crlf(прочитать(src, rel)), rel
    принято, почему = принимает_git(repo, *записанные)
    assert принято, почему
    реестр = git(repo, "diff", "--cached", "--numstat", "--", "project/src/Configuration/Configuration.mdo")
    добавлено, удалено = map(int, реестр.stdout.decode().split()[:2])
    assert добавлено <= 2 and удалено <= 1          # не весь файл: в индексе переводы сведены


def test_code_apply_rewrites_an_lf_module_as_git_checks_it_out(смешанный, tmp_path, профиль, capsys):
    """Модуль с LF на диске: правка пишет его в CRLF (в индексе изменится одна
    строка) и говорит об этом, а не «так и останется»."""
    repo, src = смешанный
    задание = {"repo": str(src), "task": "TASK-1", "date": "06.10.2026", "author": "Автор",
               "modules": [{"модуль": "ОбщийМодуль.ВендорскийМодуль", "edits": [
                   {"line": 5, "lines": 0, "first_line": "#КонецОбласти",
                    "code": "Функция Новая() Экспорт\n\tВозврат 2;\nКонецФункции"}]}]}
    путь = tmp_path / "код.json"
    путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["--apply", str(путь), "--профиль", профиль]) == 0
    текст = capsys.readouterr().out
    assert "файл LF, без BOM — станет CRLF" in текст and "так и останется" not in текст, текст
    assert только_crlf(прочитать(src, "CommonModules/ВендорскийМодуль/Module.bsl"))
    принято, почему = принимает_git(repo, "CommonModules/ВендорскийМодуль/Module.bsl")
    assert принято, почему
    удалено = git(repo, "diff", "--cached", "--numstat").stdout.decode().split()[1]
    assert удалено == "0"


def test_verify_finds_a_file_git_add_refuses_and_normalize_fixes_it(смешанный, профиль, capsys):
    repo, src = смешанный
    написать(src, "CommonModules/мой_Прямой/мой_Прямой.mdo", карточка("CommonModule", "мой_Прямой"), eol="\r\n")
    написать(src, "CommonModules/мой_Прямой/Module.bsl", ["Процедура А() Экспорт", "КонецПроцедуры"])
    ответ = os.path.join(os.path.dirname(профиль), "ответ.json")
    capsys.readouterr()
    main(["--проверить", str(src), "--профиль", профиль, "--json", ответ])
    текст = capsys.readouterr().out
    находки = json.load(open(ответ, encoding="utf-8"))["находки"]
    assert [(f["код"], f["файл"]) for f in находки] == [
        ("ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ", "CommonModules/мой_Прямой/Module.bsl")], текст
    assert "git add откажет" in находки[0]["текст"]
    модуль = "CommonModules/мой_Прямой/Module.bsl"
    assert not принимает_git(repo, модуль)[0]

    assert main(["--нормализовать", str(src), "--apply"]) == 0
    assert только_crlf(прочитать(src, модуль))
    принято, почему = принимает_git(repo, модуль)
    assert принято, почему


def test_in_a_revision_a_file_committed_whole_in_crlf_is_one_finding(смешанный, профиль, capsys):
    """Ревизия: блоб с CRLF при LF в базе — одна находка на файл, и пояснения
    «git нормализует их сам» нет: в коммите git уже ничего не сводит."""
    repo, src = смешанный
    настроить(repo, core_autocrlf="false", core_safecrlf="false")
    написать(src, "CommonModules/ВендорскийМодуль/Module.bsl",
             ["#Область ПрограммныйИнтерфейс", "Функция Публичный() Экспорт", "\tВозврат 1;", "КонецФункции",
              "#КонецОбласти"], eol="\r\n")
    git(repo, "commit", "-q", "-am", "переписан в CRLF")
    настроить(repo, core_autocrlf="true", core_safecrlf="true")
    ответ = os.path.join(os.path.dirname(профиль), "ответ.json")
    capsys.readouterr()
    main(["--проверить", str(src), "--база", "HEAD~1", "--ревизия", "HEAD", "--профиль", профиль, "--json", ответ])
    текст = capsys.readouterr().out
    находки = json.load(open(ответ, encoding="utf-8"))["находки"]
    наши = [f for f in находки if f["код"] == "ФАЙЛ-ПЕРЕВОДЫ-ЧУЖИЕ"]
    assert len(наши) == 1 and "в HEAD~1 файл с LF" in наши[0]["текст"], текст
    assert "нормализует их сам" not in текст
