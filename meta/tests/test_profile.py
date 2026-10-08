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
from meta.api.server import инструкция  # noqa: E402
from meta.application.edit_code.use_case import EditCodeUseCase  # noqa: E402
from meta.composition import mcp_server, соглашения_из_файла  # noqa: E402
from meta.domain import forms as fm  # noqa: E402
from meta.domain.atomic_roles import СхемаРолей  # noqa: E402
from meta.domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения  # noqa: E402
from meta.domain.edits import CodeJob, Edit, ModuleJob, Signature, marker_kind, marker_ranges  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Refuse, Spec, TypeRef  # noqa: E402
from meta.domain.modules import ModuleRef  # noqa: E402
from meta.jobs.code import code_job_from_json  # noqa: E402
from meta.jobs.profile import соглашения  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402


class Мир:
    """Пустая конфигурация: ничего нет, всё свободно."""

    def object_exists(self, kind, name):
        return False

    def __getattr__(self, name):
        return lambda *a, **k: None


def коды(находки):
    return [f.code for f in находки]


def справочник(имя):
    return Spec("Справочник", {"имя": имя, "синоним": "Проба"})


def test_without_a_profile_the_prefix_rule_does_not_apply():
    """Нет соглашения о приставке — проверять нечего: имя без неё не ошибка."""
    вид = kind_of("Справочник")
    assert "МД-ПРЕФИКС" not in коды(вид.check(вид.fill(справочник("Проба")), Мир()))
    вид = kind_of("Справочник", ТЕСТ)
    assert "МД-ПРЕФИКС" in коды(вид.check(вид.fill(справочник("Проба")), Мир()))


def test_without_a_profile_every_form_is_editable():
    """Типовую форму от своей отличает приставка; без неё правило
    «типовая — только кодом» не применяется."""
    правки = fm.FormEdits(("Документ", "РеализацияТоваровУслуг"), "ФормаДокумента")
    вид = fm.FormView(("Документ", "РеализацияТоваровУслуг"), "ФормаДокумента")
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" not in коды(fm.check(правки, вид, None))
    assert "ФОРМА-ТИПОВАЯ-ТОЛЬКО-КОДОМ" in коды(fm.check(правки, вид, None, соглашения=ТЕСТ))
    assert fm.is_ours("РеализацияТоваровУслуг", "ФормаДокумента", None)
    assert not fm.is_ours("РеализацияТоваровУслуг", "ФормаДокумента", ТЕСТ.приставка)


def test_a_rule_can_be_turned_off_or_reweighed():
    """Профиль меняет строгость, а не правило: «выкл» убирает находку,
    «ошибка» делает предупреждение блокирующим."""
    подписка = Spec("ПодпискаНаСобытие", {
        "имя": "мой_ПриЗаписи", "синоним": "При записи",
        "источник": [TypeRef("Документ", "мой_Заявка", "Объект")],
        "событие": "ПриЗаписи", "обработчик": "мой_Модуль.ПриЗаписи"})
    своя = [f for f in ТЕСТ.применить(kind_of("ПодпискаНаСобытие", ТЕСТ).check(подписка, Мир()))
            if f.code == "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ"]
    assert своя and not своя[0].blocking
    строже = Соглашения(приставка="мой_", правила=(("ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ", "ошибка"),))
    своя = [f for f in строже.применить(kind_of("ПодпискаНаСобытие", строже).check(подписка, Мир()))
            if f.code == "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ"]
    assert своя and своя[0].blocking
    мягче = Соглашения(приставка="мой_", правила=(("ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ", "выкл"),))
    assert "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ" not in коды(
        мягче.применить(kind_of("ПодпискаНаСобытие", мягче).check(подписка, Мир())))


