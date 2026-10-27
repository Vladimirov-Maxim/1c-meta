"""Источник правок задачи: git или пара каталогов — реализация `ChangeSource`.

Git — для выгрузки под историей: рабочая копия (вместе с новыми файлами,
которых git ещё не знает) или ревизия против базовой ревизии. Пара каталогов
— для обработки или отчёта вне репозитория: эталон из вложения задачи против
правленой копии; состав — сравнением по содержимому, различия строк — тем же
построчным сравнением, что и у git.

Строки нумеруются так, как их считает git: по переводу строки «\\n»,
возврат каретки перед ним — часть перевода, а не строки.
"""

import os
import re

from ..acl import mapping, mdo
from ..acl import modules as module_files
from ..application.ports import ChangeSource
from ..domain import verification as rules
from ..domain.changes import (
    ADDED,
    AFTER,
    BEFORE,
    DELETED,
    MODIFIED,
    FileChange,
    Hunk,
    hunks_between,
    pairs_by_content,
    pairs_by_position,
    whole_file,
)
from ..domain.model import Refuse
from ..domain.modules import COMMAND_MARK, CONFIGURATION, FORM_MARK, ModuleAddress
from ..domain.plan import Composition
from . import form_bindings, git, layout
from .repository import Plan
from .tree_lxml import LxmlCardTree

#: Сколько файлов репозитория смотреть, чтобы понять, какие в нём переводы строк.
EOL_SAMPLE = 200

HUNK = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def split_lines(data):
    """Байты файла -> строки без переводов, как их считает git."""
    if data is None:
        return None
    text = data.decode("utf-8", "replace")
    if text.startswith("﻿"):
        text = text[1:]
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        return []
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def read_composition(data, edt=False):
    """Байты карточки -> `domain.plan.Состав`; карточка не читается — состав с
    причиной: о сломанной карточке говорится словами, а не обрывом проверки.
    `edt` — карточка проекта EDT (`.mdo`), иначе — выгрузки конфигуратора."""
    tree = LxmlCardTree()
    try:
        document = tree.parse(data.decode("utf-8-sig", "replace").replace("\r\n", "\n"))
    except Refuse as refusal:
        return Composition(broken=str(refusal))
    node = tree.to_node(document)
    return mdo.composition_from_node(node) if edt else mapping.composition_from_node(node)


def bom_word(data):
    """True — файл с BOM, False — без; пустой файл — None: сказать нечего."""
    if not data:
        return None
    return data.startswith(b"\xef\xbb\xbf")


def eol_word(data):
    """«CRLF» или «LF» — каких переводов в файле больше; None — переводов нет."""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if not crlf and not lf:
        return None
    return "CRLF" if crlf > lf else "LF"


