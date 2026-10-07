"""Сценарий: план по факту задачи — тот же формат, что принимает сверка."""

from dataclasses import dataclass

from ...domain import plan as rules
from ..dto import PlanEmitResult
from ..plan_facts import факт_объекта
from ..ports import ChangeSource


@dataclass
class PlanEmitUseCase:
    source: ChangeSource

    def execute(self):
        src = self.source
        порядок, модули = [], {}
        for c in src.changes():
            объект = src.owner_of(c.path)
            if объект is None:
                continue
            if объект not in модули:
                порядок.append(объект)
                модули[объект] = {}
            модуль = src.module_of(c.path)
            if модуль is not None and модуль[:2] == объект:
                модули[объект][модуль[2]] = c.path
        факты = [факт_объекта(src, вид, имя, модули[(вид, имя)]) for вид, имя in порядок]
        return PlanEmitResult(src.describe(), rules.план_по_факту(факты))