def test_a_profile_error_is_a_refusal_not_a_guess():
    """Опечатка в профиле молча выключила бы соглашение — поэтому отказ."""
    assert соглашения({"приставка": "их_"}).приставка == "их_"
    assert соглашения({}) == НЕЙТРАЛЬНЫЕ
    for плохой, слово in (({"префикс": "их_"}, "неизвестные ключи префикс"),
                          ({"приставка": ""}, "непустая строка"),
                          ({"правила": {"МД-ПРЕФИКС": "строго"}}, "допустимы: ошибка"),
                          ({"правила": {"мд префикс": "выкл"}}, "не код находки"),
                          ([], "ожидается объект")):
        with pytest.raises(Refuse) as отказ:
            соглашения(плохой)
        assert слово in str(отказ.value), отказ.value


def test_a_profile_file_is_read_or_refused(tmp_path):
    профиль = tmp_path / "профиль.json"
    профиль.write_text('{"приставка": "их_"}', encoding="utf-8")
    assert соглашения_из_файла(str(профиль)).приставка == "их_"
    битый = tmp_path / "битый.json"
    битый.write_text("{приставка", encoding="utf-8")
    with pytest.raises(Refuse, match="не JSON"):
        соглашения_из_файла(str(битый))
    with pytest.raises(Refuse, match="не прочитан"):
        соглашения_из_файла(str(tmp_path / "нет.json"))


def через_терминал(argv):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        try:
            add.main(list(argv))
        except Refuse as отказ:
            print(f"ОТКАЗ: {отказ}")
    return буфер.getvalue()


def задание(tmp_path, имя):
    """Задание на справочник в пустую выгрузку (только просмотр)."""
    выгрузка = tmp_path / "cf"
    выгрузка.mkdir()
    (выгрузка / "Configuration.xml").write_text(
        open(os.path.join(os.path.dirname(__file__), "эталоны", "формы", "Configuration.xml"),
             encoding="utf-8-sig").read(), encoding="utf-8")
    файл = tmp_path / "задание.json"
    файл.write_text(json.dumps({"repo": str(выгрузка), "objects": [
        {"вид": "Справочник", "поля": {"имя": имя, "синоним": "Проба"}}]}, ensure_ascii=False),
        encoding="utf-8")
    return str(файл)


def test_the_terminal_key_wins_over_the_environment(tmp_path):
    """`--профиль` у терминала важнее `META_PROFILE`: тесты задают тестовый
    профиль переменной, а ключ его перекрывает."""
    другой = tmp_path / "другой.json"
    другой.write_text('{"приставка": "их_"}', encoding="utf-8")
    файл = задание(tmp_path, "мой_Проба")
    assert "МД-ПРЕФИКС" not in через_терминал([файл])
    assert "МД-ПРЕФИКС" in через_терминал([файл, "--профиль", str(другой)])
    assert "после ключа нужен путь" in через_терминал([файл, "--профиль"])


def test_the_mcp_server_takes_the_profile_from_its_environment(tmp_path, monkeypatch):
    """Сервер читает профиль из `META_PROFILE`; явные соглашения — важнее."""
    import asyncio

    файл = задание(tmp_path, "Проба")
    with open(файл, encoding="utf-8") as f:
        job = json.load(f)

    def проверить(сервер):
        ответ = asyncio.run(сервер.call_tool("metadata_check", {
            "repo": job["repo"], "objects": job["objects"]}))
        ответ = ответ[0] if isinstance(ответ, tuple) else ответ
        return "\n".join(блок.text for блок in ответ)

    roots = [job["repo"]]
    assert "МД-ПРЕФИКС" in проверить(mcp_server(roots=roots))
    assert "МД-ПРЕФИКС" not in проверить(mcp_server(roots=roots, соглашения=НЕЙТРАЛЬНЫЕ))
    monkeypatch.delenv("META_PROFILE")
    assert "МД-ПРЕФИКС" not in проверить(mcp_server(roots=roots))


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
    задание = CodeJob(Signature("ЗАДАЧА-1", "06.10.2026", "Петров"),
                      (ModuleJob(ModuleRef(path="Модуль.bsl"),
                                 (Edit(line=3, code="\tПроверка();"),)),))
    результат = EditCodeUseCase(Модули(), соглашения=соглашения_команды).execute([задание])
    (_, решения), = результат.per_module
    return next(строка.strip() for решение in решения for строка in решение.block
                if "фрагмент ДОБАВЛЕН" in строка)


