"""Сценарий: проверить правки задачи против базы.

Находки — правилами домена (`domain.verification`), правки — от источника
(`ChangeSource`): git или пара каталогов. Сценарий файлов не знает: что в
выгрузке модуль, карточка или служебный файл, где лежат роли, — говорит
источник.

Правило, которое не проверялось, называется в «пропущено» с причиной:
«чисто» при пропусках не выдаётся — зелёная проверка, смотревшая мимо, хуже
отсутствующей.
"""

import fnmatch
import re
from dataclasses import dataclass

from ...domain import verification as rules
from ...domain.changes import ADDED, AFTER, BEFORE, DELETED, MODIFIED, changed_lines
from ...domain.conventions import NEUTRAL, Conventions
from ...domain.model import Refuse
from ..dto import VerifyResult
from ..ports import ChangeSource


@dataclass
class VerifyUseCase:
    source: ChangeSource
    conventions: Conventions = NEUTRAL

    def execute(self, task=None, only=None, paths=None):
        """`task` — ИД задачи: без него правило о правке внутри чужой вставки
        не проверяется. `only` — коды правил, находки которых нужны; пусто — все.
        `paths` — какие файлы правок проверять (путь, каталог или маска от корня
        исходников); пусто — все.

        Фильтр сужает ответ, а не прячет ошибку входа: неизвестный код правила и
        отбор, под который не подошёл ни один файл, — отказ. Иначе опечатка в
        фильтре давала бы «чисто» без единой проверки."""
        only = _коды(only)
        paths = [_маска(pt) for pt in paths or () if _маска(pt)]
        src = self.source
        files = src.changes()
        if paths:
            files = [c for c in files if any(_под(c.path, pt) for pt in paths)]
            if not files:
                raise Refuse(f"ни один файл правок не подходит под paths: {', '.join(paths)} — пути от корня "
                             "исходников, каталог или маска («CommonModules/мой_*/Module.bsl»)")
        findings, skipped, notes = [], [], []

        новые_объекты = []
        for c in files:
            obj = src.object_of(c.path) if c.status == ADDED else None
            if obj is not None:
                новые_объекты.append((c.path, *obj))
        if self.conventions.prefix:
            findings += rules.prefix_findings(новые_объекты, self.conventions)
        else:
            skipped.append((rules.PREFIX, "приставка команды не задана профилем"))

        for c in files:
            if c.status == DELETED or not src.is_module(c.path):
                continue
            after = src.lines(c.path, AFTER) or []
            before_ = src.lines(c.path, BEFORE) if c.status == MODIFIED else None
            hunks = src.hunks(c.path)
            if c.status == MODIFIED and before_ is not None:
                # модуль, созданный задачей, меток не несёт: проверяется только изменённый
                findings += rules.marker_findings(c.path, before_, after, hunks, task)
            добавлено, _ = changed_lines(hunks, before_ or [], after)
            findings += rules.structure_findings(c.path, after, добавлено, task)
            bindings = src.form_bindings(c.path)
            if bindings is not None:
                findings += rules.unbound_findings(c.path, before_ or [], after, bindings)
        if not task:
            skipped.append((rules.IN_FOREIGN_INSERTION, "не задан ИД задачи"))

        findings += rules.service_findings([c.path for c in files if src.is_service(c.path)])
        notes += src.format_notes()

        _, почему = src.accepted_eol()
        if почему:
            notes.append(почему)
        bom = src.accepted_bom()
        for c in files:
            if c.status == DELETED or not src.is_text(c.path):
                continue
            data = src.data(c.path, AFTER)
            if data is not None:
                own, почему_свои = src.expected_eol(c.path)
                findings += rules.format_findings(c.path, data, own, bom, почему_свои)

        for c in files:
            if c.status != MODIFIED or not src.is_text(c.path) or src.is_service(c.path):
                continue
            if src.mode == ChangeSource.PAIR:
                before_, after = src.data(c.path, BEFORE), src.data(c.path, AFTER)
                if before_ is not None and after is not None:
                    findings += rules.trailing_findings(c.path, before_, after)
            else:
                findings += rules.cosmetic_findings(c.path, src.lines(c.path, BEFORE) or [],
                                                    src.lines(c.path, AFTER) or [], src.hunks(c.path))

        с_правами = [(kind, name) for _, kind, name in новые_объекты if kind in rules.KINDS_WITH_RIGHTS]
        if с_правами:
            roles = src.roles_granting(с_правами)
            if roles is None:
                notes.append("права на новые объекты не проверялись: ролей в этом источнике нет")
            else:
                findings += rules.rights_findings(с_правами, roles, self.conventions)

        findings += self._составы(files, skipped, notes)

        findings = self.conventions.apply(findings)
        if only:
            findings = [f for f in findings if f.code in only]
            skipped = [(what, почему) for what, почему in skipped if what in only]
        return VerifyResult(src.describe(), files, _ordered(findings), skipped, notes,
                            only=only, paths=paths)

    def _составы(self, files, skipped, notes):
        """Составные типы членов, появившихся в задаче, — по карточкам задачи."""
        src = self.source
        cards = [(c, src.object_of(c.path)) for c in files if c.status != DELETED]
        cards = [(c, obj) for c, obj in cards if obj is not None]
        if len(cards) > ПРЕДЕЛ_КАРТОЧЕК:
            skipped.append((rules.TYPE_SET_NARROWER, f"карточек в правках {len(cards)}, больше "
                                                   f"{ПРЕДЕЛ_КАРТОЧЕК}: похоже на перезалив выгрузки"))
            return []
        members = []
        for c, (kind, name) in cards:
            after = src.composition(kind, name, AFTER)
            if after is None or after.broken:
                if after is not None:
                    notes.append(f"карточка {c.path} не читается — составы типов в ней не сверялись: "
                                 f"{after.broken}")
                continue
            before_ = src.composition(kind, name, BEFORE) if c.status == MODIFIED else None
            for group, composition in after.members.items():
                before = {} if before_ is None or before_.broken else before_.members.get(group, {})
                members += [(c.path, f"{kind}.{name}.{член}", types) for член, types in composition.items()
                          if член not in before]
        return rules.type_set_findings(members)


