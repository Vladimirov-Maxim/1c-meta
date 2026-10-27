"""Процедура с именем события в модуле формы без привязки в описании формы.

Событие формы связывается с процедурой записью в описании формы (`Form.xml`,
`Form.form`), а не именем: процедуру `ПередЗакрытием` без записи `BeforeClose`
платформа не вызовет — код компилируется и проходит проверки, а обработчик
молчит. Правка кода и проверка правок о такой процедуре предупреждают.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.infra import form_bindings  # noqa: E402

from .test_verify import ПРОФИЛЬ, выгрузка, зафиксировать, написать  # noqa: E402

МОДУЛЬ = "Documents/мой_Наш/Forms/ФормаДокумента/Ext/Form/Module.bsl"
ФОРМА = "Documents/мой_Наш/Forms/ФормаДокумента/Ext/Form.xml"
ОПИСАНИЕ = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" version="2.21">',
            "\t<Events>", '\t\t<Event name="OnOpen">ПриОткрытии</Event>', "\t</Events>",
            "\t<ChildItems>", '\t\t<InputField name="Номер" id="1">', "\t\t</InputField>",
            "\t</ChildItems>", "</Form>"]
БЫЛО = ["&НаКлиенте", "Процедура ПриОткрытии(Отказ)", "КонецПроцедуры"]
НОВОЕ = ("&НаКлиенте\nПроцедура ПередЗакрытием(Отказ, ЗавершениеРаботы, ТекстПредупреждения, "
         "СтандартнаяОбработка)\nКонецПроцедуры\n\n&НаКлиенте\nПроцедура НомерПриИзменении(Элемент)\n"
         "КонецПроцедуры\n\n&НаКлиенте\nПроцедура Посчитать()\nКонецПроцедуры")


def форма(tmp_path):
    root = выгрузка(tmp_path)
    написать(root, ФОРМА, ОПИСАНИЕ)
    написать(root, МОДУЛЬ, БЫЛО)
    зафиксировать(root, "форма")
    return root


def test_code_apply_warns_about_event_named_procedures_without_binding(tmp_path, capsys):
    root = форма(tmp_path)
    задание = {"repo": str(root), "task": "TASK-1", "date": "31.08.2026", "author": "Автор",
               "modules": [{"модуль": "Документ.мой_Наш.Форма.ФормаДокумента", "edits": [
                   {"line": 4, "lines": 0, "code": НОВОЕ}]}]}
    path = tmp_path / "код.json"
    path.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    профиль = tmp_path / "профиль.json"
    профиль.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["--apply", str(path), "--профиль", str(профиль)]) == 0
    text = capsys.readouterr().out
    assert "«ПередЗакрытием» названа как событие формы «ПередЗакрытием»" in text, text
    assert "«НомерПриИзменении» названа как событие «ПриИзменении» элемента «Номер»" in text
    assert "«Посчитать»" not in text

    ответ = tmp_path / "ответ.json"
    main(["--проверить", str(root), "--задача", "TASK-1", "--профиль", str(профиль), "--json", str(ответ)])
    findings = [f for f in json.loads(ответ.read_text(encoding="utf-8"))["находки"]
               if f["код"] == "ФОРМА-ОБРАБОТЧИК-НЕ-ПРИВЯЗАН"]
    assert sorted(f["текст"].split("»")[0] for f in findings) == ["процедура «НомерПриИзменении",
                                                                 "процедура «ПередЗакрытием"]
    assert all(f["уровень"] == "предупреждение" and f["строка"] for f in findings)


def test_bindings_are_read_from_an_edt_form():
    text = """<?xml version="1.0" encoding="UTF-8"?>
<form:Form xmlns:form="http://g5.1c.ru/v8/dt/form">
  <items xsi:type="form:FormField">
    <name>Номер</name>
    <handlers>
      <event>OnChange</event>
      <name>НомерПриИзменении</name>
    </handlers>
  </items>
  <handlers>
    <event>BeforeClose</event>
    <name>ПередЗакрытием</name>
  </handlers>
  <formCommands>
    <name>Посчитать</name>
    <action xsi:type="form:FormCommandHandlerContainer">
      <handler>
        <name>ПосчитатьКоманда</name>
      </handler>
    </action>
  </formCommands>
</form:Form>
"""
    привязаны, элементы = form_bindings.bindings(text)
    assert привязаны == {"НомерПриИзменении", "ПередЗакрытием", "ПосчитатьКоманда"}
    assert "Номер" in элементы
    assert form_bindings.form_file("Documents/Д/Forms/Ф/Module.bsl") == "Documents/Д/Forms/Ф/Form.form"
    assert form_bindings.form_file("Documents/Д/Forms/Ф/Ext/Form/Module.bsl") == "Documents/Д/Forms/Ф/Ext/Form.xml"
    assert form_bindings.form_file("Documents/Д/Ext/ObjectModule.bsl") is None
