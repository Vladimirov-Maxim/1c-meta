"""Сценарий: сверить план изменений с фактом задачи.

План приходит моделью домена (`domain.plan.План`), факт — от источника
правок; расхождения — правилами домена (`domain.plan.сверить`). План с
объектом, которого выгрузка не знает, — отказ, а не половина сверки.
"""

from dataclasses import dataclass

from ...domain import plan as rules
from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.model import Собранные
from ..dto import PlanCheckResult
from ..plan_facts import затронутые, факт_объекта
from ..ports import ChangeSource


@dataclass
class PlanCheckUseCase:
    source: ChangeSource
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, план):
        src = self.source
        неизвестные = Собранные("в плане объекты, которых выгрузка не знает")
        факты = {}
        for объект in план.объекты:
            if src.card_path(объект.вид, объект.имя) is None:
                неизвестные.добавить(f"«{объект.вид}.{объект.имя}»: вид «{объект.вид}» выгрузке неизвестен")
                continue
            модули = {}
            for модуль in объект.модули:
                путь = src.module_path(объект.вид, объект.имя, модуль)
                if путь is None:
                    неизвестные.добавить(f"«{объект.вид}.{объект.имя}»: модуля «{модуль}» у вида не бывает")
                модули[модуль] = путь
            факты[(объект.вид, объект.имя)] = факт_объекта(
                src, объект.вид, объект.имя, {м: п for м, п in модули.items() if п})
        неизвестные.предъявить()
        тронутые = затронутые(src)
        findings = self.соглашения.применить(rules.сверить(план, факты, тронутые))
        return PlanCheckResult(src.describe(), план, sorted(тронутые), findings)
