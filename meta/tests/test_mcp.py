"""Канал MCP: инструменты агента, белый список, отказ текстом, свои слова.

Поведение инструмента покрыто остальными тестами; здесь — только то, что
добавляет канал: инструменты вызываются так, как их зовёт агент (`call_tool`,
со схемой и проверкой аргументов), ответ — тот же язык ответов, что у
терминала, но подсказки — словами MCP; писать можно только в разрешённые
выгрузки; отказ — ответом, а не исключением.
"""

import asyncio
import io
import os
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import meta.add as add  # noqa: E402
from meta.composition import mcp_server  # noqa: E402
from meta.tests import corpus  # noqa: E402

ЭТАЛОНЫ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны", "формы")
ФОРМА = "Документ.мой_ПробаСДвижениями.мой_Проба"
НОВАЯ = [{"форма": ФОРМА, "создать": {"назначение": "Документа", "синоним": "Проба"}}]


@pytest.fixture
def выгрузка():
    """Выгрузка из двух документов — как в тестах форм."""
    root = tempfile.mkdtemp(prefix="meta-mcp-")
    for name, reference_node in (("Configuration.xml", "Configuration.xml"),
                        ("Documents/мой_ПробаСДвижениями.xml", "мой_ПробаСДвижениями.до.xml"),
                        ("Documents/мой_ПробаНепроводимый.xml", "мой_ПробаНепроводимый.до.xml")):
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(os.path.join(ЭТАЛОНЫ, reference_node), path)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def вызвать(сервер, tool, **arguments):
    """Вызов так, как зовёт агент: через сервер, со схемой и проверкой."""
    answer = asyncio.run(сервер.call_tool(tool, arguments))
    if isinstance(answer, tuple):          # (содержимое, структурированный ответ)
        answer = answer[0]
    return "\n".join(block.text for block in answer)


def через_терминал(argv):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        add.main(list(argv))
    return буфер.getvalue().rstrip("\n")


def test_every_tool_is_registered():
    """Забытый декоратор не виден ничем, кроме отсутствия инструмента у агента."""
    tools = asyncio.run(mcp_server(roots=[]).list_tools())
    assert {ii.name for ii in tools} == {
        "show", "fields", "forms_check", "forms_apply", "metadata_check", "metadata_apply",
        "code_check", "code_apply", "verify", "normalize_check", "normalize_apply",
        "plan_check", "plan_emit"}


def test_every_schema_passes_the_api_key_rule():
    """Имена свойств верхнего уровня и ключи `$defs` — только латиница.

    API отвергает схему инструмента, если ключ не проходит `^[a-zA-Z0-9_.-]{1,64}$`,
    и клиент молча исключает инструмент из сессии: параметр «принято» выбросил бы
    `forms_check` и `forms_apply` целиком. Ключи `$defs` — имена классов моделей;
    кириллицу в них клиент перемалывает в подчёркивания, и две модели одной длины
    слились бы в один ключ. Русские ключи внутри моделей — язык заданий — правилу
    не подлежат и проходят.
    """
    import re

    правило = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
    нарушения = []
    for tool in asyncio.run(mcp_server(roots=[]).list_tools()):
        schema = tool.inputSchema
        for key in list(schema.get("properties", {})) + list(schema.get("$defs", {})):
            if not правило.match(key):
                нарушения.append(f"{tool.name}: {key}")
    assert not нарушения, нарушения


def test_the_form_job_comes_with_its_schema():
    """Формат задания на форму агент получает от сервера, а не из README:
    схема инструмента построена из модели, с теми же русскими ключами."""
    tools = {ii.name: ii for ii in asyncio.run(mcp_server(roots=[]).list_tools())}
    schema = tools["forms_check"].inputSchema
    assert {"repo", "forms"} <= set(schema["properties"])
    text = str(schema)
    for key in ("форма", "создать", "реквизиты", "элементы", "родитель", "перед", "свойства"):
        assert key in text, key


def test_check_writes_nothing_and_apply_writes(выгрузка):
    сервер = mcp_server(roots=[выгрузка])
    file = os.path.join(выгрузка, "Documents", "мой_ПробаСДвижениями",
                        "Forms", "мой_Проба", "Ext", "Form.xml")
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=НОВАЯ)
    assert "ничего не записано" in answer and not os.path.exists(file)
    answer = вызвать(сервер, "forms_apply", repo=выгрузка, forms=НОВАЯ)
    assert "Записано файлов: 3" in answer and os.path.isfile(file)


def test_the_purpose_of_a_new_form_comes_from_its_name(выгрузка):
    """Назначение новой формы язык заданий выводит из имени, как мастер:
    `ФормаСписка` — форма списка. Схема канала его не требует — иначе
    задание, которое принимает терминал, в MCP получало бы отказ."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        {"форма": "Документ.мой_ПробаСДвижениями.ФормаСписка",
         "создать": {"синоним": "Проба"}}])
    assert not answer.startswith("ОТКАЗ:"), answer
    assert "ничего не записано" in answer


def test_the_same_answer_in_the_channel_s_own_words(выгрузка):
    """Язык ответов у каналов один — сообщения не живут двумя жизнями, — а
    подсказки каждый канал говорит своими словами: терминалу ключ, агенту
    инструмент."""
    сервер = mcp_server(roots=[выгрузка])
    assert (вызвать(сервер, "fields", kind="РегистрСведений")
            == через_терминал(["--поля", "РегистрСведений"]))
    preview = вызвать(сервер, "forms_check", repo=выгрузка, forms=НОВАЯ)
    assert "вызовите forms_apply с тем же заданием" in preview
    assert "--apply" not in preview
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=НОВАЯ)
    агенту = вызвать(сервер, "show", repo=выгрузка, address=ФОРМА)
    человеку = через_терминал(["--показать", выгрузка, ФОРМА])
    assert агенту.replace("verbose=true", "«--подробно»") == человеку


def test_writing_outside_the_allowed_roots_is_refused(выгрузка, tmp_path):
    """Белый список — то, чего у терминала нет: там запускает человек."""
    сервер = mcp_server(roots=[выгрузка])
    чужая = str(tmp_path)
    assert "вне разрешённых" in вызвать(сервер, "forms_check", repo=чужая, forms=НОВАЯ)
    assert "вне разрешённых" in вызвать(сервер, "show", repo=чужая, address="Справочник.Х")
    # белый список читается при запуске: отказ говорит, что правка .mcp.json требует перезапуска
    assert "переподключите сервер" in вызвать(сервер, "show", repo=чужая, address="Справочник.Х")
    assert "вне разрешённых" in вызвать(
        сервер, "metadata_check", repo=чужая, deletions=["Справочник.Х"])
    # подкаталог разрешённого — внутри; сосед с похожим именем — снаружи
    assert "вне разрешённых" not in вызвать(
        сервер, "show", repo=os.path.join(выгрузка, "Documents"), address="Справочник.Х")
    assert "вне разрешённых" in вызвать(
        сервер, "show", repo=выгрузка + "-чужая", address="Справочник.Х")
    assert "сервер не настроен" in вызвать(
        mcp_server(roots=[]), "forms_check", repo=выгрузка, forms=НОВАЯ)


def test_a_refusal_comes_back_as_text(выгрузка):
    """Отказ агент читает и исправляет сам — если он ответ, а не исключение.
    И по-русски: лишний ключ судит язык заданий, а не валидатор транспорта."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        {"форма": ФОРМА, "создать": {"назначение": "Документа"},
         "элементы": [{"вид": "ПолеТабличногоДокумента", "имя": "мой_Т"}]}])
    # вид платформы, которого инструмент не заводит, — не опечатка
    assert answer.startswith("ОТКАЗ:") and "в платформе есть, но заводить" in answer
    опечатка = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        {"форма": ФОРМА, "создать": {"назначение": "Документа"},
         "элементы": [{"вид": "ПолеВвда", "имя": "мой_Т"}]}])
    assert опечатка.startswith("ОТКАЗ:") and "не знаю вида элемента" in опечатка
    surplus = вызвать(сервер, "forms_check", repo=выгрузка,
                     forms=[{"форма": ФОРМА, "создатъ": {}}])
    assert surplus.startswith("ОТКАЗ:") and "создатъ" in surplus
    формы_не_туда = вызвать(сервер, "metadata_check", repo=выгрузка, forms=НОВАЯ)
    assert формы_не_туда.startswith("ОТКАЗ:") and "forms_check" in формы_не_туда
    assert "нечего делать" in вызвать(сервер, "metadata_check", repo=выгрузка)