#: Больше стольких карточек составы типов не сверяются: такой объём для правок
#: задачи ненормален, а чтение тысяч карточек заняло бы минуты.
ПРЕДЕЛ_КАРТОЧЕК = 300


def _ordered(findings):
    """По файлу и строке; одна и та же находка дважды не называется."""
    seen, out = set(), []
    for f in sorted(findings, key=lambda f: (f.path or "", f.line or 0, f.code)):
        key = (f.code, f.path, f.line, f.message)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


#: Похоже на номер пункта регламента («2.5», «[9.1]», «2.1–2.6»), а не на код правила.
НОМЕР_ПУНКТА = re.compile(r"^\[?\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?\]?$")


def _коды(only):
    """Коды правил фильтра; неизвестный — отказ с перечнем известных."""
    коды = [kk.strip() for kk in only or () if kk and kk.strip()]
    неизвестные = [kk for kk in коды if kk not in rules.RULES]
    if неизвестные:
        подсказка = (" — это номера пунктов регламента, а фильтр принимает коды правил"
                     if any(НОМЕР_ПУНКТА.match(kk) for kk in неизвестные) else "")
        raise Refuse(f"неизвестные коды правил в only: {', '.join(неизвестные)}{подсказка}; "
                     f"коды: {', '.join(rules.RULES)}")
    return коды


def _маска(path):
    return path.strip().replace("\\", "/").removeprefix("./").rstrip("/")


def _под(path, маска):
    """Файл правок подходит под отбор: тот же путь, лежит в каталоге или под маской."""
    return path == маска or path.startswith(маска + "/") or fnmatch.fnmatchcase(path, маска)
