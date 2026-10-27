"""Профиль соглашений команды: правила — в домене, их значения и строгость — в профиле.

Инструмент не зависит от соглашений одной команды: без профиля правила,
которым нужна приставка, не применяются, а профиль включает, выключает и
перевзвешивает правила, не меняя их.
"""

import io
import json
import os
import sys
from contextlib import redirect_stdout

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import meta.add as add  # noqa: E402
from meta.api.server import instructions  # noqa: E402
from meta.application.edit_code.use_case import EditCodeUseCase  # noqa: E402
from meta.composition import conventions_from_file, mcp_server  # noqa: E402
from meta.domain import forms as fm  # noqa: E402
from meta.domain.atomic_roles import RoleSchema  # noqa: E402
from meta.domain.conventions import NEUTRAL, Conventions  # noqa: E402
from meta.domain.edits import CodeJob, Edit, ModuleJob, Signature, marker_kind, marker_ranges  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Refuse, Spec, TypeRef  # noqa: E402
from meta.domain.modules import ModuleRef  # noqa: E402
from meta.jobs.code import code_job_from_json  # noqa: E402
from meta.jobs.profile import conventions  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402


class Мир:
    """Пустая конфигурация: ничего нет, всё свободно."""

    def object_exists(self, kind, name):
        return False

    def __getattr__(self, name):
        return lambda *a, **k: None


def codes(findings):
    return [f.code for f in findings]


def справочник(name):
    return Spec("Справочник", {"имя": name, "синоним": "Проба"})


def test_without_a_profile_the_prefix_rule_does_not_apply():
    """Нет соглашения о приставке — проверять нечего: имя без неё не ошибка."""
    kind = kind_of("Справочник")
    assert "МД-ПРЕФИКС" not in codes(kind.check(kind.fill(справочник("Проба")), Мир()))
    kind = kind_of("Справочник", ТЕСТ)
    assert "МД-ПРЕФИКС" in codes(kind.check(kind.fill(справочник("Проба")), Мир()))


def test_without_a_profile_every_form_is_editable():
    """Типовую форму от своей отличает приставка; без неё правило
    «типовая — только кодом» не применяется."""
    edit_jobs = fm.FormEdits(("Документ", "РеализацияТоваровУслуг"), "ФормаДокумента")
    kind = fm.FormView(("Документ", "РеализацияТоваровУслуг"), "ФормаДокумента")
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" not in codes(fm.check(edit_jobs, kind, None))
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" in codes(fm.check(edit_jobs, kind, None, conventions=ТЕСТ))
    assert fm.is_ours("РеализацияТоваровУслуг", "ФормаДокумента", None)
    assert not fm.is_ours("РеализацияТоваровУслуг", "ФормаДокумента", ТЕСТ.prefix)


def test_a_rule_can_be_turned_off_or_reweighed():
    """Профиль меняет строгость, а не правило: «выкл» убирает находку,
    «ошибка» делает предупреждение блокирующим."""
    подписка = Spec("ПодпискаНаСобытие", {
        "имя": "мой_ПриЗаписи", "синоним": "При записи",
        "источник": [TypeRef("Документ", "мой_Заявка", "Объект")],
        "событие": "ПриЗаписи", "обработчик": "мой_Модуль.ПриЗаписи"})
    own_item = [f for f in ТЕСТ.apply(kind_of("ПодпискаНаСобытие", ТЕСТ).check(подписка, Мир()))
            if f.code == "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ"]
    assert own_item and not own_item[0].blocking
    строже = Conventions(prefix="мой_", rules=(("ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ", "ошибка"),))
    own_item = [f for f in строже.apply(kind_of("ПодпискаНаСобытие", строже).check(подписка, Мир()))
            if f.code == "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ"]
    assert own_item and own_item[0].blocking
    мягче = Conventions(prefix="мой_", rules=(("ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ", "выкл"),))
    assert "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ" not in codes(
        мягче.apply(kind_of("ПодпискаНаСобытие", мягче).check(подписка, Мир())))


