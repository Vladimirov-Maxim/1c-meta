"""Архитектурный гард: зависимости направлены внутрь, каналы разделены.

Правило слоёв (стрелка — «может импортировать»):

    domain       — ни от чего
    acl          → domain
    application  → domain
    infra        → domain, acl, application (только ports)
    jobs         → domain                             язык заданий: вход
    report       → domain, jobs, application (dto, ports) язык ответов: выход
    cli          → domain, jobs, report, application (dto, ports)
    api          → domain, jobs, report, application (dto, ports)
    composition  → все                                единственный корень сборки

`report` видит `jobs`, потому что справка (операции, запись типа, особые
поля) и есть описание языка заданий: печатать его по живым таблицам, а не
пересказом, можно только оттуда. Цикла нет — `jobs` знает один домен.

`cli` и `api` — два канала, терминал и MCP, и друг друга они не видят: общее
у них только то, что внутри. Каналы не знают ни инфраструктуры, ни конкретных
сценариев — корень передаёт их контроллерам фабриками, и сценарий получает
модель приложения, а не модель канала.

Точки входа (`meta/add.py`, `meta/mcp_server.py`) лежат вне слоёв и из пакета
импортируют только корень: запускают его — и всё.

Проверка разбирает исходники через `ast` как текст и ничего не импортирует:
гард должен работать и тогда, когда пакет сломан.

Отдельные правила: `domain` и `acl` не касаются диска; сторонняя библиотека
заперта в своём слое (lxml — infra, mcp и pydantic — api).
"""

import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

PACKAGE = os.path.join(ROOT, "meta")

# Слой → куда ему разрешено импортировать (свой слой разрешён всегда).
ALLOWED = {
    "domain": set(),
    "acl": {"domain"},
    "application": {"domain"},
    "infra": {"domain", "acl", "application"},
    "jobs": {"domain"},
    "report": {"domain", "application", "jobs"},
    "cli": {"domain", "application", "jobs", "report"},
    "api": {"domain", "application", "jobs", "report"},
    "composition": {"domain", "acl", "application", "infra", "jobs", "report", "cli", "api"},
}

# В `application` часть слоёв ходит только через договоры, не к сценариям:
# инфраструктура реализует порты, а каналы получают сценарии от корня.
THROUGH_CONTRACTS = {
    "infra": ("meta.application.ports",),
    "report": ("meta.application.dto", "meta.application.ports"),
    "cli": ("meta.application.dto", "meta.application.ports"),
    "api": ("meta.application.dto", "meta.application.ports"),
}

# Сторонняя библиотека -> единственный слой, которому она положена.
THIRD_PARTY = {"lxml": "infra", "mcp": "api", "pydantic": "api"}

# Слои, которым файловая система не положена.
DISKLESS = ("domain", "acl")
DISK_MODULES = ("os", "io", "pathlib", "shutil", "tempfile", "glob")


def module_name(path):
    """Путь .py -> имя модуля вида `meta.domain.model`."""
    rel = os.path.relpath(path, ROOT)
    parts = rel[: -len(".py")].split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def layer_of(module):
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "meta" and parts[1] in ALLOWED:
        return parts[1]
    return None


def resolve(node, current):
    """Абсолютное имя цели для `from …` — с учётом относительных импортов."""
    if node.level == 0:
        return node.module
    package = current.split(".")[:-1]
    base = package[: len(package) - (node.level - 1)]
    if node.module:
        base = base + node.module.split(".")
    return ".".join(base) if base else None


def imports_of(tree, current):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            target = resolve(node, current)
            if target:
                out.add(target)
                out.update(f"{target}.{alias.name}" for alias in node.names)
    return out


def sources():
    """Файлы пакета, кроме тестов: гард проверяет инструмент, а не себя."""
    for folder, subfolders, names in os.walk(PACKAGE):
        subfolders[:] = [d for d in subfolders if d not in ("__pycache__", "tests")]
        for name in sorted(names):
            if name.endswith(".py"):
                yield os.path.join(folder, name)


def test_dependencies_point_inward():
    violations = []
    for path in sources():
        current = module_name(path)
        layer = layer_of(current)
        if layer is None:          # точки входа проверяет отдельный тест
            continue
        tree = ast.parse(open(path, encoding="utf-8-sig").read())
        for target in imports_of(tree, current):
            target_layer = layer_of(target)
            if target_layer is None or target_layer == layer:
                continue
            if target_layer not in ALLOWED[layer]:
                violations.append(f"{current} ({layer}) -> {target} ({target_layer})")
            elif (target_layer == "application" and layer in THROUGH_CONTRACTS
                    and not target.startswith(THROUGH_CONTRACTS[layer])):
                violations.append(
                    f"{current} ({layer}) -> {target}: к application только через "
                    + ", ".join(THROUGH_CONTRACTS[layer]))
    assert not violations, "зависимости наружу:\n" + "\n".join(sorted(set(violations)))
    print(f"проверено файлов: {sum(1 for _ in sources())}")