# --- формат заданий находим и строг, справка и подсказки — словами канала -------------

def test_a_field_of_the_object_beside_its_kind_is_refused(выгрузка):
    """«атомарныеРоли» рядом с «вид» — отказ: иначе поле молча теряется, роли не
    заводятся, а отказ на соседнем шаге уводит в сторону."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[
        {"вид": "РегистрСведений", "атомарныеРоли": True,
         "поля": {"имя": "мой_Отметки", "синоним": "Отметки"}}])
    assert answer.startswith("ОТКАЗ:") and "атомарныеРоли" in answer and "внутри «поля»" in answer


def test_an_operation_given_as_an_object_is_refused_not_crashed(выгрузка):
    """`additions` словарём — отказ, а не падение: иначе словарь перебирается по
    ключам и роняет разбор исключением."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, additions={
        "путь": "Документ.мой_ПробаСДвижениями", "вид": "ТабличнаяЧасть",
        "поля": {"имя": "Строки"}})
    # форма запроса — по-русски, а не текстом валидатора транспорта
    assert answer.startswith("ОТКАЗ:") and "«additions» — нужен список пунктов" in answer, answer


def test_an_unknown_key_of_the_job_is_refused(выгрузка):
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, атомарныеРоли=True,
                    atomic_roles=["Документ.мой_ПробаСДвижениями"])
    # FastMCP отбросил бы лишний параметр молча — нужен отказ с перечнем
    assert answer.startswith("ОТКАЗ:") and "нет параметра «атомарныеРоли»" in answer, answer
    assert "atomic_roles" in answer and "accepted" in answer


def test_the_help_shows_item_formats_and_atomic_roles():
    """Справка показывает формат пункта каждой операции и «атомарныеРоли» среди
    полей вида: без этого формат «поля» и `additions` угадывают попытками."""
    сервер = mcp_server(roots=[])
    обзор = вызвать(сервер, "fields")
    for key in ("objects", "attributes", "additions", "changes", "deletions", "renames",
                 "atomic_roles"):
        assert re.search(rf"(?m)^   {key}\s", обзор), key
    assert обзор.count("пункт: ") >= 7 and '"путь": "Документ.мой_Заявка"' in обзор
    assert "атомарныеРоли" in вызвать(сервер, "fields", kind="РегистрСведений")


def test_no_terminal_words_reach_the_agent():
    """Подсказки на языке терминала («--поля») не доходят до агента в ответах MCP."""
    сервер = mcp_server(roots=[])
    for arguments in ({}, {"kind": "Справочник"}, {"kind": "Тип"}, {"kind": "РегистрСведений"},
                      {"kind": "НетТакогоВида"}):
        answer = вызвать(сервер, "fields", **arguments)
        assert "--поля" not in answer and "--apply" not in answer, arguments