def test_a_profile_error_is_a_refusal_not_a_guess():
    """Опечатка в профиле молча выключила бы соглашение — поэтому отказ."""
    assert conventions({"приставка": "их_"}).prefix == "их_"
    assert conventions({}) == NEUTRAL
    for плохой, word in (({"префикс": "их_"}, "неизвестные ключи префикс"),
                          ({"приставка": ""}, "непустая строка"),
                          ({"правила": {"МД-ПРЕФИКС": "строго"}}, "допустимы: ошибка"),
                          ({"правила": {"мд префикс": "выкл"}}, "не код находки"),
                          ([], "ожидается объект")):
        with pytest.raises(Refuse) as refusal:
            conventions(плохой)
        assert word in str(refusal.value), refusal.value


def test_a_profile_file_is_read_or_refused(tmp_path):
    профиль = tmp_path / "профиль.json"
    профиль.write_text('{"приставка": "их_"}', encoding="utf-8")
    assert conventions_from_file(str(профиль)).prefix == "их_"
    битый = tmp_path / "битый.json"
    битый.write_text("{приставка", encoding="utf-8")
    with pytest.raises(Refuse, match="не JSON"):
        conventions_from_file(str(битый))
    with pytest.raises(Refuse, match="не прочитан"):
        conventions_from_file(str(tmp_path / "нет.json"))


def через_терминал(argv):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        try:
            add.main(list(argv))
        except Refuse as refusal:
            print(f"ОТКАЗ: {refusal}")
    return буфер.getvalue()


def job_spec(tmp_path, name):
    """Задание на справочник в пустую выгрузку (только просмотр)."""
    выгрузка = tmp_path / "cf"
    выгрузка.mkdir()
    (выгрузка / "Configuration.xml").write_text(
        open(os.path.join(os.path.dirname(__file__), "эталоны", "формы", "Configuration.xml"),
             encoding="utf-8-sig").read(), encoding="utf-8")
    file = tmp_path / "задание.json"
    file.write_text(json.dumps({"repo": str(выгрузка), "objects": [
        {"вид": "Справочник", "поля": {"имя": name, "синоним": "Проба"}}]}, ensure_ascii=False),
        encoding="utf-8")
    return str(file)


def test_the_terminal_key_wins_over_the_environment(tmp_path):
    """`--профиль` у терминала важнее `META_PROFILE`: тесты задают тестовый
    профиль переменной, а ключ его перекрывает."""
    другой = tmp_path / "другой.json"
    другой.write_text('{"приставка": "их_"}', encoding="utf-8")
    file = job_spec(tmp_path, "мой_Проба")
    assert "МД-ПРЕФИКС" not in через_терминал([file])
    assert "МД-ПРЕФИКС" in через_терминал([file, "--профиль", str(другой)])
    assert "после ключа нужен путь" in через_терминал([file, "--профиль"])


def test_the_mcp_server_takes_the_profile_from_its_environment(tmp_path, monkeypatch):
    """Сервер читает профиль из `META_PROFILE`; явные соглашения — важнее."""
    import asyncio

    file = job_spec(tmp_path, "Проба")
    with open(file, encoding="utf-8") as f:
        job = json.load(f)

    def check(сервер):
        answer = asyncio.run(сервер.call_tool("metadata_check", {
            "repo": job["repo"], "objects": job["objects"]}))
        answer = answer[0] if isinstance(answer, tuple) else answer
        return "\n".join(block.text for block in answer)

    roots = [job["repo"]]
    assert "МД-ПРЕФИКС" in check(mcp_server(roots=roots))
    assert "МД-ПРЕФИКС" not in check(mcp_server(roots=roots, conventions=NEUTRAL))
    monkeypatch.delenv("META_PROFILE")
    assert "МД-ПРЕФИКС" not in check(mcp_server(roots=roots))


# --- метка команды в метках вставок -----------------------------------------------

ТЕЛО = ["Процедура Проба()", "\tЗначение = 1;", "КонецПроцедуры"]


