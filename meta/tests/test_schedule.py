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

from .test_edt_write import PROFILE, project, pytestmark  # noqa: E402,F401

MODULE = {"вид": "ОбщийМодуль", "поля": {"имя": "мой_Сервер", "синоним": "Сервер",
                                        "текст": "Процедура Обменяться() Экспорт\nКонецПроцедуры\n"}}
JOB = {"вид": "РегламентноеЗадание", "поля": {
    "имя": "мой_Обмен", "синоним": "Обмен", "обработчик": "мой_Сервер.Обменяться",
    "использование": False, "предопределённое": True, "количествоПовторов": "3", "интервалПовтора": "10"}}
SCHEDULE = {"повторДней": 1, "времяНачала": "01:00:00", "повторВТечениеДня": 3600, "повторНедель": 1,
              "дниНедели": ["Понедельник", "Пятница"], "месяцы": ["Январь", "Декабрь"],
              "расписанияДня": [{"времяНачала": "14:00:00"}]}
EXPECTATION = """<?xml version="1.0" encoding="UTF-8"?>
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


def execute(src, tmp_path, **job_spec):
    path = tmp_path / "задание.json"
    path.write_text(json.dumps({"repo": str(src), **job_spec}, ensure_ascii=False), encoding="utf-8")
    return main([str(path), "--apply", "--профиль", PROFILE])


def file(src):
    return os.path.join(str(src), "ScheduledJobs", "мой_Обмен", "Schedule.schedule")


def test_a_scheduled_job_is_created_with_its_schedule(project, tmp_path):
    job_spec = json.loads(json.dumps(JOB))
    job_spec["поля"]["расписание"] = SCHEDULE
    assert execute(project, tmp_path, objects=[MODULE]) == 0
    assert execute(project, tmp_path, objects=[job_spec]) == 0
    assert open(file(project), "rb").read() == EXPECTATION.encode("utf-8")


def test_the_schedule_is_changed_and_shown(project, tmp_path, capsys):
    assert execute(project, tmp_path, objects=[MODULE]) == 0
    assert execute(project, tmp_path, objects=[JOB]) == 0
    assert not os.path.exists(file(project))                     # не заказано — файла нет
    assert execute(project, tmp_path, changes=[{"путь": "РегламентноеЗадание.мой_Обмен",
                                                 "поля": {"расписание": SCHEDULE}}]) == 0
    assert open(file(project), "rb").read() == EXPECTATION.encode("utf-8")
    capsys.readouterr()
    main(["--показать", str(project), "РегламентноеЗадание.мой_Обмен"])
    assert "расписание:" in capsys.readouterr().out


def test_a_wrong_schedule_is_refused(project, tmp_path, capsys):
    job_spec = json.loads(json.dumps(JOB))
    job_spec["поля"]["расписание"] = {"дниНедели": ["Пн"], "времяНачала": "25:00:00", "частота": 1}
    assert execute(project, tmp_path, objects=[MODULE]) == 0
    capsys.readouterr()
    assert execute(project, tmp_path, objects=[job_spec]) != 0
    text = capsys.readouterr().out
    assert "РАСПИСАНИЕ-НЕВЕРНО" in text and "частота" in text and "Понедельник" in text


def test_a_schedule_is_read_and_written_back_byte_for_byte():
    assert edt_schedule.render(edt_schedule.parse(EXPECTATION)) == EXPECTATION
    assert edt_schedule.parse(EXPECTATION)["дниНедели"] == ["Понедельник", "Пятница"]
    assert schedule.problems(edt_schedule.parse(EXPECTATION)) == []


@pytest.mark.skipif(not os.environ.get("META_EDT_CORPUS"), reason="не задан проект EDT META_EDT_CORPUS")
def test_every_schedule_of_the_corpus_goes_round_byte_for_byte():
    jobs = os.path.join(os.environ["META_EDT_CORPUS"], "ScheduledJobs")
    diverged = []
    for name in sorted(os.listdir(jobs)):
        path = os.path.join(jobs, name, "Schedule.schedule")
        if os.path.isfile(path):
            text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
            if edt_schedule.render(edt_schedule.parse(text)) != text:
                diverged.append(name)
    assert diverged == []


def test_a_configurator_dump_refuses_a_schedule(tmp_path):
    from meta.domain.kinds import kind_of
    from meta.domain.model import Refuse, Spec
    from meta.infra.designer import DesignerDump

    (tmp_path / "Configuration.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
        'version="2.21">\n\t<Configuration uuid="f02dbb0b-64fd-42c8-a83c-d102640edbc0">\n\t\t<Properties>\n'
        "\t\t\t<Name>Конфигурация</Name>\n\t\t</Properties>\n\t\t<ChildObjects/>\n\t</Configuration>\n"
        "</MetaDataObject>\n", encoding="utf-8-sig")
    sandbox = DesignerDump(str(tmp_path))
    fields = dict(JOB["поля"], расписание=SCHEDULE)
    card = sandbox.translate_card(kind_of("РегламентноеЗадание").fill(Spec("РегламентноеЗадание", fields)),
                                       "7d1e2824-b889-41a0-a83e-d45103c58d47")
    with pytest.raises(Refuse, match="только в проект EDT"):
        sandbox.prepare([card])
