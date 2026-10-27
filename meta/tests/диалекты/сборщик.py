"""Учебный диалект кода формы — для проверки подключения диалектов.

Язык выдуман: «Сборка = <модуль>.Сборщик(Форма); … Сборка.Готово();». По нему
видно, что инструмент берёт из файла всё, что зависит от языка, — текст кода,
распознавание процедуры доработки, дописывание в неё, слова пояснений и
находки, — и ничего не додумывает сам.
"""

from meta.acl.form_code import quote
from meta.domain.form_dialect import CodeProcedure, FormCodeDialect
from meta.domain.model import Finding, Refuse

READY = "Сборка.Готово();"


class Assembler(FormCodeDialect):
    name = "сборщик"
    title = "Код сборщика форм"
    creating = {"элемент": r"\.\s*Элемент", "реквизит": r"\.\s*Реквизит",
                 "команда": r"\.\s*Команда"}

    def check(self, settings):
        if sorted(settings) != ["модуль"]:
            raise Refuse("у сборщика одна настройка — «модуль»")

    def description(self, settings):
        return f"сборщиком форм («{settings['модуль']}.Сборщик(Форма)»)"

    def purpose(self, settings):
        return " сборщиком"

    def code(self, edits, view, settings):
        lines = [f"Сборка = {settings['модуль']}.Сборщик(Форма);"]
        lines += [f"Сборка.Реквизит({quote(a.name)});" for a in edits.attributes]
        lines += [f"Сборка.Элемент({quote(e.name)});" for e in edits.all_elements()]
        lines.append(READY)
        return "\n".join(lines) + "\n"

    def procedure_sign(self, settings):
        return f"нет «{READY}»"

    def procedure(self, lines, span, arity, settings):
        for number in range(span[0], span[1] + 1):
            if lines[number - 1].strip() == READY:
                return CodeProcedure(span[0], span[1], "Сборка", number)
        return None

    def extension_anchor(self, procedure):
        return f"«{READY}»"

    def extension(self, lines, procedure, settings):
        return [s for s in lines if s.strip() and not s.startswith("Сборка = ")
                and s.strip() != READY]

    def movement(self, next_):
        return f'Сборка.Перед("{next_}")'

    def findings(self, edits, settings):
        if any(a.title for a in edits.attributes):
            return [Finding("ФОРМА-КОД-СБОРЩИК-ЗАГОЛОВОК", "сборщик не задаёт заголовок "
                            "реквизита", "реквизиты", Finding.WARNING)]
        return []


DIALECT = Assembler()
