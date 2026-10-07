"""Сценарий: создать объекты метаданных."""

from dataclasses import dataclass

from ...domain import atomic_roles
from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.kinds import kind_of
from ...domain.model import Finding, Refuse, Spec
from ..dto import Result, при
from ..ids import new_uuid
from ..ports import Platform

#: Поле объекта, которого нет в его карточке: просьба завести к объекту пару
#: атомарных ролей тем же заданием. Снимается здесь, до проверки домена, —
#: домен про роли-спутники не знает и знать не должен.
ATOMIC_ROLES = "атомарныеРоли"


class _Пачка:
    """Конфигурация глазами задания: объекты этой же пачки уже существуют.

    Роль-спутник ссылается на объект, который пишется тем же планом,
    а на диске его ещё нет — проверка «объекта нет» отвергла бы всю пачку.
    Всё остальное спрашивается у настоящей площадки как есть.
    """

    def __init__(self, platform, created):
        self._platform = platform
        self._created = set(created)

    def object_exists(self, kind, name):
        if (kind, name) in self._created:
            return True
        return self._platform.object_exists(kind, name)

    def __getattr__(self, name):
        return getattr(self._platform, name)


@dataclass
class AddObjectUseCase:
    """Создание самостоятельных объектов: карточка, спутники, запись в реестре.

    Порядок намеренно такой: проверить всё, потом переложить, потом подготовить
    план и только потом записать. Отказ на любом шаге означает, что на диске
    не изменилось ничего — ни одного файла, ни наполовину.
    """

    platform: Platform
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, specs, uuids=None, apply_now=False, role_notes=None):
        """`uuids` задаются только в тестах — в работе они порождаются здесь.
        `role_notes` — {имя роли: совет о составе её прав} от сценария ролей."""
        if isinstance(specs, Spec):
            specs = [specs]
        specs, notes = self._with_atomic_roles(specs)
        notes.update(role_notes or {})
        specs = [kind_of(spec.kind, self.соглашения).fill(spec) for spec in specs]
        world = _Пачка(self.platform, ((s.kind, s.get("имя")) for s in specs))
        per_object = [(spec, kind_of(spec.kind, self.соглашения).check(spec, world))
                      for spec in specs]
        # Совет о составе прав — у самой роли, предупреждением: шагом плана он
        # не является, и в «Плане» ему не место.
        for spec, findings in per_object:
            совет = notes.get(spec.get("имя")) if spec.kind == "Роль" else None
            if совет:
                findings.append(Finding("РОЛЬ-ШАБЛОН-НЕ-ПРАВИЛО", совет, "права",
                                        Finding.WARNING))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)          # до перекладки дело не доходит

        uuids = list(uuids or [])
        cards = []
        for i, spec in enumerate(specs):
            with при(f"{spec.kind} «{spec.get('имя')}»"):
                cards.append(self.platform.translate_card(
                    spec, uuids[i] if i < len(uuids) else new_uuid(), new_uuid))
        plan = self.platform.prepare(cards)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)

    def _with_atomic_roles(self, specs):
        """Раскрыть «атомарныеРоли» объекта в спецификации ролей той же пачки.

        Имена — по схеме команды из соглашений; соседи по схеме читаются раз на
        вид: по ним совет говорит, насколько типовой состав прав здесь правило.
        """
        expanded, notes, соседи = [], {}, {}
        for spec in specs:
            if ATOMIC_ROLES not in spec.fields:
                expanded.append(spec)
                continue
            asked = spec.fields[ATOMIC_ROLES]
            fields = {k: v for k, v in spec.fields.items() if k != ATOMIC_ROLES}
            bare = Spec(spec.kind, fields, asked=spec.asked - {ATOMIC_ROLES})
            expanded.append(bare)
            if asked is False or asked is None:
                continue
            # true, список ролей или объект {«права»: […], «сокращение»: «…»} —
            # сокращение нужно, когда имя роли не укладывается в 80 символов.
            сокращение = None
            if isinstance(asked, dict):
                лишние = [k for k in asked if k not in ("права", "сокращение")]
                if лишние:
                    raise Refuse(f"в «{ATOMIC_ROLES}» не знаю ключей: {', '.join(лишние)}; "
                                 "бывают: права, сокращение")
                сокращение = asked.get("сокращение")
                rights = asked.get("права")
            elif isinstance(asked, (list, tuple)):
                rights = list(asked)
            elif asked is True:
                rights = None
            else:
                raise Refuse(f"«{ATOMIC_ROLES}» — это true, список ролей (Просмотр, "
                             "Изменение) или объект {«права»: […], «сокращение»: «…»}, "
                             f"получено {asked!r}")
            схема = atomic_roles.нужна_схема(self.соглашения.атомарные_роли)
            if spec.kind in atomic_roles.kinds() and spec.kind not in соседи:
                соседи[spec.kind] = self.platform.roles_named(
                    atomic_roles.name_pattern(схема, spec.kind))
            for role, note in atomic_roles.roles_for(
                    spec.kind, spec.get("имя"), spec.get("синоним"), rights, сокращение,
                    схема, соседи.get(spec.kind)):
                expanded.append(role)
                if note:
                    notes[role.get("имя")] = note
        return expanded, notes
