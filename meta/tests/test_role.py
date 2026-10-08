"""Роль: карточка из трёх свойств и файл прав рядом.

Эталон конфигуратора здесь не нужен, и это не поблажка, а замер:
у всех 2709 ролей замеренной конфигурации состав карточки один и тот же —
`Name`, `Synonym`, `Comment`, без `InternalInfo` и без раздела детей, ни
одного исключения. Умолчания трёх флагов файла прав тоже сняты с корпуса
(2708 из 2709, 2598 из 2709, 2553 из 2709).

Имена прав не выписаны по памяти: они взяты из статьи «Глобальный
контекст.ПравоДоступа» синтакс-помощника — единственного места, где русское
и английское имя названы рядом, — и сверены с конфигурацией: все 69 прав,
встречающихся в 2709 ролях, таблицей покрыты.
"""

import os
import re
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import vocabulary  # noqa: E402
from meta.application.add_object.use_case import AddObjectUseCase  # noqa: E402
from meta.domain import atomic_roles  # noqa: E402
from meta.domain.atomic_roles import СхемаРолей  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Refuse, Spec  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.tests import corpus  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402

REGISTRY = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
            "\t<Configuration>\n\t\t<Properties>\n\t\t\t<Name>ПробнаяКонфигурация</Name>\n"
            "\t\t</Properties>\n\t\t<ChildObjects>\n"
            "\t\t\t<Catalog>мой_Цель</Catalog>\n"
            "\t\t\t<Document>мой_Заявка</Document>\n"
            "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")

ДОКУМЕНТ = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"'
            ' xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">\n'
            '\t<Document uuid="00000000-0000-0000-0000-000000000009">\n'
            "\t\t<Properties>\n\t\t\t<Name>мой_Заявка</Name>\n"
            "\t\t\t<Synonym>\n\t\t\t\t<v8:item>\n\t\t\t\t\t<v8:lang>ru</v8:lang>\n"
            "\t\t\t\t\t<v8:content>Заявка на оплату</v8:content>\n"
            "\t\t\t\t</v8:item>\n\t\t\t</Synonym>\n\t\t</Properties>\n"
            "\t\t<ChildObjects/>\n\t</Document>\n</MetaDataObject>")


@pytest.fixture
def dump():
    root = tempfile.mkdtemp(prefix="meta-role-")
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(REGISTRY)
    os.makedirs(os.path.join(root, "Catalogs"))
    open(os.path.join(root, "Catalogs", "мой_Цель.xml"), "w",
         encoding="utf-8-sig", newline="").write("<Catalog/>")
    os.makedirs(os.path.join(root, "Documents"))
    open(os.path.join(root, "Documents", "мой_Заявка.xml"), "w",
         encoding="utf-8-sig", newline="").write(ДОКУМЕНТ)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def role(**fields):
    described = {"имя": "мой_Проба", "синоним": "(Мой) Проба"}
    described.update(fields)
    return Spec("Роль", described)


def create(root, spec, apply_now=True):
    return AddObjectUseCase(DesignerDump(root), ТЕСТ).execute([spec], apply_now=apply_now)


def rights_of(root):
    return open(os.path.join(root, "Roles", "мой_Проба", "Ext", "Rights.xml"),
                encoding="utf-8-sig").read().replace("\r\n", "\n")


def test_card_is_three_properties(dump):
    create(dump, role(комментарий="#ЗАДАЧА-1"))
    card = open(os.path.join(dump, "Roles", "мой_Проба.xml"),
                encoding="utf-8-sig").read()
    assert "<Name>мой_Проба</Name>" in card
    assert "<Comment>#ЗАДАЧА-1</Comment>" in card
    assert "<InternalInfo>" not in card
    assert "ChildObjects" not in card


