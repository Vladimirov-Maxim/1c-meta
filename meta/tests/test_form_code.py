"""Код доработки формы: язык платформы и подключаемый диалект команды.

Язык по умолчанию — платформа: её методы есть в любой конфигурации. Свой язык —
соглашение команды: профиль называет файл-диалект (`кодФормы.диалект`), и всё,
что зависит от языка, инструмент берёт из него. Механизм проверяется на учебном
диалекте `диалекты/сборщик.py` с выдуманным языком.
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import platform_code  # noqa: E402
from meta.api.server import инструкция  # noqa: E402
from meta.composition import mcp_server, диалект_из_файла, соглашения_из_файла  # noqa: E402
from meta.domain import forms as fm  # noqa: E402
from meta.domain import model as dm  # noqa: E402
from meta.domain.conventions import Conventions, FormCode  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402
from meta.jobs import dialect  # noqa: E402
from meta.jobs.profile import conventions  # noqa: E402

ЭТАЛОНЫ = os.path.join(os.path.dirname(__file__), "эталоны", "формы")
СБОРЩИК = os.path.join(os.path.dirname(__file__), "диалекты", "сборщик.py")


def правки(**kwargs):
    kwargs.setdefault("owner", ("Документ", "АвансовыйОтчет"))
    kwargs.setdefault("name", "ФормаДокумента")
    kwargs.setdefault("as_code", True)
    return fm.FormEdits(**kwargs)


def kind(**elements):
    """Прочитанная форма: имя -> (вид, родитель); порядок — как перечислены."""
    return fm.FormView(("Документ", "АвансовыйОтчет"), "ФормаДокумента",
                       elements={name: fm.ViewItem(*description) for name, description in elements.items()},
                       main="Объект", assignment="Документа")


ШАПКА = kind(ГруппаШапка=("ГруппаФормы",), Дата=("ПолеВвода", "ГруппаШапка"),
            Комментарий=("ПолеВвода", "ГруппаШапка"),
            ФормаКоманднаяПанель=("КоманднаяПанель",))


def образец():
    return правки(
        attributes=[fm.FormAttribute("мой_Состояние", dialect.value_type_from_text("Строка(20)")),
                    fm.FormAttribute("мой_Строки", dialect.value_type_from_text("ТаблицаЗначений")),
                    fm.FormAttribute("Номенклатура", dialect.value_type_from_text("Справочник.Номенклатура"),
                                     table="мой_Строки")],
        commands=[fm.FormCommand("мой_Проверить", "Проверить")],
        elements=[fm.FormElement("ПолеВвода", "мой_Состояние", "мой_Состояние",
                                 parent="ГруппаШапка", before="Комментарий",
                                 properties={"ТолькоПросмотр": True},
                                 events={"ПриИзменении": "мой_СостояниеПриИзменении"}),
                  fm.FormElement("Надпись", "мой_Подсказка", parent="ГруппаШапка",
                                 properties={"Заголовок": "Заполняется автоматически"}),
                  fm.FormElement("Кнопка", "мой_Проверить", command="мой_Проверить",
                                 parent="ФормаКоманднаяПанель")])


def сборщик():
    """Язык учебного диалекта с его настройкой."""
    return FormCode("сборщик", диалект_из_файла(СБОРЩИК), (("модуль", "мой_Формы"),))


# --- язык платформы ---------------------------------------------------------------

def test_the_platform_code_uses_only_platform_methods():
    """Реквизиты — одним `ИзменитьРеквизиты`, команда — `Команды.Добавить` с
    заголовком и действием, элемент — `Вставить` перед соседом; ни слова
    чьей-либо библиотеки."""
    code = platform_code.render(образец(), ШАПКА)
    assert code.startswith("ДобавляемыеРеквизиты = Новый Массив;\n"), code
    assert ('ДобавляемыеРеквизиты.Добавить(Новый РеквизитФормы("мой_Состояние", '
            'Новый ОписаниеТипов("Строка", , Новый КвалификаторыСтроки(20))));') in code
    assert ('ДобавляемыеРеквизиты.Добавить(Новый РеквизитФормы("мой_Строки", '
            'Новый ОписаниеТипов("ТаблицаЗначений")));') in code
    # колонка таблицы — реквизит с путём к таблице
    assert ('ДобавляемыеРеквизиты.Добавить(Новый РеквизитФормы("Номенклатура", '
            'Новый ОписаниеТипов("СправочникСсылка.Номенклатура"), "мой_Строки"));') in code
    assert "Форма.ИзменитьРеквизиты(ДобавляемыеРеквизиты);" in code
    assert ('Команда = Форма.Команды.Добавить("мой_Проверить");\n'
            'Команда.Заголовок = "Проверить";\n'
            'Команда.Действие = "Подключаемый_мой_Проверить";') in code
    assert ('Элемент = Форма.Элементы.Вставить("мой_Состояние", Тип("ПолеФормы"), '
            'Форма.Элементы.ГруппаШапка, Форма.Элементы.Комментарий);\n'
            'Элемент.Вид = ВидПоляФормы.ПолеВвода;\n'
            'Элемент.ПутьКДанным = "мой_Состояние";\n'
            'Элемент.ТолькоПросмотр = Истина;\n'
            'Элемент.УстановитьДействие("ПриИзменении", '
            '"Подключаемый_мой_СостояниеПриИзменении");') in code
    assert ('Элемент = Форма.Элементы.Добавить("мой_Подсказка", Тип("ДекорацияФормы"), '
            'Форма.Элементы.ГруппаШапка);\nЭлемент.Вид = ВидДекорацииФормы.Надпись;\n'
            'Элемент.Заголовок = "Заполняется автоматически";') in code
    # кнопке в панели вид ставится явно
    assert ('Элемент = Форма.Элементы.Добавить("мой_Проверить", Тип("КнопкаФормы"), '
            'Форма.Элементы.ФормаКоманднаяПанель);\n'
            'Элемент.Вид = ВидКнопкиФормы.КнопкаКоманднойПанели;\n'
            'Элемент.ИмяКоманды = "мой_Проверить";') in code


def test_every_element_kind_is_written_by_the_platform():
    for вид_элемента in fm.ELEMENT_KINDS:
        задание = правки(elements=[fm.FormElement(вид_элемента, "мой_Э", parent="ГруппаШапка")])
        assert 'Тип("' in platform_code.render(задание, ШАПКА), вид_элемента


def test_the_platform_writes_composite_types_qualifiers_and_titles():
    """Квалификаторы — в порядке конструктора (числа, строки, даты), составной
    тип — строкой имён, заголовок — четвёртым параметром."""
    assert platform_code.type_description(dialect.value_type_from_text("Строка(20) | Булево")) == (
        'Новый ОписаниеТипов("Строка,Булево", , Новый КвалификаторыСтроки(20))')
    assert platform_code.type_description(dm.NumberType(15, 2, nonnegative=True)) == (
        'Новый ОписаниеТипов("Число", Новый КвалификаторыЧисла(15, 2, '
        'ДопустимыйЗнак.Неотрицательный))')
    assert platform_code.type_description(dm.DateType("Дата")) == (
        'Новый ОписаниеТипов("Дата", , , Новый КвалификаторыДаты(ЧастиДаты.Дата))')
    assert platform_code.type_description(dm.StringType(10, fixed=True)) == (
        'Новый ОписаниеТипов("Строка", , Новый КвалификаторыСтроки(10, '
        'ДопустимаяДлина.Фиксированная))')
    code = platform_code.render(правки(attributes=[
        fm.FormAttribute("мой_Сумма", dm.NumberType(15, 2), "Сумма к оплате")]))
    assert ('Новый РеквизитФормы("мой_Сумма", Новый ОписаниеТипов("Число", '
            'Новый КвалификаторыЧисла(15, 2)), , "Сумма к оплате")') in code


def test_after_turns_into_before_with_the_neighbours_parent():
    """«После» без родителя: перед следующим соседом и в его родителе — не на
    верхнем уровне формы."""
    after = правки(elements=[fm.FormElement("ПолеВвода", "мой_П", "Объект.Комментарий",
                                            after="Дата")])
    assert ('Элемент = Форма.Элементы.Вставить("мой_П", Тип("ПолеФормы"), '
            'Форма.Элементы.ГруппаШапка, Форма.Элементы.Комментарий);') in (
        platform_code.render(after, ШАПКА))
    # последний в группе — в конец той же группы, без места
    последний = правки(elements=[fm.FormElement("ПолеВвода", "мой_П", "Объект.Комментарий",
                                               after="Комментарий")])
    assert ('Элемент = Форма.Элементы.Добавить("мой_П", Тип("ПолеФормы"), '
            'Форма.Элементы.ГруппаШапка);') in platform_code.render(последний, ШАПКА)
    # соседа нет в форме — отказ
    with pytest.raises(Refuse):
        platform_code.render(правки(elements=[fm.FormElement("ПолеВвода", "мой_П", after="Нет")]),
                             ШАПКА)


def test_a_standard_command_is_refused():
    стандартная = правки(elements=[fm.FormElement("Кнопка", "К", command="Стандартная.Write")])
    with pytest.raises(Refuse, match="стандартную команду"):
        platform_code.render(стандартная, ШАПКА)


МОДУЛЬ = ["#Область ПрограммныйИнтерфейс", "",
          "Процедура ФормаДокумента_ПриСозданииНаСервере(Форма) Экспорт", "",
          "\tЭлемент = Форма.Элементы.Добавить(\"мой_Старое\", Тип(\"ПолеФормы\"));", "",
          "КонецПроцедуры", "", "#КонецОбласти"]


def test_platform_code_extends_an_existing_procedure_before_its_end():
    """Процедура доработки уже есть — код дописывается в неё перед
    «КонецПроцедуры», а не второй процедурой. Узнаётся по единственному
    параметру — форме."""
    procedure = fm.code_procedure(МОДУЛЬ, "ФормаДокумента_ПриСозданииНаСервере", FormCode())
    assert procedure == fm.CodeProcedure(3, 7, None, 7)
    assert fm.code_procedure(МОДУЛЬ, "ФормаДокумента_ПриСозданииНаСервере", FormCode(), 2) is None
    задание = правки(code_module="ОбщийМодуль.мой_Платежи")
    места, пояснения = fm.code_anchors(задание, МОДУЛЬ, None, FormCode())
    assert места == [fm.CodePlace("дополнение", "ОбщийМодуль.мой_Платежи", 7, "КонецПроцедуры",
                                  None, "код перед её «КонецПроцедуры»")]
    assert "её «КонецПроцедуры»" in пояснения[0], пояснения
    assert fm.code_addition("\nЭлемент = 1;\n", места[0], FormCode()) == "Элемент = 1;\n"


# --- профиль: язык и диалект ------------------------------------------------------

def test_the_code_section_of_a_profile_is_checked():
    assert conventions({}).form_code == FormCode()
    assert conventions({"кодФормы": {"язык": "платформа"}}).form_code == FormCode()
    for плохой, word in (({"кодФормы": "платформа"}, "«кодФормы» — объект"),
                          ({"кодФормы": {"язык": "сборщик"}}, "не встроен"),
                          ({"кодФормы": {"язык": "платформа", "модуль": "М"}},
                           "у языка платформы настроек нет"),
                          ({"кодФормы": {"язык": "сборщик", "диалект": "сборщик.py"}},
                           "только из файла профиля"),
                          ({"кодФормы": {"язык": "сборщик", "диалект": ""}}, "путь к файлу")):
        with pytest.raises(Refuse) as refusal:
            conventions(плохой)
        assert word in str(refusal.value), refusal.value


def профиль(папка, code):
    path = os.path.join(папка, "профиль.json")
    with open(path, "w", encoding="utf-8") as файл:
        json.dump({"приставка": "мой_", "кодФормы": code}, файл, ensure_ascii=False)
    return path


def test_a_dialect_is_found_next_to_the_profile(tmp_path):
    """Путь к диалекту — от файла профиля: профиль и диалект команда держит
    вместе, и на другой машине путь не меняется."""
    shutil.copyfile(СБОРЩИК, tmp_path / "сборщик.py")
    form_code = соглашения_из_файла(профиль(str(tmp_path), {
        "язык": "сборщик", "диалект": "сборщик.py", "модуль": "мой_Формы"})).form_code
    assert (form_code.language, form_code.dialect.name, form_code.vocabulary) == (
        "сборщик", "сборщик", {"модуль": "мой_Формы"})
    assert not form_code.builtin


def test_a_wrong_dialect_is_refused_with_its_reason(tmp_path):
    shutil.copyfile(СБОРЩИК, tmp_path / "сборщик.py")
    (tmp_path / "пустой.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "битый.py").write_text("DIALECT = (\n", encoding="utf-8")
    for code, word in (({"язык": "сборщик", "диалект": "нет.py", "модуль": "М"}, "файла диалекта"),
                       ({"язык": "сборщик", "диалект": "пустой.py"}, "нет объекта «DIALECT»"),
                       ({"язык": "сборщик", "диалект": "битый.py"}, "не загрузился"),
                       ({"язык": "другой", "диалект": "сборщик.py", "модуль": "М"},
                        "подключён не тот файл"),
                       ({"язык": "сборщик", "диалект": "сборщик.py"}, "одна настройка")):
        with pytest.raises(Refuse) as refusal:
            соглашения_из_файла(профиль(str(tmp_path), code))
        assert word in str(refusal.value), (code, refusal.value)


def test_the_server_names_the_code_language():
    assert "методами платформы" in инструкция(Conventions(prefix="их_"))
    assert "сборщиком форм («мой_Формы.Сборщик(Форма)»)" in инструкция(
        Conventions(prefix="их_", form_code=сборщик()))


# --- диалект: всё, что зависит от языка, — из его файла ------------------------------

def test_the_dialect_recognises_and_extends_its_procedure():
    module = ["#Область ПрограммныйИнтерфейс", "",
              "Процедура ФормаДокумента_ПриСозданииНаСервере(Форма) Экспорт", "",
              "\tСборка = мой_Формы.Сборщик(Форма);", "\tСборка.Элемент(\"мой_Старое\");",
              "\tСборка.Готово();", "", "КонецПроцедуры", "", "#КонецОбласти"]
    language = сборщик()
    procedure = fm.code_procedure(module, "ФормаДокумента_ПриСозданииНаСервере", language)
    assert procedure == fm.CodeProcedure(3, 9, "Сборка", 7)
    # язык платформы ту же процедуру узнаёт по параметру и дописывает в её конец
    assert fm.code_procedure(module, "ФормаДокумента_ПриСозданииНаСервере",
                             FormCode()).insert_line == 9
    места, пояснения = fm.code_anchors(правки(code_module="ОбщийМодуль.мой_Формы"), module,
                                       None, language)
    assert места[0].where == "код перед «Сборка.Готово();»", места
    assert "«Сборка.Готово();»" in пояснения[0], пояснения
    code = language.dialect.code(правки(elements=[fm.FormElement("Надпись", "мой_Н")]), None,
                           language.vocabulary)
    assert fm.code_addition(code, места[0], language) == 'Сборка.Элемент("мой_Н");\n'
    # повтор узнаётся по заводящему вызову языка
    repeat = правки(elements=[fm.FormElement("Надпись", "мой_Старое")])
    assert any(f.code == "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ"
               for f in fm._added_by_code(repeat, module, "в модуле", "повтор", language))
    assert not fm._added_by_code(repeat, module, "в модуле", "повтор", FormCode())


def test_the_dialect_speaks_in_the_notes_and_findings():
    after = правки(elements=[fm.FormElement("ПолеВвода", "мой_П", "Объект.Комментарий",
                                            after="Дата")])
    assert 'Сборка.Перед("Комментарий")' in fm.placement_notes(after, ШАПКА, сборщик())[0]
    assert "Элементы.Вставить(…, Элементы.Комментарий)" in fm.placement_notes(
        after, ШАПКА, FormCode())[0]
    с_заголовком = правки(attributes=[fm.FormAttribute("мой_С", dm.BooleanType(), "Флаг")])
    коды = {f.code for f in fm._check_code_mode(с_заголовком, "мой_", сборщик())}
    assert "ФОРМА-КОД-СБОРЩИК-ЗАГОЛОВОК" in коды
    assert "ФОРМА-КОД-СБОРЩИК-ЗАГОЛОВОК" not in {
        f.code for f in fm._check_code_mode(с_заголовком, "мой_", FormCode())}


# --- сквозной путь через сервер ------------------------------------------------------

@pytest.fixture
def выгрузка():
    root = tempfile.mkdtemp(prefix="meta-code-")
    for name, эталон in (("Configuration.xml", "Configuration.xml"),
                        ("Documents/мой_ПробаСДвижениями.xml", "мой_ПробаСДвижениями.до.xml")):
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(os.path.join(ЭТАЛОНЫ, эталон), path)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _сервер(выгрузка, conventions):
    сервер = mcp_server(roots=[выгрузка], conventions=conventions)

    def вызвать(инструмент, **аргументы):
        ответ = asyncio.run(сервер.call_tool(инструмент, аргументы))
        ответ = ответ[0] if isinstance(ответ, tuple) else ответ
        return "\n".join(блок.text for блок in ответ)
    return вызвать


ФОРМА = "Документ.мой_ПробаСДвижениями.мой_Проба"
ПОЛЕ = {"форма": ФОРМА, "код": True,
        "элементы": [{"вид": "ПолеВвода", "имя": "мой_Отметка", "путь": "Объект.Комментарий"}]}


def test_a_team_without_a_dialect_gets_platform_code_from_the_server(выгрузка):
    """Профиль без «кодФормы» — ответ сервера с кодом платформы."""
    вызвать = _сервер(выгрузка, Conventions(prefix="мой_"))
    вызвать("forms_apply", repo=выгрузка, forms=[
        {"форма": ФОРМА, "создать": {"назначение": "Документа", "синоним": "Проба"}}])
    text = вызвать("forms_check", repo=выгрузка, forms=[ПОЛЕ])
    assert f"Код доработки формы для «{ФОРМА}»" in text, text
    assert '\tЭлемент = Форма.Элементы.Добавить("мой_Отметка", Тип("ПолеФормы"));' in text, text
    assert f'// Дорабатывает форму "{ФОРМА}".' in text, text


def test_a_team_dialect_writes_the_code_from_the_server(выгрузка, tmp_path):
    """Профиль с диалектом — заголовок, текст и описание процедуры его словами."""
    shutil.copyfile(СБОРЩИК, tmp_path / "сборщик.py")
    соглашения_команды = соглашения_из_файла(профиль(str(tmp_path), {
        "язык": "сборщик", "диалект": "сборщик.py", "модуль": "мой_Формы"}))
    вызвать = _сервер(выгрузка, соглашения_команды)
    вызвать("forms_apply", repo=выгрузка, forms=[
        {"форма": ФОРМА, "создать": {"назначение": "Документа", "синоним": "Проба"}}])
    text = вызвать("forms_check", repo=выгрузка, forms=[ПОЛЕ])
    assert f"Код сборщика форм для «{ФОРМА}»" in text, text
    assert "\tСборка = мой_Формы.Сборщик(Форма);" in text, text
    assert f'// Дорабатывает форму "{ФОРМА}" сборщиком.' in text, text
    assert "Элементы.Добавить" not in text, text
