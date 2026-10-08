"""Сценарий: изменить значения свойств у существующих объектов и их частей."""

from dataclasses import dataclass

from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.kinds import kind_of
from ...domain.model import Finding, Host, ListEdit, Spec
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
        resolved = []
        for path, fields in changes:
            fields, перечни = self._lists(path, fields)
            resolved.append((path, fields))
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
                               + self._related(kind, path, fields) + перечни))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)

        plan = self.platform.prepare_changes(resolved)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)

    def _lists(self, path, fields):
        """Правки полей-перечней -> перечни целиком, сведённые с записанным.

        Добавляемое проверяется так же, как при создании объекта (существует
        ли, того ли вида): находки вида берутся только по этому полю и только
        по добавленному — записанное раньше не судится заново."""
        правки = {f: v for f, v in fields.items() if isinstance(v, ListEdit)}
        if not правки:
            return fields, []
        записано, _ = self.platform.read_spec(path)
        kind = kind_of(path[-1][0], self.соглашения)
        готово, находки = dict(fields), []
        for field, правка in правки.items():
            было = list(записано.fields.get(field) or [])
            новый, уже, нет = правка.applied(было)
            for x in нет:
                находки.append(Finding(
                    "ПЕРЕЧЕНЬ-УБРАТЬ-НЕТ",
                    f"«{x}» в «{field}» нет — убирать нечего", field))
            for x in уже:
                находки.append(Finding(
                    "ПЕРЕЧЕНЬ-УЖЕ-ЕСТЬ",
                    f"«{x}» в «{field}» уже есть — второй раз не добавляется",
                    field, Finding.WARNING))
            добавлено = правка.added(было)
            if добавлено:
                находки += [f for f in kind.own_findings(
                    Spec(kind.name, {field: добавлено}), self.platform)
                    if f.field == field]
            if правка.replace is not None:
                ушло = [x for x in было if x not in новый]
                if ушло:
                    находки.append(Finding(
                        "ПЕРЕЧЕНЬ-ЗАМЕНА",
                        f"«{field}» заменяется целиком; уходит {len(ушло)}: "
                        + ", ".join(ушло[:10]) + (" …" if len(ушло) > 10 else ""),
                        field, Finding.WARNING))
            готово[field] = новый
        return готово, находки

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
