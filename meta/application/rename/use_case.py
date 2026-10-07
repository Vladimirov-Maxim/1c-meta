"""Сценарий: переименовать объект вместе со всеми ссылками на него."""

from dataclasses import dataclass

from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.kinds import kind_of
from ...domain.model import Finding, Refuse, Spec
from ..dto import Result
from ..ports import Platform


@dataclass
class RenameUseCase:
    """Переименование объекта.

    Это не правка поля «имя», и потому операция отдельная: имя живёт в четырёх
    местах сразу — в собственной карточке (включая имена порождаемых типов
    и ввод по строке), в имени файла и каталога-спутника, в записи реестра
    конфигурации и в каждой чужой карточке, которая на объект ссылается.
    Сделать одно из четырёх — сломать конфигурацию.

    Ссылки здесь не помеха, а работа: их переписывают. Помеха одна — занятое
    имя. Не переписывается то же, что не проверяется при удалении: формы
    и код BSL, — и об этом говорится вслух каждый раз.
    """

    platform: Platform
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, renames, apply_now=False):
        """`renames` — пары (адрес объекта, новое имя)."""
        per_object = []
        for path, new_name in renames:
            if len(path) != 1:
                address = ".".join(part for pair in path for part in pair)
                raise Refuse("переименовывать умеем объект целиком, "
                             f"а адрес «{address}» указывает глубже")
            kind_name, old_name = path[0]
            kind = kind_of(kind_name, self.соглашения)
            findings = kind.check_rename(new_name, self.platform)
            findings.append(Finding(
                "ПЕРЕИМЕНОВАНИЕ-КОД-НЕ-ПРОВЕРЕН",
                "имя переписывается в карточках объектов, реестре "
                "конфигурации, правах ролей и типах схем компоновки; формы, "
                "код BSL, тексты запросов и прочие макеты инструмент не "
                "смотрит — там имя останется прежним",
                level=Finding.WARNING))
            per_object.append((Spec(kind_name, {"имя": old_name}, existing=True), findings))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)

        plan = self.platform.prepare_rename(renames)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)
