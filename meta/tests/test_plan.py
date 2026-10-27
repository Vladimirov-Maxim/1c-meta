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


def card(тег, name, members=()):
    """Карточка объекта: `члены` — [(тег ребёнка, имя, [обозначения типов] или None)]."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<MetaDataObject {ПРОСТРАНСТВА} version="2.21">',
              f"\t<{тег}>", "\t\t<Properties>", f"\t\t\t<Name>{name}</Name>", "\t\t</Properties>"]
    if members:
        lines.append("\t\t<ChildObjects>")
        for ребёнок, член, types in members:
            lines += [f"\t\t\t<{ребёнок}>", "\t\t\t\t<Properties>", f"\t\t\t\t\t<Name>{член}</Name>"]
            if types is not None:
                lines.append("\t\t\t\t\t<Type>")
                for type_ in types:
                    узел = "v8:TypeSet" if type_.startswith("cfg:DefinedType") else "v8:Type"
                    lines.append(f"\t\t\t\t\t\t<{узел}>{type_}</{узел}>")
                lines.append("\t\t\t\t\t</Type>")
            lines += ["\t\t\t\t</Properties>", f"\t\t\t</{ребёнок}>"]
        lines.append("\t\t</ChildObjects>")
    return lines + [f"\t</{тег}>", "</MetaDataObject>"]


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
    написать(root, РЕГИСТР, card("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    написать(root, МЕНЕДЖЕР, ["Процедура Записать(Набор) Экспорт", "КонецПроцедуры"])
    написать(root, "CommonModules/мой_Сервер.xml", card("CommonModule", "мой_Сервер"))
    написать(root, МОДУЛЬ, ["Функция Пересчитать(Договор) Экспорт", "\tВозврат 1;", "КонецФункции", "",
                            "Процедура Служебная()", "КонецПроцедуры"])
    написать(root, "Enums/мой_Виды.xml", card("Enum", "мой_Виды", [("EnumValue", "Первый", None)]))
    return root


def reconcile(capsys, root, plan, *ключи):
    """(код возврата, текст, находки JSON)."""
    файл = os.path.join(os.path.dirname(str(root)), "план.json")
    ответ = os.path.join(os.path.dirname(str(root)), "сверка.json")
    with open(файл, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False)
    if os.path.exists(ответ):
        os.remove(ответ)
    capsys.readouterr()
    code = main(["--сверить-план", str(root), "--план", файл, "--json", ответ, *map(str, ключи)])
    text = capsys.readouterr().out
    данные = json.load(open(ответ, encoding="utf-8")) if os.path.exists(ответ) else None
    return code, text, данные


def по_факту(capsys, root, *ключи):
    capsys.readouterr()
    code = main(["--план-по-факту", str(root), *map(str, ключи)])
    return code, json.loads(capsys.readouterr().out)


def коды(данные):
    return sorted(f["код"] for f in данные["находки"])


def изменить(plan, правка):
    copy_ = json.loads(json.dumps(plan))
    правка(copy_["объекты"])
    return copy_


# --- расхождения плана и факта ------------------------------------------------------------


def test_a_plan_matching_the_code_is_clean(tmp_path, capsys):
    code, text, данные = reconcile(capsys, задача(tmp_path), ХОРОШИЙ)
    assert code == 0 and данные["находки"] == [] and "СОВПАДАЕТ" in text, text


def test_a_type_of_a_dimension_differs(tmp_path, capsys):
    plan = изменить(ХОРОШИЙ, lambda ob: ob[0]["измерения"].update(
        Документ=["ДокументСсылка.А", "ДокументСсылка.Б", "ДокументСсылка.В"]))
    code, text, данные = reconcile(capsys, задача(tmp_path), plan)
    assert code == 1 and коды(данные) == ["ПЛАН-ТИПЫ-РАСХОДЯТСЯ"]
    assert "измерение «Документ»: типы расходятся; в плане, но не в выгрузке: ДокументСсылка.В" in text


def test_a_member_made_but_not_declared(tmp_path, capsys):
    code, text, данные = reconcile(capsys, задача(tmp_path), изменить(ХОРОШИЙ, lambda ob: ob[0].pop("ресурсы")))
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"] and "ресурс «Сумма» есть в выгрузке" in text
    assert данные["находки"][0]["файл"] == РЕГИСТР and данные["находки"][0]["объект"] == "РегистрСведений.мой_Рег"


def test_a_member_declared_but_not_made(tmp_path, capsys):
    plan = изменить(ХОРОШИЙ, lambda ob: ob[0]["измерения"].update(Период=["Дата"]))
    code, text, данные = reconcile(capsys, задача(tmp_path), plan)
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-СДЕЛАН"] and "измерение «Период» заявлено, в выгрузке нет" in text


def test_a_method_declared_but_not_written(tmp_path, capsys):
    plan = изменить(ХОРОШИЙ, lambda ob: ob[1].update(методы=["Пересчитать", "НетТакого"]))
    code, text, данные = reconcile(capsys, задача(tmp_path), plan)
    assert коды(данные) == ["ПЛАН-МЕТОД-НЕ-СДЕЛАН"] and "метод НетТакого заявлен, в модуле нет" in text
    assert данные["находки"][0]["файл"] == МОДУЛЬ


def test_an_object_of_the_task_not_declared(tmp_path, capsys):
    code, text, данные = reconcile(capsys, задача(tmp_path), изменить(ХОРОШИЙ, lambda ob: ob.pop(2)))
    assert code == 1 and коды(данные) == ["ПЛАН-ОБЪЕКТ-НЕ-ЗАЯВЛЕН"]
    assert "Перечисление.мой_Виды — новый объект, в плане не заявлен" in text


def test_only_declared_objects_are_checked_on_request(tmp_path, capsys):
    """Урезанный план круга: тронутое, но не заявленное — к сведению, не находкой;
    заявленное сверяется как обычно."""
    урезанный = изменить(ХОРОШИЙ, lambda ob: ob.pop(2))
    code, text, данные = reconcile(capsys, задача(tmp_path), урезанный, "--только-заявленные")
    assert code == 0 and данные["находки"] == [], text
    assert "сверены только заявленные объекты; к сведению — тронуто, но не заявлено: Перечисление.мой_Виды" \
        in text
    plan = изменить(урезанный, lambda ob: ob[0]["измерения"].update(Период=["Дата"]))
    _, _, данные = reconcile(capsys, задача(tmp_path / "2"), plan, "--только-заявленные")
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-СДЕЛАН"]


def test_a_new_export_method_outside_the_plan_is_a_warning_with_its_line(tmp_path, capsys):
    root = задача(tmp_path)
    написать(root, МОДУЛЬ, ["Функция Пересчитать(Договор) Экспорт", "\tВозврат 1;", "КонецФункции", "",
                            "Функция Ещё(", "\tПараметр) Экспорт", "КонецФункции", "",
                            "Процедура Служебная()", "КонецПроцедуры"])
    code, text, данные = reconcile(capsys, root, ХОРОШИЙ)
    assert code == 0 and коды(данные) == ["ПЛАН-МЕТОД-НЕ-ЗАЯВЛЕН"], text
    assert данные["находки"][0]["строка"] == 5 and "Служебная" not in text


# --- запись типов ------------------------------------------------------------------------


def test_the_type_is_written_either_way_and_compared_without_qualifiers(tmp_path, capsys):
    """«СправочникСсылка.Х» — как синтакс-помощник, «Справочник.Х» — как показ;
    длина, точность и состав даты не сверяются."""
    root = задача(tmp_path)
    написать(root, РЕГИСТР, card("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Период", ["xs:dateTime"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    plan = изменить(ХОРОШИЙ, lambda ob: ob[0].update(
        измерения={"Договор": ["Справочник.ДоговорыКонтрагентов"], "Документ": ["Документ.Б", "ДокументСсылка.А"],
                   "Период": ["Дата"]},
        ресурсы={"Сумма": ["Число(15,2)"]}))
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text


def test_a_defined_type_is_a_type_too(tmp_path, capsys):
    """Тип-набор записан другим узлом (`TypeSet`): сверка по одним `Type` видела
    бы у такого измерения пустой состав, и заявленный тип расходился бы."""
    root = задача(tmp_path)
    написать(root, РЕГИСТР, card("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Место", ["cfg:DefinedType.мой_Места"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    plan = изменить(ХОРОШИЙ, lambda ob: ob[0]["измерения"].update(Место=["ОпределяемыйТип.мой_Места"]))
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text


# --- изменяемые объекты, попутное, удаление ---------------------------------------------------


def вендорский_с_реквизитом(tmp_path):
    root = выгрузка(tmp_path)
    написать(root, "Documents/Вендорский.xml", card("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"])]))
    зафиксировать(root)
    написать(root, "Documents/Вендорский.xml", card("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"]), ("Attribute", "мой_Признак", ["xs:boolean"])]))
    return root


def test_a_changed_object_declares_only_what_the_task_added(tmp_path, capsys):
    root = вендорский_с_реквизитом(tmp_path)
    plan = {"объекты": [{"вид": "Документ", "имя": "Вендорский", "действие": "изменить",
                         "реквизиты": {"мой_Признак": ["Булево"]}}]}
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text
    plan["объекты"][0].pop("реквизиты")
    code, text, данные = reconcile(capsys, root, plan)
    assert коды(данные) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"] and "мой_Признак" in text and "«Сумма»" not in text


def test_a_change_declared_without_edits_is_a_warning(tmp_path, capsys):
    root = выгрузка(tmp_path)
    написать(root, "Documents/Вендорский.xml", card("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"])]))
    зафиксировать(root)
    plan = {"объекты": [{"вид": "Документ", "имя": "Вендорский", "действие": "изменить"}]}
    code, text, данные = reconcile(capsys, root, plan)
    assert code == 0 and коды(данные) == ["ПЛАН-ОБЪЕКТ-БЕЗ-ПРАВОК"], text


def test_an_unreadable_card_is_named_not_skipped(tmp_path, capsys):
    """Сломанная карточка — расхождение с причиной, а не молча пустой состав."""
    root = задача(tmp_path)
    написать(root, РЕГИСТР, ["<MetaDataObject/>"])
    code, text, данные = reconcile(capsys, root, ХОРОШИЙ)
    assert коды(данные) == ["ПЛАН-КАРТОЧКА-НЕ-ЧИТАЕТСЯ"] and "объявлением XML" in text, text


def test_a_role_touched_along_the_way_is_a_warning(tmp_path, capsys):
    root = задача(tmp_path)
    написать(root, "Roles/мой_Чтение/Ext/Rights.xml", ["<Rights/>"])
    code, text, данные = reconcile(capsys, root, ХОРОШИЙ)
    assert code == 0 and коды(данные) == ["ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО"], text
    assert "Роль.мой_Чтение — новый объект" not in text and "Роль.мой_Чтение — изменён" in text


def test_deletion(tmp_path, capsys):
    root = выгрузка(tmp_path)
    os.remove(os.path.join(str(root), "Documents", "мой_Наш.xml"))
    shutil.rmtree(os.path.join(str(root), "Documents", "мой_Наш"))
    plan = {"объекты": [{"вид": "Документ", "имя": "мой_Наш", "действие": "удалить"}]}
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text
    plan["объекты"].append({"вид": "Документ", "имя": "Вендорский", "действие": "удалить"})
    code, text, данные = reconcile(capsys, root, plan)
    assert коды(данные) == ["ПЛАН-ОБЪЕКТ-ОСТАЛСЯ"], text


def test_a_revision_is_checked_as_well_as_the_working_copy(tmp_path, capsys):
    root = задача(tmp_path)
    зафиксировать(root, "задача")
    code, text, _ = reconcile(capsys, root, ХОРОШИЙ, "--база", "HEAD~1", "--ревизия", "HEAD")
    assert code == 0 and "ревизия HEAD против HEAD~1" in text, text


def test_the_profile_sets_the_level(tmp_path, capsys):
    root = задача(tmp_path)
    написать(root, "Roles/мой_Чтение/Ext/Rights.xml", ["<Rights/>"])
    профиль = tmp_path / "профиль.json"
    профиль.write_text(json.dumps({"приставка": "мой_", "правила": {"ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО": "ошибка"}},
                                  ensure_ascii=False), encoding="utf-8")
    code, _, _ = reconcile(capsys, root, ХОРОШИЙ, "--профиль", профиль)
    assert code == 1


# --- неверный план — отказ ------------------------------------------------------------------


@pytest.mark.parametrize("правка, слова", [
    (lambda ob: ob[0].update(измерение={"Х": None}), "неизвестные ключи измерение"),
    (lambda ob: ob[0].update(действие="переделать"), "бывает: создать, изменить, удалить"),
    (lambda ob: ob[0].update(методы=["Записать"]), "«методы» — у вида с одним модулем"),
    (lambda ob: ob[0].update(модули={"МодульФормы": []}), "модуль «МодульФормы»"),
    (lambda ob: ob.append(dict(ob[1])), "в плане дважды"),
    (lambda ob: ob[2].update(значения={"Первый": ["Строка"]}), "у значения перечисления типов не бывает"),
    (lambda ob: ob.append({"вид": "Выдумка", "имя": "Х", "действие": "создать"}), "выгрузке неизвестен"),
])
def test_a_wrong_plan_is_refused_not_half_checked(tmp_path, capsys, правка, слова):
    """Опечатка в ключе молча выключила бы сверку того, что за ним стоит."""
    code, text, данные = reconcile(capsys, задача(tmp_path), изменить(ХОРОШИЙ, правка))
    assert code == 2 and данные is None and text.startswith("ОТКАЗ:") and слова in text, text


# --- план по факту ----------------------------------------------------------------------


def test_the_plan_by_fact_passes_the_check_itself(tmp_path, capsys):
    root = задача(tmp_path)
    code, plan = по_факту(capsys, root)
    assert code == 0
    objects = {(ob["вид"], ob["имя"]): ob for ob in plan["объекты"]}
    assert set(objects) == {("РегистрСведений", "мой_Рег"), ("ОбщийМодуль", "мой_Сервер"),
                            ("Перечисление", "мой_Виды")}
    assert objects[("ОбщийМодуль", "мой_Сервер")]["методы"] == ["Пересчитать", "Служебная"]
    assert objects[("Перечисление", "мой_Виды")]["значения"] == ["Первый"]
    assert objects[("РегистрСведений", "мой_Рег")]["ресурсы"] == {"Сумма": ["Число(0,0)"]}
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text


def test_what_the_tool_wrote_the_plan_check_reads(tmp_path, capsys):
    """Объекты, записанные самим инструментом: план по факту — записью показа,
    и сверка принимает его без расхождений."""
    root = tmp_path / "cf"
    root.mkdir()
    shutil.copyfile(os.path.join(ЭТАЛОНЫ, "Configuration.xml"), root / "Configuration.xml")
    git(root, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git(root, "config", key, value)
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
    code, plan = по_факту(capsys, root)
    регистр = next(ob for ob in plan["объекты"] if ob["имя"] == "мой_Остатки")
    assert регистр["ресурсы"] == {"Сумма": ["Число(15,2)"]} and регистр["измерения"] == {
        "Вид": ["Перечисление.мой_Виды"]}
    code, text, данные = reconcile(capsys, root, plan)
    assert code == 0 and данные["находки"] == [], text


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

    objects = json.loads(json.dumps(ХОРОШИЙ["объекты"]))
    objects[0]["измерения"]["Договор"] = None              # null — тип не сверяется
    assert "СОВПАДАЕТ" in вызвать("plan_check", repo=str(root), objects=objects)
    objects[0]["измерения"]["Лишнее"] = ["Булево"]
    assert "ПЛАН-ЧЛЕН-НЕ-СДЕЛАН" in вызвать("plan_check", repo=str(root), objects=objects)
    plan = json.loads(вызвать("plan_emit", repo=str(root)))
    assert {ob["имя"] for ob in plan["объекты"]} == {"мой_Рег", "мой_Сервер", "мой_Виды"}
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
    text = capsys.readouterr().out
    return text, json.load(open(ответ, encoding="utf-8"))


def test_a_narrower_type_set_of_a_similar_member_is_a_warning(tmp_path, capsys):
    """Измерение держит два вида документов, а соседнее — три: запись значения
    третьего вида в первое упадёт."""
    root = выгрузка(tmp_path)
    написать(root, "InformationRegisters/мой_Итог.xml", card("InformationRegister", "мой_Итог", [
        ("Dimension", "ДокументВыдачи", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "ДокументЗачета", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"])]))
    text, данные = проверить_правки(capsys, root)
    findings = [f for f in данные["находки"] if f["код"] == "СОСТАВ-ТИПОВ-УЖЕ"]
    assert len(findings) == 1 and findings[0]["уровень"] == "предупреждение", text
    assert "«РегистрСведений.мой_Итог.ДокументВыдачи» — состав типов уже" in findings[0]["текст"]
    assert "нет Документ.В" in findings[0]["текст"]


def test_equal_or_far_type_sets_and_old_members_are_left_alone(tmp_path, capsys):
    """Одинаковые составы — согласованы; различие больше чем в два типа —
    разные по смыслу члены; член, бывший до задачи, — не её решение."""
    root = выгрузка(tmp_path)
    написать(root, "InformationRegisters/мой_Итог.xml", card("InformationRegister", "мой_Итог", [
        ("Dimension", "Старый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"])]))
    зафиксировать(root)
    написать(root, "InformationRegisters/мой_Итог.xml", card("InformationRegister", "мой_Итог", [
        ("Dimension", "Старый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Первый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"]),
        ("Dimension", "Второй", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"]),
        ("Dimension", "Широкий", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В",
                                  "cfg:DocumentRef.Г", "cfg:DocumentRef.Д", "cfg:DocumentRef.Е"])]))
    text, данные = проверить_правки(capsys, root)
    assert not [f for f in данные["находки"] if f["код"] == "СОСТАВ-ТИПОВ-УЖЕ"], text
