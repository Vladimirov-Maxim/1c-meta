"""Сценарий: правки форм — заведение и наполнение существующих."""

from dataclasses import dataclass

from ...domain import forms as fm
from ...domain.characters import described, guillemet_lines, invalid_characters, line_numbers
from ...domain.conventions import НЕЙТРАЛЬНЫЕ, Соглашения
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
    соглашения: Соглашения = НЕЙТРАЛЬНЫЕ

    def _handler_conflicts(self, edits):
        """Процедура с именем обработчика в модуле формы уже есть, а обработчиком
        этого события быть не может (директива, число параметров) — ошибка."""
        if edits.create is not None:
            return []
        строки = self.platform.form_module_lines(edits.owner, edits.name)
        if not строки:
            return []
        findings = []
        for имя, директива, параметры in self.platform.handler_signatures(edits):
            конфликт = handler_conflict(строки, имя, директива, параметры)
            if конфликт:
                findings.append(Finding("ФОРМА-ОБРАБОТЧИК-НЕ-ТОТ", конфликт, "обработчики"))
        return findings

    def _own_module(self, edits):
        """«код»: true без модуля — свой модуль объекта, если он есть и годится:
        серверный, не клиентский и не вызова сервера. Модуль инструмент и так
        находит, и без этого назвал бы его только в предупреждении, а готовое
        задание выдал бы лишь со второго вызова.
        Возвращает имя взятого модуля или None."""
        приставка = self.соглашения.приставка
        if not edits.as_code or edits.code_module or not edits.owner_name or not приставка:
            return None
        свой = f"{приставка}{edits.owner_name}"
        флаги = self.platform.common_module_flags(свой)
        if not флаги or not флаги.get("сервер") or any(
                флаги.get(флаг) for флаг in ("клиентУправляемоеПриложение", "глобальный",
                                             "вызовСервера")):
            return None
        edits.code_module = f"ОбщийМодуль.{свой}"
        return свой

    def execute(self, batch, apply_now=False):
        per_object = []
        items = []
        views = []
        взятые = {}
        for edits in batch:
            свой = self._own_module(edits)
            if свой:
                взятые[edits.address] = свой
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
            findings += fm.check(edits, view, owner_spec, self.platform, self.соглашения)
            findings += self._handler_conflicts(edits)
            per_object.append((edits, findings))
            items.append((edits, owner_spec, new_uuid() if edits.create else None))
        # соглашения команды: выключенные правила — прочь, уровни — из профиля
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        if any(f.blocking for _, findings in per_object for f in findings):
            return Result(per_object)
        код, обработчики, пояснения, места = {}, {}, {}, {}
        for (edits, _, _), вид, (_, findings) in zip(items, views, per_object, strict=True):
            if edits.as_code:
                код_форм = self.соглашения.код_форм
                код[edits.address], обработчики[edits.address] = self.platform.render_form_code(
                    edits, вид, код_форм)
                места[edits.address], якоря = fm.code_anchors(
                    edits,
                    self.platform.common_module_lines(edits.code_module_name)
                    if edits.code_module_name else None,
                    self.platform.form_module_lines(edits.owner, edits.name), код_форм)
                пояснения[edits.address] = якоря + fm.placement_notes(edits, вид, код_форм)
                if edits.address in взятые:
                    пояснения[edits.address].insert(0, (
                        f"модуль не назван — взят свой модуль объекта «{взятые[edits.address]}»; "
                        "другой — «код»: {«модуль»: «ОбщийМодуль.…»}"))
                # Процедура доработки уже есть — в неё дописывается код: что
                # именно, решает язык кода формы.
                дополнение = next((м for м in места[edits.address] if м.what == "дополнение"),
                                  None)
                if дополнение:
                    код[edits.address] = fm.code_addition(код[edits.address], дополнение,
                                                          код_форм)
                # Символ, который bsl-ls считает ошибкой, и кавычки-ёлочки
                # приходят в код из заголовков задания:
                # задание на код такой текст отвергнет, и сказать об этом надо
                # здесь, где его ещё правят в задании на форму.
                символы = invalid_characters(код[edits.address])
                if символы:
                    findings.append(Finding(
                        "ФОРМА-КОД-СИМВОЛ",
                        "в коде формы " + described(символы, "строка фрагмента")
                        + " — bsl-ls считает это ошибкой, и задание на код такой текст "
                        "не примет; поправьте заголовок в задании на форму",
                        "элементы", Finding.WARNING))
                ёлочки = guillemet_lines(код[edits.address])
                if ёлочки:
                    findings.append(Finding(
                        "ФОРМА-КОД-ЁЛОЧКИ",
                        f"в коде формы кавычки-ёлочки ({line_numbers(ёлочки)} фрагмента) — "
                        "в коде кавычки прямые, задание на код такой текст не примет; "
                        "поправьте заголовок в задании на форму",
                        "элементы", Finding.WARNING))
        остальные = [item for item in items if not item[0].as_code]
        plan = (self.platform.prepare_form_edits(остальные, new_uuid) if остальные
                else None)
        written = plan.apply() if plan is not None and apply_now else []
        # и к находкам о коде формы, добавленным после решения о записи
        per_object = [(x, self.соглашения.применить(f)) for x, f in per_object]
        язык = self.соглашения.код_форм
        return Result(per_object, plan, written, код, обработчики, пояснения, места,
                      (язык.диалект.заголовок, язык.диалект.назначение(язык.словарь)))