def test_an_unknown_field_refusal_speaks_no_terminal(выгрузка):
    """Отказ «вид не знает полей» у вида с длинным списком полей отсылает к справке
    по полям, а не к «--поля» терминала."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[
        {"вид": "Справочник", "поля": {"имя": "мой_Х", "синоним": "Х", "нетТакогоПоля": 1}}])
    assert "нетТакогоПоля" in answer and "в справке по полям вида «Справочник»" in answer
    assert "--поля" not in answer


SRC = corpus.CORPUS
АВАНСОВЫЙ = "Документ.АвансовыйОтчет.ФормаДокумента"


def test_a_typical_form_snippet_after_a_neighbour_with_guidance():
    """Типовая форма: «после» не отказ, если соседа инструмент видит; подсказка
    зовёт code_apply, а не скрипт, и говорит, что «Форма» в модуле формы — это
    «ЭтотОбъект»; надпись без приставки — отказ, а не «замечаний нет».
    Только просмотр: выгрузка читается, не пишется."""
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет", "Forms",
                                       "ФормаДокумента", "Ext", "Form.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    сервер = mcp_server(roots=[SRC])

    def check(name):
        return вызвать(сервер, "forms_check", repo=SRC, forms=[{
            "форма": АВАНСОВЫЙ, "код": True,
            "элементы": [{"вид": "Надпись", "имя": name, "родитель": "ГруппаКомментарий",
                          "после": "Комментарий", "свойства": {"Заголовок": "Приложите чеки"}}]}])

    answer = check("мой_НадписьЧеки")
    # «после» превращается в «перед» следующим соседом
    assert "Форма.Элементы.Ответственный);" in answer, answer
    assert "ЭтотОбъект" in answer and "code_apply" in answer and ".py" not in answer
    # без приставки — ошибка, как у метаданных (МД-ПРЕФИКС), а не предупреждение,
    # которое принимается через accepted
    answer = check("НадписьЧеки")
    assert answer.startswith("ОТКАЗ:") and "ФОРМА-БЕЗ-ПРИСТАВКИ" in answer, answer


def test_a_handler_for_an_existing_form_module_is_not_written_and_says_so(выгрузка):
    """План говорит, что процедуру обработчика инструмент не пишет — её вносят
    заданием на код, — а также где ей место и какова заготовка: голая строка
    «в модуль формы: Процедура …» читается как «будет записано»."""
    сервер = mcp_server(roots=[выгрузка])
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=[dict(НОВАЯ[0], **{
        "реквизиты": [{"имя": "мой_Первый", "тип": "Булево"}],
        "элементы": [{"вид": "ПолеФлажка", "имя": "мой_Первый", "путь": "мой_Первый",
                      "обработчики": {"ПриИзменении": True}}]})])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[{
        "форма": ФОРМА, "реквизиты": [{"имя": "мой_Флаг", "тип": "Булево"}],
        "элементы": [{"вид": "ПолеФлажка", "имя": "мой_Флаг", "путь": "мой_Флаг",
                      "обработчики": {"ПриИзменении": True}}]}])
    # Разбито на «что», «где» и «заготовку»: одна фраза из трёх сообщений
    # читается с трудом.
    assert "процедуру не пишет — внесите её заданием на код. Где: " in answer, answer
    assert "Заготовка: «&НаКлиенте Процедура мой_ФлагПриИзменении(Элемент)»" in answer, answer


def test_the_help_knows_form_element_properties():
    """Справка знает свойства элемента формы: иначе их узнают только отказом, а
    «Заголовок» угадывают."""
    answer = вызвать(mcp_server(roots=[]), "fields", kind="Надпись")
    assert "Заголовок" in answer and "элемент формы" in answer
    assert "не заводит" in вызвать(mcp_server(roots=[]), "fields", kind="ПолеТабличногоДокумента")


def test_a_typical_form_snippet_is_a_ready_procedure():
    """Фрагмент кода формы — готовая процедура с отступами табуляцией и адрес
    модуля формы, а не текст, вокруг которого всё это набирают руками."""
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет", "Forms",
                                       "ФормаДокумента", "Ext", "Form.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    answer = вызвать(mcp_server(roots=[SRC]), "forms_check", repo=SRC, forms=[{
        "форма": АВАНСОВЫЙ, "код": True,
        "элементы": [{"вид": "Надпись", "имя": "мой_НадписьЧеки", "родитель": "ГруппаКомментарий",
                      "перед": "Ответственный", "свойства": {"Заголовок": "Приложите чеки"}}]}])
    assert "Процедура ФормаДокумента_ПриСозданииНаСервере(Форма) Экспорт" in answer
    assert '\tЭлемент = Форма.Элементы.Вставить("мой_НадписьЧеки"' in answer
    assert "«Документ.АвансовыйОтчет.Форма.ФормаДокумента»" in answer


def test_a_document_shows_which_table_has_which_attributes():
    """Реквизиты табличной части — под её именем: восемь строк «реквизиты: …»
    подряд не говорят, какой табличной части какие."""
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    answer = вызвать(mcp_server(roots=[SRC]), "show", repo=SRC, address="Документ.АвансовыйОтчет")
    lines = answer.splitlines()
    k = lines.index("      Товары:")
    assert lines[k + 1].startswith("         реквизиты: ")


# --- формы: обработчики, место соседа, поле по типу реквизита -----------------------

def test_typical_form_code_lists_handler_procedures_and_writes_nothing():
    """Обработчик в коде формы — с приставкой «Подключаемый_», а процедура для
    модуля формы названа с сигнатурой; forms_apply с «код» прямо говорит, что
    записи нет; заголовок реквизита код платформы передаёт."""
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет", "Forms",
                                       "ФормаДокумента", "Ext", "Form.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    job_spec = [{"форма": АВАНСОВЫЙ, "код": True,
                "реквизиты": [{"имя": "мой_Пометка", "тип": "Строка(10)", "заголовок": "Пометка"}],
                "элементы": [{"вид": "Надпись", "имя": "мой_НадписьЧеки",
                              "родитель": "ГруппаКомментарий", "перед": "Ответственный",
                              "обработчики": {"Нажатие": True}}]}]
    answer = вызвать(mcp_server(roots=[SRC]), "forms_apply", repo=SRC, forms=job_spec)
    assert ('Элемент.УстановитьДействие("Нажатие", "Подключаемый_мой_НадписьЧекиНажатие");'
            in answer), answer
    assert "Процедура Подключаемый_мой_НадписьЧекиНажатие(" in answer
    assert "Записи нет" in answer and ', , "Пометка")' in answer, answer


def test_a_misplaced_neighbour_says_where_it_actually_is():
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    answer = вызвать(mcp_server(roots=[SRC]), "forms_check", repo=SRC, forms=[{
        "форма": АВАНСОВЫЙ, "код": True,
        "элементы": [{"вид": "Надпись", "имя": "мой_Н", "родитель": "ГруппаШапка",
                      "после": "Комментарий"}]}])
    assert "а в «ГруппаКомментарий» — укажите этот «родитель»" in answer


def test_a_document_attribute_needs_its_own_field(выгрузка):
    """ПолеВвода на реквизите ТабличныйДокумент — находка с подсказкой, какое поле
    нужно, а не «замечаний нет»."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[dict(НОВАЯ[0], **{
        "реквизиты": [{"имя": "мой_Печать", "тип": "ТабличныйДокумент"}],
        "элементы": [{"вид": "ПолеВвода", "имя": "мой_Печать", "путь": "мой_Печать"}]})])
    assert "ФОРМА-ПОЛЕ-НЕ-ДЛЯ-ТИПА" in answer and "ПолеТабличногоДокумента" in answer


def test_show_marks_a_handler_without_a_procedure(выгрузка):
    """Форма записана, задание на код забыто — ссылка в никуда видна в показе."""
    сервер = mcp_server(roots=[выгрузка])
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=[dict(НОВАЯ[0], **{
        "реквизиты": [{"имя": "мой_Флаг", "тип": "Булево"}],
        "элементы": [{"вид": "ПолеФлажка", "имя": "мой_Флаг", "путь": "мой_Флаг",
                      "обработчики": {"ПриИзменении": True}}]})])
    module = os.path.join(выгрузка, "Documents", "мой_ПробаСДвижениями", "Forms", "мой_Проба",
                          "Ext", "Form", "Module.bsl")
    assert "@ПриИзменении=мой_ФлагПриИзменении" in вызвать(сервер, "show", repo=выгрузка, address=ФОРМА)
    with open(module, encoding="utf-8-sig") as file:
        text = file.read()
    with open(module, "w", encoding="utf-8-sig") as file:
        file.write(text.replace("мой_ФлагПриИзменении", "Другое"))
    assert ("@ПриИзменении=мой_ФлагПриИзменении (процедуры в модуле нет)"
            in вызвать(сервер, "show", repo=выгрузка, address=ФОРМА))


# --- запись типов в показе и задании, символы кода, совет по ролям ------------------

def test_a_type_set_is_read_and_not_lost():
    """Набор (определяемый тип, «все ссылки справочников») записан тегом TypeSet
    и читается наравне с Type: иначе реквизит определяемого типа показывается
    «Произвольным», а составной тип формы теряет половину состава."""
    from meta.acl import mapping
    from meta.acl.mapping import Node
    from meta.domain import model as dm

    def прочитать(*nodes):
        return dm.type_record(mapping._type_from_nodes(list(nodes)))

    assert прочитать(Node("v8:TypeSet", text="cfg:DefinedType.ДенежнаяСумма")) == \
        "ОпределяемыйТип.ДенежнаяСумма"
    assert прочитать(
        Node("v8:Type", text="xs:boolean"), Node("v8:TypeSet", text="cfg:EnumRef"),
        Node("v8:TypeSet", text="cfg:CatalogRef")) == "Булево | Перечисление.* | Справочник.*"
    assert прочитать(Node("v8:Type", text="mxl:SpreadsheetDocument")) == "ТабличныйДокумент"
    assert прочитать(Node("v8:Type", text="d5p1:TextDocument")) == "ТекстовыйДокумент"
    # незнакомое обозначение — как записано, а не отказ всему показу
    assert прочитать(Node("v8:Type", text="cfg:НетТакого")) == "cfg:НетТакого"


def test_show_prints_types_the_way_the_job_takes_them():
    """Определяемый тип, составной тип формы и табличный документ — в той
    же записи, что принимает задание."""
    банки = os.path.join(SRC, "Catalogs", "БанкиУниверсальногоОбмена.xml")
    if not os.path.isfile(банки):
        pytest.skip("не задана выгрузка META_CORPUS")
    сервер = mcp_server(roots=[SRC])
    answer = вызвать(сервер, "show", repo=SRC, address="Справочник.БанкиУниверсальногоОбмена")
    assert ("ОтпечатокДействующегоСертификата «Отпечаток действующего сертификата» "
            "(ОпределяемыйТип.ОтпечатокСертификатаДляОбменаСБанками)") in answer
    assert "Произвольный" not in answer
    # и формы объекта — с пометкой основной
    assert "формы: ФормаЭлемента (основная объекта)" in answer, answer


