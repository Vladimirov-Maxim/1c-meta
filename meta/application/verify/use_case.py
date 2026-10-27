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
        only = _codes(only)
        paths = [_mask(pt) for pt in paths or () if _mask(pt)]
        src = self.source
        files = src.changes()
        if paths:
            files = [c for c in files if any(_under(c.path, pt) for pt in paths)]
            if not files:
                raise Refuse(f"ни один файл правок не подходит под paths: {', '.join(paths)} — пути от корня "
                             "исходников, каталог или маска («CommonModules/мой_*/Module.bsl»)")
        findings, skipped, notes = [], [], []

        new_objects = []
        for c in files:
            obj = src.object_of(c.path) if c.status == ADDED else None
            if obj is not None:
                new_objects.append((c.path, *obj))
        if self.conventions.prefix:
            findings += rules.prefix_findings(new_objects, self.conventions)
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
            added_count, _ = changed_lines(hunks, before_ or [], after)
            findings += rules.structure_findings(c.path, after, added_count, task)
            bindings = src.form_bindings(c.path)
            if bindings is not None:
                findings += rules.unbound_findings(c.path, before_ or [], after, bindings)
        if not task:
            skipped.append((rules.IN_FOREIGN_INSERTION, "не задан ИД задачи"))

        findings += rules.service_findings([c.path for c in files if src.is_service(c.path)])
        notes += src.format_notes()

        _, why = src.accepted_eol()
        if why:
            notes.append(why)
        bom = src.accepted_bom()
        for c in files:
            if c.status == DELETED or not src.is_text(c.path):
                continue
            data = src.data(c.path, AFTER)
            if data is not None:
                own, why_own = src.expected_eol(c.path)
                findings += rules.format_findings(c.path, data, own, bom, why_own)

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

        with_rights = [(kind, name) for _, kind, name in new_objects if kind in rules.KINDS_WITH_RIGHTS]
        if with_rights:
            roles = src.roles_granting(with_rights)
            if roles is None:
                notes.append("права на новые объекты не проверялись: ролей в этом источнике нет")
            else:
                findings += rules.rights_findings(with_rights, roles, self.conventions)

        findings += self._compositions(files, skipped, notes)

        findings = self.conventions.apply(findings)
        if only:
            findings = [f for f in findings if f.code in only]
            skipped = [(what, why) for what, why in skipped if what in only]
        return VerifyResult(src.describe(), files, _ordered(findings), skipped, notes,
                            only=only, paths=paths)

    def _compositions(self, files, skipped, notes):
        """Составные типы членов, появившихся в задаче, — по карточкам задачи."""
        src = self.source
        cards = [(c, src.object_of(c.path)) for c in files if c.status != DELETED]
        cards = [(c, obj) for c, obj in cards if obj is not None]
        if len(cards) > CARD_LIMIT:
            skipped.append((rules.TYPE_SET_NARROWER, f"карточек в правках {len(cards)}, больше "
                                                   f"{CARD_LIMIT}: похоже на перезалив выгрузки"))
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
                members += [(c.path, f"{kind}.{name}.{member}", types) for member, types in composition.items()
                          if member not in before]
        return rules.type_set_findings(members)


#: Больше стольких карточек составы типов не сверяются: такой объём для правок
#: задачи ненормален, а чтение тысяч карточек заняло бы минуты.
CARD_LIMIT = 300


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
ITEM_NUMBER = re.compile(r"^\[?\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?\]?$")


def _codes(only):
    """Коды правил фильтра; неизвестный — отказ с перечнем известных."""
    codes = [kk.strip() for kk in only or () if kk and kk.strip()]
    unknown = [kk for kk in codes if kk not in rules.RULES]
    if unknown:
        hint = (" — это номера пунктов регламента, а фильтр принимает коды правил"
                     if any(ITEM_NUMBER.match(kk) for kk in unknown) else "")
        raise Refuse(f"неизвестные коды правил в only: {', '.join(unknown)}{hint}; "
                     f"коды: {', '.join(rules.RULES)}")
    return codes


def _mask(path):
    return path.strip().replace("\\", "/").removeprefix("./").rstrip("/")


def _under(path, mask):
    """Файл правок подходит под отбор: тот же путь, лежит в каталоге или под маской."""
    return path == mask or path.startswith(mask + "/") or fnmatch.fnmatchcase(path, mask)
