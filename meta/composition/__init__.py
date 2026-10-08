"""Корень сборки: единственное место, где инфраструктура встречается со
сценариями и каналами.

Отсюда оба канала получают контроллеры с уже подключёнными сценариями.
Выгрузка приходит в каждом запросе, поэтому контроллеру передаётся не
сценарий, а фабрика «сценарий для этой выгрузки»; в фабрику же встроена
политика доступа канала: терминалу — любая выгрузка (запускает человек),
MCP — только разрешённые (запускает агент).

Каналы подключаются здесь поимённо и лениво: терминалу не нужен пакет MCP,
и его отсутствие не должно ломать запуск из командной строки.

Здесь же читается профиль соглашений команды (`META_PROFILE`, у терминала —
ещё и ключ `--профиль`): сценарии получают соглашения значением, домен файлов
не читает.
"""

import datetime
import hashlib
import importlib.util
import json
import os

from ..application.add_child.use_case import AddChildUseCase
from ..application.add_object.use_case import AddObjectUseCase
from ..application.atomic_roles_use_case import AtomicRolesUseCase
from ..application.change_property.use_case import ChangePropertyUseCase
from ..application.delete.use_case import DeleteUseCase
from ..application.edit_code.use_case import EditCodeUseCase
from ..application.edit_form.use_case import EditFormUseCase
from ..application.normalize.use_case import NormalizeUseCase
from ..application.plan_check.use_case import PlanCheckUseCase
from ..application.plan_emit.use_case import PlanEmitUseCase
from ..application.reference.use_case import ReferenceUseCase
from ..application.rename.use_case import RenameUseCase
from ..application.show.use_case import ShowUseCase
from ..application.show_form.use_case import ShowFormUseCase
from ..application.verify.use_case import VerifyUseCase
from ..domain.conventions import НЕЙТРАЛЬНЫЕ
from ..domain.form_dialect import ДиалектКодаФорм
from ..domain.model import Refuse
from ..infra.changes import DirectoryChanges, GitChanges
from ..infra.designer import DesignerDump
from ..infra.edt_dump import EdtDump
from ..infra.external import ExternalDump
from ..infra.layout import layout_of
from ..infra.modules import DumpModules
from ..infra.reference import DesignerReference
from ..jobs import profile

#: Семья операций языка заданий -> сценарий, который её исполняет.
#: Язык заданий о сценариях не знает; связывает их только корень.
SCENARIOS = {
    "forms": EditFormUseCase,
    "atomic_roles": AtomicRolesUseCase,
    "children": AddChildUseCase,
    "renames": RenameUseCase,
    "deletions": DeleteUseCase,
    "changes": ChangePropertyUseCase,
    "objects": AddObjectUseCase,
}

#: Откуда MCP берёт разрешённые выгрузки: переменная окружения сервера.
ROOTS_VARIABLE = "META_ROOTS"

#: Где профиль соглашений команды: путь к JSON — переменная окружения.
PROFILE_VARIABLE = "META_PROFILE"


def соглашения_из_файла(путь):
    """Профиль соглашений из файла. Нечитаемый или неверный — отказ: молча
    работать без соглашений команды значило бы пропустить её правила."""
    откуда = f"профиль «{путь}»"
    try:
        with open(путь, encoding="utf-8-sig") as файл:
            данные = json.load(файл)
    except OSError as ошибка:
        raise Refuse(f"{откуда} не прочитан: {ошибка.strerror or ошибка}") from ошибка
    except ValueError as ошибка:
        raise Refuse(f"{откуда} — не JSON: {ошибка}") from ошибка
    рядом = os.path.dirname(os.path.abspath(путь))
    return profile.соглашения(
        данные, откуда, диалект_из=lambda имя: диалект_из_файла(os.path.join(рядом, имя)))