class Модули:
    """Один модуль в памяти: сценарию кода файлы не нужны, нужны строки."""

    def read(self, ref):
        return list(ТЕЛО)

    def address(self, ref):
        return None

    def base(self, ref, rev=None):
        return None

    def is_new(self, ref, rev=None):
        return False

    def prepare(self, changes):
        return None

    def file_format(self, ref):
        return None


def открывающая(соглашения_команды):
    """Открывающая метка чистой вставки перед «КонецПроцедуры» по соглашениям."""
    job_spec = CodeJob(Signature("ЗАДАЧА-1", "06.10.2026", "Петров"),
                      (ModuleJob(ModuleRef(path="Модуль.bsl"),
                                 (Edit(line=3, code="\tПроверка();"),)),))
    результат = EditCodeUseCase(Модули(), conventions=соглашения_команды).execute([job_spec])
    (_, decisions), = результат.per_module
    return next(line.strip() for решение in decisions for line in решение.block
                if "фрагмент ДОБАВЛЕН" in line)


def test_the_team_tag_comes_from_the_profile_not_from_the_job():
    """Метка команды — соглашение команды: без него метка без тега, с ним —
    тег команды перед автором, какой бы он ни был."""
    assert открывающая(NEUTRAL) == "// {[+](фрагмент ДОБАВЛЕН), 06.10.2026, Петров #ЗАДАЧА-1"
    assert открывающая(Conventions(marker_tag="#ITS")) == (
        "// {[+](фрагмент ДОБАВЛЕН), 06.10.2026, #ITS Петров #ЗАДАЧА-1")


def правленое(соглашения_команды, edit_jobs):
    """Модуль после правок задания — без файлов."""
    job_spec = CodeJob(Signature("ЗАДАЧА-1", "06.10.2026", "Петров"),
                      (ModuleJob(ModuleRef(path="Модуль.bsl"), tuple(edit_jobs)),))
    результат = EditCodeUseCase(Модули(), conventions=соглашения_команды).execute([job_spec])
    (_, decisions), = результат.per_module
    return decisions


def test_without_markers_an_edit_goes_in_place():
    """«метки.ставить»: false — замена на месте без закомментированной копии,
    удаление удаляет, вставка — как есть; ни одной метки."""
    без_меток = Conventions(marker_tag="#ITS", markers=False)
    for edit_job in (Edit(line=2, lines=1, first_line="\tЗначение = 1;", last_line="\tЗначение = 1;",
                        code="\tЗначение = 2;"),
                   Edit(line=2, lines=1, first_line="\tЗначение = 1;", last_line="\tЗначение = 1;",
                        code=""),
                   Edit(line=3, code="\tПроверка();")):
        decisions = правленое(без_меток, [edit_job])
        text = "\n".join(line for решение in decisions for line in решение.block)
        assert "фрагмент" not in text and "//Значение" not in text
        assert any("метки вставок выключены профилем" in (rr.reason or "") for rr in decisions)
        assert not any(rr.marker for rr in decisions)


def test_the_markers_switch_is_read_from_the_profile():
    assert conventions({"метки": {"ставить": False}}).markers is False
    assert conventions({"метки": {"тег": "#TEAM"}}).markers is True
    assert conventions({}).markers is True
    with pytest.raises(Refuse, match="true или false"):
        conventions({"метки": {"ставить": "нет"}})


def test_markers_of_any_team_are_parsed():
    """Разбор не знает, чья выгрузка: метка любой команды — метка, а ИД задачи —
    последний «#» в ней, с тегом и без."""
    for line in ("// #ITS{[+](фрагмент ДОБАВЛЕН), 24.12.2021, Кто #ЗАДАЧА-7",
                   "// {#ITS [+](фрагмент ДОБАВЛЕН), 24.12.2021, Кто #ЗАДАЧА-7",
                   "// {[+](фрагмент ДОБАВЛЕН), 24.12.2021, #ITS Кто #ЗАДАЧА-7",
                   "// {[+](фрагмент ДОБАВЛЕН), 24.12.2021, Кто #ЗАДАЧА-7"):
        assert marker_kind(line) == "open", line
        (вставка,) = marker_ranges([line, "А();", "// } Кто, 24.12.2021"])
        assert вставка["task"] == "ЗАДАЧА-7", line
    assert marker_kind("// #ITS {Обычный комментарий}") is None


