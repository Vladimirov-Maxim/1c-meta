"""Сценарий: завести атомарные роли к объекту, который уже есть в выгрузке."""

from dataclasses import dataclass

from ..domain import atomic_roles
from ..domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ..domain.model import Refuse
from .add_object.use_case import AddObjectUseCase
from .ports import Platform


@dataclass
class AtomicRolesUseCase:
    """Пара ролей по схеме команды к существующему объекту.

    Объект читается с диска — ради синонима, который идёт в синоним роли,
    и ради того, чтобы отказать на несуществующий сразу, а не на записи.
    Дальше всё делает создание объектов: роли — обычные объекты.
    """

    platform: Platform
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, requests, apply_now=False):
        """`requests` — (вид, имя, права или None[, сокращение или None])."""
        схема = atomic_roles.нужна_схема(self.соглашения.атомарные_роли)
        specs, notes, соседи = [], {}, {}
        for kind, name, rights, *хвост in requests:
            сокращение = хвост[0] if хвост else None
            if kind not in atomic_roles.kinds():
                raise Refuse(f"типовой состав атомарных ролей есть для видов "
                             f"{', '.join(atomic_roles.kinds())}, а не для «{kind}»")
            try:
                found, _ = self.platform.read_spec([(kind, name)])
            except Refuse as отказ:
                raise Refuse(f"{kind}.{name}: {отказ}") from отказ
            # Пара ролей у объекта уже бывает — под сокращённым именем, которое
            # по имени объекта не угадать: без этой проверки вторая пара
            # заводилась бы молча.
            if kind not in соседи:
                соседи[kind] = self.platform.roles_named(atomic_roles.name_pattern(схема, kind))
            есть = atomic_roles.roles_of_object(kind, name, соседи[kind])
            if есть:
                raise Refuse(f"{kind}.{name}: атомарные роли у объекта уже есть — "
                             f"{', '.join(есть)}; вторую пару не заводим")
            for role, note in atomic_roles.roles_for(
                    kind, name, found.get("синоним"), rights, сокращение, схема, соседи[kind]):
                specs.append(role)
                if note:
                    notes[role.get("имя")] = note
        result = AddObjectUseCase(self.platform, self.соглашения).execute(
            specs, apply_now=False, role_notes=notes)
        if not result.ok:
            return result
        if apply_now:
            result.written = result.plan.apply()
        return result
