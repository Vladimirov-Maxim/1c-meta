"""Сценарий: сверить план изменений с фактом задачи.

План приходит моделью домена (`domain.plan.План`), факт — от источника
правок; расхождения — правилами домена (`domain.plan.сверить`). План с
объектом, которого выгрузка не знает, — отказ, а не половина сверки.
"""

from dataclasses import dataclass

from ...domain import plan as rules
from ...domain.conventions import NEUTRAL, Conventions
from ...domain.model import Collected
from ..dto import PlanCheckResult
from ..plan_facts import object_fact, touched
from ..ports import ChangeSource


@dataclass
class PlanCheckUseCase:
    source: ChangeSource
    conventions: Conventions = NEUTRAL

    def execute(self, plan, declared_only=False):
        src = self.source
        unknown = Collected("в плане объекты, которых выгрузка не знает")
        facts = {}
        for obj in plan.objects:
            if src.card_path(obj.kind, obj.name) is None:
                unknown.add(f"«{obj.kind}.{obj.name}»: вид «{obj.kind}» выгрузке неизвестен")
                continue
            modules = {}
            for module in obj.modules:
                path = src.module_path(obj.kind, obj.name, module)
                if path is None:
                    unknown.add(f"«{obj.kind}.{obj.name}»: модуля «{module}» у вида не бывает")
                modules[module] = path
            facts[(obj.kind, obj.name)] = object_fact(
                src, obj.kind, obj.name, {mm: pt for mm, pt in modules.items() if pt})
        unknown.raise_collected()
        touched_files = touched(src)
        findings = self.conventions.apply(rules.reconcile(plan, facts, touched_files, declared_only))
        notes = []
        if declared_only:
            outside = rules.undeclared(plan, touched_files)
            notes.append("сверены только заявленные объекты"
                         + (f"; к сведению — тронуто, но не заявлено: {', '.join(outside)}" if outside else ""))
        return PlanCheckResult(src.describe(), plan, sorted(touched_files), findings, notes)
