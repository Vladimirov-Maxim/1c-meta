"""Учебный диалект кода формы — для проверки подключения диалектов.

Язык выдуман: «Сборка = <модуль>.Сборщик(Форма); … Сборка.Готово();». По нему
видно, что инструмент берёт из файла всё, что зависит от языка, — текст кода,
распознавание процедуры доработки, дописывание в неё, слова пояснений и
находки, — и ничего не додумывает сам.
"""

from meta.acl.form_code import quote
from meta.domain.form_dialect import CodeProcedure, ДиалектКодаФорм
from meta.domain.model import Finding, Refuse

ГОТОВО = "Сборка.Готово();"


class Сборщик(ДиалектКодаФорм):
    имя = "сборщик"
    заголовок = "Код сборщика форм"
    заводящие = {"элемент": r"\.\s*Элемент", "реквизит": r"\.\s*Реквизит",
                 "команда": r"\.\s*Команда"}

    def проверить(self, настройки):
        if sorted(настройки) != ["модуль"]:
            raise Refuse("у сборщика одна настройка — «модуль»")

    def описание(self, настройки):
        return f"сборщиком форм («{настройки['модуль']}.Сборщик(Форма)»)"

    def назначение(self, настройки):
        return " сборщиком"

    def код(self, edits, view, настройки):
        строки = [f"Сборка = {настройки['модуль']}.Сборщик(Форма);"]
        строки += [f"Сборка.Реквизит({quote(a.name)});" for a in edits.attributes]
        строки += [f"Сборка.Элемент({quote(e.name)});" for e in edits.all_elements()]
        строки.append(ГОТОВО)
        return "\n".join(строки) + "\n"

    def признак_процедуры(self, настройки):
        return f"нет «{ГОТОВО}»"

    def процедура(self, lines, span, arity, настройки):
        for номер in range(span[0], span[1] + 1):
            if lines[номер - 1].strip() == ГОТОВО:
                return CodeProcedure(span[0], span[1], "Сборка", номер)
        return None

    def якорь_дополнения(self, procedure):
        return f"«{ГОТОВО}»"

    def дополнение(self, строки, procedure, настройки):
        return [s for s in строки if s.strip() and not s.startswith("Сборка = ")
                and s.strip() != ГОТОВО]

    def перемещение(self, следующий):
        return f'Сборка.Перед("{следующий}")'

    def находки(self, edits, настройки):
        if any(a.title for a in edits.attributes):
            return [Finding("ФОРМА-КОД-СБОРЩИК-ЗАГОЛОВОК", "сборщик не задаёт заголовок "
                            "реквизита", "реквизиты", Finding.WARNING)]
        return []


ДИАЛЕКТ = Сборщик()