def диалект_из_файла(путь):
    """Язык кода формы из файла-диалекта: модуль Python с объектом `ДИАЛЕКТ`.

    Файл подключает профиль команды, то есть его пишет та же команда, что и
    профиль: это её код, и исполняется он так же, как код инструмента.
    Нет файла, он не загрузился или в нём нет `ДИАЛЕКТ` нужного рода — отказ
    с причиной: молча вернуться к языку платформы значило бы выдать команде
    код не на её языке.
    """
    if not os.path.isfile(путь):
        raise Refuse(f"файла диалекта «{путь}» нет")
    имя = "meta_dialect_" + hashlib.sha1(os.path.abspath(путь).encode("utf-8")).hexdigest()[:12]
    описание = importlib.util.spec_from_file_location(имя, путь)
    модуль = importlib.util.module_from_spec(описание)
    try:
        описание.loader.exec_module(модуль)
    except Exception as ошибка:
        raise Refuse(f"файл диалекта «{путь}» не загрузился: "
                     f"{type(ошибка).__name__}: {ошибка}") from ошибка
    диалект = getattr(модуль, "ДИАЛЕКТ", None)
    if not isinstance(диалект, ДиалектКодаФорм):
        raise Refuse(f"в файле диалекта «{путь}» нет объекта «ДИАЛЕКТ» — наследника "
                     "meta.domain.form_dialect.ДиалектКодаФорм")
    return диалект


def соглашения_из_окружения():
    """Профиль из `META_PROFILE`; не задан — нейтральные соглашения."""
    путь = (os.environ.get(PROFILE_VARIABLE) or "").strip()
    return соглашения_из_файла(путь) if путь else НЕЙТРАЛЬНЫЕ


def roots_from_environment():
    """Разрешённые выгрузки из «META_ROOTS» (через «;»). Пусто — никуда."""
    return tuple(путь.strip() for путь in (os.environ.get(ROOTS_VARIABLE) or "").split(";")
                 if путь.strip())


def _inside(repo, roots):
    """Путь внутри одного из корней (или сам корень).

    Сравниваются нормализованные абсолютные пути: `..` и регистр диска не
    должны превращать чужой каталог в разрешённый. Пустой список — отказ:
    сервер без настройки не должен иметь доступа к диску шире, чем ему дали
    намеренно.
    """
    if not roots:
        raise Refuse(f"сервер не настроен: в «{ROOTS_VARIABLE}» не указано ни одной "
                     "выгрузки, писать некуда")
    цель = os.path.normcase(os.path.abspath(repo))
    for корень in roots:
        полный = os.path.normcase(os.path.abspath(корень))
        if цель == полный or цель.startswith(полный + os.sep):
            return
    raise Refuse(f"выгрузка «{repo}» вне разрешённых: " + "; ".join(roots))


def _allowed(repo, roots):
    """Политика канала: белый список (MCP) или без ограничений (`None`)."""
    if roots is not None:
        _inside(repo, roots)
        if not os.path.isdir(repo):
            raise Refuse(f"каталога «{repo}» не существует")


def platform_factory(roots=None):
    """Фабрика площадки. `roots` — белый список (MCP); `None` — без ограничений."""
    def для(repo):
        _allowed(repo, roots)
        # Формат — по корню: `Configuration/Configuration.mdo` — проект EDT,
        # `Configuration.xml` — выгрузка конфигуратора, ни того ни другого —
        # выгрузка внешних обработок и отчётов (пустой каталог — под новую).
        if layout_of(repo).edt:
            return EdtDump(repo)
        if os.path.isfile(os.path.join(repo, "Configuration.xml")) or not os.path.isdir(repo):
            return DesignerDump(repo)
        return ExternalDump(repo)
    return для


def modules_factory(roots=None):
    """Фабрика модулей кода — с той же политикой доступа, что у площадки."""
    def для(repo):
        _allowed(repo, roots)
        return DumpModules(repo)
    return для


