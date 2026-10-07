"""Круг переходника EDT: карточка `.mdo` -> дерево в форме выгрузки -> карточка `.mdo`.

Тот путь, которым площадка EDT читает и пишет объект: байты -> узел EDT
(`infra.edt_xml`) -> обратная перекладка (`acl.edt_card.Reverse`) -> дерево
lxml в форме выгрузки -> узел -> прямая перекладка (`Translation`) -> байты.
Нетронутый объект обязан вернуться байт в байт: только тогда правка одного
свойства меняет в файле одну строку.

Запуск: `py -3 tools/edt_adapter_roundtrip.py <каталог исходников EDT> [предел]`.
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.acl import edt_card  # noqa: E402
from meta.infra import edt_xml  # noqa: E402
from meta.infra.tree_lxml import LxmlCardTree  # noqa: E402

LONG = r"\\?" + "\\" if os.name == "nt" else ""


def main(argv):
    root = argv[0]
    предел = int(argv[1]) if len(argv) > 1 else None
    tree = LxmlCardTree()
    итог, примеры, беды = collections.Counter(), {}, collections.Counter()
    for папка, _, имена in os.walk(root):
        for имя in имена:
            if not имя.endswith(".mdo"):
                continue
            путь = os.path.join(папка, имя)
            with open(LONG + os.path.abspath(путь), "rb") as f:
                было = f.read().replace(b"\r\n", b"\n")
            узел = edt_xml.parse(было)
            выгрузка = edt_card.Reverse().card(узел)
            # как у площадки: дерево lxml и обратно в узел
            выгрузка = tree.to_node(tree.build(выгрузка))
            перекладка = edt_card.Translation()
            стало = edt_xml.to_bytes(перекладка.card(выгрузка))
            for беда in перекладка.problems:
                беды[беда.split(": ", 1)[-1]] += 1
            if стало == было:
                итог["совпало"] += 1
            else:
                итог["разошлось"] += 1
                a, b = было.decode("utf-8").split("\n"), стало.decode("utf-8").split("\n")
                i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
                ключ = (a[i].strip()[:50] if i < len(a) else "<конец>", b[i].strip()[:50] if i < len(b) else "<конец>")
                примеры.setdefault(ключ, [0, f"{os.path.relpath(путь, root)}:{i + 1}"])
                примеры[ключ][0] += 1
            if предел and sum(итог.values()) >= предел:
                break
        if предел and sum(итог.values()) >= предел:
            break
    print(dict(итог))
    for (a, b), (n, где) in sorted(примеры.items(), key=lambda x: -x[1][0])[:30]:
        print(f"{n:6} {где}\n         было:  {a}\n         стало: {b}")
    for беда, n in беды.most_common(20):
        print(f"{n:6} {беда}")


if __name__ == "__main__":
    main(sys.argv[1:])
