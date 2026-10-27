"""Сценарий: изменить значения свойств у существующих объектов и их частей."""

from dataclasses import dataclass

from ...domain import query_text
from ...domain.conventions import NEUTRAL, Conventions
from ...domain.kinds import kind_of
from ...domain.model import Finding, Host, ListEdit, Spec, TextEdit
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
    conventions: Conventions = NEUTRAL

    def execute(self, changes, apply_now=False):
        """`changes` — пары (путь, поля). Путь: [(вид, имя), …] от объекта вглубь."""
        per_object = []
        resolved = []
        diffs = []
        for path, fields in changes:
            fields, list_edits = self._lists(path, fields)
            fields, texts, diff = self._texts(path, fields)
            list_edits += texts
            diffs += diff
            resolved.append((path, fields))
            target_kind, target_name = path[-1]
            # Хозяин — весь адрес до цели, а не только ближайшая пара: вид
            # берётся у ближайшего родителя, имя объекта — у начала адреса.
            # С одной парой `Host.name` означал бы здесь имя ближайшего
            # родителя, и любое правило про имя объекта прочитало бы «Строки».
            host = (Host(path[-2][0], path[-2][1], path=path[:-1])
                    if len(path) > 1 else None)
            kind = kind_of(target_kind, self.conventions)
            spec = _spec(target_kind, target_name, fields)
            per_object.append((spec, kind.check_change(fields, host)
                               + self._related(kind, path, fields) + list_edits))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.conventions.apply(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)

        plan = self.platform.prepare_changes(resolved)
        for line in diffs:
            plan.note(line)
        written = plan.apply() if apply_now else []
        return Result(per_object, plan, written)

    def _texts(self, path, fields):
        """Правки полей-текстов фрагментами -> тексты целиком, сведённые с
        записанным; беды якорей и непарные скобки — ошибки; разница — строками
        для показа: ради неё правку фрагментом и затевают."""
        import difflib

        edit_jobs = {f: v for f, v in fields.items() if isinstance(v, TextEdit)}
        if not edit_jobs:
            return fields, [], []
        written_as, _ = self.platform.read_spec(path)
        ready, findings, diff = dict(fields), [], []
        address = ".".join(f"{kind}.{name}" for kind, name in path)
        for field, edit_job in edit_jobs.items():
            before = written_as.fields.get(field) or ""
            after_, problems = edit_job.applied(before)
            findings += [Finding("ТЕКСТ-ЯКОРЬ", problem, field) for problem in problems]
            if after_ is None:
                ready.pop(field)
                continue
            errors, warnings = query_text.problems(before, after_)
            findings += [Finding("ТЕКСТ-СКОБКИ", x, field) for x in errors]
            findings += [Finding("ТЕКСТ-ПАКЕТ", x, field, Finding.WARNING) for x in warnings]
            ready[field] = after_
            diff.append(f"{address}: «{field}» правится фрагментами ({edit_job}):")
            diff += ["    " + x.rstrip("\n") for x in difflib.unified_diff(
                before.split("\n"), after_.split("\n"), lineterm="", n=1)][2:]
        return ready, findings, diff

    def _lists(self, path, fields):
        """Правки полей-перечней -> перечни целиком, сведённые с записанным.

        Добавляемое проверяется так же, как при создании объекта (существует
        ли, того ли вида): находки вида берутся только по этому полю и только
        по добавленному — записанное раньше не судится заново."""
        edit_jobs = {f: v for f, v in fields.items() if isinstance(v, ListEdit)}
        if not edit_jobs:
            return fields, []
        written_as, _ = self.platform.read_spec(path)
        kind = kind_of(path[-1][0], self.conventions)
        ready, findings = dict(fields), []
        for field, edit_job in edit_jobs.items():
            before = list(written_as.fields.get(field) or [])
            new, already, missing = edit_job.applied(before)
            for x in missing:
                findings.append(Finding(
                    "ПЕРЕЧЕНЬ-УБРАТЬ-НЕТ",
                    f"«{x}» в «{field}» нет — убирать нечего", field))
            for x in already:
                findings.append(Finding(
                    "ПЕРЕЧЕНЬ-УЖЕ-ЕСТЬ",
                    f"«{x}» в «{field}» уже есть — второй раз не добавляется",
                    field, Finding.WARNING))
            added_count = edit_job.added(before)
            if added_count:
                findings += [f for f in kind.own_findings(
                    Spec(kind.name, {field: added_count}), self.platform)
                    if f.field == field]
            if edit_job.replace is not None:
                went = [x for x in before if x not in new]
                if went:
                    findings.append(Finding(
                        "ПЕРЕЧЕНЬ-ЗАМЕНА",
                        f"«{field}» заменяется целиком; уходит {len(went)}: "
                        + ", ".join(went[:10]) + (" …" if len(went) > 10 else ""),
                        field, Finding.WARNING))
            ready[field] = new
        return ready, findings

    def _related(self, kind, path, fields):
        """Правка поля из связанной группы — проверка группы вместе с тем, что
        у объекта уже записано. Нет таких полей в правке — выгрузка не читается."""
        if not any(set(group) & set(fields) for group in kind.RELATED):
            return []
        written_as, _ = self.platform.read_spec(path)
        obj = Spec(written_as.kind, {**written_as.fields, **fields})
        return kind.related_findings(obj, self.platform, fields)


def _spec(kind, name, fields):
    """Правка в виде спецификации — чтобы отчёт печатался тем же кодом."""
    described = dict(fields)
    described["имя"] = name
    return Spec(kind, described, existing=True)
