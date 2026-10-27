"""Профиль соглашений команды: JSON -> `Соглашения` домена.

Один файл на команду — всё, что у неё своё, а не общее для всех:

    {
      "приставка": "мой_",
      "метки": {"тег": "#TEAM"},
      "атомарныеРоли": {"имя": "мой_атом_{вид}_{объект}_{право}",
                        "синоним": "(Мой) Атом. {вид} - {синоним} - {право}"},
      "кодФормы": {"язык": "платформа"},
      "правила": {"ПОДПИСКА-НА-СВОЙ-ОБЪЕКТ": "ошибка", "МД-БЕЗ-СИНОНИМА": "выкл"}
    }

`приставка` — с чего начинаются имена всего, что команда добавляет сама; без
неё правила о приставке не применяются. Списком — основная первой, остальные
тоже свои: прежние приставки команды, имена тестовых модулей. `метки.тег` — метка команды, которую
открывающая метка вставки ставит перед автором: «// {[+](фрагмент ДОБАВЛЕН),
дата, #TEAM Автор #Задача»; без неё — «…, дата, Автор #Задача». `метки.ставить` —
false: команда меток вставок не ставит — правка кода пишется на место старого
кода, а проверка правок не требует меток. `атомарныеРоли` —
шаблоны имени и синонима атомарных ролей; без них инструмент таких ролей не
заводит. `кодФормы` — на каком языке пишется код доработки типовой формы:
«платформа» (встроен, по умолчанию) или язык команды — тогда «диалект» называет
файл, который его описывает (путь от файла профиля), а прочие ключи раздела —
настройки этого языка, их проверяет сам диалект. `правила` — код
находки → уровень: «ошибка», «предупреждение» или «выкл». Правило при этом не
меняется, меняется только то, насколько строго команда его держит.

Неизвестный ключ — отказ: опечатка в профиле молча выключила бы соглашение.
"""

import re

from ..domain.atomic_roles import RoleSchema
from ..domain.conventions import LEVELS, PLATFORM, Conventions, FormCode
from ..domain.form_dialect import PLATFORM as PLATFORM_DIALECT
from ..domain.model import Refuse

КЛЮЧИ = ("приставка", "метки", "атомарныеРоли", "кодФормы", "правила")
КЛЮЧИ_МЕТОК = ("тег", "ставить")
КЛЮЧИ_СХЕМЫ = ("имя", "синоним")
#: Ключи «кодФормы», которые читает сам профиль; прочие — настройки языка.
КЛЮЧИ_КОДА = ("язык", "диалект")

#: Код находки — заглавные слова через дефис, как их печатает инструмент.
КОД = re.compile(r"^[A-ZА-ЯЁ0-9]+(?:-[A-ZА-ЯЁ0-9]+)*$")
#: Метка команды — «#» и слово: пробел разорвал бы её, а второй «#» в метке
#: читается как ИД задачи.
ТЕГ = re.compile(r"^#[^\s#]+$")


def conventions(data, откуда="профиль", диалект_из=None):
    """Разобранный профиль. Ошибка в нём — отказ с объяснением, а не догадка.

    `диалект_из` — как получить диалект по имени файла из «кодФормы.диалект»:
    файл читает тот, кто знает, где лежит профиль. Без него профиль с
    диалектом — отказ.
    """
    if not isinstance(data, dict):
        raise Refuse(f"{откуда}: ожидается объект JSON с ключами {', '.join(КЛЮЧИ)}")
    extra = sorted(set(data) - set(КЛЮЧИ))
    if extra:
        raise Refuse(f"{откуда}: неизвестные ключи {', '.join(extra)}; известны: {', '.join(КЛЮЧИ)}")
    prefix, others = _приставки(data.get("приставка"), откуда)
    rules = data.get("правила") or {}
    if not isinstance(rules, dict):
        raise Refuse(f"{откуда}: «правила» — объект «код находки: уровень»")
    for code, level in rules.items():
        if not _код_допустим(code):
            raise Refuse(f"{откуда}: «{code}» — не код находки: заглавные слова через дефис, "
                         "как в ответе инструмента, например «МД-ПРЕФИКС»")
        if level not in LEVELS:
            raise Refuse(f"{откуда}: правило «{code}» — уровень «{level}»; допустимы: "
                         f"{', '.join(LEVELS)}")
    return Conventions(prefix=prefix, other_prefixes=others,
                      marker_tag=_тег(data.get("метки"), откуда),
                      markers=_метки_ставятся(data.get("метки"), откуда),
                      atomic_roles=_схема_ролей(data.get("атомарныеРоли"), откуда),
                      form_code=_код_форм(data.get("кодФормы"), откуда, диалект_из),
                      rules=tuple(sorted(rules.items())))