def test_the_code_snippet_has_no_character_bsl_ls_rejects():
    """В описании выданной процедуры нет длинного тире: иначе bsl-ls выдаёт
    ошибку на каждый фрагмент. Тире из заголовка задания — находка сразу, а не
    отказ потом в задании на код."""
    from meta.domain.characters import invalid_characters

    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет", "Forms",
                                       "ФормаДокумента", "Ext", "Form.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    сервер = mcp_server(roots=[SRC])
    job_spec = {"форма": АВАНСОВЫЙ, "код": True,
               "элементы": [{"вид": "Надпись", "имя": "мой_НадписьЧеки",
                             "родитель": "ГруппаКомментарий", "перед": "Ответственный",
                             "свойства": {"Заголовок": "Приложите чеки"}}]}
    answer = вызвать(сервер, "forms_check", repo=SRC, forms=[job_spec])
    фрагмент = answer[answer.index("// Дорабатывает"):answer.index("КонецПроцедуры")]
    assert not invalid_characters(фрагмент), фрагмент
    job_spec["элементы"][0]["свойства"]["Заголовок"] = "Чеки — приложить"
    answer = вызвать(сервер, "forms_check", repo=SRC, forms=[job_spec])
    assert "ФОРМА-КОД-СИМВОЛ" in answer and "длинное тире (U+2014)" in answer, answer


def test_the_metadata_job_is_typed_and_takes_the_short_type(выгрузка):
    """Задание на метаданные — типами, тип — той же записью, что печатает show;
    подробный просмотр показывает XML: изменённый файл — разницей."""
    сервер = mcp_server(roots=[выгрузка])
    job_spec = {"repo": выгрузка, "attributes": [
        {"объект": "Документ.мой_ПробаСДвижениями",
         "поля": {"имя": "мой_Пометка", "синоним": "Пометка", "тип": "Строка(50)"}}]}
    answer = вызвать(сервер, "metadata_check", verbose=True, **job_spec)
    assert not answer.startswith("ОТКАЗ"), answer
    assert "Реквизит мой_Пометка" in answer and "тип: Строка(50)" in answer, answer
    assert "── изменить" in answer and "+" in answer and "<v8:Length>50</v8:Length>" in answer
    # без verbose — один план, без текстов
    assert "── изменить" not in вызвать(сервер, "metadata_check", **job_spec)
    # схема инструмента — типами: операции и пункты видны агенту без примеров
    schema = next(t for t in asyncio.run(сервер.list_tools()) if t.name == "metadata_check")
    assert {"repo", "objects", "attributes", "additions", "changes", "deletions", "renames",
            "atomic_roles", "accepted", "verbose"} == set(schema.inputSchema["properties"])


def соседи_просмотра(сервер, выгрузка):
    """Две роли «Просмотр» документов выгрузки — без «ВводПоСтроке»: соседи по
    схеме, у которых типовой состав не правило."""
    answer = вызвать(сервер, "metadata_apply", repo=выгрузка, objects=[
        {"вид": "Роль", "поля": {
            "имя": f"мой_атом_Документ_{neighbour}_Просмотр", "синоним": "Просмотр",
            "права": [{"объект": f"Документ.{document}", "права": ["Чтение", "Просмотр"]}]}}
        for neighbour, document in (("СоседА", "мой_ПробаСДвижениями"),
                                ("СоседБ", "мой_ПробаНепроводимый"))])
    assert not answer.startswith("ОТКАЗ"), answer


def test_role_rights_advice_is_a_warning_not_a_plan_step(выгрузка):
    """«Состав прав — большинство, а не правило» — предупреждение над планом, а не
    строка «Плана»: шагом плана оно не является."""
    сервер = mcp_server(roots=[выгрузка])
    соседи_просмотра(сервер, выгрузка)
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[
        {"вид": "Документ", "поля": {
            "имя": "мой_Отметки", "синоним": "Отметки", "атомарныеРоли": ["Просмотр"]}}])
    assert not answer.startswith("ОТКАЗ"), answer
    plan = answer[answer.index("\nПлан:"):]
    assert "не правило" not in plan, plan
    assert "РОЛЬ-ШАБЛОН-НЕ-ПРАВИЛО" in answer[:answer.index("\nПлан:")]


# --- повтор элемента, флажок не по типу, «ё» и длина имени, схемы и XML -------------

def test_a_repeated_element_is_refused_and_places_are_given(выгрузка):
    """Повтор доработки под другим именем процедуры завёл бы второй элемент с
    тем же именем. Место процедуры и вызова — номерами строк, а не словами."""
    сервер = mcp_server(roots=[выгрузка])
    # Заводит надпись настоящим вызовом: повтором считается только вызов,
    # который заводит элемент. Два параметра — процедуры доработки формы в
    # ней не узнать, и имя занято.
    text = ("#Область ПрограммныйИнтерфейс\n\nПроцедура Доработать(Форма, Режим) Экспорт\n"
             "\tФорма.Элементы.Добавить(\"мой_Надпись\", Тип(\"ДекорацияФормы\"));\n"
             "КонецПроцедуры\n\n#КонецОбласти")
    answer = вызвать(сервер, "metadata_apply", repo=выгрузка, objects=[
        {"вид": "ОбщийМодуль", "поля": {"имя": "мой_ПробаФормы", "синоним": "Проба формы",
                                         "текст": text}}])
    assert not answer.startswith("ОТКАЗ"), answer
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=НОВАЯ)
    надпись = {"вид": "Надпись", "имя": "мой_Надпись", "свойства": {"Заголовок": "Проба"}}
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        {"форма": ФОРМА, "код": {"модуль": "ОбщийМодуль.мой_ПробаФормы", "процедура": "Другая"},
         "элементы": [надпись]}])
    assert "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ" in answer and "(строка 4)" in answer, answer
    свежая = dict(надпись, имя="мой_НадписьНовая")
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        {"форма": ФОРМА, "код": {"модуль": "ОбщийМодуль.мой_ПробаФормы"}, "элементы": [свежая]}])
    assert "процедура — вставкой перед строкой 7 модуля «мой_ПробаФормы»" in answer, answer
    taken = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        {"форма": ФОРМА, "код": {"модуль": "ОбщийМодуль.мой_ПробаФормы",
                                 "процедура": "Доработать"}, "элементы": [свежая]}])
    assert "ФОРМА-КОД-ИМЯ-ЗАНЯТО" in taken and "та же доработка, она уже внесена" in taken


