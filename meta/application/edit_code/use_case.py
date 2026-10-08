"""Сценарий: правка кода вставками — по всему заданию сразу."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from ...domain import edits
from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
from ...domain.edits import Edit, ModuleJob
from ...domain.model import Refuse
from ...domain.modules import own_qualifiers
from ..dto import CodeResult, при
from ..ports import Modules


@dataclass
class EditCodeUseCase:
    """Правки, откаты, переименования и перенос метода — одним актом.

    Сначала готовятся новые версии всех модулей в памяти, и только если
    подготовились все, площадка получает план. Какой файл стоит за ссылкой на
    модуль, сценарий не знает: он берёт строки, решает по правилам меток и отдаёт
    строки обратно.
    """

    modules: Modules
    #: Сегодняшняя дата «дд.мм.гггг» — часы площадки: у сценария их нет, а
    #: дата меток — дата правки.
    today: Callable[[], str] = None
    #: Соглашения команды: метка команды, которую ставят открывающие метки.
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def execute(self, jobs, apply_now=False):
        """Договор общий для всех сценариев — список работ; у задания на код
        работа одна: всё задание с общей подписью."""
        (job,) = jobs
        # Метка команды — соглашение команды, а не поле задания: задание
        # называет задачу, дату и автора, а чья это команда, говорит профиль.
        signature = replace(job.signature, tag=self.соглашения.тег_меток)
        # База сверки — общая на всё задание: «создан задачей» и сверка отката
        # спрашивают одну и ту же ревизию до задачи.
        self._base = job.base
        entries = list(job.modules)
        # Отказы — по всем модулям сразу: по первому видна была бы одна ошибка,
        # следующая — только после исправления. Отказ переноса — один из них.
        prepared, отказы = [], []
        if job.move is not None:
            try:
                entries.extend(self._expand_move(job.move))
            except Refuse as отказ:
                отказы.append(str(отказ))
        if not entries and not отказы:
            raise Refuse("в задании нет ни одного модуля")
        for entry in entries:
            try:
                with при(str(entry.ref)):
                    prepared.append(self._prepare(entry, signature))
            except Refuse as отказ:
                отказы.append(str(отказ))
        if len(отказы) == 1:
            raise Refuse(отказы[0])
        if отказы:
            raise Refuse(f"отказов по модулям: {len(отказы)} — не меняется ни один модуль:\n"
                         + "\n".join(f"  {номер}. {текст}" for номер, текст in enumerate(отказы, 1)))
        plan = self.modules.prepare([(ref, lines) for ref, lines, _ in prepared])
        written = plan.apply() if apply_now else []
        дата = edits.date_note(signature.date, self.today() if self.today else None)
        форматы = {str(ref): self.modules.file_format(ref) for ref, _, _ in prepared}
        return CodeResult(signature, [(ref, decisions) for ref, _, decisions in prepared],
                          plan, written, [дата] if дата else [],
                          {ref: формат for ref, формат in форматы.items() if формат})

    def _prepare(self, entry, signature):
        lines = self.modules.read(entry.ref)
        if entry.revert:
            new_lines, decisions = edits.revert(lines, signature.task,
                                                self.modules.base(entry.ref, self._base))
            return entry.ref, new_lines, decisions
        work = list(entry.edits)
        notes = []
        if entry.rename is not None:
            renamed, notes = edits.rename(lines, *entry.rename,
                                          own=own_qualifiers(self.modules.address(entry.ref)))
            work.extend(renamed)
        new_lines, decisions = edits.edit_module(lines, work, signature,
                                                 self.modules.is_new(entry.ref, self._base), notes)
        return entry.ref, new_lines, decisions

    def _expand_move(self, move):
        """Перенос метода: удаление в источнике и добавление в приёмнике — один
        акт. Обе половины идут общим порядком и применяются вместе или никак:
        разъехавшиеся половины — это метод потерянный или задвоенный."""
        with при(str(move.source)):
            source = self.modules.read(move.source)
            span = edits.method_range(source, move.method)
            if span is None:
                raise Refuse(f"метод «{move.method}» не найден")
        start, end = span
        body = source[start - 1:end]
        return (
            ModuleJob(move.source, (Edit(line=start, lines=end - start + 1,
                                         first_line=source[start - 1],
                                         last_line=source[end - 1], code=""),)),
            ModuleJob(move.target, (Edit(line=move.line, lines=0, code="\n".join(body),
                                         carried=True),)),
        )
