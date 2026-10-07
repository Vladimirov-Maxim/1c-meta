"""Сверка перекладки «выгрузка конфигуратора -> проект EDT» с тем, что пишет EDT.

Вход — пара деревьев одной конфигурации: выгрузка конфигуратора и проект EDT
(например, проект EDT и его выгрузка командой EDT `export`, или выгрузка и её
импорт командой `import`). Каждая карточка выгрузки перекладывается
(`acl.edt_card`) и сравнивается побайтно с карточкой `.mdo` проекта.

Запуск: `py -3 tools/edt_convert_check.py <выгрузка> <исходники EDT> [вид,вид] [предел]`.
Печатает сводку: совпало, разошлось (первые различия по видам), чего перекладка
не умеет (`problems`).
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.acl import edt_card  # noqa: E402
from meta.infra import edt_xml, layout  # noqa: E402
from meta.infra.tree_lxml import LxmlCardTree  # noqa: E402

LONG = r"\\?" + "\\" if os.name == "nt" else ""
TREE = LxmlCardTree()


def read(path):
    with open(LONG + os.path.abspath(path), "rb") as f:
        return f.read()


def designer_node(path):
    текст = read(path).decode("utf-8-sig").replace("\r\n", "\n")
    return TREE.to_node(TREE.parse(текст))


def main(argv):
    выгрузка, edt = argv[0], argv[1]
    виды = set(argv[2].split(",")) if len(argv) > 2 and argv[2] else None
    предел = int(argv[3]) if len(argv) > 3 else None
    итог, различия, беды = collections.Counter(), {}, collections.Counter()
    примеры_бед = {}
    for каталог, (вид, _) in sorted(layout.OBJECT_FOLDERS.items()):
        if виды and вид not in виды and каталог not in виды:
            continue
        папка = os.path.join(выгрузка, каталог)
        if not os.path.isdir(папка):
            continue
        счёт = 0
        for файл in sorted(os.listdir(папка)):
            if not файл.endswith(".xml"):
                continue
            имя = файл[:-4]
            ожидание = os.path.join(edt, каталог, имя, имя + ".mdo")
            if not os.path.exists(LONG + os.path.abspath(ожидание)):
                итог["нет .mdo"] += 1
                continue

            def спутник(тег, имя_спутника, каталог=каталог, имя=имя):
                папка_спутника = {"Form": "Forms", "Template": "Templates", "Command": "Commands",
                                  "Subsystem": "Subsystems"}.get(тег)
                путь = os.path.join(выгрузка, каталог, имя, папка_спутника or тег, имя_спутника + ".xml")
                return designer_node(путь) if os.path.exists(LONG + os.path.abspath(путь)) else None

            перекладка = edt_card.Translation(спутник)
            узел = перекладка.card(designer_node(os.path.join(папка, файл)))
            for беда in перекладка.problems:
                ключ = беда.split(": ", 1)[1] if ": " in беда else беда
                ключ = f"{каталог}: {ключ}"
                беды[ключ] += 1
                примеры_бед.setdefault(ключ, f"{каталог}/{имя}: {беда}")
            стало = edt_xml.to_bytes(узел)
            было = read(ожидание).replace(b"\r\n", b"\n")
            if стало == было:
                итог["совпало"] += 1
            else:
                итог["разошлось"] += 1
                a, b = было.decode("utf-8").split("\n"), стало.decode("utf-8").split("\n")
                i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
                ключ = (каталог, a[i].strip()[:50] if i < len(a) else "<конец>",
                        b[i].strip()[:50] if i < len(b) else "<конец>")
                различия.setdefault(ключ, [0, f"{каталог}/{имя}:{i + 1}"])
                различия[ключ][0] += 1
            счёт += 1
            if предел and счёт >= предел:
                break
    print(dict(итог))
    print(f"\nразличий (первая строка расхождения): {len(различия)}")
    for (_, было, стало), (n, где) in sorted(различия.items(), key=lambda x: -x[1][0])[:40]:
        print(f"{n:6} {где}\n         было:  {было}\n         стало: {стало}")
    print(f"\nчего перекладка не умеет: {len(беды)}")
    for ключ, n in беды.most_common(40):
        print(f"{n:6} {примеры_бед[ключ]}")


if __name__ == "__main__":
    main(sys.argv[1:])