def test_the_team_tag_comes_from_the_profile_not_from_the_job():
    """Метка команды — соглашение команды: без него метка без тега, с ним —
    тег команды перед автором, какой бы он ни был."""
    assert открывающая(НЕЙТРАЛЬНЫЕ) == "// {[+](фрагмент ДОБАВЛЕН), 06.10.2026, Петров #ЗАДАЧА-1"
    assert открывающая(Соглашения(тег_меток="#ITS")) == (
        "// {[+](фрагмент ДОБАВЛЕН), 06.10.2026, #ITS Петров #ЗАДАЧА-1")


def правленое(соглашения_команды, правки):
    """Модуль после правок задания — без файлов."""
    задание = CodeJob(Signature("ЗАДАЧА-1", "06.10.2026", "Петров"),
                      (ModuleJob(ModuleRef(path="Модуль.bsl"), tuple(правки)),))
    результат = EditCodeUseCase(Модули(), соглашения=соглашения_команды).execute([задание])
    (_, решения), = результат.per_module
    return решения


def test_without_markers_an_edit_goes_in_place():
    """«метки.ставить»: false — замена на месте без закомментированной копии,
    удаление удаляет, вставка — как есть; ни одной метки."""
    без_меток = Соглашения(тег_меток="#ITS", метки=False)
    for правка in (Edit(line=2, lines=1, first_line="\tЗначение = 1;", last_line="\tЗначение = 1;",
                        code="\tЗначение = 2;"),
                   Edit(line=2, lines=1, first_line="\tЗначение = 1;", last_line="\tЗначение = 1;",
                        code=""),
                   Edit(line=3, code="\tПроверка();")):
        решения = правленое(без_меток, [правка])
        текст = "\n".join(строка for решение in решения for строка in решение.block)
        assert "фрагмент" not in текст and "//Значение" not in текст
        assert any("метки вставок выключены профилем" in (р.reason or "") for р in решения)
        assert not any(р.marker for р in решения)


def test_the_markers_switch_is_read_from_the_profile():
    assert соглашения({"метки": {"ставить": False}}).метки is False
    assert соглашения({"метки": {"тег": "#TEAM"}}).метки is True
    assert соглашения({}).метки is True
    with pytest.raises(Refuse, match="true или false"):
        соглашения({"метки": {"ставить": "нет"}})


def test_markers_of_any_team_are_parsed():
    """Разбор не знает, чья выгрузка: метка любой команды — метка, а ИД задачи —
    последний «#» в ней, с тегом и без."""
    for строка in ("// #ITS{[+](фрагмент ДОБАВЛЕН), 24.12.2021, Кто #ЗАДАЧА-7",
                   "// {#ITS [+](фрагмент ДОБАВЛЕН), 24.12.2021, Кто #ЗАДАЧА-7",
                   "// {[+](фрагмент ДОБАВЛЕН), 24.12.2021, #ITS Кто #ЗАДАЧА-7",
                   "// {[+](фрагмент ДОБАВЛЕН), 24.12.2021, Кто #ЗАДАЧА-7"):
        assert marker_kind(строка) == "open", строка
        (вставка,) = marker_ranges([строка, "А();", "// } Кто, 24.12.2021"])
        assert вставка["task"] == "ЗАДАЧА-7", строка
    assert marker_kind("// #ITS {Обычный комментарий}") is None


