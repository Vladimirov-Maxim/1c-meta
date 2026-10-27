"""Сценарий: завести атомарные роли к объекту, который уже есть в выгрузке."""

from dataclasses import dataclass

from ..domain import atomic_roles
from ..domain.conventions import NEUTRAL, Conventions
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
    conventions: Conventions = NEUTRAL

    def execute(self, requests, apply_now=False):
        """`requests` — (вид, имя, права или None[, сокращение[, комментарий]])."""
        schema = atomic_roles.needs_schema(self.conventions.atomic_roles)
        specs, notes, neighbours = [], {}, {}
        for kind, name, rights, *tail in requests:
            abbreviation = tail[0] if tail else None
            comment = tail[1] if len(tail) > 1 else None
            if kind not in atomic_roles.kinds():
                raise Refuse(f"типовой состав атомарных ролей есть для видов "
                             f"{', '.join(atomic_roles.kinds())}, а не для «{kind}»")
            try:
                found, _ = self.platform.read_spec([(kind, name)])
            except Refuse as refusal:
                raise Refuse(f"{kind}.{name}: {refusal}") from refusal
            # Пара ролей у объекта уже бывает — под сокращённым именем, которое
            # по имени объекта не угадать: без этой проверки вторая пара
            # заводилась бы молча.
            if kind not in neighbours:
                neighbours[kind] = self.platform.roles_named(atomic_roles.name_pattern(schema, kind))
            exists = atomic_roles.roles_of_object(kind, name, neighbours[kind])
            if exists:
                raise Refuse(f"{kind}.{name}: атомарные роли у объекта уже есть — "
                             f"{', '.join(exists)}; вторую пару не заводим")
            for role, note in atomic_roles.roles_for(
                    kind, name, found.get("синоним"), rights, abbreviation, schema, neighbours[kind],
                    comment):
                specs.append(role)
                if note:
                    notes[role.get("имя")] = note
        result = AddObjectUseCase(self.platform, self.conventions).execute(
            specs, apply_now=False, role_notes=notes)
        if not result.ok:
            return result
        if apply_now:
            result.written = result.plan.apply()
        return result