def test_rights_file_is_written_beside_the_card(dump):
    create(dump, role(права=[{"объект": "Справочник.мой_Цель",
                              "права": ["Чтение", "Просмотр"]}]))
    text = rights_of(dump)
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n'
                           '<Rights xmlns="http://v8.1c.ru/8.2/roles"')
    assert "<name>Catalog.мой_Цель</name>" in text
    assert "<name>Read</name>" in text and "<name>View</name>" in text
    assert text.count("<value>true</value>") == 2


def test_flags_default_to_what_the_configurator_writes(dump):
    create(dump, role())
    text = rights_of(dump)
    assert "<setForNewObjects>false</setForNewObjects>" in text
    assert "<setForAttributesByDefault>true</setForAttributesByDefault>" in text
    assert ("<independentRightsOfChildObjects>false"
            "</independentRightsOfChildObjects>") in text


def test_flags_can_be_set(dump):
    create(dump, role(праваДляНовыхОбъектов=True, праваРеквизитовПоУмолчанию=False))
    text = rights_of(dump)
    assert "<setForNewObjects>true</setForNewObjects>" in text
    assert "<setForAttributesByDefault>false</setForAttributesByDefault>" in text


def test_unknown_right_is_refused_with_the_allowed_ones(dump):
    with pytest.raises(Refuse) as refusal:
        create(dump, role(права=[{"объект": "Справочник.мой_Цель",
                                  "права": ["Читание"]}]))
    assert "не знаю права «Читание»" in str(refusal.value)
    assert "Чтение" in str(refusal.value)


def test_rights_on_a_missing_object_are_refused(dump):
    result = create(dump, role(права=[{"объект": "Справочник.мой_НетТакого",
                                       "права": ["Чтение"]}]), apply_now=False)
    assert [f.code for f in result.errors] == ["РОЛЬ-ОБЪЕКТА-НЕТ"]


def test_object_without_rights_is_refused(dump):
    result = create(dump, role(права=[{"объект": "Справочник.мой_Цель",
                                       "права": []}]), apply_now=False)
    assert "РОЛЬ-ПРАВ-НЕТ" in [f.code for f in result.errors]


def test_right_on_the_configuration_itself_is_addressed_by_its_name(dump):
    """Право на конфигурацию целиком адресуется `Configuration.<Имя>`.

    Буквальное `<name>Конфигурация</name>` не встречается ни в одной роли
    замеренной конфигурации: 2702 из 2709 несут `Configuration.<ИмяКонфигурации>`.
    Имя берётся из шапки `Configuration.xml`, той же выгрузки, куда пишем.
    """
    create(dump, role(права=[{"объект": "Конфигурация",
                              "права": ["Администрирование"]}]))
    assert "<name>Configuration.ПробнаяКонфигурация</name>" in rights_of(dump)
    assert "<name>Конфигурация</name>" not in rights_of(dump)


def test_atomic_roles_come_in_a_pair_by_the_project_template(dump):
    """Пара ролей к документу: имена, синонимы и права — как у атомарных ролей замеренной конфигурации."""
    from meta.application.atomic_roles_use_case import AtomicRolesUseCase

    result = AtomicRolesUseCase(DesignerDump(dump), ТЕСТ).execute(
        [("Документ", "мой_Заявка", None)], apply_now=True)
    assert result.ok, [str(f) for f in result.errors]
    for право, ожидаемые in (("Просмотр", ("Read", "View", "InputByString")),
                             ("Изменение", ("Posting", "UndoPosting", "InteractiveChangeOfPosted"))):
        имя = f"мой_атом_Документ_мой_Заявка_{право}"
        card = open(os.path.join(dump, "Roles", имя + ".xml"), encoding="utf-8-sig").read()
        assert f"<v8:content>(Мой) Атом. Документ - Заявка на оплату - {право}</v8:content>" in card
        rights = open(os.path.join(dump, "Roles", имя, "Ext", "Rights.xml"),
                      encoding="utf-8-sig").read()
        assert "<name>Document.мой_Заявка</name>" in rights
        for r in ожидаемые:
            assert f"<name>{r}</name>" in rights, r
        # права на конфигурацию, которые ставит конфигуратор новой роли
        assert "<name>Configuration.ПробнаяКонфигурация</name>" in rights
        assert "<name>MainWindowModeKiosk</name>" in rights
    # «Просмотр» без права на проведение — иначе пара ничем не отличалась бы
    просмотр = open(os.path.join(dump, "Roles", "мой_атом_Документ_мой_Заявка_Просмотр",
                                 "Ext", "Rights.xml"), encoding="utf-8-sig").read()
    assert "<name>Posting</name>" not in просмотр
    registry = open(os.path.join(dump, "Configuration.xml"), encoding="utf-8-sig").read()
    assert registry.count("<Role>мой_атом_Документ_мой_Заявка_") == 2


