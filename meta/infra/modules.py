"""Модули кода в исходниках: где лежит файл, как он записан, новый ли он.

Исходники — выгрузка конфигуратора или проект EDT: раскладка модулей
у них разная (`acl.modules`), какая именно — решает корень (`layout.layout_of`).

Формат файла модуля сохраняется таким, каким был: BOM, переводы строк (CRLF у
конфигуратора, LF у части выгрузок), наличие последнего перевода строки.
Навязать свои значило бы переписать файл целиком — diff во весь модуль вместо
одной вставки.

«Новый ли модуль» — по истории выгрузки в git: модуль, которого в индексе ещё
нет, создан текущей задачей, и разметка внутри него не нужна.
Сомнение толкуется в пользу меток: лишний маркер не навредит, а его
отсутствие — потеря следа навсегда. Поэтому «новый» — только прямой ответ git
«файл не отслеживается»; выгрузка вне git и git, которого нет, — «существует»;
git, который не ответил или ответил непонятно, — отказ, а не догадка.
"""

import os
import re

from ..acl import modules as vocabulary
from ..application.ports import Modules
from ..domain.model import Refuse
from . import git, layout
from .repository import Plan


class DumpModules(Modules):
    def __init__(self, root):
        self.root = root
        self._format = {}          # путь -> (bom, eol, final_eol), снятый при чтении
        self.files = (vocabulary.EDT if layout.layout_of(root).edt else vocabulary.DESIGNER)

    # --- где лежит ---

    def relative(self, ref):
        """Путь модуля относительно корня выгрузки, через «/»."""
        if ref.path is not None:
            return ref.path.replace("\\", "/")
        return "/".join(self.files.module_file(ref.address))

    def address(self, ref):
        if ref.address is not None:
            return ref.address
        return self.files.address_of_file(self.relative(ref).split("/"))

    def full_path(self, ref):
        return os.path.join(self.root, *self.relative(ref).split("/"))

    def _missing(self, ref):
        """Модуля нет — отказ, и по адресу сказано, какие модули у объекта есть."""
        if ref.address is None:
            return Refuse(f"модуль не найден: {ref.path}")
        folder = vocabulary.object_folder(ref.address)
        есть = self._existing(ref.address, folder) if folder else []
        if not есть:
            return Refuse(f"модуля «{ref.address}» в выгрузке нет")
        return Refuse(f"модуля «{ref.address}» в выгрузке нет; у объекта есть: "
                      + ", ".join(есть))

    def _existing(self, address, folder):
        base = os.path.join(self.root, *folder)
        есть = []
        ext = os.path.join(base, *self.files.own)
        if os.path.isdir(ext):
            есть += [f"{address.kind}.{address.name}.{vocabulary.OWN_BY_FILE[имя]}"
                     for имя in sorted(os.listdir(ext)) if имя in vocabulary.OWN_BY_FILE]
        for папка, метка in (("Forms", "Форма"), ("Commands", "Команда")):
            where = os.path.join(base, папка)
            if os.path.isdir(where):
                есть += [f"{address.kind}.{address.name}.{метка}.{имя}"
                         for имя in sorted(os.listdir(where))
                         if os.path.isdir(os.path.join(where, имя))]
        return есть

    # --- порт ---

    def read(self, ref):
        path = self.full_path(ref)
        if not os.path.isfile(path):
            raise self._missing(ref)
        raw = open(path, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
        final_eol = text.endswith("\n")
        if final_eol:
            text = text[:-1]
            if text.endswith("\r"):
                text = text[:-1]
        eol = "\r\n" if text.count("\r\n") >= text.count("\n") - text.count("\r\n") else "\n"
        self._format[path] = (bom, eol, final_eol)
        return re.split(r"\r\n|\n|\r", text) if text else []

    def file_format(self, ref):
        known = self._format.get(self.full_path(ref))
        if known is None:
            return None
        bom, eol, _ = known
        return ("CRLF" if eol == "\r\n" else "LF") + (", BOM" if bom else ", без BOM")

    def _git(self, *args, why):
        """git над выгрузкой; git нет — None, не ответил в срок — отказ (`infra.git`)."""
        return git.run(self.root, *args, why=why)

    def base(self, ref):
        done = self._git("show", f"HEAD:./{self.relative(ref)}",
                         why=f"не могу прочитать базовую версию модуля «{self.relative(ref)}»")
        if done is None or done.returncode != 0:
            return None
        text = done.stdout.decode("utf-8-sig")
        if text.endswith("\n"):
            text = text[:-1].removesuffix("\r")
        return re.split(r"\r\n|\n|\r", text) if text else []

    def is_new(self, ref):
        # Сбой git не читается как «модуль новый»: иначе снятый руками
        # зависший git дал бы «создан задачей» типовому модулю формы.
        done = self._git("ls-files", "--error-unmatch", self.relative(ref),
                         why=f"не могу определить, создан ли модуль «{self.relative(ref)}» задачей")
        if done is None:
            return False
        if done.returncode in (0, 1):
            return done.returncode == 1         # 1 — «файл не отслеживается»
        said = done.stderr.decode("utf-8", "replace").strip()
        if "not a git repository" in said:
            return False
        raise Refuse(f"git не смог сказать, создан ли модуль «{self.relative(ref)}» "
                     f"задачей: {said or f'код {done.returncode}'}")

    def prepare(self, changes):
        plan = Plan()
        for ref, lines in changes:
            path = self.full_path(ref)
            bom, eol, final_eol = self._format[path]
            text = eol.join(lines)
            if final_eol:
                text += eol
            body = text.encode("utf-8")
            plan.add(path, b"\xef\xbb\xbf" + body if bom else body, False)
        return plan
