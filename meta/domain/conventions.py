"""Соглашения команды: значения, на которых работают правила домена.

Правила — общие для всех и живут в домене: «новый объект называется с
приставкой доработок», «типовая форма правится только кодом», «подписка на
собственный объект — лишнее звено». Названы они кодами находок — языком
домена, без номеров чьих-либо регламентов. А вот *какая* приставка, какие
правила команда соблюдает и насколько строго — у разных команд разное. Это
и есть соглашения: они приходят снаружи, из профиля команды (`jobs/profile`),
и домен получает их значением, а не читает откуда-то сам.

Без профиля — нейтральные соглашения: приставки нет, и правила, которым
она нужна, не применяются — проверять нечего. Инструмент при этом остаётся
писателем выгрузки, каким его знают все: соглашения одной команды не
навязываются другой.
"""

import copy
from dataclasses import dataclass

from .atomic_roles import RoleSchema
from .form_dialect import PLATFORM as PLATFORM_DIALECT
from .form_dialect import FormCodeDialect
from .model import Finding, Refuse

#: Уровень правила в профиле: «ошибка» — писать нельзя, «предупреждение» —
#: можно, но посмотреть; «выкл» — правило команда не соблюдает, находки нет.
ERROR = Finding.ERROR
WARNING = Finding.WARNING
OFF = "выкл"
LEVELS = (ERROR, WARNING, OFF)

#: Встроенный язык кода доработки формы — методы платформы. Свой язык команда
#: подключает файлом-диалектом (`domain.form_dialect`).
PLATFORM = PLATFORM_DIALECT.name

#: Правила проверки правок, у которых предмет — метки вставок. Команда, которая
#: меток не ставит (`Соглашения.метки`), их не держит: иначе каждая её правка
#: была бы «вне вставки».
MARKER_RULES = ("ВСТАВКА-БУКВА-Ё", "ВСТАВКА-БЕЗ-ТИПА", "ВСТАВКА-БЕЗ-ДАТЫ",
                 "ВСТАВКА-БЕЗ-ЗАДАЧИ", "ПРАВКА-ВНЕ-ВСТАВКИ", "ПРАВКА-В-ЧУЖОЙ-ВСТАВКЕ",
                 "ВСТАВКА-НЕ-ЗАКРЫТА", "ВСТАВКА-МЕТОДА-НЕ-НА-КОНЦЕ")


@dataclass(frozen=True)
class FormCode:
    """На каком языке пишется код доработки формы — для типовой формы, которую
    правят только кодом.

    `язык` — имя из профиля; встроен один, «платформа». Другой язык описывает
    `диалект` — объект из файла, который назвал профиль; его имя обязано
    совпасть с `языком`, иначе профиль подключил не тот файл. `настройки` —
    пары «имя: значение» из раздела «кодФормы», кроме «язык» и «диалект»; их
    проверяет сам язык: неполная запись — отказ, а не догадка.
    """

    language: str = PLATFORM
    dialect: FormCodeDialect = PLATFORM_DIALECT
    settings: tuple = ()

    def __post_init__(self):
        if self.language == PLATFORM:
            if self.dialect is not PLATFORM_DIALECT:
                raise Refuse("язык «платформа» встроен — файл диалекта ему не нужен")
        elif self.dialect is PLATFORM_DIALECT:
            raise Refuse(f"язык кода формы «{self.language}» не встроен (встроен «{PLATFORM}»): "
                         "укажите в «кодФормы» «диалект» — файл диалекта, путь от файла "
                         "профиля")
        elif self.dialect.name != self.language:
            raise Refuse(f"файл диалекта описывает язык «{self.dialect.name}», а профиль "
                         f"называет «{self.language}» — подключён не тот файл")
        self.dialect.check(self.vocabulary)

    @property
    def vocabulary(self):
        """Настройки языка словарём — так их получает диалект."""
        return dict(self.settings)

    @property
    def builtin(self):
        """Код пишут методы платформы — перекладкой, а не файлом диалекта."""
        return self.dialect is PLATFORM_DIALECT


@dataclass(frozen=True)
class Conventions:
    """Соглашения одной команды.

    `приставка` — с чего начинается имя всего, что команда добавляет сама
    («мой_»); `None` — соглашения о приставке нет. `other_prefixes` — тоже
    свои, но не для новых имён: прежние приставки команды, имена тестовых
    модулей («ОМ_мой_» — так YAxUnit зовёт модуль тестов). `marker_tag` — метка
    команды в открывающей метке вставки перед автором («#TEAM»); `None` —
    метка пишется без неё. `метки` — ставит ли команда метки
    вставок вообще: нет — правка кода пишется на место старого кода, правила
    меток выключены. `atomic_roles` — как команда называет атомарные
    роли (`RoleSchema`); `None` — команда их не заводит. `form_code` — на
    каком языке пишется код доработки типовой формы (`FormCode`, по умолчанию
    методы платформы). `правила` — пары (код находки, уровень): правило можно
    выключить или сменить ему уровень, само правило при этом не меняется. Пары,
    а не словарь: соглашения неизменяемы и сравниваются значением — по ним
    кешируется, например, реестр видов.
    """

    prefix: str | None = None
    other_prefixes: tuple = ()
    marker_tag: str | None = None
    markers: bool = True
    atomic_roles: RoleSchema | None = None
    form_code: FormCode = FormCode()
    rules: tuple = ()

    def level(self, code, regular):
        """Уровень правила с учётом профиля."""
        if not self.markers and code in MARKER_RULES:
            return OFF
        return dict(self.rules).get(code, regular)

    def apply(self, findings):
        """Находки домена по соглашениям: выключенные — прочь, уровень — из профиля.

        Применяется там, где находки собраны, до решения «писать или нет»:
        иначе выключенное правило всё равно остановило бы запись. Находка
        копируется целиком: у находки проверки правок есть ещё файл и строка,
        и профиль меняет строгость, а не место.
        """
        if not self.rules and self.markers:
            return list(findings)
        result = []
        for finding in findings:
            level = self.level(finding.code, finding.level)
            if level == OFF:
                continue
            if level != finding.level:
                finding = copy.copy(finding)
                finding.level = level
            result.append(finding)
        return result

    @property
    def prefixes(self):
        """Все свои приставки: основная первой. Пусто — соглашения нет."""
        return ((self.prefix,) + tuple(self.other_prefixes)) if self.prefix else ()

    def is_own(self, name):
        """Названо ли имя по соглашению о приставке. Без соглашения — неизвестно (`None`)."""
        if not self.prefix:
            return None
        return (name or "").startswith(self.prefixes)


#: Соглашения по умолчанию — когда профиль не задан.
NEUTRAL = Conventions()