def test_a_checkbox_on_a_string_is_refused(выгрузка):
    """Поле флажка редактирует Булево (Число — при «ТриСостояния»): флажок на
    строковом реквизите — находка, а не «замечаний нет»."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[dict(НОВАЯ[0], **{
        "реквизиты": [{"имя": "мой_Строка", "тип": "Строка(10)"},
                      {"имя": "мой_Флаг", "тип": "Булево"}],
        "элементы": [{"вид": "ПолеФлажка", "имя": "мой_Строка", "путь": "мой_Строка"},
                     {"вид": "ПолеФлажка", "имя": "мой_Флаг", "путь": "мой_Флаг"}]})])
    assert answer.count("ФОРМА-ФЛАЖОК-ТИП") == 1 and "типа Строка(10)" in answer, answer


def test_yo_and_names_longer_than_80_are_refused(выгрузка):
    """#std474: «ё» в имени, синониме, комментарии — нет (п. 4); имя не длиннее
    80 (п. 2.3). Имя роли строит инструмент — для длинного объекта задаётся
    «сокращение»."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[
        {"вид": "Справочник", "поля": {"имя": "мой_Отчеты", "синоним": "Отчёты"}}])
    assert "МД-БУКВА-Ё" in answer and "«Отчеты»" in answer and answer.startswith("ОТКАЗ:"), answer
    длинное = "мой_" + "ОченьДлинноеИмяРегистраДляПроверки" * 2
    регистр = {"вид": "РегистрСведений", "поля": {
        "имя": длинное, "синоним": "Проба", "атомарныеРоли": True,
        "измерения": [{"имя": "Ключ", "синоним": "Ключ", "тип": "Строка(10)"}]}}
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[регистр])
    assert "МД-ИМЯ-ДЛИННОЕ" in answer and "«сокращение»" in answer and answer.startswith("ОТКАЗ:")
    регистр["поля"]["атомарныеРоли"] = {"сокращение": "мой_ДлинныйРегистр"}
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[регистр])
    assert "мой_атом_РегистрСведений_мой_ДлинныйРегистр_Просмотр" in answer, answer
    assert "МД-ИМЯ-ДЛИННОЕ" not in answer


def test_no_service_notes_reach_the_tool_schemas():
    """Описание класса модели уходит в схему, поэтому служебных пометок о ходе
    разработки в нём быть не должно: агенту они — шум."""
    import json

    for tool in asyncio.run(mcp_server(roots=[]).list_tools()):
        schema = json.dumps(tool.inputSchema, ensure_ascii=False).lower()
        assert "прогон" not in schema and "испытани" not in schema, tool.name


def test_forms_check_shows_the_xml_on_verbose(выгрузка):
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=НОВАЯ, verbose=True)
    assert "── создать" in answer and "<Form" in answer and "uuid" in answer, answer


# --- модуль формы и код доработки: повтор, кавычки, готовые правки -------------------

МОДУЛЬ_ФОРМЫ = "Documents/мой_ПробаСДвижениями/Forms/мой_Проба/Ext/Form/Module.bsl"


def форма_с_модулем(выгрузка):
    """Форма, чей модуль сам добавляет элемент кодом, и общий модуль для
    процедуры доработки формы — как у авансового отчёта."""
    сервер = mcp_server(roots=[выгрузка])
    text = "#Область ПрограммныйИнтерфейс\n\n#КонецОбласти"
    answer = вызвать(сервер, "metadata_apply", repo=выгрузка, objects=[
        {"вид": "ОбщийМодуль", "поля": {"имя": "мой_ПробаФормы", "синоним": "Проба формы",
                                         "сервер": True, "текст": text}}])
    assert not answer.startswith("ОТКАЗ"), answer
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=НОВАЯ)
    module = ["#Область ОбработчикиСобытийФормы", "", "&НаСервере",
              "Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)",
              "\t//Элементы.Добавить(\"мой_Старое\", Тип(\"ПолеФормы\"));",
              "\tЭлементы.Добавить(\"мой_ИтогоВыдано\", Тип(\"ПолеФормы\"));",
              "КонецПроцедуры", "", "#КонецОбласти"]
    path = os.path.join(выгрузка, *МОДУЛЬ_ФОРМЫ.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)       # у свежей формы модуля нет
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        file.write("\r\n".join(module))
    return сервер


def надпись(name, title="Приложите чеки"):
    return {"форма": ФОРМА, "код": {"модуль": "ОбщийМодуль.мой_ПробаФормы"},
            "элементы": [{"вид": "Надпись", "имя": name, "свойства": {"Заголовок": title}}]}


def test_an_element_the_form_module_adds_itself_is_refused(выгрузка):
    """Повтор имени ищется и в модуле формы: элемент может добавлять он сам, и
    без этого надпись прошла бы, а форма упала бы при открытии.
    Закомментированное не в счёт."""
    сервер = форма_с_модулем(выгрузка)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_ИтогоВыдано")])
    assert "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ" in answer and "в модуле формы (строка 6)" in answer, answer
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Старое")])
    assert "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ" not in answer, answer


def test_the_code_snippet_uses_straight_quotes_and_flags_guillemets(выгрузка):
    """В описании выданной процедуры кавычки прямые: ёлочки стояли бы в каждом
    фрагменте, а проверка кода их не пускает. Ёлочки из заголовка — находка."""
    сервер = форма_с_модулем(выгрузка)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки")])
    фрагмент = answer[answer.index("// Дорабатывает"):answer.index("КонецПроцедуры")]
    assert f'форму "{ФОРМА}"' in фрагмент and "«" not in фрагмент and "»" not in фрагмент
    answer = вызвать(сервер, "forms_check", repo=выгрузка,
                    forms=[надпись("мой_Чеки", "Приложите «чеки»")])
    assert "ФОРМА-КОД-ЁЛОЧКИ" in answer and "кавычки прямые" in answer, answer


def test_the_ready_edits_go_to_code_check_as_they_are(выгрузка):
    """Ответ даёт готовые правки, и code_check берёт их как есть: иначе процедуру,
    номера строк и тексты якорей переносят в задание на код руками."""
    import json

    сервер = форма_с_модулем(выгрузка)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки")])
    # и что forms_apply здесь незачем — порядок «check, затем apply» к нему
    # подталкивает
    assert "Запись формы не нужна" in answer, answer
    start = answer.index('{"modules": [')
    block = json.loads(answer[start:answer.index("\n]}", start) + 3])
    assert [mm["module"] for mm in block["modules"]] == [
        "ОбщийМодуль.мой_ПробаФормы", "Документ.мой_ПробаСДвижениями.Форма.мой_Проба"]
    caption = {"task": "TASK-1", "date": "31.08.2026", "author": "Кто"}
    code = вызвать(сервер, "code_check", repo=выгрузка, modules=block["modules"], **caption)
    assert not code.startswith("ОТКАЗ"), code
    assert "(в конце области «ПрограммныйИнтерфейс»)" in code
    assert "(в конце метода «ПриСозданииНаСервере»)" in code
    вызвать(сервер, "code_apply", repo=выгрузка, modules=block["modules"], **caption)
    file = os.path.join(выгрузка, "CommonModules", "мой_ПробаФормы", "Ext", "Module.bsl")
    assert "Процедура мой_Проба_ПриСозданииНаСервере(Форма) Экспорт" in open(
        file, encoding="utf-8-sig").read()