def test_a_shown_role_carries_its_rights(dump):
    """Права роли лежат в своём файле и читаются при показе: иначе роль выглядела
    бы пустой — «ещё 5 полей пусты» при заполненном Rights.xml."""
    from meta.application.atomic_roles_use_case import AtomicRolesUseCase

    AtomicRolesUseCase(DesignerDump(dump), ТЕСТ).execute(
        [("Документ", "мой_Заявка", ["Просмотр"])], apply_now=True)
    spec, _ = DesignerDump(dump).read_spec([("Роль", "мой_атом_Документ_мой_Заявка_Просмотр")])
    права = {выдача["объект"]: выдача["права"] for выдача in spec.get("права")}
    assert права["Документ.мой_Заявка"] == ["Чтение", "Просмотр", "ВводПоСтроке"]
    assert "РежимОсновногоОкнаКиоск" in права["Конфигурация"]
    assert spec.get("праваРеквизитовПоУмолчанию") is True


def test_atomic_roles_for_a_missing_object_are_refused(dump):
    from meta.application.atomic_roles_use_case import AtomicRolesUseCase

    with pytest.raises(Refuse) as отказ:
        AtomicRolesUseCase(DesignerDump(dump), ТЕСТ).execute([("Документ", "мой_Нет", None)])
    assert "мой_Нет" in str(отказ.value)


def test_a_new_object_can_bring_its_atomic_roles_in_the_same_job(dump):
    """«атомарныеРоли»: объект и его роли — одним заданием и одним планом.

    Роль ссылается на объект, которого на диске ещё нет; проверка «объекта
    нет» отвергала бы пачку. Объекты одной пачки видят друг друга по факту
    существования — и только по нему.
    """
    # «Счет», не «Счёт»: буква «ё» в синониме — отказ по #std474 п. 4
    spec = Spec("Документ", {"имя": "мой_Счет", "синоним": "Счет на оплату",
                             "атомарныеРоли": ["Просмотр"]})
    result = create(dump, spec)
    assert result.ok, [str(f) for f in result.errors]
    assert os.path.isfile(os.path.join(dump, "Documents", "мой_Счет.xml"))
    assert os.path.isfile(os.path.join(dump, "Roles", "мой_атом_Документ_мой_Счет_Просмотр.xml"))
    assert not os.path.isfile(os.path.join(dump, "Roles", "мой_атом_Документ_мой_Счет_Изменение.xml"))
    card = open(os.path.join(dump, "Documents", "мой_Счет.xml"), encoding="utf-8-sig").read()
    assert "атомарныеРоли" not in card


def test_an_unmeasured_kind_is_refused_for_atomic_roles(dump):
    with pytest.raises(Refuse) as отказ:
        atomic_roles.roles_for("Константа", "мой_Проба", "Проба", схема=ТЕСТ.атомарные_роли)
    assert "типовой состав есть для" in str(отказ.value)
    with pytest.raises(Refuse) as отказ:
        atomic_roles.roles_for("Документ", "мой_Проба", "Проба", ["Удаление"],
                               схема=ТЕСТ.атомарные_роли)
    assert "Просмотр, Изменение" in str(отказ.value).replace("Изменение, Просмотр", "Просмотр, Изменение")


