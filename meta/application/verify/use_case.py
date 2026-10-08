"""Сценарий: проверить правки задачи против базы.

Находки — правилами домена (`domain.verification`), правки — от источника
(`ChangeSource`): git или пара каталогов. Сценарий файлов не знает: что в
выгрузке модуль, карточка или служебный файл, где лежат роли, — говорит
источник.

Правило, которое не проверялось, называется в «пропущено» с причиной:
«чисто» при пропусках не выдаётся — зелёная проверка, смотревшая мимо, хуже
отсутствующей.
"""

from dataclasses import dataclass

from ...domain import verification as rules
from ...domain.changes import ADDED, AFTER, BEFORE, DELETED, MODIFIED, changed_lines
from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ..dto import VerifyResult
from ..ports import ChangeSource


@dataclass
class VerifyUseCase:
    source: ChangeSource
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, task=None, only=None):
        """`task` — ИД задачи: без него правило о правке внутри чужой вставки
        не проверяется. `only` — коды правил, находки которых нужны; пусто — все."""
        src = self.source
        files = src.changes()
        findings, skipped, notes = [], [], []

        новые_объекты = []
        for c in files:
            объект = src.object_of(c.path) if c.status == ADDED else None
            if объект is not None:
                новые_объекты.append((c.path, *объект))
        if self.соглашения.приставка:
            findings += rules.prefix_findings(новые_объекты, self.соглашения)
        else:
            skipped.append((rules.ПРИСТАВКА, "приставка команды не задана профилем"))

        for c in files:
            if c.status == DELETED or not src.is_module(c.path):
                continue
            после = src.lines(c.path, AFTER) or []
            до = src.lines(c.path, BEFORE) if c.status == MODIFIED else None
            hunks = src.hunks(c.path)
            if c.status == MODIFIED and до is not None:
                # модуль, созданный задачей, меток не несёт: проверяется только изменённый
                findings += rules.marker_findings(c.path, до, после, hunks, task)
            добавлено, _ = changed_lines(hunks, до or [], после)
            findings += rules.structure_findings(c.path, после, добавлено)
        if not task:
            skipped.append((rules.В_ЧУЖОЙ_ВСТАВКЕ, "не задан ИД задачи"))

        findings += rules.service_findings([c.path for c in files if src.is_service(c.path)])
        notes += src.format_notes()

        принятые, почему = src.accepted_eol()
        if почему:
            notes.append(почему)
        bom = src.accepted_bom()
        for c in files:
            if c.status == DELETED or not src.is_text(c.path):
                continue
            данные = src.data(c.path, AFTER)
            if данные is not None:
                findings += rules.format_findings(c.path, данные, принятые, bom)

        for c in files:
            if c.status != MODIFIED or not src.is_text(c.path) or src.is_service(c.path):
                continue
            if src.mode == ChangeSource.PAIR:
                до, после = src.data(c.path, BEFORE), src.data(c.path, AFTER)
                if до is not None and после is not None:
                    findings += rules.trailing_findings(c.path, до, после)
            else:
                findings += rules.cosmetic_findings(c.path, src.lines(c.path, BEFORE) or [],
                                                    src.lines(c.path, AFTER) or [], src.hunks(c.path))

        с_правами = [(вид, имя) for _, вид, имя in новые_объекты if вид in rules.KINDS_WITH_RIGHTS]
        if с_правами:
            роли = src.roles_granting(с_правами)
            if роли is None:
                notes.append("права на новые объекты не проверялись: ролей в этом источнике нет")
            else:
                findings += rules.rights_findings(с_правами, роли, self.соглашения)

        findings += self._составы(files, skipped, notes)

        findings = self.соглашения.применить(findings)
        if only:
            findings = [f for f in findings if f.code in only]
        return VerifyResult(src.describe(), files, _ordered(findings), skipped, notes)

    def _составы(self, files, skipped, notes):
        """Составные типы членов, появившихся в задаче, — по карточкам задачи."""
        src = self.source
        карточки = [(c, src.object_of(c.path)) for c in files if c.status != DELETED]
        карточки = [(c, объект) for c, объект in карточки if объект is not None]
        if len(карточки) > ПРЕДЕЛ_КАРТОЧЕК:
            skipped.append((rules.СОСТАВ_ТИПОВ_УЖЕ, f"карточек в правках {len(карточки)}, больше "
                                                   f"{ПРЕДЕЛ_КАРТОЧЕК}: похоже на перезалив выгрузки"))
            return []
        члены = []
        for c, (вид, имя) in карточки:
            после = src.composition(вид, имя, AFTER)
            if после is None or после.сломан:
                if после is not None:
                    notes.append(f"карточка {c.path} не читается — составы типов в ней не сверялись: "
                                 f"{после.сломан}")
                continue
            до = src.composition(вид, имя, BEFORE) if c.status == MODIFIED else None
            for группа, состав in после.члены.items():
                было = {} if до is None or до.сломан else до.члены.get(группа, {})
                члены += [(c.path, f"{вид}.{имя}.{член}", типы) for член, типы in состав.items()
                          if член not in было]
        return rules.type_set_findings(члены)


#: Больше стольких карточек составы типов не сверяются: такой объём для правок
#: задачи ненормален, а чтение тысяч карточек заняло бы минуты.
ПРЕДЕЛ_КАРТОЧЕК = 300


def _ordered(findings):
    """По файлу и строке; одна и та же находка дважды не называется."""
    seen, out = set(), []
    for f in sorted(findings, key=lambda f: (f.path or "", f.line or 0, f.code)):
        ключ = (f.code, f.path, f.line, f.message)
        if ключ not in seen:
            seen.add(ключ)
            out.append(f)
    return out
