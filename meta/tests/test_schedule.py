# ruff: noqa: F811 — фикстура `проект` взята из test_edt_write и принимается параметром
"""Расписание регламентного задания — `Schedule.schedule` проекта EDT.

Пишется при создании задания (поле «расписание») и правкой `changes`;
`show` его читает. Круг «прочитать → записать» обратим побайтно — на образце
и, если задан проект (`META_EDT_CORPUS`), на всех его расписаниях. В
выгрузке конфигуратора формат расписания не замерен — там отказ.
"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.add import main  # noqa: E402
from meta.domain import schedule  # noqa: E402
from meta.infra import edt_schedule  # noqa: E402

from .test_edt_write import ПРОФИЛЬ, pytestmark, проект  # noqa: E402,F401

МОДУЛЬ = {"вид": "ОбщийМодуль", "поля": {"имя": "мой_Сервер", "синоним": "Сервер",
                                        "текст": "Процедура Обменяться() Экспорт\nКонецПроцедуры\n"}}
ЗАДАНИЕ = {"вид": "РегламентноеЗадание", "поля": {
    "имя": "мой_Обмен", "синоним": "Обмен", "обработчик": "мой_Сервер.Обменяться",
    "использование": False, "предопределённое": True, "количествоПовторов": "3", "интервалПовтора": "10"}}
РАСПИСАНИЕ = {"повторДней": 1, "времяНачала": "01:00:00", "повторВТечениеДня": 3600, "повторНедель": 1,
              "дниНедели": ["Понедельник", "Пятница"], "месяцы": ["Январь", "Декабрь"],
              "расписанияДня": [{"времяНачала": "14:00:00"}]}
ОЖИДАНИЕ = """<?xml version="1.0" encoding="UTF-8"?>
<schedule:Schedule xmlns:schedule="http://g5.1c.ru/v8/dt/schedule" beginDate="0001-01-01" \
endDate="0001-01-01" daysRepeatPeriod="1" beginTime="01:00:00" endTime="00:00:00" completionTime="00:00:00" \
repeatPeriodInDay="3600" weeksPeriod="1">
  <weekDays>Mon</weekDays>
  <weekDays>Fri</weekDays>
  <months>Jan</months>
  <months>Dec</months>
  <dailySchedules beginTime="14:00:00" endTime="00:00:00" completionTime="00:00:00"/>
</schedule:Schedule>
"""


def выполнить(src, tmp_path, **задание):
    path = tmp_path / "задание.json"
    path.write_text(json.dumps({"repo": str(src), **задание}, ensure_ascii=False), encoding="utf-8")
    return main([str(path), "--apply", "--профиль", ПРОФИЛЬ])


def файл(src):
    return os.path.join(str(src), "ScheduledJobs", "мой_Обмен", "Schedule.schedule")


def test_a_scheduled_job_is_created_with_its_schedule(проект, tmp_path):
    задание = json.loads(json.dumps(ЗАДАНИЕ))
    задание["поля"]["расписание"] = РАСПИСАНИЕ
    assert выполнить(проект, tmp_path, objects=[МОДУЛЬ]) == 0
    assert выполнить(проект, tmp_path, objects=[задание]) == 0
    assert open(файл(проект), "rb").read() == ОЖИДАНИЕ.encode("utf-8")


def test_the_schedule_is_changed_and_shown(проект, tmp_path, capsys):
    assert выполнить(проект, tmp_path, objects=[МОДУЛЬ]) == 0
    assert выполнить(проект, tmp_path, objects=[ЗАДАНИЕ]) == 0
    assert not os.path.exists(файл(проект))                     # не заказано — файла нет
    assert выполнить(проект, tmp_path, changes=[{"путь": "РегламентноеЗадание.мой_Обмен",
                                                 "поля": {"расписание": РАСПИСАНИЕ}}]) == 0
    assert open(файл(проект), "rb").read() == ОЖИДАНИЕ.encode("utf-8")
    capsys.readouterr()
    main(["--показать", str(проект), "РегламентноеЗадание.мой_Обмен"])
    assert "расписание:" in capsys.readouterr().out


def test_a_wrong_schedule_is_refused(проект, tmp_path, capsys):
    задание = json.loads(json.dumps(ЗАДАНИЕ))
    задание["поля"]["расписание"] = {"дниНедели": ["Пн"], "времяНачала": "25:00:00", "частота": 1}
    assert выполнить(проект, tmp_path, objects=[МОДУЛЬ]) == 0
    capsys.readouterr()
    assert выполнить(проект, tmp_path, objects=[задание]) != 0
    text = capsys.readouterr().out
    assert "РАСПИСАНИЕ-НЕВЕРНО" in text and "частота" in text and "Понедельник" in text


def test_a_schedule_is_read_and_written_back_byte_for_byte():
    assert edt_schedule.render(edt_schedule.parse(ОЖИДАНИЕ)) == ОЖИДАНИЕ
    assert edt_schedule.parse(ОЖИДАНИЕ)["дниНедели"] == ["Понедельник", "Пятница"]
    assert schedule.problems(edt_schedule.parse(ОЖИДАНИЕ)) == []


@pytest.mark.skipif(not os.environ.get("META_EDT_CORPUS"), reason="не задан проект EDT META_EDT_CORPUS")
def test_every_schedule_of_the_corpus_goes_round_byte_for_byte():
    задания = os.path.join(os.environ["META_EDT_CORPUS"], "ScheduledJobs")
    разошлись = []
    for name in sorted(os.listdir(задания)):
        path = os.path.join(задания, name, "Schedule.schedule")
        if os.path.isfile(path):
            text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
            if edt_schedule.render(edt_schedule.parse(text)) != text:
                разошлись.append(name)
    assert разошлись == []


def test_a_configurator_dump_refuses_a_schedule(tmp_path):
    from meta.domain.kinds import kind_of
    from meta.domain.model import Refuse, Spec
    from meta.infra.designer import DesignerDump

    (tmp_path / "Configuration.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
        'version="2.21">\n\t<Configuration uuid="f02dbb0b-64fd-42c8-a83c-d102640edbc0">\n\t\t<Properties>\n'
        "\t\t\t<Name>Конфигурация</Name>\n\t\t</Properties>\n\t\t<ChildObjects/>\n\t</Configuration>\n"
        "</MetaDataObject>\n", encoding="utf-8-sig")
    площадка = DesignerDump(str(tmp_path))
    fields = dict(ЗАДАНИЕ["поля"], расписание=РАСПИСАНИЕ)
    card = площадка.translate_card(kind_of("РегламентноеЗадание").fill(Spec("РегламентноеЗадание", fields)),
                                       "7d1e2824-b889-41a0-a83e-d45103c58d47")
    with pytest.raises(Refuse, match="только в проект EDT"):
        площадка.prepare([card])