def test_a_document_attribute_without_a_creatable_field_is_warned(выгрузка):
    """Табличный документ показывается только своим полем, которого инструмент
    не заводит: что показать реквизит нечем, предупреждает уже шаг реквизита, а
    не шаг элемента."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[dict(НОВАЯ[0], **{
        "реквизиты": [{"имя": "мой_Печать", "тип": "ТабличныйДокумент"}]})])
    assert "ФОРМА-РЕКВИЗИТ-БЕЗ-ПОЛЯ" in answer and "ПолеТабличногоДокумента" in answer, answer


def test_the_overview_sends_forms_to_their_own_tools():
    """Обзор операций MCP не числит «forms» рядом с objects: у metadata_* такого
    ключа нет, формам — свои инструменты. У терминала это ключ задания — там он
    есть."""
    обзор = вызвать(mcp_server(roots=[]), "fields")
    assert not re.search(r"(?m)^   forms\s", обзор) and "forms_check / forms_apply" in обзор
    assert re.search(r"(?m)^   forms\s", через_терминал(["--поля"]))


# --- длина описаний, первая строка отказа, показ XML и ролей -------------------------

#: Сколько символов описания инструмента клиент показывает агенту: дальше —
#: «… [truncated]» (клиент обрезает на 2048-м знаке).
ПРЕДЕЛ_ОПИСАНИЯ = 2000


def test_every_description_fits_what_the_client_shows():
    """Описание каждого инструмента укладывается в то, что показывает клиент:
    длиннее — и хвост описания (у code_check — метод без закрывающей, откат,
    verbose) агент не увидит. Полные правила — справкой fields(kind="Код")."""
    сервер = mcp_server(roots=[])
    for tool in asyncio.run(сервер.list_tools()):
        assert len(tool.description or "") <= ПРЕДЕЛ_ОПИСАНИЯ, (tool.name, len(tool.description))
    assert len(сервер.instructions or "") <= ПРЕДЕЛ_ОПИСАНИЯ
    rules = вызвать(сервер, "fields", kind="Код")
    assert "Метка — комментарий" in rules and "revert" in rules and "verbose=true" in rules
    # справка говорит то же, что делает инструмент: плоское тело — отказ, а не
    # предупреждение
    assert "вровень с объявлением, — отказ" in rules and "предупреждение" not in rules
    assert "Метка — комментарий" in через_терминал(["--поля", "Код"])


def test_a_job_that_will_not_pass_starts_with_a_refusal(выгрузка):
    """Задание, которое не пройдёт, начинается с «ОТКАЗ:»: «НЕ ВЫПОЛНЕНО» внизу
    ответа поиск по «ОТКАЗ:» пропустил бы, а у просмотра оно и звучит странно."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[
        {"вид": "Справочник", "поля": {"имя": "БезПриставки", "синоним": "Проба"}}])
    first, вторая = answer.split("\n")[:2]
    assert first.startswith("ОТКАЗ: ошибок 1") and "задание не пройдёт" in first, answer
    assert вторая.startswith("Выгрузка:") and "НЕ ВЫПОЛНЕНО" not in answer


def test_the_xml_preview_mentions_uuid_only_when_there_are_new_ones(выгрузка):
    """Оговорка про uuid — только когда новые uuid есть: у правки формы их нет."""
    сервер = mcp_server(roots=[выгрузка])
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=НОВАЯ)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, verbose=True, forms=[{
        "форма": ФОРМА, "элементы": [{"вид": "Надпись", "имя": "мой_Надпись",
                                     "свойства": {"Заголовок": "Проба"}}]}])
    assert "Тексты файлов:" in answer and "uuid новых объектов" not in answer, answer
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, verbose=True, attributes=[
        {"объект": "Документ.мой_ПробаСДвижениями",
         "поля": {"имя": "мой_Пометка", "синоним": "Пометка", "тип": "Булево"}}])
    assert "uuid новых объектов" in answer, answer


def test_a_role_shows_only_the_objects_it_grants_something():
    """Роль показывает только объекты, на которые что-то выдано: иначе роль с
    сотней тысяч объектов под явным «false» выливается в девять миллионов знаков
    строк «(пусто)»."""
    from meta.domain.model import Spec
    from meta.report.objects import shown_object

    role = Spec("Роль", {"имя": "мой_Проба", "права": [
        {"объект": "Справочник.А", "права": ["Чтение"]},
        {"объект": "Справочник.Б", "права": []}, {"объект": "Справочник.В", "права": []}]})
    shown = "\n".join(shown_object(role, "Roles/мой_Проба.xml"))
    assert "Справочник.А: Чтение" in shown and "Справочник.Б" not in shown
    assert "ещё объектов: 2 — названы в файле прав, но ни одного права на них не выдано" in shown


def test_the_role_advice_names_the_other_compositions(выгрузка):
    """Совет по ролям называет, как устроены остальные роли, а не только «сверьте
    с соседями»; доля и составы — по ролям этой выгрузки, а не числа чужой
    конфигурации."""
    сервер = mcp_server(roots=[выгрузка])
    соседи_просмотра(сервер, выгрузка)
    answer = вызвать(сервер, "metadata_check", repo=выгрузка, objects=[
        {"вид": "Документ", "поля": {
            "имя": "мой_Отметки", "синоним": "Отметки", "атомарныеРоли": ["Просмотр"]}}])
    assert "так устроены 0 из 2 ролей «Просмотр»" in answer, answer
    assert ("другие составы: без ВводПоСтроке — 2, например "
            "«Роль.мой_атом_Документ_СоседА_Просмотр»") in answer, answer
    # и как другой состав получить: «права» атомарных ролей выбирают роли, а не
    # права платформы
    assert "пунктом objects вида «Роль» с полем «права»" in answer


# --- описания параметров, повтор имени, процедура доработки и её модуль --------------

def test_verbose_and_accepted_are_described_in_every_schema():
    """У `verbose` и `accepted` в каждой схеме есть описание: смысл подробного
    показа у каждого инструмента свой, а формат кода в accepted иначе угадывают."""
    for tool in asyncio.run(mcp_server(roots=[]).list_tools()):
        props = tool.inputSchema.get("properties", {})
        for name in ("verbose", "accepted"):
            if name in props:
                assert props[name].get("description"), (tool.name, name)


def test_only_a_creating_call_makes_a_name_taken(выгрузка):
    """Повтором считается только вызов, который заводит элемент, а не любое имя в
    кавычках: иначе «ОписаниеОповещения("мой_…")» — имя процедуры — даёт ошибку,
    которую нельзя принять, а вместо строки «Элементы.Добавить» называется
    «Элементы.Найти». Элемент и реквизит с одним именем — законно: пространства
    разные."""
    сервер = форма_с_модулем(выгрузка)
    path = os.path.join(выгрузка, *МОДУЛЬ_ФОРМЫ.split("/"))
    module = open(path, encoding="utf-8-sig").read().replace(
        "\tЭлементы.Добавить(\"мой_ИтогоВыдано\"",
        "\tОповещение = Новый ОписаниеОповещения(\"мой_Подбор\", ЭтотОбъект);\r\n"
        "\tГруппа = Элементы.Найти(\"мой_Итоги\");\r\n"
        "\tЭлементы.Добавить(\"мой_Итоги\", Тип(\"ГруппаФормы\"));\r\n"
        "\tЭлементы.Добавить(\"мой_ИтогоВыдано\"")
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        file.write(module)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Подбор")])
    assert "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ" not in answer, answer
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Итоги")])
    # строка 8 — «Элементы.Добавить», а не 7 — «Элементы.Найти»
    assert "элемент «мой_Итоги» уже заводится кодом в модуле формы (строка 8)" in answer, answer
    attribute = {"форма": ФОРМА, "код": {"модуль": "ОбщийМодуль.мой_ПробаФормы"},
                "реквизиты": [{"имя": "мой_ИтогоВыдано", "тип": "Булево"}]}
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[attribute])
    assert "ФОРМА-КОД-УЖЕ-В-МОДУЛЕ" not in answer, answer


