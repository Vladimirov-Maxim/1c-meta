"""Сценарий: удалить объект целиком или его вложенную часть."""

from dataclasses import dataclass

from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.kinds import kind_of
from ...domain.model import Spec
from ..dto import Result
from ..ports import Platform


@dataclass
class DeleteUseCase:
    """Удаление по адресу.

    Порядок тот же, что у остальных операций: проверить всё, потом план, потом
    запись. Здесь это особенно важно: половина удаления хуже, чем ни одного —
    карточки уже нет, а ссылки на неё остались.

    Главный инвариант — «не удалять то, на что ссылаются» — домен спрашивает
    через порт: сам поиск по выгрузке дело инфраструктуры. Инструмент смотрит
    карточки объектов и права ролей, но не формы и не код BSL, и говорит об
    этом вслух каждый раз, а не молчит.
    """

    platform: Platform
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, paths, apply_now=False):
        """`paths` — адреса: [(вид, имя)] для объекта, длиннее — для его части."""
        per_object = []
        for path in paths:
            target_kind, target_name = path[-1]
            kind = kind_of(target_kind, self.соглашения)
            per_object.append((Spec(target_kind, {"имя": target_name}, existing=True),
                               kind.check_delete(path, self.platform)))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)

        plan = self.platform.prepare_deletion(paths)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)