class _Layout(ChangeSource):
    """Раскладка исходников — общая для обоих источников; какая именно
    (выгрузка конфигуратора или проект EDT), решает корень (`layout.layout_of`)."""

    #: раскладка файлов и раскладка модулей; ставит конструктор источника
    layout = layout.DESIGNER

    @property
    def format_name(self):
        return self.layout.name

    @property
    def _modules(self):
        return module_files.EDT if self.layout.edt else module_files.DESIGNER

    def format_notes(self):
        if self.layout.edt:
            return [f"правило {rules.SERVICE_FILE} не применяется: в проекте EDT служебного файла "
                    "выгрузки нет"]
        return []

    def is_module(self, path):
        return self.layout.is_module(path)

    def form_bindings(self, path):
        description = form_bindings.form_file(path)
        data = self.data(description, AFTER) if description else None
        if data is None:
            return None
        bound, elements = form_bindings.bindings(data.decode("utf-8-sig", "replace"))
        return bound, elements, form_bindings.FORM_EVENT_NAMES

    def is_text(self, path):
        return self.layout.is_text(path)

    def is_service(self, path):
        return self.layout.is_service(path)

    def object_of(self, path):
        return self.layout.object_of(path)

    def owner_of(self, path):
        return self.layout.owner_of(path)

    def card_path(self, kind, name):
        return self.layout.card_path(kind, name)

    def composition(self, kind, name, side):
        path = self.layout.card_path(kind, name)
        data = self.data(path, side) if path else None
        return None if data is None else read_composition(data, self.layout.edt)

    def module_of(self, path):
        address = self._modules.address_of_file(path.split("/"))
        if address is None or address.sub is not None or address.module in (FORM_MARK, COMMAND_MARK) \
                or address.kind == CONFIGURATION:
            return None
        return address.kind, address.name, address.module

    def module_path(self, kind, name, module):
        if kind not in module_files.CONTAINERS or module not in module_files.OWN_FILES:
            return None
        return "/".join(self._modules.module_file(ModuleAddress(kind, name, module)))

    def lines(self, path, side):
        return split_lines(self.data(path, side))

    def _granting(self, objects, mentions, read):
        """{объект: [(роль, право)]} по упоминаниям: `mentions` — {объект: [файлы
        прав]}, `read(файл)` — его байты. Упоминание ещё не право: блок объекта
        может перечислять права со значением false."""
        tree, granted, result = LxmlCardTree(), {}, {}
        for obj in objects:
            rights_name = self.layout.rights_name(*obj)
            for file in sorted(set(mentions.get(obj, ()))):
                if file not in granted:
                    text = (read(file) or b"").decode("utf-8-sig", "replace").replace("\r\n", "\n")
                    granted[file] = {name for name, _ in tree.granted(tree.parse(text))}
                role = self.layout.rights_file.match(file).group(1)
                result.setdefault(obj, []).append((role, rights_name in granted[file]))
        return result


