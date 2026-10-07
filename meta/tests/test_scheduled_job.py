"""Регламентное задание: сверка со всеми карточками конфигурации.

Тот же приём, что на подписках и реквизитах: разобрать написанное платформой
обратно в доменную спецификацию, собрать инструментом и сравнить байты.
Эталонов здесь 297 — все регламентные задания конфигурации.

Что этой сверкой **не** доказано: умолчания. Значения в корпусе — настроенные,
а не те, каким задание родится (`3` повтора с интервалом `10` стоят почти
у всех, и это соглашение БСП). Поэтому такие поля обязательны, а не
подставляются: сверка их берёт из файла, как и всё остальное.
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Spec  # noqa: E402
from meta.infra import serializer  # noqa: E402
from meta.tests import corpus  # noqa: E402

BOOLEAN = {"использование": "Use", "предопределённое": "Predefined"}
TEXT = {"наименование": "Description", "ключ": "Key",
        "количествоПовторов": "RestartCountOnFailure",
        "интервалПовтора": "RestartIntervalOnFailure"}


def unescape(text):
    return (text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&"))


def spec_from_card(text):
    """Карточка платформы -> доменная спецификация."""
    def value(tag):
        found = re.search(rf"<{tag}(?:\s[^>]*)?(?:/>|>(.*?)</{tag}>)", text, re.S)
        return None if not found else unescape(found.group(1) or "")

    fields = {"имя": value("Name"), "комментарий": value("Comment") or ""}
    synonym = re.findall(
        r"<v8:lang>(\w+)</v8:lang>\s*<v8:content>([^<]*)</v8:content>",
        re.search(r"<Synonym>(.*?)</Synonym>", text, re.S).group(1))
    fields["синоним"] = {lang: unescape(said) for lang, said in synonym} or ""
    handler = value("MethodName") or ""
    fields["обработчик"] = handler[len("CommonModule."):] if handler.startswith(
        "CommonModule.") else handler
    for domain, tag in TEXT.items():
        fields[domain] = value(tag) or ""
    for domain, tag in BOOLEAN.items():
        fields[domain] = value(tag) == "true"
    return Spec("РегламентноеЗадание", fields)


def test_all_scheduled_jobs_bytewise():
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    folder = os.path.join(corpus.CORPUS, "ScheduledJobs")
    checked = skipped = 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".xml"):
            continue
        text = open(os.path.join(folder, name),
                    encoding="utf-8-sig").read().replace("\r\n", "\n")
        handler = re.search(r"<MethodName>([^<]*)</MethodName>", text)
        if not handler or not handler.group(1).startswith("CommonModule."):
            skipped += 1          # обработчик не в общем модуле — домен так не умеет
            continue
        uuid = re.search(r'<ScheduledJob uuid="([^"]+)"', text).group(1)
        spec = kind_of("РегламентноеЗадание").fill(spec_from_card(text))
        card = mapping.translate(spec, uuid)
        assert serializer.card_to_text(card) == text, name
        checked += 1
    print(f"регламентных заданий сверено {checked}, пропущено {skipped}")
    assert checked > 250


def test_handler_must_name_a_module_and_a_method():
    kind = kind_of("РегламентноеЗадание")
    codes = [f.code for f in kind.own_findings(
        Spec("РегламентноеЗадание", {"обработчик": "простоИмя"}), None)]
    assert codes == ["ЗАДАНИЕ-ОБРАБОТЧИК"]


def test_repeat_counters_must_be_numbers():
    kind = kind_of("РегламентноеЗадание")
    codes = [f.code for f in kind.own_findings(Spec("РегламентноеЗадание", {
        "обработчик": "мой_Модуль.Метод", "количествоПовторов": "трижды",
        "интервалПовтора": "10"}), None)]
    assert codes == ["ЗАДАНИЕ-ЧИСЛО"]


def test_undefaulted_fields_are_required_not_guessed():
    """Умолчания не замерены — значит задание обязано их назвать.

    Мода по корпусу (`3` и `10`) — соглашение БСП, а не то, что пишет
    конфигуратор новому заданию. Подставить её значило бы выдать догадку
    за умолчание.
    """
    kind = kind_of("РегламентноеЗадание")
    findings = kind.check(kind.fill(Spec("РегламентноеЗадание", {
        "имя": "мой_Проба", "синоним": "Проба",
        "обработчик": "мой_Модуль.Метод"})), None)
    empty = sorted(f.field for f in findings if f.code == "МД-ПОЛЕ-ПУСТО")
    assert empty == ["интервалПовтора", "использование", "количествоПовторов",
                     "предопределённое"], empty
