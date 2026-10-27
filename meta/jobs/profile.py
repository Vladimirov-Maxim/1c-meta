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

KEYS = ("приставка", "метки", "атомарныеРоли", "кодФормы", "правила")
MARKER_KEYS = ("тег", "ставить")
SCHEMA_KEYS = ("имя", "синоним")
#: Ключи «кодФормы», которые читает сам профиль; прочие — настройки языка.
CODE_KEYS = ("язык", "диалект")

#: Код находки — заглавные слова через дефис, как их печатает инструмент.
CODE = re.compile(r"^[A-ZА-ЯЁ0-9]+(?:-[A-ZА-ЯЁ0-9]+)*$")
#: Метка команды — «#» и слово: пробел разорвал бы её, а второй «#» в метке
#: читается как ИД задачи.
TAG = re.compile(r"^#[^\s#]+$")


def conventions(data, origin="профиль", dialect_from=None):
    """Разобранный профиль. Ошибка в нём — отказ с объяснением, а не догадка.

    `dialect_from` — как получить диалект по имени файла из «кодФормы.диалект»:
    файл читает тот, кто знает, где лежит профиль. Без него профиль с
    диалектом — отказ.
    """
    if not isinstance(data, dict):
        raise Refuse(f"{origin}: ожидается объект JSON с ключами {', '.join(KEYS)}")
    extra = sorted(set(data) - set(KEYS))
    if extra:
        raise Refuse(f"{origin}: неизвестные ключи {', '.join(extra)}; известны: {', '.join(KEYS)}")
    prefix, others = _prefixes(data.get("приставка"), origin)
    rules = data.get("правила") or {}
    if not isinstance(rules, dict):
        raise Refuse(f"{origin}: «правила» — объект «код находки: уровень»")
    for code, level in rules.items():
        if not _code_allowed(code):
            raise Refuse(f"{origin}: «{code}» — не код находки: заглавные слова через дефис, "
                         "как в ответе инструмента, например «МД-ПРЕФИКС»")
        if level not in LEVELS:
            raise Refuse(f"{origin}: правило «{code}» — уровень «{level}»; допустимы: "
                         f"{', '.join(LEVELS)}")
    return Conventions(prefix=prefix, other_prefixes=others,
                      marker_tag=_tag(data.get("метки"), origin),
                      markers=_markers_placed(data.get("метки"), origin),
                      atomic_roles=_role_schema(data.get("атомарныеРоли"), origin),
                      form_code=_form_code(data.get("кодФормы"), origin, dialect_from),
                      rules=tuple(sorted(rules.items())))


def _prefixes(value, origin):
    """(основная приставка, другие свои). Список — основная первой: её ставят
    новым именам и называют в находках, остальные тоже свои — прежние приставки
    команды, имена тестовых модулей («ОМ_мой_»)."""
    if value is None:
        return None, ()
    listing = value if isinstance(value, list) else [value]
    if not listing or not all(isinstance(pt, str) and pt.strip() for pt in listing):
        raise Refuse(f"{origin}: «приставка» — непустая строка или список строк, например "
                     "«мой_» или [«мой_», «ОМ_мой_»]")
    return listing[0], tuple(listing[1:])


def _form_code(code, origin, dialect_from=None):
    """Язык кода доработки формы; без раздела — методы платформы."""
    if code is None:
        return FormCode()
    if not isinstance(code, dict):
        raise Refuse(f"{origin}: «кодФормы» — объект: {{\"язык\": \"платформа\"}} или "
                     "{\"язык\": <язык команды>, \"диалект\": <файл диалекта>, …}")
    language = code.get("язык", PLATFORM)
    file = code.get("диалект")
    # Настройки — значением, как и все соглашения: по ним кешируется реестр видов.
    settings = tuple(sorted((key, _with_value(value)) for key, value in code.items()
                             if key not in CODE_KEYS))
    try:
        if file is None:
            dialect = PLATFORM_DIALECT
        elif not isinstance(file, str) or not file.strip():
            raise Refuse("«диалект» — путь к файлу диалекта строкой")
        elif dialect_from is None:
            raise Refuse("«диалект» подключается только из файла профиля "
                         "(META_PROFILE или --профиль): путь к нему считается от профиля")
        else:
            dialect = dialect_from(file)
        return FormCode(language, dialect, settings)
    except Refuse as refusal:
        raise Refuse(f"{origin}: «кодФормы»: {refusal}") from refusal


def _with_value(value):
    """Значение настройки — неизменяемым: список кортежем, объект — парами."""
    if isinstance(value, list):
        return tuple(_with_value(element) for element in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _with_value(element)) for key, element in value.items()))
    return value


def _markers_placed(markers, origin):
    """`метки.ставить` — ставит ли команда метки вставок; по умолчанию — да."""
    to_place = (markers or {}).get("ставить", True) if isinstance(markers, dict) else True
    if not isinstance(to_place, bool):
        raise Refuse(f"{origin}: «метки.ставить» — true или false")
    return to_place


def _tag(markers, origin):
    """Метка команды из раздела «метки»; `None` — команда её не ставит."""
    if markers is None:
        return None
    if not isinstance(markers, dict):
        raise Refuse(f"{origin}: «метки» — объект, например {{\"тег\": \"#TEAM\"}}")
    extra = sorted(set(markers) - set(MARKER_KEYS))
    if extra:
        raise Refuse(f"{origin}: в «метки» неизвестные ключи {', '.join(extra)}; "
                     f"известны: {', '.join(MARKER_KEYS)}")
    tag = markers.get("тег")
    if tag is not None and not (isinstance(tag, str) and TAG.match(tag)):
        raise Refuse(f"{origin}: «метки.тег» — «#» и слово без пробелов, например «#TEAM»")
    return tag


def _role_schema(schema, origin):
    """Схема имён атомарных ролей; `None` — команда их не заводит. Что схема
    даёт различимые имена, проверяет домен — здесь только форма записи."""
    if schema is None:
        return None
    if not isinstance(schema, dict):
        raise Refuse(f"{origin}: «атомарныеРоли» — объект с ключами «имя» и «синоним»")
    extra = sorted(set(schema) - set(SCHEMA_KEYS))
    if extra:
        raise Refuse(f"{origin}: в «атомарныеРоли» неизвестные ключи {', '.join(extra)}; "
                     f"известны: {', '.join(SCHEMA_KEYS)}")
    if not all(isinstance(schema.get(key), str) and schema[key].strip() for key in SCHEMA_KEYS):
        raise Refuse(f"{origin}: в «атомарныеРоли» нужны «имя» и «синоним» — шаблоны строкой, "
                     "например «мой_атом_{вид}_{объект}_{право}» и «Атом. {вид} - {синоним} - {право}»")
    try:
        return RoleSchema(schema["имя"], schema["синоним"])
    except Refuse as refusal:
        raise Refuse(f"{origin}: {refusal}") from refusal


def _code_allowed(code):
    return isinstance(code, str) and bool(CODE.match(code))