class GitChanges(_Layout):
    """Правки задачи по истории git: рабочая копия или ревизия против базы."""

    mode = ChangeSource.GIT

    def __init__(self, root, base="HEAD", rev=None):
        self.root = os.path.abspath(root)
        self.base = base or "HEAD"
        self.rev = rev or None
        self._cache = {}
        if not os.path.isdir(self.root):
            raise Refuse(f"каталога «{self.root}» не существует")
        self.layout = layout.layout_of(self.root)
        inside = self._git("rev-parse", "--is-inside-work-tree", why="не могу узнать, под git ли выгрузка")
        if inside is None:
            raise Refuse("git не найден — для сравнения с базой он нужен; без git сравнивайте парой "
                         "каталогов «эталон — копия»")
        if inside.returncode != 0:
            raise Refuse(f"«{self.root}» не под git: {git.said(inside)}")
        for revision in filter(None, (self.base, self.rev)):
            exists = self._git("rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}",
                             why=f"не могу проверить ревизию «{revision}»")
            if exists.returncode != 0:
                raise Refuse(f"ревизии «{revision}» в репозитории нет")

    def _git(self, *args, why):
        return git.run(self.root, *args, why=why)

    def _ok(self, done, why):
        if done is None or done.returncode != 0:
            raise Refuse(f"git: {why}: {git.said(done) if done is not None else 'git не найден'}")
        return done.stdout

    def against_head(self):
        if self.rev:
            return None
        base = self._git("rev-parse", "--verify", "--quiet", f"{self.base}^{{commit}}", why="не могу прочитать базу")
        head = self._git("rev-parse", "--verify", "--quiet", "HEAD^{commit}", why="не могу прочитать HEAD")
        if base is None or head is None or head.returncode != 0 or base.stdout == head.stdout:
            return None
        return GitChanges(self.root, "HEAD")

    def describe(self):
        if self.rev:
            what = f"ревизия {self.rev} против {self.base}"
        else:
            what = f"рабочая копия против {self.base} (с новыми файлами)"
        return f"{self.layout.name}: {what}" if self.layout.edt else what

    def changes(self):
        if "changes" in self._cache:
            return self._cache["changes"]
        revisions = [self.base] + ([self.rev] if self.rev else [])
        output = self._ok(self._git("diff", "--relative", "--no-renames", "--name-status", *revisions,
                                   why="не могу получить состав правок"), "состав правок")
        files = {}
        for line in output.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue
            status, _, path = line.partition("\t")
            files[git.unquote(path)] = {"A": ADDED, "D": DELETED}.get(status[:1], MODIFIED)
        untracked = self._untracked() if not self.rev else set()
        for path in untracked:
            files[path] = ADDED
        self._cache["неотслеживаемые"] = untracked
        self._cache["changes"] = [FileChange(status, path) for path, status in sorted(files.items())]
        return self._cache["changes"]

    def _untracked(self):
        """Новые файлы, которых git ещё не знает, — от корня выгрузки.

        `git status`, а не `ls-files --others`: на выгрузке в сотню тысяч
        файлов он втрое быстрее (1,6 с против 5,3) при том же составе.
        `--no-optional-locks` — чтение не обновляет индекс. Пути у него от
        корня репозитория: выгрузка, лежащая в репозитории глубже, отрезает
        свою приставку.
        """
        prefix = self._ok(self._git("rev-parse", "--show-prefix", why="не могу узнать место выгрузки"),
                             "место выгрузки").decode("utf-8", "replace").strip()
        output = self._ok(self._git("--no-optional-locks", "status", "--porcelain=v1", "-z",
                                   "--untracked-files=all", why="не могу получить новые файлы"), "новые файлы")
        new_items = set()
        for record in output.decode("utf-8", "replace").split("\0"):
            if record.startswith("?? ") and record[3:].startswith(prefix):
                new_items.add(record[3 + len(prefix):])
        return new_items

    def _blob(self, revision, path):
        key = ("blob", revision, path)
        if key not in self._cache:
            done = self._git("show", f"{revision}:./{path}", why=f"не могу прочитать «{path}» в {revision}")
            self._cache[key] = done.stdout if done is not None and done.returncode == 0 else None
        return self._cache[key]

    def data(self, path, side):
        if side == BEFORE:
            return self._blob(self.base, path)
        if self.rev:
            return self._blob(self.rev, path)
        full = os.path.join(self.root, *path.split("/"))
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as file:
            return file.read()

    def hunks(self, path):
        key = ("hunks", path)
        if key in self._cache:
            return self._cache[key]
        self.changes()
        if path in self._cache["неотслеживаемые"]:
            # новых файлов git diff не видит вовсе: добавлена каждая строка
            found = whole_file(self.lines(path, AFTER) or [])
        else:
            revisions = [self.base] + ([self.rev] if self.rev else [])
            # histogram, а не алгоритм по умолчанию: тот относит неизменённый
            # КонецПроцедуры чужого метода к добавленным, когда за вложенной
            # вставкой в его конце следует новый метод, — и правка «в чужой
            # вставке» находится там, где её нет
            output = self._ok(self._git("diff", "--relative", "--no-renames", "--no-color", "--no-ext-diff",
                                       "--diff-algorithm=histogram", "-U0", *revisions, "--", path,
                                       why=f"не могу получить различия «{path}»"), f"различия «{path}»")
            found = []
            for line in output.splitlines():
                m = HUNK.match(line)
                if m:
                    found.append(Hunk(int(m.group(1)), int(m.group(2) or 1),
                                      int(m.group(3)), int(m.group(4) or 1)))
        self._cache[key] = found
        return found

    def unchanged_pairs(self, path):
        return pairs_by_position(self.hunks(path))

    def _samples(self):
        """Начала образцов репозитория — модулей и карточек: по ним видно, какие
        в нём переводы строк и есть ли BOM. Читается один раз."""
        if "образцы" not in self._cache:
            samples = self._git("ls-files", "--", "*.bsl", "*.xml", "*.mdo",
                                why="не могу получить образцы файлов")
            data = []
            if samples is not None and samples.returncode == 0:
                for path in samples.stdout.decode("utf-8", "replace").splitlines()[:EOL_SAMPLE]:
                    full = os.path.join(self.root, *git.unquote(path).split("/"))
                    if os.path.isfile(full):
                        with open(full, "rb") as file:
                            data.append(file.read())
            self._cache["образцы"] = data
        return self._cache["образцы"]

    def accepted_eol(self):
        if not self.rev and git.setting(self.root, "core.autocrlf") in ("true", "input"):
            if self._strict():
                return None, ("переводы строк сверяются с тем, как git кладёт файлы в рабочую копию: "
                              "при core.safecrlf=true другие git add не примет")
            return None, "переводы строк не сверяются: git нормализует их сам (core.autocrlf)"
        return self._repository_eol()

    def _strict(self):
        if "safecrlf" not in self._cache:
            self._cache["safecrlf"] = git.strict_eol(self.root)
        return self._cache["safecrlf"]

    def _checkout_eol(self, path):
        """Как git кладёт файл в рабочую копию — для всех текстовых файлов правок
        разом: `check-attr` по одному файлу на сотне правок стоил бы секунды."""
        if "checkout" not in self._cache:
            paths = [c.path for c in self.changes() if self.is_text(c.path)]
            self._cache["checkout"] = git.checkout_eols(self.root, paths)
        if path not in self._cache["checkout"]:
            self._cache["checkout"][path] = git.checkout_eol(self.root, path)
        return self._cache["checkout"][path]

    def expected_eol(self, path):
        """Рабочая копия: если переводы строк задаёт git — те, которыми он кладёт
        файл (сверяются только при `core.safecrlf=true`: иначе git сводит их сам
        и на коммит они не влияют); не задаёт — принятые в репозитории.

        Ревизия: блоб git уже не нормализует — CRLF в коммите остаётся в
        истории. Изменённый файл держится переводов строк своего блоба в базе;
        новый — LF, если переводы строк задаёт git (в индексе он их сводит к
        LF), иначе принятых в репозитории."""
        if self.rev:
            before_ = self._blob(self.base, path)
            if before_ is not None:
                crlf, lf = rules.eol_counts(before_)
                if crlf and lf:
                    return None, None
                word = "CRLF" if crlf else "LF" if lf else None
                return word, f"в {self.base} файл с {word}: коммит переписывает его целиком"
            if self._checkout_eol(path):
                return "LF", "в истории git такие файлы хранит с LF (core.autocrlf, атрибуты)"
            return self._repository_eol()[0], None
        from_git = self._checkout_eol(path)
        if from_git:
            if not self._strict():
                return None, None
            return from_git, (f"git кладёт его в рабочую копию с {from_git}: при core.safecrlf=true "
                            "git add откажет — нормализуйте файл")
        return self._repository_eol()[0], None

    def _repository_eol(self):
        crlf = lf = 0
        for data in self._samples():
            word = eol_word(data)
            crlf += word == "CRLF"
            lf += word == "LF"
        if not crlf and not lf:
            return None, "переводы строк не сверяются: в репозитории нет модулей и карточек, с которыми сверить"
        return ("CRLF" if crlf >= lf else "LF"), None

    def accepted_bom(self):
        """BOM, принятый в репозитории: так, как у большинства его образцов; образцов
        нет — как принято в формате исходников."""
        ss, without = 0, 0
        for data in self._samples():
            exists = bom_word(data)
            ss += exists is True
            without += exists is False
        if not ss and not without:
            return self.layout.bom
        return ss >= without

    def roles_granting(self, objects):
        if not objects:
            return {}
        names = {self.layout.rights_name(*obj): obj for obj in objects}
        arguments = ["grep", "-F", "-o"]
        for name in names:
            arguments += ["-e", f"<name>{name}</name>"]
        if self.rev:
            arguments += [self.rev, "--", layout.RIGHTS_FOLDER]
        else:
            arguments = [arguments[0], "--untracked"] + arguments[1:] + ["--", layout.RIGHTS_FOLDER]
        done = self._git(*arguments, why="не могу найти объекты в правах ролей")
        if done is None or done.returncode not in (0, 1):     # 1 — «ничего не найдено»
            raise Refuse(f"git: поиск в правах ролей: {git.said(done) if done else 'git не найден'}")
        mentions = {}
        for line in done.stdout.decode("utf-8", "replace").splitlines():
            if self.rev and line.startswith(f"{self.rev}:"):
                line = line[len(self.rev) + 1:]
            file, _, found = line.partition(":<name>")
            name = found.removesuffix("</name>")
            if name in names and self.layout.rights_file.match(file):
                mentions.setdefault(names[name], []).append(file)
        return self._granting(objects, mentions, lambda file: self.data(file, AFTER))

    def target_eol(self, path):
        return self.expected_eol(path)[0]

    def target_bom(self, path):
        if "bom" not in self._cache:
            self._cache["bom"] = self.accepted_bom()
        return self._cache["bom"]

    def prepare_rewrites(self, items):
        if self.rev:
            raise Refuse(f"ревизию {self.rev} не переписывают — нормализуется рабочая копия")
        plan = Plan()
        for path, data in items:
            plan.add(os.path.join(self.root, *path.split("/")), data, False)
        return plan


