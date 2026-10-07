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

from ..acl import mapping
from ..acl import modules as module_files
from ..application.ports import ChangeSource
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
from ..domain.plan import Состав
from . import git, layout
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
    return [строка[:-1] if строка.endswith("\r") else строка for строка in text.split("\n")]


def read_composition(data):
    """Байты карточки -> `domain.plan.Состав`; карточка не читается — состав с
    причиной: о сломанной карточке говорится словами, а не обрывом проверки."""
    tree = LxmlCardTree()
    try:
        документ = tree.parse(data.decode("utf-8-sig", "replace").replace("\r\n", "\n"))
    except Refuse as отказ:
        return Состав(сломан=str(отказ))
    return mapping.composition_from_node(tree.to_node(документ))


def eol_word(data):
    """«CRLF» или «LF» — каких переводов в файле больше; None — переводов нет."""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if not crlf and not lf:
        return None
    return "CRLF" if crlf > lf else "LF"


class _Layout(ChangeSource):
    """Раскладка выгрузки конфигуратора — общая для обоих источников."""

    def is_module(self, path):
        return layout.is_module(path)

    def is_text(self, path):
        return layout.is_text(path)

    def is_service(self, path):
        return layout.is_service(path)

    def object_of(self, path):
        return layout.object_of(path)

    def owner_of(self, path):
        return layout.owner_of(path)

    def card_path(self, kind, name):
        return layout.card_path(kind, name)

    def composition(self, kind, name, side):
        путь = layout.card_path(kind, name)
        данные = self.data(путь, side) if путь else None
        return None if данные is None else read_composition(данные)

    def module_of(self, path):
        адрес = module_files.address_of_file(path.split("/"))
        if адрес is None or адрес.sub is not None or адрес.module in (FORM_MARK, COMMAND_MARK) \
                or адрес.kind == CONFIGURATION:
            return None
        return адрес.kind, адрес.name, адрес.module

    def module_path(self, kind, name, module):
        if kind not in module_files.CONTAINERS or module not in module_files.OWN_FILES:
            return None
        return "/".join(module_files.module_file(ModuleAddress(kind, name, module)))

    def lines(self, path, side):
        return split_lines(self.data(path, side))

    def _granting(self, objects, mentions, read):
        """{объект: [(роль, право)]} по упоминаниям: `mentions` — {объект: [файлы
        прав]}, `read(файл)` — его байты. Упоминание ещё не право: блок объекта
        может перечислять права со значением false."""
        tree, выдано, итог = LxmlCardTree(), {}, {}
        for объект in objects:
            имя = layout.rights_name(*объект)
            for файл in sorted(set(mentions.get(объект, ()))):
                if файл not in выдано:
                    текст = (read(файл) or b"").decode("utf-8-sig", "replace").replace("\r\n", "\n")
                    выдано[файл] = {name for name, _ in tree.granted(tree.parse(текст))}
                роль = layout.RIGHTS_FILE.match(файл).group(1)
                итог.setdefault(объект, []).append((роль, имя in выдано[файл]))
        return итог


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
        внутри = self._git("rev-parse", "--is-inside-work-tree", why="не могу узнать, под git ли выгрузка")
        if внутри is None:
            raise Refuse("git не найден — для сравнения с базой он нужен; без git сравнивайте парой "
                         "каталогов «эталон — копия»")
        if внутри.returncode != 0:
            raise Refuse(f"«{self.root}» не под git: {git.said(внутри)}")
        for ревизия in filter(None, (self.base, self.rev)):
            есть = self._git("rev-parse", "--verify", "--quiet", f"{ревизия}^{{commit}}",
                             why=f"не могу проверить ревизию «{ревизия}»")
            if есть.returncode != 0:
                raise Refuse(f"ревизии «{ревизия}» в репозитории нет")

    def _git(self, *args, why):
        return git.run(self.root, *args, why=why)

    def _ok(self, done, why):
        if done is None or done.returncode != 0:
            raise Refuse(f"git: {why}: {git.said(done) if done is not None else 'git не найден'}")
        return done.stdout

    def describe(self):
        if self.rev:
            return f"ревизия {self.rev} против {self.base}"
        return f"рабочая копия против {self.base} (с новыми файлами)"

    def changes(self):
        if "changes" in self._cache:
            return self._cache["changes"]
        ревизии = [self.base] + ([self.rev] if self.rev else [])
        вывод = self._ok(self._git("diff", "--relative", "--no-renames", "--name-status", *ревизии,
                                   why="не могу получить состав правок"), "состав правок")
        files = {}
        for строка in вывод.decode("utf-8", "replace").splitlines():
            if not строка.strip():
                continue
            статус, _, путь = строка.partition("\t")
            files[git.unquote(путь)] = {"A": ADDED, "D": DELETED}.get(статус[:1], MODIFIED)
        неотслеживаемые = self._untracked() if not self.rev else set()
        for путь in неотслеживаемые:
            files[путь] = ADDED
        self._cache["неотслеживаемые"] = неотслеживаемые
        self._cache["changes"] = [FileChange(статус, путь) for путь, статус in sorted(files.items())]
        return self._cache["changes"]

    def _untracked(self):
        """Новые файлы, которых git ещё не знает, — от корня выгрузки.

        `git status`, а не `ls-files --others`: на выгрузке в сотню тысяч
        файлов он втрое быстрее (1,6 с против 5,3) при том же составе.
        `--no-optional-locks` — чтение не обновляет индекс. Пути у него от
        корня репозитория: выгрузка, лежащая в репозитории глубже, отрезает
        свою приставку.
        """
        приставка = self._ok(self._git("rev-parse", "--show-prefix", why="не могу узнать место выгрузки"),
                             "место выгрузки").decode("utf-8", "replace").strip()
        вывод = self._ok(self._git("--no-optional-locks", "status", "--porcelain=v1", "-z",
                                   "--untracked-files=all", why="не могу получить новые файлы"), "новые файлы")
        новые = set()
        for запись in вывод.decode("utf-8", "replace").split("\0"):
            if запись.startswith("?? ") and запись[3:].startswith(приставка):
                новые.add(запись[3 + len(приставка):])
        return новые

    def _blob(self, ревизия, path):
        ключ = ("blob", ревизия, path)
        if ключ not in self._cache:
            done = self._git("show", f"{ревизия}:./{path}", why=f"не могу прочитать «{path}» в {ревизия}")
            self._cache[ключ] = done.stdout if done is not None and done.returncode == 0 else None
        return self._cache[ключ]

    def data(self, path, side):
        if side == BEFORE:
            return self._blob(self.base, path)
        if self.rev:
            return self._blob(self.rev, path)
        полный = os.path.join(self.root, *path.split("/"))
        if not os.path.isfile(полный):
            return None
        with open(полный, "rb") as файл:
            return файл.read()

    def hunks(self, path):
        ключ = ("hunks", path)
        if ключ in self._cache:
            return self._cache[ключ]
        self.changes()
        if path in self._cache["неотслеживаемые"]:
            # новых файлов git diff не видит вовсе: добавлена каждая строка
            found = whole_file(self.lines(path, AFTER) or [])
        else:
            ревизии = [self.base] + ([self.rev] if self.rev else [])
            вывод = self._ok(self._git("diff", "--relative", "--no-renames", "--no-color", "--no-ext-diff",
                                       "-U0", *ревизии, "--", path,
                                       why=f"не могу получить различия «{path}»"), f"различия «{path}»")
            found = []
            for строка in вывод.splitlines():
                m = HUNK.match(строка)
                if m:
                    found.append(Hunk(int(m.group(1)), int(m.group(2) or 1),
                                      int(m.group(3)), int(m.group(4) or 1)))
        self._cache[ключ] = found
        return found

    def unchanged_pairs(self, path):
        return pairs_by_position(self.hunks(path))

    def accepted_eol(self):
        флаг = self._git("config", "core.autocrlf", why="не могу прочитать настройку переводов строк")
        if флаг is not None and флаг.stdout.decode("utf-8", "replace").strip().lower() in ("true", "input"):
            return None, "переводы строк не сверяются: git нормализует их сам (core.autocrlf)"
        образцы = self._git("ls-files", "--", "*.bsl", "*.xml", why="не могу получить образцы файлов")
        crlf = lf = 0
        if образцы is not None and образцы.returncode == 0:
            for путь in образцы.stdout.decode("utf-8", "replace").splitlines()[:EOL_SAMPLE]:
                полный = os.path.join(self.root, *git.unquote(путь).split("/"))
                if not os.path.isfile(полный):
                    continue
                with open(полный, "rb") as файл:
                    слово = eol_word(файл.read())
                crlf += слово == "CRLF"
                lf += слово == "LF"
        if not crlf and not lf:
            return None, "переводы строк не сверяются: в репозитории нет модулей и карточек, с которыми сверить"
        return ("CRLF" if crlf >= lf else "LF"), None

    def roles_granting(self, objects):
        if not objects:
            return {}
        имена = {layout.rights_name(*объект): объект for объект in objects}
        аргументы = ["grep", "-F", "-o"]
        for имя in имена:
            аргументы += ["-e", f"<name>{имя}</name>"]
        if self.rev:
            аргументы += [self.rev, "--", layout.RIGHTS_FOLDER]
        else:
            аргументы = [аргументы[0], "--untracked"] + аргументы[1:] + ["--", layout.RIGHTS_FOLDER]
        done = self._git(*аргументы, why="не могу найти объекты в правах ролей")
        if done is None or done.returncode not in (0, 1):     # 1 — «ничего не найдено»
            raise Refuse(f"git: поиск в правах ролей: {git.said(done) if done else 'git не найден'}")
        упоминания = {}
        for строка in done.stdout.decode("utf-8", "replace").splitlines():
            if self.rev and строка.startswith(f"{self.rev}:"):
                строка = строка[len(self.rev) + 1:]
            файл, _, найдено = строка.partition(":<name>")
            имя = найдено.removesuffix("</name>")
            if имя in имена and layout.RIGHTS_FILE.match(файл):
                упоминания.setdefault(имена[имя], []).append(файл)
        return self._granting(objects, упоминания, lambda файл: self.data(файл, AFTER))

    def target_eol(self, path):
        if "eol" not in self._cache:
            self._cache["eol"] = self.accepted_eol()[0]
        return self._cache["eol"]

    def prepare_rewrites(self, items):
        if self.rev:
            raise Refuse(f"ревизию {self.rev} не переписывают — нормализуется рабочая копия")
        plan = Plan()
        for путь, данные in items:
            plan.add(os.path.join(self.root, *путь.split("/")), данные, False)
        return plan


