"""План изменений: сверка с фактом и план по факту — через терминал и MCP.

Кейсы: тип измерения разошёлся, член не заявлен, заявленный метод не написан,
объект задачи не заявлен, заявлено и не сделано. И то, что отличает сверку от
сравнения по тексту: тип пишут и записью показа, и записью синтакс-помощника;
тип-набор (определяемый тип) — тоже тип; у изменяемого вендорского объекта
сверяется только добавленное задачей; роль, тронутая попутно, —
предупреждение. Главный кейс — объект, записанный самим инструментом: план по
факту проходит сверку сам с собой.
"""

import asyncio
import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.tests.test_verify import git, выгрузка, зафиксировать, написать  # noqa: E402

ПРОСТРАНСТВА = ('xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"')
ЭТАЛОНЫ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны", "формы")


def карточка(тег, имя, члены=()):
    """Карточка объекта: `члены` — [(тег ребёнка, имя, [обозначения типов] или None)]."""
    строки = ['<?xml version="1.0" encoding="UTF-8"?>', f'<MetaDataObject {ПРОСТРАНСТВА} version="2.21">',
              f"\t<{тег}>", "\t\t<Properties>", f"\t\t\t<Name>{имя}</Name>", "\t\t</Properties>"]
    if члены:
        строки.append("\t\t<ChildObjects>")
        for ребёнок, член, типы in члены:
            строки += [f"\t\t\t<{ребёнок}>", "\t\t\t\t<Properties>", f"\t\t\t\t\t<Name>{член}</Name>"]
            if типы is not None:
                строки.append("\t\t\t\t\t<Type>")
                for тип in типы:
                    узел = "v8:TypeSet" if тип.startswith("cfg:DefinedType") else "v8:Type"
                    строки.append(f"\t\t\t\t\t\t<{узел}>{тип}</{узел}>")
                строки.append("\t\t\t\t\t</Type>")
            строки += ["\t\t\t\t</Properties>", f"\t\t\t</{ребёнок}>"]
        строки.append("\t\t</ChildObjects>")
    return строки + [f"\t</{тег}>", "</MetaDataObject>"]


РЕГИСТР = "InformationRegisters/мой_Рег.xml"
МОДУЛЬ = "CommonModules/мой_Сервер/Ext/Module.bsl"
МЕНЕДЖЕР = "InformationRegisters/мой_Рег/Ext/ManagerModule.bsl"

ХОРОШИЙ = {"объекты": [
    {"вид": "РегистрСведений", "имя": "мой_Рег", "действие": "создать",
     "измерения": {"Договор": ["СправочникСсылка.ДоговорыКонтрагентов"],
                   "Документ": ["ДокументСсылка.А", "ДокументСсылка.Б"]},
     "ресурсы": {"Сумма": ["Число"]},
     "модули": {"МодульМенеджера": ["Записать"]}},
    {"вид": "ОбщийМодуль", "имя": "мой_Сервер", "действие": "создать", "методы": ["Пересчитать"]},
    {"вид": "Перечисление", "имя": "мой_Виды", "действие": "создать", "значения": ["Первый"]}]}