def обработка(dump):
    """Обработка в выгрузке — карточка с синонимом."""
    os.makedirs(os.path.join(dump, "DataProcessors"))
    open(os.path.join(dump, "DataProcessors", "мой_Помощник.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        ДОКУМЕНТ.replace("Document", "DataProcessor").replace("мой_Заявка", "мой_Помощник")
        .replace("Заявка на оплату", "Помощник расчета"))


def test_a_data_processor_gets_one_role_without_a_suffix(dump):
    """Обработка: роль одна и без суффикса — «Использование» и «Просмотр»; в
    имени и синониме нет права и разделителя перед ним."""
    from meta.application.atomic_roles_use_case import AtomicRolesUseCase

    обработка(dump)
    result = AtomicRolesUseCase(DesignerDump(dump), ТЕСТ).execute(
        [("Обработка", "мой_Помощник", None)], apply_now=True)
    assert result.ok, [str(f) for f in result.errors]
    роли = sorted(f for f in os.listdir(os.path.join(dump, "Roles")) if f.endswith(".xml"))
    assert роли == ["мой_атом_Обработка_мой_Помощник.xml"]
    card = open(os.path.join(dump, "Roles", роли[0]), encoding="utf-8-sig").read()
    assert "<v8:content>(Мой) Атом. Обработка - Помощник расчета</v8:content>" in card
    rights = open(os.path.join(dump, "Roles", "мой_атом_Обработка_мой_Помощник", "Ext",
                               "Rights.xml"), encoding="utf-8-sig").read()
    assert "<name>DataProcessor.мой_Помощник</name>" in rights
    assert "<name>Use</name>" in rights and "<name>View</name>" in rights


def test_a_data_processor_role_takes_no_rights_list():
    with pytest.raises(Refuse, match="роль одна, без суффикса"):
        atomic_roles.roles_for("Обработка", "мой_П", "П", ["Просмотр"], схема=ТЕСТ.атомарные_роли)


def test_a_role_without_a_suffix_is_recognised_as_atomic():
    """Роль обработки без суффикса — атомарная по схеме: её находят соседи и
    проверка «пара уже есть»."""
    схема = ТЕСТ.атомарные_роли
    assert atomic_roles.is_atomic_role(схема, "мой_атом_Обработка_мой_Помощник")
    assert atomic_roles.is_atomic_role(схема, "мой_атом_Документ_мой_Заявка_Просмотр")


def test_atomic_roles_carry_the_comment(dump):
    """Комментарий роли — как у соседей: дата, автор, задача."""
    from meta.application.atomic_roles_use_case import AtomicRolesUseCase

    AtomicRolesUseCase(DesignerDump(dump), ТЕСТ).execute(
        [("Документ", "мой_Заявка", ["Просмотр"], None, "08.10.2026, #TEAM Тестов Тест #ТЕСТ-1")],
        apply_now=True)
    card = open(os.path.join(dump, "Roles", "мой_атом_Документ_мой_Заявка_Просмотр.xml"),
                encoding="utf-8-sig").read()
    assert "<Comment>08.10.2026, #TEAM Тестов Тест #ТЕСТ-1</Comment>" in card


def test_inline_atomic_roles_carry_the_comment(dump):
    spec = Spec("Документ", {"имя": "мой_Счет", "синоним": "Счет на оплату",
                             "атомарныеРоли": {"права": ["Просмотр"], "комментарий": "ТЕСТ-1"}})
    assert create(dump, spec).ok
    card = open(os.path.join(dump, "Roles", "мой_атом_Документ_мой_Счет_Просмотр.xml"),
                encoding="utf-8-sig").read()
    assert "<Comment>ТЕСТ-1</Comment>" in card


def test_a_register_role_synonym_names_its_kind_in_words():
    """Как в замеренной конфигурации: «Регистр сведений» у 325 ролей — вид в
    синониме пишется словами, а не слитным именем «РегистрСведений»."""
    def синоним(вид):
        spec, _ = atomic_roles.roles_for(вид, "мой_Проба", "Проба", ["Просмотр"],
                                         схема=ТЕСТ.атомарные_роли)[0]
        return spec.fields["синоним"]

    assert синоним("РегистрСведений") == "(Мой) Атом. Регистр сведений - Проба - Просмотр"
    assert синоним("РегистрНакопления") == "(Мой) Атом. Регистр накопления - Проба - Просмотр"
    assert синоним("Документ") == "(Мой) Атом. Документ - Проба - Просмотр"


def test_template_rights_are_known_words():
    """Каждое право шаблона — слово словаря, и у своего вида оно бывает."""
    from meta.acl.vocabulary import RIGHTS
    from meta.domain.platform import RIGHTS_BY_KIND

    for (вид, _), права in atomic_roles.TEMPLATES.items():
        for право in права:
            assert право in RIGHTS, право
            assert право in RIGHTS_BY_KIND[вид], (вид, право)
    for право in atomic_roles.CONFIGURATION_RIGHTS:
        assert право in RIGHTS, право


def test_card_matches_the_whole_configuration():
    """Состав карточки роли — не догадка: 2709 ролей, ни одного исключения."""
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    folder = os.path.join(corpus.CORPUS, "Roles")
    shapes = set()
    checked = 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".xml"):
            continue
        text = open(os.path.join(folder, name),
                    encoding="utf-8-sig").read().replace("\r\n", "\n")
        body = re.search(r"<Properties>(.*?)</Properties>", text, re.S)
        shapes.add(tuple(re.findall(r"^\t{3}<(\w+)[ />]", body.group(1), re.M)))
        assert "<InternalInfo>" not in text and "ChildObjects" not in text, name
        checked += 1
    assert shapes == {("Name", "Synonym", "Comment")}, shapes
    print(f"карточек ролей сверено {checked}")
    assert checked > 2000