class DirectoryChanges(_Layout):
    """Правки как пара каталогов: эталон («до») против копии («после»)."""

    mode = ChangeSource.PAIR

    def __init__(self, baseline, target):
        self.baseline = os.path.abspath(baseline)
        self.target = os.path.abspath(target)
        for directory, what in ((self.baseline, "эталона"), (self.target, "копии")):
            if not os.path.isdir(directory):
                raise Refuse(f"каталога {what} «{directory}» не существует")
        self._changes = None
        self.layout = layout.layout_of(self.target, layout.layout_of(self.baseline))

    def describe(self):
        return f"копия {self.target} против эталона {self.baseline}"

    @staticmethod
    def _files(root):
        found = {}
        for folder, _, names in os.walk(root):
            for name in names:
                full = os.path.join(folder, name)
                found[os.path.relpath(full, root).replace(os.sep, "/")] = full
        return found

    def changes(self):
        if self._changes is None:
            before, after_ = self._files(self.baseline), self._files(self.target)
            out = []
            for path in sorted(set(before) | set(after_)):
                if path not in before:
                    out.append(FileChange(ADDED, path))
                elif path not in after_:
                    out.append(FileChange(DELETED, path))
                elif _read(before[path]) != _read(after_[path]):
                    out.append(FileChange(MODIFIED, path))
            self._changes = out
        return self._changes

    def data(self, path, side):
        full = os.path.join(self.baseline if side == BEFORE else self.target, *path.split("/"))
        return _read(full) if os.path.isfile(full) else None

    def hunks(self, path):
        before_, after = self.lines(path, BEFORE), self.lines(path, AFTER)
        if after is None:
            return []
        return whole_file(after) if before_ is None else hunks_between(before_, after)

    def unchanged_pairs(self, path):
        before_, after = self.lines(path, BEFORE), self.lines(path, AFTER)
        return pairs_by_content(before_ or [], after or [])

    def accepted_eol(self):
        return None, None

    def accepted_bom(self):
        """У пары каталогов — как принято в формате: эталон приходит вложением, и
        обработка выгрузки конфигуратора несёт BOM в каждом файле."""
        return self.layout.bom

    def roles_granting(self, objects):
        roles = os.path.join(self.target, layout.RIGHTS_FOLDER)
        if not self.layout.is_configuration(self.target):
            return None                     # обработка вне конфигурации: ролей нет
        mentions = {}
        if os.path.isdir(roles):
            for role in sorted(os.listdir(roles)):
                file = self.layout.rights_path(role)
                data = self.data(file, AFTER)
                if data is None:
                    continue
                for obj in objects:
                    if f"<name>{self.layout.rights_name(*obj)}</name>".encode() in data:
                        mentions.setdefault(obj, []).append(file)
        return self._granting(objects, mentions, lambda file: self.data(file, AFTER))

    def target_eol(self, path):
        """Как у эталона; эталон с разными переводами или нового файла нет — свои
        переводы файла: приводить к одному виду значило бы тронуть строки,
        которых задача не касалась."""
        reference_node = self.data(path, BEFORE)
        if reference_node is None:
            return None
        crlf = reference_node.count(b"\r\n")
        lf = reference_node.count(b"\n") - crlf
        if crlf and lf:
            return None
        return "CRLF" if crlf else "LF" if lf else None

    def target_bom(self, path):
        """Как у эталона; нового файла в эталоне нет — как принято в формате."""
        reference_node = self.data(path, BEFORE)
        exists = bom_word(reference_node) if reference_node is not None else None
        return self.layout.bom if exists is None else exists

    def prepare_rewrites(self, items):
        plan = Plan()
        for path, data in items:
            plan.add(os.path.join(self.target, *path.split("/")), data, False)
        return plan


def _read(path):
    with open(path, "rb") as file:
        return file.read()