def _приставки(value, откуда):
    """(основная приставка, другие свои). Список — основная первой: её ставят
    новым именам и называют в находках, остальные тоже свои — прежние приставки
    команды, имена тестовых модулей («ОМ_мой_»)."""
    if value is None:
        return None, ()
    список = value if isinstance(value, list) else [value]
    if not список or not all(isinstance(pt, str) and pt.strip() for pt in список):
        raise Refuse(f"{откуда}: «приставка» — непустая строка или список строк, например "
                     "«мой_» или [«мой_», «ОМ_мой_»]")
    return список[0], tuple(список[1:])


def _код_форм(code, откуда, диалект_из=None):
    """Язык кода доработки формы; без раздела — методы платформы."""
    if code is None:
        return FormCode()
    if not isinstance(code, dict):
        raise Refuse(f"{откуда}: «кодФормы» — объект: {{\"язык\": \"платформа\"}} или "
                     "{\"язык\": <язык команды>, \"диалект\": <файл диалекта>, …}")
    language = code.get("язык", PLATFORM)
    file = code.get("диалект")
    # Настройки — значением, как и все соглашения: по ним кешируется реестр видов.
    settings = tuple(sorted((key, _значением(value)) for key, value in code.items()
                             if key not in КЛЮЧИ_КОДА))
    try:
        if file is None:
            dialect = PLATFORM_DIALECT
        elif not isinstance(file, str) or not file.strip():
            raise Refuse("«диалект» — путь к файлу диалекта строкой")
        elif диалект_из is None:
            raise Refuse("«диалект» подключается только из файла профиля "
                         "(META_PROFILE или --профиль): путь к нему считается от профиля")
        else:
            dialect = диалект_из(file)
        return FormCode(language, dialect, settings)
    except Refuse as refusal:
        raise Refuse(f"{откуда}: «кодФормы»: {refusal}") from refusal


def _значением(value):
    """Значение настройки — неизменяемым: список кортежем, объект — парами."""
    if isinstance(value, list):
        return tuple(_значением(element) for element in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _значением(element)) for key, element in value.items()))
    return value


def _метки_ставятся(markers, откуда):
    """`метки.ставить` — ставит ли команда метки вставок; по умолчанию — да."""
    ставить = (markers or {}).get("ставить", True) if isinstance(markers, dict) else True
    if not isinstance(ставить, bool):
        raise Refuse(f"{откуда}: «метки.ставить» — true или false")
    return ставить


def _тег(markers, откуда):
    """Метка команды из раздела «метки»; `None` — команда её не ставит."""
    if markers is None:
        return None
    if not isinstance(markers, dict):
        raise Refuse(f"{откуда}: «метки» — объект, например {{\"тег\": \"#TEAM\"}}")
    extra = sorted(set(markers) - set(КЛЮЧИ_МЕТОК))
    if extra:
        raise Refuse(f"{откуда}: в «метки» неизвестные ключи {', '.join(extra)}; "
                     f"известны: {', '.join(КЛЮЧИ_МЕТОК)}")
    tag = markers.get("тег")
    if tag is not None and not (isinstance(tag, str) and ТЕГ.match(tag)):
        raise Refuse(f"{откуда}: «метки.тег» — «#» и слово без пробелов, например «#TEAM»")
    return tag


def _схема_ролей(schema, откуда):
    """Схема имён атомарных ролей; `None` — команда их не заводит. Что схема
    даёт различимые имена, проверяет домен — здесь только форма записи."""
    if schema is None:
        return None
    if not isinstance(schema, dict):
        raise Refuse(f"{откуда}: «атомарныеРоли» — объект с ключами «имя» и «синоним»")
    extra = sorted(set(schema) - set(КЛЮЧИ_СХЕМЫ))
    if extra:
        raise Refuse(f"{откуда}: в «атомарныеРоли» неизвестные ключи {', '.join(extra)}; "
                     f"известны: {', '.join(КЛЮЧИ_СХЕМЫ)}")
    if not all(isinstance(schema.get(key), str) and schema[key].strip() for key in КЛЮЧИ_СХЕМЫ):
        raise Refuse(f"{откуда}: в «атомарныеРоли» нужны «имя» и «синоним» — шаблоны строкой, "
                     "например «мой_атом_{вид}_{объект}_{право}» и «Атом. {вид} - {синоним} - {право}»")
    try:
        return RoleSchema(schema["имя"], schema["синоним"])
    except Refuse as refusal:
        raise Refuse(f"{откуда}: {refusal}") from refusal


def _код_допустим(code):
    return isinstance(code, str) and bool(КОД.match(code))