def test_a_client_or_server_call_module_cannot_hold_the_form_code(выгрузка):
    """Модуль для процедуры доработки формы проверяется не по одному признаку
    «Сервер»: клиент-серверный модуль и модуль вызова сервера — находки, а не
    «замечаний нет»."""
    сервер = форма_с_модулем(выгрузка)
    for name, flags in (("мой_ПробаКлиентСервер", {"клиентУправляемоеПриложение": True,
                                                  "клиентОбычноеПриложение": True,
                                                  "сервер": True, "внешнееСоединение": True}),
                       ("мой_ПробаВызовСервера", {"сервер": True, "вызовСервера": True})):
        answer = вызвать(сервер, "metadata_apply", repo=выгрузка, objects=[
            {"вид": "ОбщийМодуль", "поля": dict({"имя": name, "синоним": "Проба",
                                                 "текст": "#Область ПрограммныйИнтерфейс\n\n"
                                                          "#КонецОбласти"}, **flags)}])
        assert not answer.startswith("ОТКАЗ"), answer
    def check(module):
        return вызвать(сервер, "forms_check", repo=выгрузка, forms=[
            dict(надпись("мой_Чеки"), **{"код": {"модуль": f"ОбщийМодуль.{module}"}})])
    assert "ФОРМА-КОД-МОДУЛЬ-КЛИЕНТ" in check("мой_ПробаКлиентСервер")
    assert "ФОРМА-КОД-МОДУЛЬ-ВЫЗОВ-СЕРВЕРА" in check("мой_ПробаВызовСервера")
    assert "замечаний нет" in check("мой_ПробаФормы")


def test_a_second_procedure_is_warned_and_the_addition_keeps_a_blank(выгрузка):
    """Явное имя процедуры не отключает защиту от второго вызова, а дописанный
    код отделён пустой строкой от строки, перед которой его дописывают.
    Описание процедуры — что она добавляет, а не постоянная оговорка."""
    import json

    сервер = форма_с_модулем(выгрузка)
    caption = {"task": "TASK-1", "date": "31.08.2026", "author": "Кто"}

    def готовые(answer):
        start = answer.index('{"modules": [')
        return json.loads(answer[start:answer.index("\n]}", start) + 3])["modules"]

    first = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки")])
    # описание без перечня элементов: дополнение его не трогает
    assert '// Дорабатывает форму "Документ.мой_ПробаСДвижениями.мой_Проба".' in first, first
    вызвать(сервер, "code_apply", repo=выгрузка, modules=готовые(first), **caption)
    вторая = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки2")])
    assert готовые(вторая)[0]["edits"][0]["code"].endswith(";\n\t"), вторая
    другая = вызвать(сервер, "forms_check", repo=выгрузка, forms=[dict(
        надпись("мой_Чеки3"), **{"код": {"модуль": "ОбщийМодуль.мой_ПробаФормы",
                                        "процедура": "Другая"}})])
    assert "ФОРМА-КОД-ВТОРАЯ-ДОРАБОТКА" in другая and "без «процедура»" in другая, другая


def test_show_says_code_added_elements_are_not_in_the_tree():
    """Дерево — из XML: что добавляет код, в нём не видно, и показ это говорит."""
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет", "Forms",
                                       "ФормаДокумента", "Ext", "Form.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    answer = вызвать(mcp_server(roots=[SRC]), "show", repo=SRC, address=АВАНСОВЫЙ)
    assert "элементы, которые добавляет код (модуль формы, код доработки), в дереве не видны" \
        in answer


def test_a_second_change_extends_the_procedure(выгрузка):
    """Вторая доработка той же типовой формы: код дописывается в процедуру
    первой, вызов не повторяется; без модуля — отказ с подсказкой, какой
    назвать."""
    import json

    сервер = форма_с_модулем(выгрузка)
    caption = {"task": "TASK-1", "date": "31.08.2026", "author": "Кто"}

    def готовые(answer):
        start = answer.index('{"modules": [')
        return json.loads(answer[start:answer.index("\n]}", start) + 3])["modules"]

    first = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки")])
    вызвать(сервер, "code_apply", repo=выгрузка, modules=готовые(first), **caption)
    вторая = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки2", "Ещё")])
    assert "дополнение процедуры «мой_Проба_ПриСозданииНаСервере»" in вторая, вторая
    assert "вызов в модуле формы уже есть" in вторая and "Процедура мой_Проба" not in вторая
    modules = готовые(вторая)
    assert [mm["module"] for mm in modules] == ["ОбщийМодуль.мой_ПробаФормы"]
    # якорь — конец процедуры, внесённой первой доработкой (с её закрывающей меткой)
    assert modules[0]["edits"][0]["first_line"].startswith("КонецПроцедуры"), modules
    code = вызвать(сервер, "code_check", repo=выгрузка, modules=modules, **caption)
    assert not code.startswith("ОТКАЗ"), code
    вызвать(сервер, "code_apply", repo=выгрузка, modules=modules, **caption)
    text = open(os.path.join(выгрузка, "CommonModules", "мой_ПробаФормы", "Ext", "Module.bsl"),
                 encoding="utf-8-sig").read()
    assert text.count("Процедура мой_Проба_ПриСозданииНаСервере") == 1
    assert '"мой_Чеки2"' in text
    form = open(os.path.join(выгрузка, *МОДУЛЬ_ФОРМЫ.split("/")), encoding="utf-8-sig").read()
    assert form.count("мой_Проба_ПриСозданииНаСервере(ЭтотОбъект)") == 1
    без_модуля = вызвать(сервер, "forms_check", repo=выгрузка, forms=[
        dict(надпись("мой_Чеки3"), **{"код": True})])
    assert без_модуля.startswith("ОТКАЗ:") and "ФОРМА-КОД-ВЫЗОВ-ЕСТЬ" in без_модуля, без_модуля
    assert "«ОбщийМодуль.мой_ПробаФормы»" in без_модуля


# --- события и обработчики, свой модуль объекта, ветка показа, отступ ----------------

def флажок(handlers, name="мой_Флаг", create=True):
    return [dict(НОВАЯ[0] if create else {"форма": ФОРМА}, **{
        "реквизиты": [{"имя": name, "тип": "Булево"}],
        "элементы": [{"вид": "ПолеФлажка", "имя": name, "путь": name,
                      "обработчики": handlers}]})]


def test_an_event_of_another_kind_is_refused_at_once(выгрузка):
    """У каждого вида свой словарь событий: «НачалоВыбора» и «ПриСменеСтраницы» у
    флажка — находки сразу, неизвестное имя — тоже, с кодом, а не отказ позже
    и без кода."""
    сервер = mcp_server(roots=[выгрузка])
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=флажок(
        {"НачалоВыбора": True, "ПриСменеСтраницы": True, "ПриИзмененииЗначения": True}))
    assert answer.startswith("ОТКАЗ: ошибок 3"), answer
    assert answer.count("ФОРМА-СОБЫТИЕ-НЕ-ДЛЯ-ВИДА") == 2 and "ФОРМА-СОБЫТИЕ-НЕИЗВЕСТНО" in answer
    assert "у ПолеФлажка событий: ПриИзменении" in answer
    assert "События (ключ «обработчики»): ПриИзменении" in вызвать(сервер, "fields",
                                                                   kind="ПолеФлажка")
    assert "ПриСменеСтраницы" in вызвать(сервер, "fields", kind="Страницы")


