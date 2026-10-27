"""Сценарий: правки форм — заведение и наполнение существующих."""

from dataclasses import dataclass

from ...domain import forms as fm
from ...domain.characters import described, guillemet_lines, invalid_characters, line_numbers
from ...domain.conventions import NEUTRAL, Conventions
from ...domain.form_events import handler_conflict
from ...domain.model import Finding, Refuse
from ..dto import Result
from ..ids import new_uuid
from ..ports import Platform


@dataclass
class EditFormUseCase:
    """Правки приходят словами домена (`FormEdits`); разбор задания — дело
    интерфейса, сценарий одинаков для любого входа.

    Порядок обычный: прочитать хозяина и форму, проверить инварианты всех
    правок, и только потом просить площадку о плане. Идентификаторы
    порождаются здесь, площадке передаётся лишь способ их получить.
    """

    platform: Platform
    conventions: Conventions = NEUTRAL

    def _handler_conflicts(self, edits):
        """Процедура с именем обработчика в модуле формы уже есть, а обработчиком
        этого события быть не может (директива, число параметров) — ошибка."""
        if edits.create is not None:
            return []
        lines = self.platform.form_module_lines(edits.owner, edits.name)
        if not lines:
            return []
        findings = []
        for name, directive, parameters in self.platform.handler_signatures(edits):
            конфликт = handler_conflict(lines, name, directive, parameters)
            if конфликт:
                findings.append(Finding("ФОРМА-ОБРАБОТЧИК-НЕ-ТОТ", конфликт, "обработчики"))
        return findings

    def _own_module(self, edits):
        """«код»: true без модуля — свой модуль объекта, если он есть и годится:
        серверный, не клиентский и не вызова сервера. Модуль инструмент и так
        находит, и без этого назвал бы его только в предупреждении, а готовое
        задание выдал бы лишь со второго вызова.
        Возвращает имя взятого модуля или None."""
        prefix = self.conventions.prefix
        if not edits.as_code or edits.code_module or not edits.owner_name or not prefix:
            return None
        own_one = f"{prefix}{edits.owner_name}"
        flags = self.platform.common_module_flags(own_one)
        if not flags or not flags.get("сервер") or any(
                flags.get(флаг) for флаг in ("клиентУправляемоеПриложение", "глобальный",
                                             "вызовСервера")):
            return None
        edits.code_module = f"ОбщийМодуль.{own_one}"
        return own_one

    def execute(self, batch, apply_now=False):
        per_object = []
        items = []
        views = []
        взятые = {}
        for edits in batch:
            own_one = self._own_module(edits)
            if own_one:
                взятые[edits.address] = own_one
            owner_spec = None
            if edits.owner:
                try:
                    owner_spec, _ = self.platform.read_spec([edits.owner])
                except Refuse:
                    owner_spec = None          # находка скажет, что хозяина нет
            view = self.platform.read_form(edits.owner, edits.name)
            views.append(view)
            findings = []
            if edits.create is not None and view is not None:
                findings.append(Finding("ФОРМА-УЖЕ-ЕСТЬ",
                                        f"форма «{edits.address}» уже есть — «создать» лишнее",
                                        "создать"))
                view = None
            fm.bind_paths(edits, view)
            findings += fm.check(edits, view, owner_spec, self.platform, self.conventions)
            findings += self._handler_conflicts(edits)
            per_object.append((edits, findings))
            items.append((edits, owner_spec, new_uuid() if edits.create else None))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.conventions.apply(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)
        code, обработчики, пояснения, места = {}, {}, {}, {}
        for (edits, _, _), kind, (_, findings) in zip(items, views, per_object, strict=True):
            if edits.as_code:
                form_code = self.conventions.form_code
                code[edits.address], обработчики[edits.address] = self.platform.render_form_code(
                    edits, kind, form_code)
                места[edits.address], якоря = fm.code_anchors(
                    edits,
                    self.platform.common_module_lines(edits.code_module_name)
                    if edits.code_module_name else None,
                    self.platform.form_module_lines(edits.owner, edits.name), form_code)
                пояснения[edits.address] = якоря + fm.placement_notes(edits, kind, form_code)
                if edits.address in взятые:
                    пояснения[edits.address].insert(0, (
                        f"модуль не назван — взят свой модуль объекта «{взятые[edits.address]}»; "
                        "другой — «код»: {«модуль»: «ОбщийМодуль.…»}"))
                # Процедура доработки уже есть — в неё дописывается код: что
                # именно, решает язык кода формы.
                extension = next((м for м in места[edits.address] if м.what == "дополнение"),
                                  None)
                if extension:
                    code[edits.address] = fm.code_addition(code[edits.address], extension,
                                                          form_code)
                # Символ, который bsl-ls считает ошибкой, и кавычки-ёлочки
                # приходят в код из заголовков задания:
                # задание на код такой текст отвергнет, и сказать об этом надо
                # здесь, где его ещё правят в задании на форму.
                symbols = invalid_characters(code[edits.address])
                if symbols:
                    findings.append(Finding(
                        "ФОРМА-КОД-СИМВОЛ",
                        "в коде формы " + described(symbols, "строка фрагмента")
                        + " — bsl-ls считает это ошибкой, и задание на код такой текст "
                        "не примет; поправьте заголовок в задании на форму",
                        "элементы", Finding.WARNING))
                guillemets = guillemet_lines(code[edits.address])
                if guillemets:
                    findings.append(Finding(
                        "ФОРМА-КОД-ЁЛОЧКИ",
                        f"в коде формы кавычки-ёлочки ({line_numbers(guillemets)} фрагмента) — "
                        "в коде кавычки прямые, задание на код такой текст не примет; "
                        "поправьте заголовок в задании на форму",
                        "элементы", Finding.WARNING))
        остальные = [item for item in items if not item[0].as_code]
        plan = (self.platform.prepare_form_edits(остальные, new_uuid) if остальные
                else None)
        written = plan.apply() if plan is not None and apply_now else []
        # и к находкам о коде формы, добавленным после решения о записи
        per_object = [(x, self.conventions.apply(f)) for x, f in per_object]
        language = self.conventions.form_code
        return Result(per_object, plan, written, code, обработчики, пояснения, места,
                      (language.dialect.title, language.dialect.purpose(language.vocabulary)))
