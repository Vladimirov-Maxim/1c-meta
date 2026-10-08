"""Круг текста EDT: каждый файл проекта разбирается в узел и пишется обратно —
байты обязаны совпасть (`infra.edt_xml`).

Запуск: `py -3 tools/edt_text_roundtrip.py <каталог исходников EDT> [.mdo,.form]`.
Файлы с CRLF (проект, выгруженный `git archive` при `core.autocrlf=true`)
сравниваются после приведения переводов строк к LF.
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.infra import edt_xml  # noqa: E402

LONG = r"\\?" + "\\" if os.name == "nt" else ""


def main(argv):
    root = argv[0]
    suffixes = tuple((argv[1] if len(argv) > 1 else ".mdo").split(","))
    итог, примеры = collections.Counter(), {}
    for папка, _, имена in os.walk(root):
        for имя in имена:
            if not имя.endswith(suffixes):
                continue
            путь = os.path.join(папка, имя)
            with open(LONG + os.path.abspath(путь), "rb") as f:
                было = f.read().replace(b"\r\n", b"\n")
            стало = edt_xml.to_bytes(edt_xml.parse(было))
            if стало == было:
                итог["совпало"] += 1
                continue
            итог["разошлось"] += 1
            a, b = было.decode("utf-8").split("\n"), стало.decode("utf-8").split("\n")
            i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
            ключ = (a[i].strip()[:60] if i < len(a) else "<конец>")
            примеры.setdefault(ключ, (os.path.relpath(путь, root), i + 1, a[i] if i < len(a) else "",
                                      b[i] if i < len(b) else ""))
    print(dict(итог))
    for путь, строка, a, b in list(примеры.values())[:25]:
        print(f"{путь}:{строка}\n   было:  {a!r}\n   стало: {b!r}")


if __name__ == "__main__":
    main(sys.argv[1:])