def changes_factory(roots=None):
    """Фабрика источника правок: выгрузка под git против базы или пара каталогов
    «эталон — копия». Политика доступа та же, что у площадки: у MCP — только
    разрешённые выгрузки, и пара каталогов — тоже."""
    def для(repo=None, base="HEAD", rev=None, baseline=None, target=None):
        if baseline or target:
            if not (baseline and target):
                raise Refuse("эталон и копия задаются вместе")
            if repo:
                raise Refuse("источник правок один: выгрузка под git или пара каталогов "
                             "«эталон — копия»")
            if roots is not None:
                _inside(baseline, roots)
                _inside(target, roots)
            return DirectoryChanges(baseline, target)
        if not repo:
            raise Refuse("не задано, что проверять: выгрузка под git (repo) или пара каталогов "
                         "«эталон — копия»")
        _allowed(repo, roots)
        return GitChanges(repo, base, rev)
    return для


def _today():
    """Сегодня — так, как дата пишется в метках вставок."""
    return datetime.date.today().strftime("%d.%m.%Y")


def _controller(cls, platform, modules, соглашения=НЕЙТРАЛЬНЫЕ, changes=None):
    """Контроллер канала с подключёнными сценариями и соглашениями команды."""
    scenarios = {семья: (lambda repo, сценарий=сценарий: сценарий(platform(repo), соглашения))
                 for семья, сценарий in SCENARIOS.items()}
    # Сценарию кода нужна не площадка метаданных, а модули: у правки вставками
    # своя работа с файлами (кодировка, переводы строк, история в git). Часы —
    # тоже отсюда: дата меток сверяется с сегодняшней.
    scenarios["code"] = lambda repo: EditCodeUseCase(modules(repo), today=_today,
                                                     соглашения=соглашения)
    changes = changes or changes_factory()
    return cls(scenarios=scenarios,
               show=lambda repo: ShowUseCase(platform(repo)),
               show_form=lambda repo: ShowFormUseCase(platform(repo), соглашения),
               reference=ReferenceUseCase(DesignerReference()),
               verify=lambda **источник: VerifyUseCase(changes(**источник), соглашения),
               normalize=lambda **источник: NormalizeUseCase(changes(**источник)),
               plan_check=lambda **источник: PlanCheckUseCase(changes(**источник), соглашения),
               plan_emit=lambda **источник: PlanEmitUseCase(changes(**источник)))


def _ключ_профиля(argv):
    """(путь из `--профиль <файл>` или None, остальные аргументы)."""
    if "--профиль" not in argv:
        return None, list(argv)
    i = argv.index("--профиль")
    if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
        raise Refuse("--профиль <файл.json>: после ключа нужен путь к профилю соглашений")
    return argv[i + 1], list(argv[:i]) + list(argv[i + 2:])


def terminal(argv):
    """Терминал: код возврата; отказ поднимается `Refuse`."""
    from ..cli.app import main
    from ..cli.controller import Controller

    путь, argv = _ключ_профиля(argv)
    соглашения = соглашения_из_файла(путь) if путь else соглашения_из_окружения()
    return main(argv, _controller(Controller, platform_factory(), modules_factory(), соглашения,
                                  changes_factory()))


def run_terminal(argv):
    """Терминал для запуска из командной строки: отказ печатается словом «ОТКАЗ»."""
    try:
        return terminal(argv)
    except Refuse as отказ:
        print(f"ОТКАЗ: {отказ}")
        return 1


def mcp_server(roots=None, соглашения=None):
    """Сервер MCP; белый список и соглашения — из окружения, если не переданы явно."""
    from ..api.controller import Controller
    from ..api.server import build

    roots = roots_from_environment() if roots is None else tuple(roots)
    соглашения = соглашения_из_окружения() if соглашения is None else соглашения
    return build(_controller(Controller, platform_factory(roots), modules_factory(roots), соглашения,
                             changes_factory(roots)),
                 соглашения)
