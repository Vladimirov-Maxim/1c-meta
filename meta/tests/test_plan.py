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
from meta.tests.test_verify import commit, dump_dir, git, write_file  # noqa: E402

NAMESPACES = ('xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
                'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"')
GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "эталоны", "формы")


def card(tag, name, members=()):
    """Карточка объекта: `члены` — [(тег ребёнка, имя, [обозначения типов] или None)]."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<MetaDataObject {NAMESPACES} version="2.21">',
              f"\t<{tag}>", "\t\t<Properties>", f"\t\t\t<Name>{name}</Name>", "\t\t</Properties>"]
    if members:
        lines.append("\t\t<ChildObjects>")
        for child, member, types in members:
            lines += [f"\t\t\t<{child}>", "\t\t\t\t<Properties>", f"\t\t\t\t\t<Name>{member}</Name>"]
            if types is not None:
                lines.append("\t\t\t\t\t<Type>")
                for type_ in types:
                    node = "v8:TypeSet" if type_.startswith("cfg:DefinedType") else "v8:Type"
                    lines.append(f"\t\t\t\t\t\t<{node}>{type_}</{node}>")
                lines.append("\t\t\t\t\t</Type>")
            lines += ["\t\t\t\t</Properties>", f"\t\t\t</{child}>"]
        lines.append("\t\t</ChildObjects>")
    return lines + [f"\t</{tag}>", "</MetaDataObject>"]


REGISTER = "InformationRegisters/мой_Рег.xml"
MODULE = "CommonModules/мой_Сервер/Ext/Module.bsl"
MANAGER = "InformationRegisters/мой_Рег/Ext/ManagerModule.bsl"

GOOD = {"объекты": [
    {"вид": "РегистрСведений", "имя": "мой_Рег", "действие": "создать",
     "измерения": {"Договор": ["СправочникСсылка.ДоговорыКонтрагентов"],
                   "Документ": ["ДокументСсылка.А", "ДокументСсылка.Б"]},
     "ресурсы": {"Сумма": ["Число"]},
     "модули": {"МодульМенеджера": ["Записать"]}},
    {"вид": "ОбщийМодуль", "имя": "мой_Сервер", "действие": "создать", "методы": ["Пересчитать"]},
    {"вид": "Перечисление", "имя": "мой_Виды", "действие": "создать", "значения": ["Первый"]}]}


def task_dir(tmp_path):
    """Выгрузка с правками задачи: новый регистр с модулем менеджера, общий
    модуль и перечисление — в рабочей копии, против базы."""
    root = dump_dir(tmp_path)
    write_file(root, REGISTER, card("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    write_file(root, MANAGER, ["Процедура Записать(Набор) Экспорт", "КонецПроцедуры"])
    write_file(root, "CommonModules/мой_Сервер.xml", card("CommonModule", "мой_Сервер"))
    write_file(root, MODULE, ["Функция Пересчитать(Договор) Экспорт", "\tВозврат 1;", "КонецФункции", "",
                            "Процедура Служебная()", "КонецПроцедуры"])
    write_file(root, "Enums/мой_Виды.xml", card("Enum", "мой_Виды", [("EnumValue", "Первый", None)]))
    return root


def reconcile(capsys, root, plan, *keys):
    """(код возврата, текст, находки JSON)."""
    file = os.path.join(os.path.dirname(str(root)), "план.json")
    answer = os.path.join(os.path.dirname(str(root)), "сверка.json")
    with open(file, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False)
    if os.path.exists(answer):
        os.remove(answer)
    capsys.readouterr()
    code = main(["--сверить-план", str(root), "--план", file, "--json", answer, *map(str, keys)])
    text = capsys.readouterr().out
    data = json.load(open(answer, encoding="utf-8")) if os.path.exists(answer) else None
    return code, text, data


def from_fact(capsys, root, *keys):
    capsys.readouterr()
    code = main(["--план-по-факту", str(root), *map(str, keys)])
    return code, json.loads(capsys.readouterr().out)


def codes(data):
    return sorted(f["код"] for f in data["находки"])


def modify(plan, edit_job):
    copy_ = json.loads(json.dumps(plan))
    edit_job(copy_["объекты"])
    return copy_


# --- расхождения плана и факта ------------------------------------------------------------


def test_a_plan_matching_the_code_is_clean(tmp_path, capsys):
    code, text, data = reconcile(capsys, task_dir(tmp_path), GOOD)
    assert code == 0 and data["находки"] == [] and "СОВПАДАЕТ" in text, text


def test_a_type_of_a_dimension_differs(tmp_path, capsys):
    plan = modify(GOOD, lambda ob: ob[0]["измерения"].update(
        Документ=["ДокументСсылка.А", "ДокументСсылка.Б", "ДокументСсылка.В"]))
    code, text, data = reconcile(capsys, task_dir(tmp_path), plan)
    assert code == 1 and codes(data) == ["ПЛАН-ТИПЫ-РАСХОДЯТСЯ"]
    assert "измерение «Документ»: типы расходятся; в плане, но не в выгрузке: ДокументСсылка.В" in text


def test_a_member_made_but_not_declared(tmp_path, capsys):
    code, text, data = reconcile(capsys, task_dir(tmp_path), modify(GOOD, lambda ob: ob[0].pop("ресурсы")))
    assert codes(data) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"] and "ресурс «Сумма» есть в выгрузке" in text
    assert data["находки"][0]["файл"] == REGISTER and data["находки"][0]["объект"] == "РегистрСведений.мой_Рег"


def test_a_member_declared_but_not_made(tmp_path, capsys):
    plan = modify(GOOD, lambda ob: ob[0]["измерения"].update(Период=["Дата"]))
    code, text, data = reconcile(capsys, task_dir(tmp_path), plan)
    assert codes(data) == ["ПЛАН-ЧЛЕН-НЕ-СДЕЛАН"] and "измерение «Период» заявлено, в выгрузке нет" in text


def test_a_method_declared_but_not_written(tmp_path, capsys):
    plan = modify(GOOD, lambda ob: ob[1].update(методы=["Пересчитать", "НетТакого"]))
    code, text, data = reconcile(capsys, task_dir(tmp_path), plan)
    assert codes(data) == ["ПЛАН-МЕТОД-НЕ-СДЕЛАН"] and "метод НетТакого заявлен, в модуле нет" in text
    assert data["находки"][0]["файл"] == MODULE


def test_an_object_of_the_task_not_declared(tmp_path, capsys):
    code, text, data = reconcile(capsys, task_dir(tmp_path), modify(GOOD, lambda ob: ob.pop(2)))
    assert code == 1 and codes(data) == ["ПЛАН-ОБЪЕКТ-НЕ-ЗАЯВЛЕН"]
    assert "Перечисление.мой_Виды — новый объект, в плане не заявлен" in text


def test_only_declared_objects_are_checked_on_request(tmp_path, capsys):
    """Урезанный план круга: тронутое, но не заявленное — к сведению, не находкой;
    заявленное сверяется как обычно."""
    trimmed = modify(GOOD, lambda ob: ob.pop(2))
    code, text, data = reconcile(capsys, task_dir(tmp_path), trimmed, "--только-заявленные")
    assert code == 0 and data["находки"] == [], text
    assert "сверены только заявленные объекты; к сведению — тронуто, но не заявлено: Перечисление.мой_Виды" \
        in text
    plan = modify(trimmed, lambda ob: ob[0]["измерения"].update(Период=["Дата"]))
    _, _, data = reconcile(capsys, task_dir(tmp_path / "2"), plan, "--только-заявленные")
    assert codes(data) == ["ПЛАН-ЧЛЕН-НЕ-СДЕЛАН"]


def test_a_new_export_method_outside_the_plan_is_a_warning_with_its_line(tmp_path, capsys):
    root = task_dir(tmp_path)
    write_file(root, MODULE, ["Функция Пересчитать(Договор) Экспорт", "\tВозврат 1;", "КонецФункции", "",
                            "Функция Ещё(", "\tПараметр) Экспорт", "КонецФункции", "",
                            "Процедура Служебная()", "КонецПроцедуры"])
    code, text, data = reconcile(capsys, root, GOOD)
    assert code == 0 and codes(data) == ["ПЛАН-МЕТОД-НЕ-ЗАЯВЛЕН"], text
    assert data["находки"][0]["строка"] == 5 and "Служебная" not in text


# --- запись типов ------------------------------------------------------------------------


def test_the_type_is_written_either_way_and_compared_without_qualifiers(tmp_path, capsys):
    """«СправочникСсылка.Х» — как синтакс-помощник, «Справочник.Х» — как показ;
    длина, точность и состав даты не сверяются."""
    root = task_dir(tmp_path)
    write_file(root, REGISTER, card("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Период", ["xs:dateTime"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    plan = modify(GOOD, lambda ob: ob[0].update(
        измерения={"Договор": ["Справочник.ДоговорыКонтрагентов"], "Документ": ["Документ.Б", "ДокументСсылка.А"],
                   "Период": ["Дата"]},
        ресурсы={"Сумма": ["Число(15,2)"]}))
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text


def test_a_defined_type_is_a_type_too(tmp_path, capsys):
    """Тип-набор записан другим узлом (`TypeSet`): сверка по одним `Type` видела
    бы у такого измерения пустой состав, и заявленный тип расходился бы."""
    root = task_dir(tmp_path)
    write_file(root, REGISTER, card("InformationRegister", "мой_Рег", [
        ("Dimension", "Договор", ["cfg:CatalogRef.ДоговорыКонтрагентов"]),
        ("Dimension", "Документ", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Место", ["cfg:DefinedType.мой_Места"]),
        ("Resource", "Сумма", ["xs:decimal"])]))
    plan = modify(GOOD, lambda ob: ob[0]["измерения"].update(Место=["ОпределяемыйТип.мой_Места"]))
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text


# --- изменяемые объекты, попутное, удаление ---------------------------------------------------


def vendor_with_attribute(tmp_path):
    root = dump_dir(tmp_path)
    write_file(root, "Documents/Вендорский.xml", card("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"])]))
    commit(root)
    write_file(root, "Documents/Вендорский.xml", card("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"]), ("Attribute", "мой_Признак", ["xs:boolean"])]))
    return root


def test_a_changed_object_declares_only_what_the_task_added(tmp_path, capsys):
    root = vendor_with_attribute(tmp_path)
    plan = {"объекты": [{"вид": "Документ", "имя": "Вендорский", "действие": "изменить",
                         "реквизиты": {"мой_Признак": ["Булево"]}}]}
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text
    plan["объекты"][0].pop("реквизиты")
    code, text, data = reconcile(capsys, root, plan)
    assert codes(data) == ["ПЛАН-ЧЛЕН-НЕ-ЗАЯВЛЕН"] and "мой_Признак" in text and "«Сумма»" not in text


def test_a_change_declared_without_edits_is_a_warning(tmp_path, capsys):
    root = dump_dir(tmp_path)
    write_file(root, "Documents/Вендорский.xml", card("Document", "Вендорский", [
        ("Attribute", "Сумма", ["xs:decimal"])]))
    commit(root)
    plan = {"объекты": [{"вид": "Документ", "имя": "Вендорский", "действие": "изменить"}]}
    code, text, data = reconcile(capsys, root, plan)
    assert code == 0 and codes(data) == ["ПЛАН-ОБЪЕКТ-БЕЗ-ПРАВОК"], text


def test_an_unreadable_card_is_named_not_skipped(tmp_path, capsys):
    """Сломанная карточка — расхождение с причиной, а не молча пустой состав."""
    root = task_dir(tmp_path)
    write_file(root, REGISTER, ["<MetaDataObject/>"])
    code, text, data = reconcile(capsys, root, GOOD)
    assert codes(data) == ["ПЛАН-КАРТОЧКА-НЕ-ЧИТАЕТСЯ"] and "объявлением XML" in text, text


def test_a_role_touched_along_the_way_is_a_warning(tmp_path, capsys):
    root = task_dir(tmp_path)
    write_file(root, "Roles/мой_Чтение/Ext/Rights.xml", ["<Rights/>"])
    code, text, data = reconcile(capsys, root, GOOD)
    assert code == 0 and codes(data) == ["ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО"], text
    assert "Роль.мой_Чтение — новый объект" not in text and "Роль.мой_Чтение — изменён" in text


def test_deletion(tmp_path, capsys):
    root = dump_dir(tmp_path)
    os.remove(os.path.join(str(root), "Documents", "мой_Наш.xml"))
    shutil.rmtree(os.path.join(str(root), "Documents", "мой_Наш"))
    plan = {"объекты": [{"вид": "Документ", "имя": "мой_Наш", "действие": "удалить"}]}
    code, text, _ = reconcile(capsys, root, plan)
    assert code == 0, text
    plan["объекты"].append({"вид": "Документ", "имя": "Вендорский", "действие": "удалить"})
    code, text, data = reconcile(capsys, root, plan)
    assert codes(data) == ["ПЛАН-ОБЪЕКТ-ОСТАЛСЯ"], text


def test_a_revision_is_checked_as_well_as_the_working_copy(tmp_path, capsys):
    root = task_dir(tmp_path)
    commit(root, "задача")
    code, text, _ = reconcile(capsys, root, GOOD, "--база", "HEAD~1", "--ревизия", "HEAD")
    assert code == 0 and "ревизия HEAD против HEAD~1" in text, text


def test_the_profile_sets_the_level(tmp_path, capsys):
    root = task_dir(tmp_path)
    write_file(root, "Roles/мой_Чтение/Ext/Rights.xml", ["<Rights/>"])
    profile = tmp_path / "профиль.json"
    profile.write_text(json.dumps({"приставка": "мой_", "правила": {"ПЛАН-ПОПУТНОЕ-НЕ-ЗАЯВЛЕНО": "ошибка"}},
                                  ensure_ascii=False), encoding="utf-8")
    code, _, _ = reconcile(capsys, root, GOOD, "--профиль", profile)
    assert code == 1


# --- неверный план — отказ ------------------------------------------------------------------


@pytest.mark.parametrize("edit_job, words", [
    (lambda ob: ob[0].update(измерение={"Х": None}), "неизвестные ключи измерение"),
    (lambda ob: ob[0].update(действие="переделать"), "бывает: создать, изменить, удалить"),
    (lambda ob: ob[0].update(методы=["Записать"]), "«методы» — у вида с одним модулем"),
    (lambda ob: ob[0].update(модули={"МодульФормы": []}), "модуль «МодульФормы»"),
    (lambda ob: ob.append(dict(ob[1])), "в плане дважды"),
    (lambda ob: ob[2].update(значения={"Первый": ["Строка"]}), "у значения перечисления типов не бывает"),
    (lambda ob: ob.append({"вид": "Выдумка", "имя": "Х", "действие": "создать"}), "выгрузке неизвестен"),
])
def test_a_wrong_plan_is_refused_not_half_checked(tmp_path, capsys, edit_job, words):
    """Опечатка в ключе молча выключила бы сверку того, что за ним стоит."""
    code, text, data = reconcile(capsys, task_dir(tmp_path), modify(GOOD, edit_job))
    assert code == 2 and data is None and text.startswith("ОТКАЗ:") and words in text, text


# --- план по факту ----------------------------------------------------------------------


def test_the_plan_by_fact_passes_the_check_itself(tmp_path, capsys):
    root = task_dir(tmp_path)
    code, plan = from_fact(capsys, root)
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
    shutil.copyfile(os.path.join(GOLDEN, "Configuration.xml"), root / "Configuration.xml")
    git(root, "init", "-q")
    for key, value in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git(root, "config", key, value)
    commit(root)
    job_spec = tmp_path / "задание.json"
    job_spec.write_text(json.dumps({"repo": str(root), "objects": [
        {"вид": "Перечисление", "поля": {"имя": "мой_Виды", "синоним": "Виды",
                                         "значения": [{"имя": "Первый", "синоним": "Первый"}]}},
        {"вид": "РегистрСведений", "поля": {"имя": "мой_Остатки", "синоним": "Остатки", "измерения": [
            {"имя": "Вид", "синоним": "Вид", "тип": "Перечисление.мой_Виды"}],
            "ресурсы": [{"имя": "Сумма", "синоним": "Сумма", "тип": "Число(15,2)"}]}}]},
        ensure_ascii=False), encoding="utf-8")
    assert main([str(job_spec), "--apply"]) == 0
    code, plan = from_fact(capsys, root)
    register = next(ob for ob in plan["объекты"] if ob["имя"] == "мой_Остатки")
    assert register["ресурсы"] == {"Сумма": ["Число(15,2)"]} and register["измерения"] == {
        "Вид": ["Перечисление.мой_Виды"]}
    code, text, data = reconcile(capsys, root, plan)
    assert code == 0 and data["находки"] == [], text


# --- MCP ----------------------------------------------------------------------------------


def test_the_agent_checks_a_plan_and_gets_the_fact(tmp_path):
    from meta.composition import mcp_server

    root = task_dir(tmp_path)
    server = mcp_server(roots=[str(root)])

    def call_tool(tool, **arguments):
        answer = asyncio.run(server.call_tool(tool, arguments))
        if isinstance(answer, tuple):
            answer = answer[0]
        return "\n".join(block.text for block in answer)

    objects = json.loads(json.dumps(GOOD["объекты"]))
    objects[0]["измерения"]["Договор"] = None              # null — тип не сверяется
    assert "СОВПАДАЕТ" in call_tool("plan_check", repo=str(root), objects=objects)
    objects[0]["измерения"]["Лишнее"] = ["Булево"]
    assert "ПЛАН-ЧЛЕН-НЕ-СДЕЛАН" in call_tool("plan_check", repo=str(root), objects=objects)
    plan = json.loads(call_tool("plan_emit", repo=str(root)))
    assert {ob["имя"] for ob in plan["объекты"]} == {"мой_Рег", "мой_Сервер", "мой_Виды"}
    assert call_tool("plan_emit", repo=str(tmp_path)).startswith("ОТКАЗ: выгрузка")


# --- составы типов: правило проверки правок ----------------------------------------------
# Плана оно не требует — судит правки задачи, поэтому живёт в verify; карточки
# для него строятся здесь же.


def check_edits(capsys, root):
    answer = os.path.join(os.path.dirname(str(root)), "проверка.json")
    if os.path.exists(answer):
        os.remove(answer)
    capsys.readouterr()
    main(["--проверить", str(root), "--json", answer])
    text = capsys.readouterr().out
    return text, json.load(open(answer, encoding="utf-8"))


def test_a_narrower_type_set_of_a_similar_member_is_a_warning(tmp_path, capsys):
    """Измерение держит два вида документов, а соседнее — три: запись значения
    третьего вида в первое упадёт."""
    root = dump_dir(tmp_path)
    write_file(root, "InformationRegisters/мой_Итог.xml", card("InformationRegister", "мой_Итог", [
        ("Dimension", "ДокументВыдачи", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "ДокументЗачета", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"])]))
    text, data = check_edits(capsys, root)
    findings = [f for f in data["находки"] if f["код"] == "СОСТАВ-ТИПОВ-УЖЕ"]
    assert len(findings) == 1 and findings[0]["уровень"] == "предупреждение", text
    assert "«РегистрСведений.мой_Итог.ДокументВыдачи» — состав типов уже" in findings[0]["текст"]
    assert "нет Документ.В" in findings[0]["текст"]


def test_equal_or_far_type_sets_and_old_members_are_left_alone(tmp_path, capsys):
    """Одинаковые составы — согласованы; различие больше чем в два типа —
    разные по смыслу члены; член, бывший до задачи, — не её решение."""
    root = dump_dir(tmp_path)
    write_file(root, "InformationRegisters/мой_Итог.xml", card("InformationRegister", "мой_Итог", [
        ("Dimension", "Старый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"])]))
    commit(root)
    write_file(root, "InformationRegisters/мой_Итог.xml", card("InformationRegister", "мой_Итог", [
        ("Dimension", "Старый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б"]),
        ("Dimension", "Первый", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"]),
        ("Dimension", "Второй", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В"]),
        ("Dimension", "Широкий", ["cfg:DocumentRef.А", "cfg:DocumentRef.Б", "cfg:DocumentRef.В",
                                  "cfg:DocumentRef.Г", "cfg:DocumentRef.Д", "cfg:DocumentRef.Е"])]))
    text, data = check_edits(capsys, root)
    assert not [f for f in data["находки"] if f["код"] == "СОСТАВ-ТИПОВ-УЖЕ"], text
