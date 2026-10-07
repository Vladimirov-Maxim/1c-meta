"""Домен и перекладка на примере подписки на событие.

Инварианты: каждый должен и срабатывать на нарушении, и молчать на исправном
объекте — иначе проверка либо слепа, либо шумит. Диска здесь нет вовсе: мир
конфигурации подставляется заглушкой через порт, в этом и смысл расслоения.

Сверка с настоящими файлами — в `test_infra.py`, побайтно по всем 639 карточкам
замеренной конфигурации.
"""

import os
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping, schema  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Configuration, Finding, Refuse, Spec, TypeRef  # noqa: E402
from meta.tests.conftest import ТЕСТ  # noqa: E402


class FakeConfiguration(Configuration):
    """Мир, каким его видит тест. Домен не отличает её от чтения корпуса —
    в этом и смысл порта: инварианты проверяются без диска."""

    def __init__(self, modules=(), methods=(), objects=()):
        self.modules = set(modules)
        self.methods = set(methods)
        self.objects = set(objects)

    def common_module_exists(self, name):
        return name in self.modules

    def handler_arity(self, module, method):
        # Столько, сколько ждёт таблица: проверка сигнатуры здесь не предмет,
        # а мешать соседним проверкам она не должна.
        return None

    def method_is_exported(self, module, method):
        return (module, method) in self.methods

    def object_exists(self, kind, name):
        return (kind, name) in self.objects


WORLD = FakeConfiguration(
    modules=["мой_Обмен"],
    methods=[("мой_Обмен", "мой_СчетаПриЗаписиОбработчик")],
    objects=[("Справочник", "БанковскиеСчета"), ("Документ", "ПлатежноеПоручение"),
             ("Документ", "мой_Заявка")])


def flatten(node, path=""):
    """Дерево -> список пар «путь до узла, текст». Порядок сохраняется."""
    here = path + "/" + node.tag
    if not node.children:
        # Без нормализации: в замеренной конфигурации есть синонимы с хвостовым
        # пробелом, и запись обязана сохранять их как есть.
        return [(here, node.text or "")]
    out = []
    for child in node.children:
        out.extend(flatten(child, here))
    return out


# Сверка с настоящими карточками живёт в tests/test_infra.py: там она идёт
# побайтно по всем 639 файлам, то есть строго сильнее сверки деревьев. Здесь
# остаются инварианты — предмет этого слоя.


# --- тесты ------------------------------------------------------------------


def sample():
    return Spec("ПодпискаНаСобытие", {
        "имя": "мой_СчетаПриЗаписи",
        "синоним": "(Мой) Банковские счета при записи",
        "комментарий": "#TASK-2",
        "источник": [TypeRef("Справочник", "БанковскиеСчета", "Объект")],
        "событие": "ПриЗаписи",
        "обработчик": "мой_Обмен.мой_СчетаПриЗаписиОбработчик",
    })


def test_sample_has_no_findings():
    findings = kind_of("ПодпискаНаСобытие", ТЕСТ).check(sample(), WORLD)
    assert not findings, [str(f) for f in findings]


def expect_finding(changes, expected, world=WORLD):
    fields = dict(sample().fields)
    fields.update(changes)
    findings = kind_of("ПодпискаНаСобытие", ТЕСТ).check(Spec("ПодпискаНаСобытие", fields), world)
    codes = [f.code for f in findings]
    assert expected in codes, f"ждали {expected}, получили {codes}"


def test_missing_prefix():
    expect_finding({"имя": "БанковскиеСчетаПриЗаписи"}, "МД-ПРЕФИКС")


def test_invalid_name():
    expect_finding({"имя": "мой_Банковские Счета"}, "МД-ИМЯ-НЕДОПУСТИМО")


def test_empty_source():
    expect_finding({"источник": []}, "МД-ПОЛЕ-ПУСТО")


def test_event_facet_mismatch():
    # ОбработкаПроведения существует только у объекта; менеджеру она не бывает
    expect_finding({"событие": "ОбработкаПроведения",
               "источник": [TypeRef("Документ", "ПлатежноеПоручение", "Менеджер")]},
              "ПОДПИСКА-СОБЫТИЕ-ГРАНЬ")


def test_unknown_event():
    expect_finding({"событие": "ПриОченьХорошем"}, "ПОДПИСКА-СОБЫТИЕ-НЕИЗВЕСТНО")


def test_handler_not_a_module_method():
    expect_finding({"обработчик": "мой_СчетаПриЗаписи"},
              "ПОДПИСКА-ОБРАБОТЧИК-ФОРМА")


def test_handler_module_missing():
    expect_finding({}, "ПОДПИСКА-МОДУЛЬ-НЕТ", world=FakeConfiguration())


def test_handler_method_missing():
    expect_finding({}, "ПОДПИСКА-МЕТОД-НЕТ",
              world=FakeConfiguration(modules=["мой_Обмен"]))