def test_a_tag_in_the_author_is_cut_whatever_team_it_is():
    """Тег, переписанный из соседней метки в автора, — не имя: его ставит
    инструмент по профилю. Другой «#» в авторе — отказ."""
    def автор(кто):
        return code_job_from_json({"task": "ЗАДАЧА-1", "date": "06.10.2026", "author": кто,
                                   "path": "Модуль.bsl", "edits": [{"line": 1, "code": "А();"}]}
                                  ).signature.author
    assert автор("#ITS Петров") == "Петров" and автор("#TEAM Петров") == "Петров"
    with pytest.raises(Refuse, match="метку команды и ИД задачи ставит инструмент"):
        автор("Петров #ЗАДАЧА-1")


def test_the_marker_section_of_a_profile_is_checked():
    assert соглашения({"метки": {"тег": "#ITS"}}).тег_меток == "#ITS"
    assert соглашения({"приставка": "их_"}).тег_меток is None
    for плохой, слово in (({"метки": "#ITS"}, "«метки» — объект"),
                          ({"метки": {"метка": "#ITS"}}, "неизвестные ключи метка"),
                          ({"метки": {"тег": "ITS"}}, "«#» и слово без пробелов"),
                          ({"метки": {"тег": "#I TS"}}, "«#» и слово без пробелов"),
                          ({"метки": {"тег": "#A#B"}}, "«#» и слово без пробелов")):
        with pytest.raises(Refuse) as отказ:
            соглашения(плохой)
        assert слово in str(отказ.value), отказ.value


def test_the_server_tells_the_team_conventions_up_front():
    """Приставку и метку команды агент узнаёт из инструкции сервера, а не из
    отказа; без профиля инструкция не называет ничьей приставки."""
    assert "«их_»" in инструкция(Соглашения(приставка="их_", тег_меток="#ITS"))
    assert "«#ITS»" in инструкция(Соглашения(приставка="их_", тег_меток="#ITS"))
    нейтральная = инструкция(НЕЙТРАЛЬНЫЕ)
    assert "приставки доработок нет" in нейтральная and "мой_" not in нейтральная


def test_the_scheme_section_of_a_profile_is_checked():
    схема = соглашения({"атомарныеРоли": {"имя": "их_{вид}_{объект}_{право}",
                                          "синоним": "А {синоним} {право}"}}).атомарные_роли
    assert схема == СхемаРолей("их_{вид}_{объект}_{право}", "А {синоним} {право}")
    for плохой, слово in (({"атомарныеРоли": "их_"}, "«атомарныеРоли» — объект"),
                          ({"атомарныеРоли": {"имя": "их_{вид}_{объект}_{право}"}},
                           "нужны «имя» и «синоним»"),
                          ({"атомарныеРоли": {"имя": "а", "синоним": "б", "кто": "в"}},
                           "неизвестные ключи кто"),
                          ({"атомарныеРоли": {"имя": "их_{вид}", "синоним": "б"}},
                           "каждое ровно один раз")):
        with pytest.raises(Refuse) as отказ:
            соглашения(плохой)
        assert слово in str(отказ.value), отказ.value


def test_a_prefix_list_names_the_main_prefix_first():
    """Приставок у команды может быть несколько — например, тестовые модули
    «ОМ_<приставка>…»: все они свои, но новым именам ставится основная, первая."""
    команда = соглашения({"приставка": ["мой_", "ОМ_мой_"]})
    assert команда.приставка == "мой_" and команда.другие_приставки == ("ОМ_мой_",)
    assert команда.своё("ОМ_мой_Тест") and команда.своё("мой_Х") and not команда.своё("Чужой")
    находки = kind_of("ОбщийМодуль", команда).check(
        Spec("ОбщийМодуль", {"имя": "ОМ_мой_Тест", "синоним": "Тест"}), None)
    assert "МД-ПРЕФИКС" not in [f.code for f in находки]
    for плохо in ([], ["мой_", ""], ["мой_", 7]):
        with pytest.raises(Refuse, match="непустая строка или список строк"):
            соглашения({"приставка": плохо})