def test_channels_do_not_see_each_other():
    """Терминал и MCP — два канала. Правка одного не должна задевать другой,
    и проще всего это обеспечить, запретив им знать друг о друге. Правило
    следует и из таблицы слоёв; здесь оно сказано отдельно, своим текстом."""
    crossed = []
    for path in sources():
        current = module_name(path)
        layer = layer_of(current)
        if layer not in ("cli", "api"):
            continue
        other = "api" if layer == "cli" else "cli"
        tree = ast.parse(open(path, encoding="utf-8-sig").read())
        crossed += [f"{current} -> {target}" for target in imports_of(tree, current)
                    if layer_of(target) == other]
    assert not crossed, "каналы видят друг друга:\n" + "\n".join(sorted(set(crossed)))


def test_entry_points_only_start_the_root():
    """Точка входа запускает корень и больше ничего: собирать граф — дело
    корня, и второй сборки в обход него быть не должно."""
    leaked = []
    for path in sources():
        current = module_name(path)
        if layer_of(current) is not None or current == "meta":
            continue
        tree = ast.parse(open(path, encoding="utf-8-sig").read())
        for target in imports_of(tree, current):
            if target.startswith("meta.") and not target.startswith("meta.composition"):
                leaked.append(f"{current} -> {target}")
    assert not leaked, "точка входа в обход корня:\n" + "\n".join(sorted(set(leaked)))


def test_domain_and_acl_have_no_disk():
    violations = []
    for path in sources():
        current = module_name(path)
        if layer_of(current) not in DISKLESS:
            continue
        tree = ast.parse(open(path, encoding="utf-8-sig").read())
        for target in imports_of(tree, current):
            корень = target.split(".")[0]
            if корень in DISK_MODULES:
                violations.append(f"{current} -> {target}")
    assert not violations, (
        "домен и перекладка не должны знать про файловую систему:\n"
        + "\n".join(sorted(set(violations))))
    print(", ".join(DISKLESS) + " — без диска")


def test_every_layer_is_checked():
    """Гард бесполезен, если слой переименовали и он перестал попадать в проверку."""
    seen = {layer_of(module_name(p)) for p in sources()}
    seen.discard(None)
    assert seen == set(ALLOWED), (
        f"слои на диске {sorted(seen)} не совпадают с описанными {sorted(ALLOWED)}")
    print(", ".join(sorted(seen)))

def test_domain_vocabulary_stays_russian():
    """Ключи словарей перекладки — доменные слова, и они русские.

    Механическое переименование идентификаторов может задеть и строки-данные:
    ключ «Дата» в `DATE_PARTS` превратится в `DateType`. Остальные тесты
    этого не поймают — портятся обе стороны разом, и сверка сходится сама
    с собой. Ловится только так.
    """
    from meta.acl import vocabulary
    from meta.domain import model

    # Таблицы, у которых ключ — слово выгрузки, а не домена, и латинский он
    # по существу: порядок детей ключуется каталогом выгрузки («Catalogs»),
    # корнем документа или тегом контейнера — тем, что стоит в файле.
    BY_DUMP_WORD = ("CARD_ORDER", "DOCUMENT_ORDER", "CONTAINER_ORDER")
    # У прав один ключ латиницей — `Automation`. Так право называет сама
    # платформа, и переводить его нам не по чину.
    LATIN_BY_PLATFORM = {"RIGHTS": {"Automation"}}

    latin = []
    for name in dir(vocabulary):
        # `_BACK` — обратные таблицы, там ключи по построению латинские;
        # подчёркнутые имена — служебные, вроде `__builtins__`.
        if name.startswith("_") or name.endswith("_BACK") or name in BY_DUMP_WORD:
            continue
        value = getattr(vocabulary, name)
        if not isinstance(value, dict):
            continue
        allowed = LATIN_BY_PLATFORM.get(name, ())
        for key in value:
            if (isinstance(key, str) and key not in allowed
                    and not re.search("[А-Яа-яЁё]", key)):
                latin.append(f"{name}[{key!r}]")
    assert not latin, "ключи словаря должны быть русскими:\n" + "\n".join(latin)

    # удобные обёртки платформенных типов обязаны совпадать со словарём
    for cls in (model.ValueStorageType, model.UuidType):
        assert cls().name in vocabulary.PLATFORM_TYPES, cls().name

def test_third_party_is_locked_in_its_layer():
    """Внешняя библиотека заперта в своём слое.

    lxml — в инфраструктуре: заменяемость держится на договоре `CardTree`
    (`infra/tree.py`) и на том, что типы и вызовы lxml не просачиваются в
    домен, перекладку или сценарии. mcp и pydantic — в канале MCP: модель
    запроса агента не должна становиться моделью сценария.
    """
    leaked = []
    for path in sources():
        current = module_name(path)
        layer = layer_of(current)
        tree = ast.parse(open(path, encoding="utf-8-sig").read())
        for target in imports_of(tree, current):
            owner = THIRD_PARTY.get(target.split(".")[0])
            if owner is not None and layer != owner:
                leaked.append(f"{current} ({layer}) -> {target}: положено только {owner}")
    assert not leaked, "сторонняя библиотека вне своего слоя:\n" + "\n".join(leaked)
    print("; ".join(f"{lib} — только {layer}" for lib, layer in THIRD_PARTY.items()))