def test_subscription_on_own_object():
    # Соглашение: обработчику собственного объекта место в модуле самого объекта
    expect_finding({"источник": [TypeRef("Документ", "мой_Заявка", "Объект")]},
              "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ")


def test_defined_type_unresolved():
    # 95 подписок из 639 в замеренной конфигурации задают источник определяемым
    # типом. Если мир его не раскрывает, инвариант обязан сказать об этом вслух,
    # а не промолчать.
    expect_finding({"источник": [TypeRef("ОпределяемыйТип", "мой_МестоХранения", None)]},
              "ПОДПИСКА-ТИП-НЕ-РАСКРЫТ")


def test_defined_type_resolved():
    class ResolvingConfig(FakeConfiguration):
        def defined_type_facets(self, name):
            return ("Менеджер",)
    world = ResolvingConfig(modules=["мой_Обмен"],
                       methods=[("мой_Обмен",
                                "мой_СчетаПриЗаписиОбработчик")])
    expect_finding({"источник": [TypeRef("ОпределяемыйТип", "мой_МестоХранения", None)]},
              "ПОДПИСКА-СОБЫТИЕ-ГРАНЬ", world=world)


def test_source_missing():
    expect_finding({"источник": [TypeRef("Справочник", "мой_НетТакого", "Объект")]},
              "ПОДПИСКА-ИСТОЧНИК-НЕТ")


def test_type_set_not_checked_for_existence():
    # «Все документы» не именует объект, проверять нечего
    findings = kind_of("ПодпискаНаСобытие", ТЕСТ).check(
        Spec("ПодпискаНаСобытие", dict(sample().fields,
             **{"источник": [TypeRef.of_kind("Документ")]})), WORLD)
    assert not [f for f in findings if f.code == "ПОДПИСКА-ИСТОЧНИК-НЕТ"], \
        [str(f) for f in findings]


def test_type_notation():
    cases = [
        (TypeRef("Справочник", "БанковскиеСчета", "Объект"), "cfg:CatalogObject.БанковскиеСчета"),
        (TypeRef("Константа", "Тест", "МенеджерЗначения"), "cfg:ConstantValueManager.Тест"),
        (TypeRef("РегистрСведений", "Курсы", "НаборЗаписей"), "cfg:InformationRegisterRecordSet.Курсы"),
        (TypeRef("ЖурналДокументов", "Банк", "Менеджер"), "cfg:DocumentJournalManager.Банк"),
        # Два безымянных случая: набор и один абстрактный тип. Обозначения похожи,
        # теги в файле разные — признак «набор» вывести не из чего, он задаётся явно.
        (TypeRef.of_kind("Документ"), "cfg:DocumentObject"),
        (TypeRef("Документ", None, "Менеджер"), "cfg:DocumentManager"),
        (TypeRef.defined("их_ОбъектыКонтроля"), "cfg:DefinedType.их_ОбъектыКонтроля"),
    ]
    for vtype, want in cases:
        out = mapping.type_notation(vtype)
        assert out == want, f"{vtype} -> {out}, ждали {want}"


def test_set_and_type_tags_differ():
    field = [f for f in schema.SCHEMA["ПодпискаНаСобытие"].fields
            if f.domain == "источник"][0]
    node = mapping._value(field, [TypeRef.of_kind("Документ"),
                                 TypeRef("Документ", None, "Менеджер"),
                                 TypeRef.defined("их_ОбъектыКонтроля")])
    assert [ch.tag for ch in node.children] == ["v8:TypeSet", "v8:Type", "v8:TypeSet"]


def test_synonym_in_two_languages():
    fields = dict(sample().fields)
    fields["синоним"] = OrderedDict([("ru", "Проверка"), ("en", "Check")])
    card = mapping.translate(Spec("ПодпискаНаСобытие", fields), uuid="х")
    synonym = [n for n in card.properties if n.tag == "Synonym"][0]
    assert flatten(synonym) == [
        ("/Synonym/v8:item/v8:lang", "ru"), ("/Synonym/v8:item/v8:content", "Проверка"),
        ("/Synonym/v8:item/v8:lang", "en"), ("/Synonym/v8:item/v8:content", "Check")]


def test_refuse_instead_of_guess():
    for patch in ({"событие": "ПриОченьХорошем"},
                   {"источник": [TypeRef("Нечто", "Х", "Объект")]},
                   {"источник": [TypeRef("Справочник", "Х", "Бок")]}):
        fields = dict(sample().fields)
        fields.update(patch)
        try:
            mapping.translate(Spec("ПодпискаНаСобытие", fields), uuid="х")
        except Refuse:
            continue
        raise AssertionError(f"перекладка не отказалась на {patch}")


def test_warning_is_not_error():
    findings = kind_of("ПодпискаНаСобытие", ТЕСТ).check(
        Spec("ПодпискаНаСобытие", dict(sample().fields,
             **{"источник": [TypeRef("Документ", "мой_Заявка", "Объект")]})), WORLD)
    own_one = [f for f in findings if f.code == "ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ"][0]
    assert not own_one.blocking and own_one.level == Finding.WARNING
