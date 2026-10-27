"""Семьи операций в задании: какие ключи, как разбирается каждый.

Задание несёт ровно одну операцию — создание, добавление, изменение, удаление,
переименование, роли или формы. Здесь перечислено, какими ключами каждая
приходит и чем разбирается; какой сценарий её исполняет, решает корень сборки —
язык заданий о сценариях не знает.

Таблица, а не цепочка `if`: добавить операцию значит дописать строку.
`attributes` и `additions` — одна семья: реквизит и есть «ребёнок по адресу»,
просто адрес короче.
"""

import os

from ..domain.model import Refuse
from . import code, dialect

#: Семья операций: её имя и ключи задания с разбором каждого.
#: Порядок строк — порядок в сообщении, когда семей в задании больше одной.
FAMILIES = (
    ("forms", (("forms", dialect.form_edits_from_json),)),
    ("atomic_roles", (("atomic_roles", dialect.atomic_roles_job_from_json),)),
    ("children", (("attributes", dialect.attribute_job_from_json),
                  ("additions", dialect.addition_job_from_json))),
    ("renames", (("renames", dialect.rename_job_from_json),)),
    ("deletions", (("deletions", dialect.delete_job_from_json),)),
    ("changes", (("changes", dialect.change_job_from_json),)),
    ("objects", (("objects", dialect.spec_from_json),)),
)
#: Семьи, у которых работа — всё задание целиком, а не каждый его пункт:
#: у задания на код общая подпись (задача, дата, автор) и атомарность по
#: всем модулям сразу. Имя семьи, ключи, по которым она опознаётся, разбор.
WHOLE_JOB = (
    ("code", code.CODE_KEYS, code.code_job_from_json),
)
JOB_KEYS = (tuple(key for _, keys in FAMILIES for key, _ in keys)
            + tuple(key for _, keys, _ in WHOLE_JOB for key in keys))
#: Ключи верхнего уровня, общие для всех операций: выгрузка, принятые
#: предупреждения, файл для кода доработки формы (терминал).
COMMON_KEYS = ("repo", "принято", "файлКода")


def repo_of(job):
    """Путь к выгрузке из задания — с проверками, которые нельзя пропустить."""
    if not isinstance(job, dict):
        raise Refuse("задание — объект JSON с полем «repo» и одной операцией")
    if not job.get("repo"):
        raise Refuse("в задании не указана выгрузка (поле «repo» с путём "
                     "к каталогу исходников)")
    if not os.path.isabs(job["repo"]):
        # Относительный путь разрешается от текущего каталога, а он у запуска
        # какой угодно: одно и то же задание из двух мест нацелится на две
        # разные выгрузки — и обе с ответом «замечаний нет». Инструмент пишет
        # в чужие файлы, и угадывать, куда именно, он не должен.
        raise Refuse(
            f"путь выгрузки «{job['repo']}» относительный, а разрешался бы "
            f"от текущего каталога ({os.getcwd()}). Напишите полный путь")
    return job["repo"]


def parse(job):
    """Задание -> (имя семьи, работы словами домена). Семья строго одна.

    Смешивать создание с удалением в одном задании нельзя не из строгости:
    порядок применения между семьями не определён, и «создать и переименовать»
    давало бы разный результат от перестановки ключей.
    """
    for _, keys in FAMILIES:
        for key, _ in keys:
            value = job.get(key)
            if value and not isinstance(value, list):
                # Словарь вместо списка перебирался бы по ключам, и пункт-строка
                # роняла бы разбор исключением «'str' object has no attribute
                # 'get'».
                raise Refuse(f"«{key}» — список пунктов: [{{…}}, {{…}}]; получено "
                             f"{'объект' if isinstance(value, dict) else repr(value)} — "
                             "оберните пункт в [ ]")
    found = [(name, [parsed(item) for key, parsed in keys
                    for item in job.get(key) or []])
             for name, keys in FAMILIES
             if any(job.get(key) for key, _ in keys)]
    if len(found) == 1:
        # ключи других операций — забота проверки «операция одна» ниже
        extra = [key for key in job if key not in COMMON_KEYS and key not in JOB_KEYS]
        if extra:
            raise Refuse(f"в задании неизвестные ключи: {', '.join(extra)}; на верхнем уровне — "
                         f"{', '.join(COMMON_KEYS)} и одна операция, поля объекта — внутри "
                         "её пунктов")
    found += [(name, [parsed(job)]) for name, keys, parsed in WHOLE_JOB
              if any(job.get(key) for key in keys)]
    if not found:
        raise Refuse("в задании нечего делать: нет ни объектов, ни реквизитов, "
                     "ни правок, ни удалений, ни переименований")
    if len(found) > 1:
        before = [key for key in JOB_KEYS if job.get(key)]
        raise Refuse("создание, добавление, изменение, удаление и переименование — "
                     "разные операции; задание должно содержать что-то одно, "
                     f"а здесь сразу: {', '.join(before)}")
    return found[0]
