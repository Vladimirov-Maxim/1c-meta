"""Сценарий: вернуть файлам задачи физический формат исходников.

Операция с просмотром, как у всех операций инструмента: без записи —
что будет исправлено, с записью — перезапись всех файлов разом или ни
одного. Повторный запуск после записи находит ноль работы: операция
идемпотентна (`domain.normalization`).
"""

from dataclasses import dataclass

from ...domain.changes import ADDED, AFTER, BEFORE, DELETED, changed_lines
from ...domain.normalization import normalized
from ..dto import NormalizeResult
from ..ports import ChangeSource


@dataclass
class NormalizeUseCase:
    source: ChangeSource

    def execute(self, apply_now=False):
        src = self.source
        files = [c for c in src.changes()
                 if c.status != DELETED and src.is_text(c.path) and not src.is_service(c.path)]
        _, почему = src.accepted_eol()
        notes = [почему] if почему else []
        # База старше HEAD: правки других задач, влитые между ней и HEAD, — не
        # наши. Пишутся только файлы, изменённые против HEAD, и строки — тоже
        # против него: иначе пустая строка, добавленная чужой задачей, получила
        # бы отступ, и чужой модуль попал бы в правки задачи.
        мерило = src.against_head() or src
        if мерило is not src:
            тронутые = {c.path: c.status for c in мерило.changes()}
            чужие = [c.path for c in files if c.path not in тронутые]
            files = [c for c in files if c.path in тронутые]
            files = [c.__class__(тронутые[c.path], c.path) for c in files]
            if чужие:
                notes.append(f"база сверки — не HEAD: файлов, изменённых только между базой и HEAD "
                             f"(правки других задач), — {len(чужие)}, они не трогаются; строки "
                             "сверяются с HEAD")
        fixes, rewrites = [], []
        for c in files:
            data = мерило.data(c.path, AFTER)
            if data is None:
                continue
            old = мерило.data(c.path, BEFORE) if c.status != ADDED else None
            added = None
            if old is not None:
                added, _ = changed_lines(мерило.hunks(c.path), мерило.lines(c.path, BEFORE) or [],
                                         мерило.lines(c.path, AFTER) or [])
            new, что = normalized(data, old, мерило.unchanged_pairs(c.path) if old is not None else (),
                                  added, src.target_eol(c.path), src.is_module(c.path),
                                  src.target_bom(c.path))
            if что:
                fixes.append((c.path, что))
                rewrites.append((c.path, new))
        plan = src.prepare_rewrites(rewrites) if rewrites else None
        written = plan.apply() if apply_now and plan is not None else []
        return NormalizeResult(src.describe(), files, fixes, plan, written, notes)
