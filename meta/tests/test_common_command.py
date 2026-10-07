"""Общая команда: сверка со всеми 705 карточками конфигурации.

Тот же приём, что на подписках, реквизитах и регламентных заданиях: разобрать
написанное платформой обратно в спецификацию, собрать инструментом
и сравнить байты.

Русские имена двух перечислений взяты не из головы: `ОтображениеКнопки`
(ButtonRepresentation) и `РежимИспользованияПараметраКоманды`
(CommandParameterUseMode) — статьи синтакс-помощника; первая прямо называет
себя свойством общей команды. В самой выгрузке русских имён нет, и сверить
их по конфигурации невозможно — только по платформе.
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import mapping, vocabulary  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Spec  # noqa: E402
from meta.infra import serializer  # noqa: E402
from meta.tests import corpus  # noqa: E402

BACK = {tag: {v: k for k, v in table.items()} for tag, table in (
    ("Representation", vocabulary.BUTTON_REPRESENTATION),
    ("ParameterUseMode", vocabulary.PARAMETER_USE_MODE),
    ("OnMainServerUnavalableBehavior", vocabulary.MAIN_SERVER_UNAVAILABLE),
)}
DICTIONARY = {"отображение": "Representation",
              "режимИспользованияПараметра": "ParameterUseMode",
              "приНедоступностиГлавногоСервера": "OnMainServerUnavalableBehavior"}
PLAIN = {"группа": "Group", "сочетаниеКлавиш": "Shortcut"}
FLAGS = {"включатьСправкуВСодержание": "IncludeHelpInContents",
         "изменяетДанные": "ModifiesData"}


def unescape(text):
    return text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")


def multilang(text, tag):
    found = re.search(rf"<{tag}(/>|>.*?</{tag}>)", text, re.S)
    pairs = re.findall(r"<v8:lang>(\w+)</v8:lang>\s*<v8:content>([^<]*)</v8:content>",
                       found.group(0))
    return {lang: unescape(said) for lang, said in pairs} if pairs else ""


def spec_from_card(text):
    def value(tag):
        found = re.search(rf"<{tag}(?:\s[^>]*)?(?:/>|>(.*?)</{tag}>)", text, re.S)
        return None if not found else unescape(found.group(1) or "")

    fields = {"имя": value("Name"), "комментарий": value("Comment") or "",
              "синоним": multilang(text, "Synonym"),
              "подсказка": multilang(text, "ToolTip"),
              "картинка": "", "типПараметраКоманды": []}
    for domain, tag in PLAIN.items():
        fields[domain] = value(tag) or ""
    for domain, tag in FLAGS.items():
        fields[domain] = value(tag) == "true"
    for domain, tag in DICTIONARY.items():
        fields[domain] = BACK[tag][value(tag)]
    return Spec("ОбщаяКоманда", fields)


def test_all_common_commands_bytewise():
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    folder = os.path.join(corpus.CORPUS, "CommonCommands")
    checked = skipped = 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".xml"):
            continue
        text = open(os.path.join(folder, name),
                    encoding="utf-8-sig").read().replace("\r\n", "\n")
        # Картинка и тип параметра — вложенные структуры, домен их не выражает;
        # такие карточки не сверяются, но и не прячутся: их число печатается.
        if "<Picture>" in text or "<CommandParameterType>" in text:
            skipped += 1
            continue
        uuid = re.search(r'<CommonCommand uuid="([^"]+)"', text).group(1)
        card = mapping.translate(kind_of("ОбщаяКоманда").fill(spec_from_card(text)),
                                 uuid)
        assert serializer.card_to_text(card) == text, name
        checked += 1
    print(f"общих команд сверено {checked}, пропущено {skipped}")
    assert checked > 400


def test_group_is_not_an_enumeration():
    """Группа принимает и панель, и ссылку на группу команд — словаря тут нет."""
    kind = kind_of("ОбщаяКоманда")
    for group in ("NavigationPanelOrdinary", "CommandGroup.Отчеты"):
        card = mapping.translate(kind.fill(Spec("ОбщаяКоманда", {
            "имя": "мой_Проба", "синоним": "Проба", "группа": group,
            "отображение": "Авто", "режимИспользованияПараметра": "Одиночный"})), "x")
        assert f"<Group>{group}</Group>" in serializer.card_to_text(card)


def test_undefaulted_fields_are_required():
    """Значения, которые в корпусе расходятся, задание называет само."""
    kind = kind_of("ОбщаяКоманда")
    findings = kind.check(kind.fill(Spec("ОбщаяКоманда", {"имя": "мой_Проба"})), None)
    empty = sorted(f.field for f in findings if f.code == "МД-ПОЛЕ-ПУСТО")
    assert empty == ["группа", "отображение", "режимИспользованияПараметра",
                     "синоним"], empty


def test_universal_values_are_defaults():
    """А те, что по всему корпусу одни и те же, — не выбор, а факт."""
    kind = kind_of("ОбщаяКоманда")
    filled = kind.fill(Spec("ОбщаяКоманда", {"имя": "мой_Проба"}))
    assert filled.get("включатьСправкуВСодержание") is False
    assert filled.get("приНедоступностиГлавногоСервера") == "Авто"