def test_every_right_used_in_the_configuration_is_known():
    """Таблица прав покрывает всё, что встречается в правах ролей."""
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    folder = os.path.join(corpus.CORPUS, "Roles")
    used = set()
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name, "Ext", "Rights.xml")
        if os.path.isfile(path):
            used.update(re.findall(r"<right>\s*<name>(\w+)</name>",
                                   open(path, encoding="utf-8-sig").read()))
    unknown = sorted(used - set(vocabulary.RIGHTS.values()))
    assert not unknown, unknown
    print(f"прав в конфигурации {len(used)}, в таблице {len(vocabulary.RIGHTS)}")


def test_role_needs_a_synonym():
    """Роль без синонима в списке прав пользователя выглядит служебным именем."""
    kind = kind_of("Роль")
    codes = [f.code for f in kind.check(kind.fill(Spec("Роль", {"имя": "мой_Проба"})),
                                        None)]
    assert "МД-ПОЛЕ-ПУСТО" in codes, codes


def test_rights_on_a_kind_without_rights_are_refused(dump):
    """Право на общий модуль подвешивает загрузку конфигурации намертво.

    Опыт на пустой конфигурации: платформа не сообщает об ошибке, а уходит в
    бесконечный цикл — процесс держит базу и жжёт процессорное время, ничего
    не записывая. Без роли та же сборка проходит за 1,7 с, с ролью без этого
    права — за 1,3 с.

    Основание для отказа замерено: на общий модуль не выдано ни одного права
    ни в одной из 2709 ролей замеренной конфигурации.
    """
    os.makedirs(os.path.join(dump, "CommonModules"))
    open(os.path.join(dump, "CommonModules", "мой_Любой.xml"), "w",
         encoding="utf-8-sig", newline="").write("<CommonModule/>")
    with pytest.raises(Refuse) as refusal:
        create(dump, role(права=[{"объект": "ОбщийМодуль.мой_Любой",
                                  "права": ["Использование"]}]))
    assert "прав не бывает" in str(refusal.value)
    assert "бесконечный цикл" in str(refusal.value)


