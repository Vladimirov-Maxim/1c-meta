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
from ..plan_facts import touched, факт_объекта
from ..ports import ChangeSource


@dataclass
class PlanCheckUseCase:
    source: ChangeSource
    conventions: Conventions = NEUTRAL

    def execute(self, plan, declared_only=False):
        src = self.source
        неизвестные = Collected("в плане объекты, которых выгрузка не знает")
        facts = {}
        for obj in plan.objects:
            if src.card_path(obj.kind, obj.name) is None:
                неизвестные.add(f"«{obj.kind}.{obj.name}»: вид «{obj.kind}» выгрузке неизвестен")
                continue
            modules = {}
            for module in obj.modules:
                path = src.module_path(obj.kind, obj.name, module)
                if path is None:
                    неизвестные.add(f"«{obj.kind}.{obj.name}»: модуля «{module}» у вида не бывает")
                modules[module] = path
            facts[(obj.kind, obj.name)] = факт_объекта(
                src, obj.kind, obj.name, {м: pt for м, pt in modules.items() if pt})
        неизвестные.raise_collected()
        тронутые = touched(src)
        findings = self.conventions.apply(rules.reconcile(plan, facts, тронутые, declared_only))
        notes = []
        if declared_only:
            outside = rules.undeclared(plan, тронутые)
            notes.append("сверены только заявленные объекты"
                         + (f"; к сведению — тронуто, но не заявлено: {', '.join(outside)}" if outside else ""))
        return PlanCheckResult(src.describe(), plan, sorted(тронутые), findings, notes)