def задача(tmp_path):
    """Выгрузка с правками задачи: новый регистр с модулем менеджера, общий
    модуль и перечисление — в рабочей копии, против базы."""
    root = выгрузка(tmp_path)
    написать(root, РЕГИСТР, карточка("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    написать(root, МЕНЕДЖЕР, ["Процедура Записать(Набор) Экспорт", "КонецПроцедуры"])
    написать(root, "CommonModules/мой_Сервер.xml", карточка("CommonModule", "мой_Сервер"))
    написать(root, МОДУЛЬ, ["Функция Пересчитать(Договор) Экспорт", "\tВозврат 1;", "КонецФункции", "",
                            "Процедура Служебная()", "КонецПроцедуры"])
    написать(root, "Enums/мой_Виды.xml", карточка("Enum", "мой_Виды", [("EnumValue", "Первый", None)]))
    return root


def сверить(capsys, root, план, *ключи):
    """(код возврата, текст, находки JSON)."""
    файл = os.path.join(os.path.dirname(str(root)), "план.json")
    ответ = os.path.join(os.path.dirname(str(root)), "сверка.json")
    with open(файл, "w", encoding="utf-8") as f:
        json.dump(план, f, ensure_ascii=False)
    if os.path.exists(ответ):
        os.remove(ответ)
    capsys.readouterr()
    код = main(["--сверить-план", str(root), "--план", файл, "--json", ответ, *map(str, ключи)])
    текст = capsys.readouterr().out
    данные = json.load(open(ответ, encoding="utf-8")) if os.path.exists(ответ) else None
    return код, текст, данные


def по_факту(capsys, root, *ключи):
    capsys.readouterr()
    код = main(["--план-по-факту", str(root), *map(str, ключи)])
    return код, json.loads(capsys.readouterr().out)


def коды(данные):
    return sorted(f["код"] for f in данные["находки"])


def изменить(план, правка):
    копия = json.loads(json.dumps(план))
    правка(копия["объекты"])
    return копия


# --- расхождения плана и факта ------------------------------------------------------------


def test_a_plan_matching_the_code_is_clean(tmp_path, capsys):
    код, текст, данные = сверить(capsys, задача(tmp_path), ХОРОШИЙ)
    assert код == 0 and данные["находки"] == [] and "СОВПАДАЕТ" in текст, текст


def test_a_type_of_a_dimension_differs(tmp_path, capsys):
    план = изменить(ХОРОШИЙ, lambda о: о[0]["измерения"].update(
        Документ=["ДокументСсылка.А", "ДокументСсылка.Б", "ДокументСсылка.В"]))
    код, текст, данные = сверить(capsys, задача(tmp_path), план)
    assert код == 1 and коды(данные) == ["ПЛАН-ТИПЫ-РАСХОДЯТСЯ"]
    assert "измерение «Документ»: типы расходятся; в плане, но не в выгрузке: ДокументСсылка.В" in текст


def test_a_member_made_but_not_declared(tmp_path, capsys):
    код, текст, данные = сверить(capsys, задача(tmp_path), изменить(ХОРОШИЙ, lambda о: о[0].pop("ресурсы")))
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"] and "ресурс «Сумма» есть в выгрузке" in текст
    assert данные["находки"][0]["файл"] == РЕГИСТР and данные["находки"][0]["объект"] == "РегистрСведений.мой_Рег"


def test_a_member_declared_but_not_made(tmp_path, capsys):
    план = изменить(ХОРОШИЙ, lambda о: о[0]["измерения"].update(Период=["Дата"]))
    код, текст, данные = сверить(capsys, задача(tmp_path), план)
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-СДЕЛАН"] and "измерение «Период» заявлено, в выгрузке нет" in текст


def test_a_method_declared_but_not_written(tmp_path, capsys):
    план = изменить(ХОРОШИЙ, lambda о: о[1].update(методы=["Пересчитать", "НетТакого"]))
    код, текст, данные = сверить(capsys, задача(tmp_path), план)
    assert коды(данные) == ["ПЛАН-МЕТОД-НЕ-СДЕЛАН"] and "метод НетТакого заявлен, в модуле нет" in текст
    assert данные["находки"][0]["файл"] == МОДУЛЬ


def test_an_object_of_the_task_not_declared(tmp_path, capsys):
    код, текст, данные = сверить(capsys, задача(tmp_path), изменить(ХОРОШИЙ, lambda о: о.pop(2)))
    assert код == 1 and коды(данные) == ["ПЛАН-ОБЪЕКТ-НЕ-ЗАЯВЛЕН"]
    assert "Перечисление.мой_Виды — новый объект, в плане не заявлен" in текст


def test_a_new_export_method_outside_the_plan_is_a_warning_with_its_line(tmp_path, capsys):
    root = задача(tmp_path)
    написать(root, МОДУЛЬ, ["Функция Пересчитать(Договор) Экспорт", "\tВозврат 1;", "КонецФункции", "",
                            "Функция Ещё(", "\tПараметр) Экспорт", "КонецФункции", "",
                            "Процедура Служебная()", "КонецПроцедуры"])
    код, текст, данные = сверить(capsys, root, ХОРОШИЙ)
    assert код == 0 and коды(данные) == ["ПЛАН-МЕТОД-НЕ-ЗАЯВЛЕН"], текст
    assert данные["находки"][0]["строка"] == 5 and "Служебная" not in текст


# --- запись типов ------------------------------------------------------------------------


def test_the_type_is_written_either_way_and_compared_without_qualifiers(tmp_path, capsys):
    """«СправочникСсылка.Х» — как синтакс-помощник, «Справочник.Х» — как показ;
    длина, точность и состав даты не сверяются."""
    root = задача(tmp_path)
    написать(root, РЕГИСТР, карточка("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Период", ["xs:dateTime"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    план = изменить(ХОРОШИЙ, lambda о: о[0].update(
        измерения={"Договор": ["Справочник.ДоговорыКонтрагентов"], "Документ": ["Документ.Б", "ДокументСсылка.А"],
                   "Период": ["Дата"]},
        ресурсы={"Сумма": ["Число(15,2)"]}))
    код, текст, _ = сверить(capsys, root, план)
    assert код == 0, текст


def test_a_defined_type_is_a_type_too(tmp_path, capsys):
    """Тип-набор записан другим узлом (`TypeSet`): сверка по одним `Type` видела
    бы у такого измерения пустой состав, и заявленный тип расходился бы."""
    root = задача(tmp_path)
    написать(root, РЕГИСТР, карточка("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Место", ["cfg:DefinedType.мой_Места"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    план = изменить(ХОРОШИЙ, lambda о: о[0]["измерения"].update(Место=["ОпределяемыйТип.мой_Места"]))
    код, текст, _ = сверить(capsys, root, план)
    assert код == 0, текст


# --- изменяемые объекты, попутное, удаление ---------------------------------------------------


def вендорский_с_реквизитом(tmp_path):
    root = выгрузка(tmp_path)
    написать(root, "Documents/Вендорский.xml", карточка("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"])]))
    зафиксировать(root)
    написать(root, "Documents/Вендорский.xml", карточка("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"]), ("Attribute", "мой_Признак", ["xs:boolean"])]))
    return root


def test_a_changed_object_declares_only_what_the_task_added(tmp_path, capsys):
    root = вендорский_с_реквизитом(tmp_path)
    план = {"объекты": [{"вид": "Документ", "имя": "Вендорский", "действие": "изменить",
                         "реквизиты": {"мой_Признак": ["Булево"]}}]}
    код, текст, _ = сверить(capsys, root, план)
    assert код == 0, текст
    план["объекты"][0].pop("реквизиты")
    код, текст, данные = сверить(capsys, root, план)
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"] and "мой_Признак" in текст and "«Сумма»" not in текст


def test_a_change_declared_without_edits_is_a_warning(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, "Documents/Вендорский.xml", карточка("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"])]))
    зафиксировать(root)
    план = {"объекты": [{"вид": "Документ", "имя": "Вендорский", "действие": "изменить"}]}
    код, текст, данные = сверить(capsys, root, план)
    assert код == 0 and коды(данные) == ["ПЛАН-ОБЪЕКТ-БЕЗ-ПРАВОК"], текст