def test_an_existing_procedure_must_fit_the_handler(выгрузка):
    """Процедуру, которая в модуле уже есть, подсказка заводить не зовёт, а
    серверная «УправлениеФормой()» без параметров клиентским обработчиком
    элемента молча не проходит: находка называет и имеющуюся процедуру, и нужную."""
    сервер = форма_с_модулем(выгрузка)
    path = os.path.join(выгрузка, *МОДУЛЬ_ФОРМЫ.split("/"))
    module = open(path, encoding="utf-8-sig").read().replace(
        "#КонецОбласти", "&НаСервере\r\nПроцедура УправлениеФормой()\r\nКонецПроцедуры\r\n\r\n"
        "&НаКлиенте\r\nПроцедура Подходит(Элемент)\r\nКонецПроцедуры\r\n\r\n#КонецОбласти")
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        file.write(module)
    answer = вызвать(сервер, "forms_check", repo=выгрузка,
                    forms=флажок({"ПриИзменении": "УправлениеФормой"}, create=False))
    assert "ФОРМА-ОБРАБОТЧИК-НЕ-ТОТ" in answer and "«&НаСервере Процедура УправлениеФормой()»" \
        in answer and "«&НаКлиенте Процедура УправлениеФормой(Элемент)»" in answer, answer
    answer = вызвать(сервер, "forms_check", repo=выгрузка,
                    forms=флажок({"ПриИзменении": "Подходит"}, create=False))
    assert not answer.startswith("ОТКАЗ"), answer
    assert "обработчик Подходит: процедура в модуле формы уже есть (строка 14) — заводить " \
           "не нужно" in answer, answer


def test_an_own_module_that_does_not_fit_leaves_the_placeholder(выгрузка):
    """Свой модуль объекта берётся сам, только если он есть и годится; иначе —
    заглушка с предупреждением."""
    сервер = mcp_server(roots=[выгрузка])
    вызвать(сервер, "forms_apply", repo=выгрузка, forms=НОВАЯ)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[{
        "форма": ФОРМА, "код": True,
        "элементы": [{"вид": "Надпись", "имя": "мой_Н", "свойства": {"Заголовок": "Проба"}}]}])
    assert "ФОРМА-КОД-БЕЗ-МОДУЛЯ" in answer and "<Модуль>." in answer, answer


def test_the_preview_names_handlers_as_the_code_does(выгрузка):
    """Показ задания называет обработчик так же, как код, — с приставкой
    «Подключаемый_» (#std492): иначе по показу заводят процедуру не под тем
    именем, под которым её назначит код. Действие команды код тоже назначает
    программно — оно с приставкой, и его процедура названа среди обработчиков."""
    сервер = форма_с_модулем(выгрузка)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[{
        "форма": ФОРМА, "код": {"модуль": "ОбщийМодуль.мой_ПробаФормы"},
        "реквизиты": [{"имя": "мой_Флаг", "тип": "Булево"}],
        "команды": [{"имя": "мой_Обновить"}],
        "элементы": [{"вид": "ПолеФлажка", "имя": "мой_Флаг", "путь": "мой_Флаг",
                      "обработчики": {"ПриИзменении": True}}]}])
    assert not answer.startswith("ОТКАЗ"), answer
    assert "@ПриИзменении=Подключаемый_мой_ФлагПриИзменении" in answer, answer
    assert "=мой_ФлагПриИзменении" not in answer, answer
    assert "команда мой_Обновить -> Подключаемый_мой_Обновить" in answer, answer
    assert 'Команда.Действие = "Подключаемый_мой_Обновить";' in answer, answer
    assert "Процедура Подключаемый_мой_Обновить(" in answer, answer


def test_show_narrows_a_typical_form_to_one_branch():
    """У типовой формы показ целиком — сотни строк, а место вставки ищут в одной
    группе (типичная доработка: 330 строк ради правой колонки шапки)."""
    if not os.path.isfile(os.path.join(SRC, "Documents", "АвансовыйОтчет", "Forms",
                                       "ФормаДокумента", "Ext", "Form.xml")):
        pytest.skip("не задана выгрузка META_CORPUS")
    сервер = mcp_server(roots=[SRC])
    answer = вызвать(сервер, "show", repo=SRC, address=АВАНСОВЫЙ, element="ГруппаШапкаПравая")
    assert "Ветка «ГруппаШапкаПравая»: ГруппаШапка › ГруппаШапкаПравая" in answer, answer
    assert "ЦеныИВалюта (ПолеНадписи)" in answer and "Организация (ПолеВвода)" in answer, answer
    assert "ГруппаСтраницы" not in answer and "Реквизиты:" not in answer, answer
    assert len(answer.splitlines()) < 20, answer
    мимо = вызвать(сервер, "show", repo=SRC, address=АВАНСОВЫЙ, element="ГруппаШапкаПрав")
    assert "элемента «ГруппаШапкаПрав» на форме нет; похожие: ГруппаШапкаПравая" in мимо, мимо
    assert "без «element»" in мимо, мимо
    терминал = через_терминал(["--показать", SRC, АВАНСОВЫЙ, "ГруппаШапкаПравая"])
    assert "Ветка «ГруппаШапкаПравая»" in терминал and "без третьего аргумента --показать" \
        in терминал, терминал
    obj = вызвать(сервер, "show", repo=SRC, address="Документ.АвансовыйОтчет",
                     element="ГруппаШапка")
    assert "у объекта не применяется" in obj


def test_the_ready_edits_say_who_puts_the_indent(выгрузка):
    """Вызов в готовых правках — без отступа, и заголовок блока говорит, что
    отступ ставит инструмент: иначе неясно, ставить ли табуляцию самому."""
    сервер = форма_с_модулем(выгрузка)
    answer = вызвать(сервер, "forms_check", repo=выгрузка, forms=[надпись("мой_Чеки")])
    assert "отступ вызова до уровня места ставит инструмент" in answer, answer


def test_object_names_cannot_lead_outside_the_dump(выгрузка):
    """Имя в адресе объекта — не путь: «Справочник.C:/чужое» и «../» не читают файлы вне выгрузки."""
    outside = tempfile.mkdtemp(prefix="meta-outside-")
    try:
        with open(os.path.join(outside, "secret.xml"), "w", encoding="utf-8") as file:
            file.write("<secret>outside-marker</secret>")
        server = mcp_server(roots=[выгрузка])
        for address in ("Справочник." + os.path.join(outside, "secret"),
                        "Справочник.../../" + os.path.basename(outside) + "/secret"):
            answer = вызвать(server, "show", repo=выгрузка, address=address)
            assert "outside-marker" not in answer
            assert answer.startswith("ОТКАЗ"), answer
    finally:
        shutil.rmtree(outside, ignore_errors=True)

#: Схемы и описания инструментов агент читает в каждом запуске: бюджет держит
#: их от разрастания (замер: 56 тыс. знаков до сжатия, 30 тыс. после).
БЮДЖЕТ_СХЕМ = 32000


def test_tool_schemas_stay_within_the_budget():
    import json
    tools = asyncio.run(mcp_server(roots=[]).list_tools())
    размер = sum(len(ii.description or "") + len(json.dumps(ii.inputSchema, ensure_ascii=False))
                 for ii in tools)
    assert размер <= БЮДЖЕТ_СХЕМ, размер


def test_an_apply_schema_refers_to_its_check_and_has_no_pydantic_noise():
    import json
    tools = {ii.name: ii for ii in asyncio.run(mcp_server(roots=[]).list_tools())}
    record = tools["metadata_apply"].inputSchema
    assert "$defs" not in record
    assert record["properties"]["objects"] == {"description": "то же, что «objects» у metadata_check"}
    text = json.dumps([ii.inputSchema for ii in tools.values()], ensure_ascii=False)
    assert '"title"' not in text
    assert ', {"type": "null"}]' not in text and '[{"type": "null"}' not in text      # anyOf с null