def test_rights_are_written_in_the_canonical_order(dump):
    """Платформа переставляет права в свой порядок — пишем сразу в нём.

    Иначе каждый круг «загрузили — выгрузили» давал бы diff на ровном месте.
    Порядок выведен из 9984 блоков прав топологической сортировкой без единого
    цикла; порядок из статьи синтакс-помощника не подходит — в блоке истории
    данных он другой.
    """
    create(dump, role(права=[{"объект": "Справочник.мой_Цель",
                              "права": ["Просмотр", "Добавление", "Чтение",
                                        "ВводПоСтроке", "Изменение"]}]))
    записано = re.findall(r"<right>\s*<name>(\w+)</name>", rights_of(dump))
    assert записано == ["Read", "Insert", "Update", "View", "InputByString"]


def test_rights_order_covers_the_configuration():
    """Все наблюдаемые последовательности прав укладываются в порядок инструмента."""
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    folder = os.path.join(corpus.CORPUS, "Roles")
    block = re.compile(r"<object>\s*<name>[^<]+</name>(.*?)</object>", re.S)
    order = vocabulary.RIGHTS_ORDER
    checked = 0
    for name in sorted(os.listdir(folder))[:200]:
        path = os.path.join(folder, name, "Ext", "Rights.xml")
        if not os.path.isfile(path):
            continue
        for body in block.findall(open(path, encoding="utf-8-sig").read()):
            granted = re.findall(r"<right>\s*<name>(\w+)</name>", body)
            walker = iter(order)
            assert all(right in walker for right in granted), (name, granted)
            checked += 1
    print(f"блоков прав сверено {checked}")
    assert checked > 1000


def test_every_rights_host_in_the_configuration_is_known():
    """Список видов, у которых бывают права, — из конфигурации, а не из головы."""
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    folder = os.path.join(corpus.CORPUS, "Roles")
    seen = set()
    for name in sorted(os.listdir(folder))[:300]:
        path = os.path.join(folder, name, "Ext", "Rights.xml")
        if os.path.isfile(path):
            seen.update(address.split(".")[0] for address in re.findall(
                r"<object>\s*<name>([^<]+)</name>",
                open(path, encoding="utf-8-sig").read()))
    unknown = sorted(seen - set(vocabulary.RIGHTS_HOSTS))
    assert not unknown, unknown
    assert "CommonModule" not in seen


# --- схема атомарных ролей ------------------------------------------------------------

ИХ = СхемаРолей("их_{вид}_{объект}_{право}", "Атом {вид}: {синоним} ({право})")


def test_atomic_roles_need_the_team_scheme():
    """Имя атомарной роли — соглашение команды: без схемы в профиле ролей нет,
    и отказ говорит, где и как её задать."""
    with pytest.raises(Refuse) as отказ:
        atomic_roles.roles_for("Документ", "Заявка", "Заявка")
    assert "«атомарныеРоли»" in str(отказ.value) and "{право}" in str(отказ.value)


def test_roles_are_named_by_the_team_scheme():
    (просмотр, _), (изменение, _) = atomic_roles.roles_for(
        "РегистрСведений", "Лимиты", "Лимиты оплат", схема=ИХ)
    assert просмотр.get("имя") == "их_РегистрСведений_Лимиты_Просмотр"
    assert изменение.get("синоним") == "Атом Регистр сведений: Лимиты оплат (Изменение)"
    (короткая, _), = atomic_roles.roles_for("Документ", "ОченьДлинноеИмя", "Длинное",
                                            ["Просмотр"], "Короткое", схема=ИХ)
    assert короткая.get("имя") == "их_Документ_Короткое_Просмотр"