def test_a_tag_in_the_author_is_cut_whatever_team_it_is():
    """Тег, переписанный из соседней метки в автора, — не имя: его ставит
    инструмент по профилю. Другой «#» в авторе — отказ."""
    def автор(who):
        return code_job_from_json({"task": "ЗАДАЧА-1", "date": "06.10.2026", "author": who,
                                   "path": "Модуль.bsl", "edits": [{"line": 1, "code": "А();"}]}
                                  ).signature.author
    assert автор("#ITS Петров") == "Петров" and автор("#TEAM Петров") == "Петров"
    with pytest.raises(Refuse, match="метку команды и ИД задачи ставит инструмент"):
        автор("Петров #ЗАДАЧА-1")


def test_the_marker_section_of_a_profile_is_checked():
    assert conventions({"метки": {"тег": "#ITS"}}).marker_tag == "#ITS"
    assert conventions({"приставка": "их_"}).marker_tag is None
    for плохой, word in (({"метки": "#ITS"}, "«метки» — объект"),
                          ({"метки": {"метка": "#ITS"}}, "неизвестные ключи метка"),
                          ({"метки": {"тег": "ITS"}}, "«#» и слово без пробелов"),
                          ({"метки": {"тег": "#I TS"}}, "«#» и слово без пробелов"),
                          ({"метки": {"тег": "#A#B"}}, "«#» и слово без пробелов")):
        with pytest.raises(Refuse) as refusal:
            conventions(плохой)
        assert word in str(refusal.value), refusal.value


def test_the_server_tells_the_team_conventions_up_front():
    """Приставку и метку команды агент узнаёт из инструкции сервера, а не из
    отказа; без профиля инструкция не называет ничьей приставки."""
    assert "«их_»" in instructions(Conventions(prefix="их_", marker_tag="#ITS"))
    assert "«#ITS»" in instructions(Conventions(prefix="их_", marker_tag="#ITS"))
    нейтральная = instructions(NEUTRAL)
    assert "приставки доработок нет" in нейтральная and "мой_" not in нейтральная


def test_the_scheme_section_of_a_profile_is_checked():
    schema = conventions({"атомарныеРоли": {"имя": "их_{вид}_{объект}_{право}",
                                          "синоним": "А {синоним} {право}"}}).atomic_roles
    assert schema == RoleSchema("их_{вид}_{объект}_{право}", "А {синоним} {право}")
    for плохой, word in (({"атомарныеРоли": "их_"}, "«атомарныеРоли» — объект"),
                          ({"атомарныеРоли": {"имя": "их_{вид}_{объект}_{право}"}},
                           "нужны «имя» и «синоним»"),
                          ({"атомарныеРоли": {"имя": "а", "синоним": "б", "кто": "в"}},
                           "неизвестные ключи кто"),
                          ({"атомарныеРоли": {"имя": "их_{вид}", "синоним": "б"}},
                           "каждое ровно один раз")):
        with pytest.raises(Refuse) as refusal:
            conventions(плохой)
        assert word in str(refusal.value), refusal.value


def test_a_prefix_list_names_the_main_prefix_first():
    """Приставок у команды может быть несколько — например, тестовые модули
    «ОМ_<приставка>…»: все они свои, но новым именам ставится основная, первая."""
    command = conventions({"приставка": ["мой_", "ОМ_мой_"]})
    assert command.prefix == "мой_" and command.other_prefixes == ("ОМ_мой_",)
    assert command.is_own("ОМ_мой_Тест") and command.is_own("мой_Х") and not command.is_own("Чужой")
    findings = kind_of("ОбщийМодуль", command).check(
        Spec("ОбщийМодуль", {"имя": "ОМ_мой_Тест", "синоним": "Тест"}), None)
    assert "МД-ПРЕФИКС" not in [f.code for f in findings]
    for плохо in ([], ["мой_", ""], ["мой_", 7]):
        with pytest.raises(Refuse, match="непустая строка или список строк"):
            conventions({"приставка": плохо})
