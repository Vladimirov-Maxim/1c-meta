"""Сценарий: план по факту задачи — тот же формат, что принимает сверка."""

from dataclasses import dataclass

from ...domain import plan as rules
from ..dto import PlanEmitResult
from ..plan_facts import object_fact
from ..ports import ChangeSource


@dataclass
class PlanEmitUseCase:
    source: ChangeSource

    def execute(self):
        src = self.source
        order, modules = [], {}
        for c in src.changes():
            obj = src.owner_of(c.path)
            if obj is None:
                continue
            if obj not in modules:
                order.append(obj)
                modules[obj] = {}
            module = src.module_of(c.path)
            if module is not None and module[:2] == obj:
                modules[obj][module[2]] = c.path
        facts = [object_fact(src, kind, name, modules[(kind, name)]) for kind, name in order]
        return PlanEmitResult(src.describe(), rules.plan_from_fact(facts))