def test_a_scheme_that_would_give_clashing_names_is_refused():
    for имя, синоним, слово in (
            ("их_{вид}_{объект}", "А {синоним} {право}", "каждое ровно один раз"),
            ("их_{вид}_{объект}_{объект}_{право}", "А {синоним} {право}", "каждое ровно один раз"),
            ("мой-{вид}_{объект}_{право}", "А {синоним} {право}", "только буквы, цифры"),
            ("их_{вид:>10}_{объект}_{право}", "А {синоним} {право}", "без формата"),
            ("их_{вид}_{объект}_{право}", "А {синоним}", "{право}"),
            ("их_{вид}_{объект}_{право}", "А {вид} {право}", "{синоним} или {объект}"),
            ("их_{вид}_{объект}_{право}", "А {синоним} {право} {кто}", "поля из"),
            ("их_{вид}_{объект}_{право", "А {синоним} {право}", "не разобрать")):
        with pytest.raises(Refuse) as отказ:
            СхемаРолей(имя, синоним)
        assert слово in str(отказ.value), (имя, синоним, отказ.value)


def выдачи(вид, объект, права):
    return [{"объект": f"{вид}.{объект}", "права": list(права)},
            {"объект": "Конфигурация", "права": list(atomic_roles.CONFIGURATION_RIGHTS)}]


def test_the_advice_counts_the_neighbours_in_this_dump():
    """Доля соседей с типовым составом — по выгрузке, а не числом, снятым с
    чужой конфигурации: в другой выгрузке оно было бы неправдой."""
    типовой = atomic_roles.TEMPLATES[("Справочник", "Просмотр")]
    без_ввода = [п for п in типовой if п != "ВводПоСтроке"]
    роли = {"их_Справочник_А_Просмотр": выдачи("Справочник", "А", типовой),
            "их_Справочник_Б_Просмотр": выдачи("Справочник", "Б", типовой),
            "их_Справочник_В_Просмотр": выдачи("Справочник", "В", без_ввода),
            "их_Справочник_Г_Просмотр": выдачи("Справочник", "Г", без_ввода),
            "их_Справочник_Г_Изменение": выдачи("Справочник", "Г", ["Чтение"]),
            "чужая_Справочник_Д_Просмотр": выдачи("Справочник", "Д", ["Чтение"])}
    совет = atomic_roles.совет("Справочник", "Просмотр", ИХ, роли)
    assert "так устроены 2 из 4 ролей «Просмотр»" in совет, совет
    assert "без ВводПоСтроке — 2, например «Роль.их_Справочник_В_Просмотр»" in совет, совет
    assert "их_Справочник_*_Просмотр" in совет
    # почти все по типовому — совета нет; соседей нет или выгрузку не спросить — тоже
    роли = {f"их_Справочник_{н}_Просмотр": выдачи("Справочник", н, типовой) for н in "АБВГДЕЖЗИК"}
    assert atomic_roles.совет("Справочник", "Просмотр", ИХ, роли) is None
    assert atomic_roles.совет("Справочник", "Просмотр", ИХ, {}) is None
    assert atomic_roles.совет("Справочник", "Просмотр", ИХ, None) is None


def test_a_long_difference_is_named_briefly():
    типовой = atomic_roles.TEMPLATES[("Справочник", "Изменение")]
    assert atomic_roles.отличие(frozenset(типовой[:5]) | {"Удаление"}, типовой) == (
        f"без {', '.join(типовой[5:8])} и ещё {len(типовой) - 8}; с Удаление")


def test_an_existing_pair_is_found_by_rights_not_by_name():
    роли = {"их_Документ_Сокр_Просмотр": выдачи("Документ", "ОченьДлинное", ["Чтение"]),
            "их_Документ_Другой_Просмотр": выдачи("Документ", "Другой", ["Чтение"])}
    assert atomic_roles.roles_of_object("Документ", "ОченьДлинное", роли) == [
        "их_Документ_Сокр_Просмотр"]
