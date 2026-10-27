"""Модули кода в исходниках: где лежит файл, как он записан, новый ли он.

Исходники — выгрузка конфигуратора или проект EDT: раскладка модулей
у них разная (`acl.modules`), какая именно — решает корень (`layout.layout_of`).

Формат файла модуля сохраняется таким, каким был: BOM, переводы строк (CRLF у
конфигуратора, LF у части выгрузок), наличие последнего перевода строки.
Навязать свои значило бы переписать файл целиком — diff во весь модуль вместо
одной вставки.

«Новый ли модуль» — по истории выгрузки в git: модуль, которого нет в ревизии
до задачи (база сверки задания, по умолчанию `HEAD`), создан текущей задачей, и
разметка внутри него не нужна. Индекс тут не ответ: модуль задачи, уже
добавленный в него или закоммиченный в ветке задачи, остаётся её модулем.
Репозиторий без единого коммита базы не имеет — тогда новый тот, которого нет
в индексе. Файл, который git игнорирует, — вне учёта версий: новым он не
считается (копия внешней обработки в игнорируемом каталоге задачи — чужой код).
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
from ..domain.modules import MODULES_OF_KIND
from . import form_bindings, git, layout
from .paths import check_relative, within
from .repository import Plan


class DumpModules(Modules):
    def __init__(self, root):
        self.root = root
        self._format = {}          # путь -> (bom, eol, final_eol), снятый при чтении
        self._converted = {}       # путь -> свои переводы строк, если git требует других
        self._created = set()      # пути модулей, которых не было: их создаёт правка
        self.files = (vocabulary.EDT if layout.layout_of(root).edt else vocabulary.DESIGNER)

    # --- где лежит ---

    def relative(self, ref):
        """Путь модуля относительно корня выгрузки, через «/»."""
        if ref.path is not None:
            return check_relative(ref.path).replace("\\", "/")
        return "/".join(self.files.module_file(ref.address))

    def address(self, ref):
        if ref.address is not None:
            return ref.address
        return self.files.address_of_file(self.relative(ref).split("/"))

    def full_path(self, ref):
        return within(self.root, os.path.join(self.root, *self.relative(ref).split("/")))

    def _missing(self, ref):
        """Модуля нет — отказ, и по адресу сказано, какие модули у объекта есть."""
        if ref.address is None:
            return Refuse(f"модуль не найден: {ref.path}")
        folder = vocabulary.object_folder(ref.address)
        exists = self._existing(ref.address, folder) if folder else []
        if not exists:
            return Refuse(f"модуля «{ref.address}» в выгрузке нет")
        return Refuse(f"модуля «{ref.address}» в выгрузке нет; у объекта есть: "
                      + ", ".join(exists))

    def _existing(self, address, folder):
        base = os.path.join(self.root, *folder)
        exists = []
        ext = os.path.join(base, *self.files.own)
        if os.path.isdir(ext):
            exists += [f"{address.kind}.{address.name}.{vocabulary.OWN_BY_FILE[name]}"
                     for name in sorted(os.listdir(ext)) if name in vocabulary.OWN_BY_FILE]
        for папка, marker in (("Forms", "Форма"), ("Commands", "Команда")):
            where = os.path.join(base, папка)
            if os.path.isdir(where):
                exists += [f"{address.kind}.{address.name}.{marker}.{name}"
                         for name in sorted(os.listdir(where))
                         if os.path.isdir(os.path.join(where, name))]
        return exists

    # --- порт ---

    def _creatable(self, ref):
        """Модуля нет, но объект есть и такой модуль у его вида бывает: правка
        его создаёт. Новый модуль объекта — обычное дело (менеджер регистра,
        которого не было), и писать его мимо инструмента значит проверять
        формат файла и метки руками."""
        address = ref.address
        if address is None or address.sub is not None or address.kind not in MODULES_OF_KIND.get(address.module, ()):
            return False
        папка = vocabulary.object_folder(address)
        if not папка:
            return False
        каталог = os.path.join(self.root, *папка)
        return (os.path.isfile(os.path.join(каталог, address.name + ".mdo"))      # проект EDT
                or os.path.isfile(каталог + ".xml"))                          # выгрузка

    def _new_format(self, ref):
        """(BOM, перевод строки) нового модуля: BOM — как принято в формате
        (выгрузка — с BOM, проект EDT — без); переводы строк — как кладёт git,
        а где git их не задаёт — как у площадки."""
        edt = layout.layout_of(self.root).edt
        от_git = git.checkout_eol(self.root, self.relative(ref))
        if от_git:
            return not edt, "\r\n" if от_git == "CRLF" else "\n"
        if edt:
            from .edt_dump import EdtDump
            return False, EdtDump(self.root).eol
        return True, "\r\n"

    def read(self, ref):
        path = self.full_path(ref)
        if not os.path.isfile(path):
            if not self._creatable(ref):
                raise self._missing(ref)
            bom, eol = self._new_format(ref)
            self._format[path] = (bom, eol, True)
            self._created.add(path)
            return []
        raw = open(path, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
        final_eol = text.endswith("\n")
        if final_eol:
            text = text[:-1]
            if text.endswith("\r"):
                text = text[:-1]
        eol = "\r\n" if text.count("\r\n") >= text.count("\n") - text.count("\r\n") else "\n"
        # переводы строк задаёт git (`core.autocrlf`, атрибуты) — те, которыми он
        # кладёт файл в рабочую копию: иные `git add` при `core.safecrlf=true`
        # не примет, а в индексе они сводятся, и diff во весь файл не возникает
        от_git = git.checkout_eol(self.root, self.relative(ref))
        if от_git:
            is_own = "CRLF" if eol == "\r\n" else "LF"
            eol = "\r\n" if от_git == "CRLF" else "\n"
            if "\n" in text and is_own != от_git:
                self._converted[path] = is_own
        self._format[path] = (bom, eol, final_eol)
        return re.split(r"\r\n|\n|\r", text) if text else []

    def form_bindings(self, ref):
        """(привязанные процедуры, элементы, события формы) по описанию формы
        рядом с модулем; не модуль формы или описания нет — None."""
        description = form_bindings.form_file(self.full_path(ref))
        if description is None or not os.path.isfile(description):
            return None
        with open(description, encoding="utf-8-sig") as файл:
            привязаны, элементы = form_bindings.bindings(файл.read())
        return привязаны, элементы, form_bindings.FORM_EVENT_NAMES

    def file_format(self, ref):
        known = self._format.get(self.full_path(ref))
        if known is None:
            return None
        bom, eol, _ = known
        word = "CRLF" if eol == "\r\n" else "LF"
        if self.full_path(ref) in self._created:
            return f"{word}{', BOM' if bom else ', без BOM'} — новый: модуля не было, правка его создаёт"
        before = self._converted.get(self.full_path(ref))
        if before:
            return (f"{before}{', BOM' if bom else ', без BOM'} — станет {word}: так файл кладёт в рабочую "
                    "копию git (core.autocrlf), иначе git add при core.safecrlf=true откажет")
        return word + (", BOM" if bom else ", без BOM")

    def _git(self, *args, why):
        """git над выгрузкой; git нет — None, не ответил в срок — отказ (`infra.git`)."""
        return git.run(self.root, *args, why=why)

    def base(self, ref, rev=None):
        done = self._git("show", f"{rev or 'HEAD'}:./{self.relative(ref)}",
                         why=f"не могу прочитать базовую версию модуля «{self.relative(ref)}»")
        if done is None or done.returncode != 0:
            return None
        text = done.stdout.decode("utf-8-sig")
        if text.endswith("\n"):
            text = text[:-1].removesuffix("\r")
        return re.split(r"\r\n|\n|\r", text) if text else []

    def is_new(self, ref, rev=None):
        if self.full_path(ref) in self._created:
            return True                 # модуля не было на диске — его создаёт задача
        # Сбой git не читается как «модуль новый»: иначе снятый руками
        # зависший git дал бы «создан задачей» типовому модулю формы.
        if self._resolves(rev or "HEAD"):
            done = self._git("cat-file", "-e", f"{rev or 'HEAD'}:./{self.relative(ref)}",
                             why=f"не могу определить, создан ли модуль «{self.relative(ref)}» задачей")
            if done is None:
                return False
            if done.returncode == 0:
                return False
            if done.returncode in (1, 128):
                # В ревизии до задачи файла нет. Но игнорируемый git файл —
                # вне учёта версий вовсе (копия внешней обработки в каталоге
                # задачи), и «новым» он не доказан: сомнение — в пользу меток.
                return not self._ignored(ref)
            raise Refuse(f"git не смог сказать, создан ли модуль «{self.relative(ref)}» "
                         f"задачей: {git.said(done)}")
        if rev:
            raise Refuse(f"база сверки «{rev}» в репозитории не найдена — назовите коммит "
                         "или ветку, от которой начата задача")
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

    def _ignored(self, ref):
        """git игнорирует файл (`.gitignore`): учёта версий у него нет."""
        done = self._git("check-ignore", "-q", "--", self.relative(ref),
                         why=f"не могу проверить, игнорирует ли git «{self.relative(ref)}»")
        return done is not None and done.returncode == 0

    def _resolves(self, rev):
        """Ревизия есть в репозитории (выгрузка вне git — нет)."""
        done = self._git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}",
                         why=f"не могу найти ревизию «{rev}»")
        return done is not None and done.returncode == 0

    def prepare(self, changes):
        plan = Plan()
        for ref, lines in changes:
            path = self.full_path(ref)
            bom, eol, final_eol = self._format[path]
            text = eol.join(lines)
            if final_eol:
                text += eol
            body = text.encode("utf-8")
            plan.add(path, b"\xef\xbb\xbf" + body if bom else body, path in self._created)
        return plan