def test_an_unreadable_card_is_named_not_skipped(tmp_path, capsys):
    """Сломанная карточка — расхождение с причиной, а не молча пустой состав."""
    root = задача(tmp_path)
    написать(root, РЕГИСТР, ["<MetaDataObject/>"])
    код, текст, данные = сверить(capsys, root, ХОРОШИЙ)
    assert коды(данные) == ["ПЛАН-КАРТОЧКА-НЕ-ЧИТАЕТСЯ"] and "объявлением XML" in текст, текст


def test_a_role_touched_along_the_way_is_a_warning(tmp_path, capsys):
    root = задача(tmp_path)
    написать(root, "Roles/мой_Чтение/Ext/Rights.xml", ["<Rights/>"])
    код, текст, данные = сверить(capsys, root, ХОРОШИЙ)
    assert код == 0 and коды(данные) == ["ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО"], текст
    assert "Роль.мой_Чтение — новый объект" not in текст and "Роль.мой_Чтение — изменён" in текст


def test_deletion(tmp_path, capsys):
    root = выгрузка(tmp_path)
    os.remove(os.path.join(str(root), "Documents", "мой_Наш.xml"))
    shutil.rmtree(os.path.join(str(root), "Documents", "мой_Наш"))
    план = {"объекты": [{"вид": "Документ", "имя": "мой_Наш", "действие": "удалить"}]}
    код, текст, _ = сверить(capsys, root, план)
    assert код == 0, текст
    план["объекты"].append({"вид": "Документ", "имя": "Вендорский", "действие": "удалить"})
    код, текст, данные = сверить(capsys, root, план)
    assert коды(данные) == ["ПЛАН-ОБЪЕКТ-ОСТАЛСЯ"], текст


