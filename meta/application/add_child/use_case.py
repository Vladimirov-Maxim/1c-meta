"""Сценарий: добавить вложенную сущность в существующий объект или схему."""

from dataclasses import dataclass

from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.kinds import kind_of
from ...domain.model import Host, представление
from ..dto import Result, при
from ..ids import new_uuid
from ..ports import Platform


@dataclass
class AddChildUseCase:
    """Добавление ребёнка по адресу хозяина.

    Адрес указывает любого хозяина — объект, его табличную часть или схему
    компоновки в макете, — а вид ребёнка задаётся отдельно. Так измерение,
    ресурс и табличную часть можно добавить в существующий объект, а не
    только вместе с его созданием.

    Порядок обычный: проверить всё, потом переложить, потом план, потом
    запись. Идентификаторы порождаются здесь — инфраструктуре про них знать
    незачем.
    """

    platform: Platform
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, additions, apply_now=False):
        """`additions` — пары (адрес хозяина, спецификация ребёнка)."""
        per_object = []
        filled = []
        for path, spec in additions:
            # Вид берётся у ближайшего родителя — от него зависит состав
            # свойств; имя у объекта — оно решает вопрос префикса; адрес
            # целиком — по нему проверяется занятость имени. Три вопроса,
            # три источника: слепить их в одну пару значит завести дефект.
            host_kind = path[-1][0]
            owner_name = path[0][1]
            kind = kind_of(spec.kind, self.соглашения)
            host = Host(host_kind, owner_name, path=path)
            ready = kind.fill(spec, host)
            per_object.append((ready, kind.check(ready, self.platform, host)))
            filled.append((path, ready, host_kind, owner_name))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)

        prepared = []
        for path, spec, host_kind, host_name in filled:
            адрес = ".".join(f"{kind}.{name}" for kind, name in path)
            with при(f"{адрес} → {spec.kind} «{представление(spec)}»"):
                node = self.platform.translate_node_for(
                    spec, new_uuid(), host_kind, host_name, new_uuid)
            prepared.append((path, node, spec.get("имя"), spec.kind,
                             представление(spec)))
        plan = self.platform.prepare_addition(prepared)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)