class DirectoryChanges(_Layout):
    """Правки как пара каталогов: эталон («до») против копии («после»)."""

    mode = ChangeSource.PAIR

    def __init__(self, baseline, target):
        self.baseline = os.path.abspath(baseline)
        self.target = os.path.abspath(target)
        for каталог, что in ((self.baseline, "эталона"), (self.target, "копии")):
            if not os.path.isdir(каталог):
                raise Refuse(f"каталога {что} «{каталог}» не существует")
        self._changes = None

    def describe(self):
        return f"копия {self.target} против эталона {self.baseline}"

    @staticmethod
    def _files(root):
        found = {}
        for папка, _, имена in os.walk(root):
            for имя in имена:
                полный = os.path.join(папка, имя)
                found[os.path.relpath(полный, root).replace(os.sep, "/")] = полный
        return found

    def changes(self):
        if self._changes is None:
            было, стало = self._files(self.baseline), self._files(self.target)
            out = []
            for путь in sorted(set(было) | set(стало)):
                if путь not in было:
                    out.append(FileChange(ADDED, путь))
                elif путь not in стало:
                    out.append(FileChange(DELETED, путь))
                elif _read(было[путь]) != _read(стало[путь]):
                    out.append(FileChange(MODIFIED, путь))
            self._changes = out
        return self._changes

    def data(self, path, side):
        полный = os.path.join(self.baseline if side == BEFORE else self.target, *path.split("/"))
        return _read(полный) if os.path.isfile(полный) else None

    def hunks(self, path):
        до, после = self.lines(path, BEFORE), self.lines(path, AFTER)
        if после is None:
            return []
        return whole_file(после) if до is None else hunks_between(до, после)

    def unchanged_pairs(self, path):
        до, после = self.lines(path, BEFORE), self.lines(path, AFTER)
        return pairs_by_content(до or [], после or [])

    def accepted_eol(self):
        return None, None

    def roles_granting(self, objects):
        роли = os.path.join(self.target, layout.RIGHTS_FOLDER)
        if not os.path.isfile(os.path.join(self.target, "Configuration.xml")):
            return None                     # обработка вне конфигурации: ролей нет
        упоминания = {}
        if os.path.isdir(роли):
            for роль in sorted(os.listdir(роли)):
                файл = f"{layout.RIGHTS_FOLDER}/{роль}/Ext/Rights.xml"
                данные = self.data(файл, AFTER)
                if данные is None:
                    continue
                for объект in objects:
                    if f"<name>{layout.rights_name(*объект)}</name>".encode() in данные:
                        упоминания.setdefault(объект, []).append(файл)
        return self._granting(objects, упоминания, lambda файл: self.data(файл, AFTER))

    def target_eol(self, path):
        """Как у эталона; эталон с разными переводами или нового файла нет — свои
        переводы файла: приводить к одному виду значило бы тронуть строки,
        которых задача не касалась."""
        эталон = self.data(path, BEFORE)
        if эталон is None:
            return None
        crlf = эталон.count(b"\r\n")
        lf = эталон.count(b"\n") - crlf
        if crlf and lf:
            return None
        return "CRLF" if crlf else "LF" if lf else None

    def prepare_rewrites(self, items):
        plan = Plan()
        for путь, данные in items:
            plan.add(os.path.join(self.target, *путь.split("/")), данные, False)
        return plan


def _read(path):
    with open(path, "rb") as файл:
        return файл.read()