def test_a_revision_is_checked_as_well_as_the_working_copy(tmp_path, capsys):
    root = задача(tmp_path)
    зафиксировать(root, "задача")
    код, текст, _ = сверить(capsys, root, ХОРОШИЙ, "--база", "HEAD~1", "--ревизия", "HEAD")
    assert код == 0 and "ревизия HEAD против HEAD~1" in текст, текст


def test_the_profile_sets_the_level(tmp_path, capsys):
    root = задача(tmp_path)
    написать(root, "Roles/мой_Чтение/Ext/Rights.xml", ["<Rights/>"])
    профиль = tmp_path / "профиль.json"
    профиль.write_text(json.dumps({"приставка": "мой_", "правила": {"ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО": "ошибка"}},
                                  ensure_ascii=False), encoding="utf-8")
    код, _, _ = сверить(capsys, root, ХОРОШИЙ, "--профиль", профиль)
    assert код == 1


# --- неверный план — отказ ------------------------------------------------------------------


@pytest.mark.parametrize("правка, слова", [
    (lambda о: о[0].update(измерение={"Х": None}), "неизвестные ключи измерение"),
    (lambda о: о[0].update(действие="переделать"), "бывает: создать, изменить, удалить"),
    (lambda о: о[0].update(методы=["Записать"]), "«методы» — у вида с одним модулем"),
    (lambda о: о[0].update(модули={"МодульФормы": []}), "модуль «МодульФормы»"),
    (lambda о: о.append(dict(о[1])), "в плане дважды"),
    (lambda о: о[2].update(значения={"Первый": ["Строка"]}), "у значения перечисления типов не бывает"),
    (lambda о: о.append({"вид": "Выдумка", "имя": "Х", "действие": "создать"}), "выгрузке неизвестен"),
])
def test_a_wrong_plan_is_refused_not_half_checked(tmp_path, capsys, правка, слова):
    """Опечатка в ключе молча выключила бы сверку того, что за ним стоит."""
    код, текст, данные = сверить(capsys, задача(tmp_path), изменить(ХОРОШИЙ, правка))
    assert код == 2 and данные is None and текст.startswith("ОТКАЗ:") and слова in текст, текст


# --- план по факту ----------------------------------------------------------------------


def test_the_plan_by_fact_passes_the_check_itself(tmp_path, capsys):
    root = задача(tmp_path)
    код, план = по_факту(capsys, root)
    assert код == 0
    объекты = {(о["вид"], о["имя"]): о for о in план["объекты"]}
    assert set(объекты) == {("РегистрСведений", "мой_Рег"), ("ОбщийМодуль", "мой_Сервер"),
                            ("Перечисление", "мой_Виды")}
    assert объекты[("ОбщийМодуль", "мой_Сервер")]["методы"] == ["Пересчитать", "Служебная"]
    assert объекты[("Перечисление", "мой_Виды")]["значения"] == ["Первый"]
    assert объекты[("РегистрСведений", "мой_Рег")]["ресурсы"] == {"Сумма": ["Число(0,0)"]}
    код, текст, _ = сверить(capsys, root, план)
    assert код == 0, текст


def test_what_the_tool_wrote_the_plan_check_reads(tmp_path, capsys):
    """Объекты, записанные самим инструментом: план по факту — записью показа,
    и сверка принимает его без расхождений."""
    root = tmp_path / "cf"
    root.mkdir()
    shutil.copyfile(os.path.join(ЭТАЛОНЫ, "Configuration.xml"), root / "Configuration.xml")
    git(root, "init", "-q")
    for ключ, значение in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git(root, "config", ключ, значение)
    зафиксировать(root)
    задание = tmp_path / "задание.json"
    задание.write_text(json.dumps({"repo": str(root), "objects": [
        {"вид": "Перечисление", "поля": {"имя": "мой_Виды", "синоним": "Виды",
                                         "значения": [{"имя": "Первый", "синоним": "Первый"}]}},
        {"вид": "РегистрСведений", "поля": {"имя": "мой_Остатки", "синоним": "Остатки", "измерения": [
            {"имя": "Вид", "синоним": "Вид", "тип": "Перечисление.мой_Виды"}],
            "ресурсы": [{"имя": "Сумма", "синоним": "Сумма", "тип": "Число(15,2)"}]}}]},
        ensure_ascii=False), encoding="utf-8")
    assert main([str(задание), "--apply"]) == 0
    код, план = по_факту(capsys, root)
    регистр = next(о for о in план["объекты"] if о["имя"] == "мой_Остатки")
    assert регистр["ресурсы"] == {"Сумма": ["Число(15,2)"]} and регистр["измерения"] == {
        "Вид": ["Перечисление.мой_Виды"]}
    код, текст, данные = сверить(capsys, root, план)
    assert код == 0 and данные["находки"] == [], текст


