"""Оракул внешних обработок и отчётов: эталоны — от самого конфигуратора.

Запись внешней обработки проверяется тем, что с ней делает платформа:

1. задания `эталоны/внешние/задания/*.json` по порядку пишут инструментом
   в пустой каталог, с воспроизводимыми uuid (`ORACLE_SEED`);
2. каждая карточка в корне загружается конфигуратором в файл
   (`/LoadExternalDataProcessorOrReportFromFiles`) на пустой базе и
   выгружается обратно (`/DumpExternalDataProcessorOrReportToFiles`);
3. выгрузка конфигуратора — эталон `эталоны/внешние/ожидание/`.

Тест `test_external_write.py` применяет те же задания и сверяет каждый файл
с эталоном побайтно. Расхождение записи с выгрузкой оракул печатает сразу:
всё, что конфигуратор дописал или переставил, — недоработка инструмента.

    py -3 tools/epf_oracle.py <рабочий каталог> [<1cv8.exe>]

Нужна установленная платформа 1С (по умолчанию — последняя в
`C:\\Program Files\\1cv8`). База создаётся в рабочем каталоге: чужие базы
и открытый конфигуратор не мешают.
"""

import glob
import json
import os
import random
import shutil
import subprocess
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ВНЕШНИЕ = os.path.join(ROOT, "meta", "tests", "эталоны", "внешние")
ЗАДАНИЯ = os.path.join(ВНЕШНИЕ, "задания")
ОЖИДАНИЕ = os.path.join(ВНЕШНИЕ, "ожидание")
ПРОФИЛЬ = os.path.join(ROOT, "meta", "tests", "профиль-тестов.json")

#: Зерно uuid: тест пользуется тем же, и uuid новых объектов совпадают.
ORACLE_SEED = 20261008


def seeded_uuids(seed=ORACLE_SEED):
    rng = random.Random(seed)
    uuid.uuid4 = lambda: uuid.UUID(int=rng.getrandbits(128), version=4)


def platform():
    """Последний установленный `1cv8.exe`."""
    найдено = sorted(glob.glob(r"C:\Program Files\1cv8\8.*\bin\1cv8.exe"))
    if not найдено:
        raise SystemExit("платформа 1С не найдена в C:\\Program Files\\1cv8")
    return найдено[-1]


def apply_jobs(repo, tool):
    for имя in sorted(os.listdir(ЗАДАНИЯ)):
        if not имя.endswith(".json"):
            continue
        with open(os.path.join(ЗАДАНИЯ, имя), encoding="utf-8") as f:
            задание = json.loads(f.read().replace("{repo}", repo.replace("\\", "/")))
        временный = os.path.join(os.path.dirname(repo), "_задание.json")
        with open(временный, "w", encoding="utf-8") as f:
            json.dump(задание, f, ensure_ascii=False)
        код = tool([временный, "--apply", "--профиль", ПРОФИЛЬ])
        os.remove(временный)
        if код:
            raise SystemExit(f"задание {имя}: код {код}")


def designer(v8, base, *args, log):
    done = subprocess.run([v8, "DESIGNER", "/F", base, "/DisableStartupDialogs", *args, "/Out", log],
                          timeout=900)
    текст = open(log, encoding="utf-8-sig", errors="replace").read() if os.path.exists(log) else ""
    if done.returncode:
        raise SystemExit(f"конфигуратор: код {done.returncode}\n{текст[-1500:]}")


def round_trip(v8, work, src, target):
    """Каждая карточка корня `src` -> файл -> выгрузка в `target`."""
    base = os.path.join(work, "ib")
    subprocess.run([v8, "CREATEINFOBASE", f"File={base}", "/Out", os.path.join(work, "create.log")],
                   timeout=600, check=True)
    for имя in sorted(os.listdir(src)):
        карточка = os.path.join(src, имя)
        if not (имя.endswith(".xml") and os.path.isfile(карточка)):
            continue
        with open(карточка, "rb") as f:
            отчет = b"<ExternalReport " in f.read(4096)
        файл = os.path.join(work, os.path.splitext(имя)[0] + (".erf" if отчет else ".epf"))
        designer(v8, base, "/LoadExternalDataProcessorOrReportFromFiles", карточка, файл,
                 log=os.path.join(work, "load.log"))
        designer(v8, base, "/DumpExternalDataProcessorOrReportToFiles", os.path.join(target, имя), файл,
                 log=os.path.join(work, "dump.log"))


def differences(written, expected):
    """Файлы, в которых запись инструмента расходится с выгрузкой конфигуратора."""
    def files(root):
        return {os.path.relpath(os.path.join(п, и), root): os.path.join(п, и)
                for п, _, имена in os.walk(root) for и in имена}
    a, b = files(written), files(expected)
    out = [f"нет у конфигуратора: {п}" for п in sorted(set(a) - set(b))]
    out += [f"дописал конфигуратор: {п}" for п in sorted(set(b) - set(a))]
    for п in sorted(set(a) & set(b)):
        with open(a[п], "rb") as x, open(b[п], "rb") as y:
            if x.read() != y.read():
                out.append(f"различие: {п}")
    return out


def main(argv):
    work = os.path.abspath(argv[0])
    v8 = argv[1] if len(argv) > 1 else platform()
    if os.path.isdir(work):
        shutil.rmtree(work)
    src = os.path.join(work, "src")
    os.makedirs(src)
    seeded_uuids()
    sys.path.insert(0, ROOT)
    from meta.add import main as tool
    apply_jobs(src, tool)
    if os.path.isdir(ОЖИДАНИЕ):
        shutil.rmtree(ОЖИДАНИЕ)
    os.makedirs(ОЖИДАНИЕ)
    round_trip(v8, work, src, ОЖИДАНИЕ)
    расхождения = differences(src, ОЖИДАНИЕ)
    for строка in расхождения:
        print(строка)
    print(f"эталоны внешних: {ОЖИДАНИЕ}; расхождений записи с конфигуратором: {len(расхождения)}")
    return 1 if расхождения else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
