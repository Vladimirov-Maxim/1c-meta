"""Сценарий: изменить значения свойств у существующих объектов и их частей."""

from dataclasses import dataclass

from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.kinds import kind_of
from ...domain.model import Host, Spec
from ..dto import Result
from ..ports import Platform


@dataclass
class ChangePropertyUseCase:
    """Правка свойств по адресу.

    Порядок тот же, что у создания и врезки: проверить всё, потом переложить,
    потом план, потом запись. Иначе задание из двух правок могло бы применить
    первую и споткнуться на второй.

    Проверяется только сама правка, а не объект целиком: карточка на диске
    несёт свойства, которых домен не выражает, и собрать из неё полную
    спецификацию нельзя без потерь. Поэтому домен отвечает на вопросы, которые
    от сдвига зависят («знает ли вид такое поле», «бывает ли оно у этого
    хозяина»), а всё остальное в файле остаётся нетронутым.

    Исключение — поля, которые правило связывает (`Kind.RELATED`): правка
    одного из них сверяется с остальными, прочитанными из выгрузки.
    """

    platform: Platform
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, changes, apply_now=False):
        """`changes` — пары (путь, поля). Путь: [(вид, имя), …] от объекта вглубь."""
        per_object = []
        for path, fields in changes:
            target_kind, target_name = path[-1]
            # Хозяин — весь адрес до цели, а не только ближайшая пара: вид
            # берётся у ближайшего родителя, имя объекта — у начала адреса.
            # С одной парой `Host.name` означал бы здесь имя ближайшего
            # родителя, и любое правило про имя объекта прочитало бы «Строки».
            host = (Host(path[-2][0], path[-2][1], path=path[:-1])
                    if len(path) > 1 else None)
            kind = kind_of(target_kind, self.соглашения)
            spec = _spec(target_kind, target_name, fields)
            per_object.append((spec, kind.check_change(fields, host)
                               + self._related(kind, path, fields)))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)

        plan = self.platform.prepare_changes(changes)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)

    def _related(self, kind, path, fields):
        """Правка поля из связанной группы — проверка группы вместе с тем, что
        у объекта уже записано. Нет таких полей в правке — выгрузка не читается."""
        if not any(set(группа) & set(fields) for группа in kind.RELATED):
            return []
        записано, _ = self.platform.read_spec(path)
        объект = Spec(записано.kind, {**записано.fields, **fields})
        return kind.related_findings(объект, self.platform, fields)


def _spec(kind, name, fields):
    """Правка в виде спецификации — чтобы отчёт печатался тем же кодом."""
    described = dict(fields)
    described["имя"] = name
    return Spec(kind, described, existing=True)