# --- MCP ----------------------------------------------------------------------------------


def test_the_agent_checks_a_plan_and_gets_the_fact(tmp_path):
    from meta.composition import mcp_server

    root = задача(tmp_path)
    сервер = mcp_server(roots=[str(root)])

    def вызвать(инструмент, **аргументы):
        ответ = asyncio.run(сервер.call_tool(инструмент, аргументы))
        if isinstance(ответ, tuple):
            ответ = ответ[0]
        return "\n".join(блок.text for блок in ответ)

    объекты = json.loads(json.dumps(ХОРОШИЙ["объекты"]))
    объекты[0]["измерения"]["Договор"] = None              # null — тип не сверяется
    assert "СОВПАДАЕТ" in вызвать("plan_check", repo=str(root), objects=объекты)
    объекты[0]["измерения"]["Лишнее"] = ["Булево"]
    assert "ПЛАН-ЧЛЕН-НЕ-СДЕЛАН" in вызвать("plan_check", repo=str(root), objects=объекты)
    план = json.loads(вызвать("plan_emit", repo=str(root)))
    assert {о["имя"] for о in план["объекты"]} == {"мой_Рег", "мой_Сервер", "мой_Виды"}
    assert вызвать("plan_emit", repo=str(tmp_path)).startswith("ОТКАЗ: выгрузка")


# --- составы типов: правило проверки правок ----------------------------------------------
# Плана оно не требует — судит правки задачи, поэтому живёт в verify; карточки
# для него строятся здесь же.


def проверить_правки(capsys, root):
    ответ = os.path.join(os.path.dirname(str(root)), "проверка.json")
    if os.path.exists(ответ):
        os.remove(ответ)
    capsys.readouterr()
    main(["--проверить", str(root), "--json", ответ])
    текст = capsys.readouterr().out
    return текст, json.load(open(ответ, encoding="utf-8"))


def test_a_narrower_type_set_of_a_similar_member_is_a_warning(tmp_path, capsys):
    """Измерение держит два вида документов, а соседнее — три: запись значения
    третьего вида в первое упадёт."""
    root = выгрузка(tmp_path)
    написать(root, "InformationRegisters/мой_Итог.xml", карточка("InformationRegister", "мой_Итог", [
        ("Dimension", "ДокументВыдачи", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "ДокументЗачета", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"])]))
    текст, данные = проверить_правки(capsys, root)
    находки = [f for f in данные["находки"] if f["код"] == "СОСТАВ-ТИПОВ-УЖЕ"]
    assert len(находки) == 1 and находки[0]["уровень"] == "предупреждение", текст
    assert "«РегистрСведений.мой_Итог.ДокументВыдачи» — состав типов уже" in находки[0]["текст"]
    assert "нет Документ.В" in находки[0]["текст"]


def test_equal_or_far_type_sets_and_old_members_are_left_alone(tmp_path, capsys):
    """Одинаковые составы — согласованы; различие больше чем в два типа —
    разные по смыслу члены; член, бывший до задачи, — не её решение."""
    root = выгрузка(tmp_path)
    написать(root, "InformationRegisters/мой_Итог.xml", карточка("InformationRegister", "мой_Итог", [
        ("Dimension", "Старый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"])]))
    зафиксировать(root)
    написать(root, "InformationRegisters/мой_Итог.xml", карточка("InformationRegister", "мой_Итог", [
        ("Dimension", "Старый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Первый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"]),
        ("Dimension", "Второй", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"]),
        ("Dimension", "Широкий", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В",
                                  "cfg:DocumentRef.Г", "cfg:DocumentRef.Д", "cfg:DocumentRef.Е"])]))
    текст, данные = проверить_правки(capsys, root)
    assert not [f for f in данные["находки"] if f["код"] == "СОСТАВ-ТИПОВ-УЖЕ"], текст
