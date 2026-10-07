"""Оракул EDT: эталоны записи проекта EDT — от самого EDT.

Писатель проекта EDT проверяется так же, как писатель выгрузки — по тому, что
пишет сама платформа. Здесь «платформа» — EDT: те же задания записываются
проверенным писателем выгрузки, выгрузка импортируется командой EDT `import`,
и полученный проект — эталон. Писатель EDT, применённый к тем же заданиям
на импорт базовой выгрузки, обязан дать те же байты.

    py -3 tools/edt_oracle.py <рабочий каталог>

1. базовая выгрузка: пустая конфигурация (`эталоны/формы/Configuration.xml`)
   и язык «Русский»;
2. копия базы + задания `эталоны/edt/задания/*.json` по порядку — писателем
   выгрузки, с воспроизводимыми uuid (`ORACLE_SEED`);
3. `1cedtcli import` обеих выгрузок в проекты EDT (`edtcli.ps1` рядом с
   рабочим каталогом — запуск командной строки EDT с JDK из её комплекта);
4. в `meta/tests/эталоны/edt/`: `база/` — проект EDT базы, `ожидание/` —
   проект EDT после заданий (только исходники `src`).

Нужны установленный 1C:EDT и Windows PowerShell.
"""

import json
import os
import random
import shutil
import subprocess
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ЭТАЛОНЫ = os.path.join(ROOT, "meta", "tests", "эталоны")
EDT = os.path.join(ЭТАЛОНЫ, "edt")
ЗАДАНИЯ = os.path.join(EDT, "задания")

#: Зерно uuid: тесты пользуются тем же, и uuid новых объектов совпадают.
ORACLE_SEED = 20261007

LANGUAGE = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" \
xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.21">
\t<Language uuid="2fbe6c63-3b0c-4c2f-9e6b-5b3a8d3f0e11">
\t\t<Properties>
\t\t\t<Name>Русский</Name>
\t\t\t<Synonym>
\t\t\t\t<v8:item>
\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t<v8:content>Русский</v8:content>
\t\t\t\t</v8:item>
\t\t\t</Synonym>
\t\t\t<Comment/>
\t\t\t<LanguageCode>ru</LanguageCode>
\t\t</Properties>
\t</Language>
</MetaDataObject>
"""


def seeded_uuids(seed=ORACLE_SEED):
    """`uuid.uuid4` -> воспроизводимый: одно зерно — одна последовательность."""
    rng = random.Random(seed)
    uuid.uuid4 = lambda: uuid.UUID(int=rng.getrandbits(128), version=4)


def base_dump(target):
    os.makedirs(os.path.join(target, "Languages"), exist_ok=True)
    shutil.copy(os.path.join(ЭТАЛОНЫ, "формы", "Configuration.xml"), target)
    with open(os.path.join(target, "Languages", "Русский.xml"), "w", encoding="utf-8-sig",
              newline="\r\n") as f:
        f.write(LANGUAGE)


def jobs():
    return [os.path.join(ЗАДАНИЯ, имя) for имя in sorted(os.listdir(ЗАДАНИЯ)) if имя.endswith(".json")]


def apply_jobs(repo, main):
    """Задания по порядку; отказ — остановка: эталон из недописанного не нужен."""
    for путь in jobs():
        with open(путь, encoding="utf-8") as f:
            задание = json.loads(f.read().replace("{repo}", repo.replace("\\", "/")))
        временный = путь + ".tmp"
        with open(временный, "w", encoding="utf-8") as f:
            json.dump(задание, f, ensure_ascii=False)
        try:
            код = main([временный, "--apply"])
        finally:
            os.remove(временный)
        if код:
            raise SystemExit(f"задание {os.path.basename(путь)}: код {код}")


def edt_cli():
    """(1cedtcli.exe, окружение с JDK из комплекта EDT в PATH)."""
    edt = os.path.join(os.environ["LOCALAPPDATA"], "1C", "1cedtstart", "installations")
    найдено = sorted(d for d in os.listdir(edt) if d.startswith("1C_EDT"))
    if not найдено:
        raise SystemExit(f"1C:EDT не найден в {edt}")
    exe = os.path.join(edt, найдено[-1], "1cedt", "1cedtcli.exe")
    компоненты = r"C:\Program Files\1C\1CE\components"
    jdk = sorted(d for d in os.listdir(компоненты) if d.startswith("axiom-jdk-full-17"))
    if not jdk:
        raise SystemExit(f"JDK 17 из комплекта EDT не найден в {компоненты}")
    env = dict(os.environ, PATH=os.path.join(компоненты, jdk[-1], "bin") + os.pathsep + os.environ["PATH"])
    return exe, env


def edt_import(work, pairs):
    """[(выгрузка, проект)] -> проекты EDT одной сессией командной строки EDT:
    запуск EDT — минута, импорт пустой конфигурации — секунды."""
    exe, env = edt_cli()
    сценарий = os.path.join(work, "import.script")
    with open(сценарий, "w", encoding="utf-8", newline="\n") as f:      # без BOM: иначе «команда не найдена»
        for cf, project in pairs:
            f.write(f'import --configuration-files "{cf}" --project "{project}"\n')
    done = subprocess.run([exe, "-data", os.path.join(work, "ws"), "-file", сценарий],
                          cwd=os.path.dirname(exe), env=env, capture_output=True)
    вывод = done.stdout.decode("utf-8", "replace") + done.stderr.decode("utf-8", "replace")
    print(вывод[-2000:])
    if done.returncode != 0:
        raise SystemExit(f"1cedtcli: код {done.returncode}")


def collect(project, target):
    """Исходники проекта EDT -> эталон. Переводы строк — LF, как файлы лежат
    в репозитории: командная строка EDT на Windows пишет CRLF, а git
    нормализует их в индексе."""
    src = os.path.join(project, "src")
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(src, target)
    for папка, _, имена in os.walk(target):
        for имя in имена:
            путь = os.path.join(папка, имя)
            with open(путь, "rb") as f:
                данные = f.read()
            with open(путь, "wb") as f:
                f.write(данные.replace(b"\r\n", b"\n"))


def main(argv):
    work = os.path.abspath(argv[0])
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work)
    seeded_uuids()
    sys.path.insert(0, ROOT)
    from meta.add import main as tool

    base, cf = os.path.join(work, "base_cf"), os.path.join(work, "cf")
    base_dump(base)
    shutil.copytree(base, cf)
    apply_jobs(cf, tool)
    edt_import(work, [(base, os.path.join(work, "base_edt")), (cf, os.path.join(work, "edt"))])
    collect(os.path.join(work, "base_edt"), os.path.join(EDT, "база"))
    collect(os.path.join(work, "edt"), os.path.join(EDT, "ожидание"))
    print(f"эталоны EDT: {os.path.join(EDT, 'база')}, {os.path.join(EDT, 'ожидание')}")


if __name__ == "__main__":
    main(sys.argv[1:])
