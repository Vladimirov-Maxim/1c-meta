"""Пересоздание объектов проекта EDT писателем инструмента — против того, что лежит в проекте.

Каждый объект названного вида читается инструментом (`read_spec`), дополняется
умолчаниями вида и записывается заново тем же путём, что и создание объекта, —
с uuid из файла. Карточка и модуль обязаны совпасть с файлами проекта байт в
байт: так проверяется запись там, где оракула EDT нет (расширение конфигурации
EDT импортирует только вместе с базовым проектом).

Заимствованные объекты (`objectBelonging`) не пересоздаются: инструмент их не
заводит. Идентификаторы, которые писатель порождает (типы, реквизиты), берутся
из файла по порядку.

Ожидаемые расхождения — не ошибки записи: синонимы на других языках (модель
синонима — один `ru`), хвостовые пробелы значений (чтение их обрезает), формы и
команды в карточке (их добавляют отдельные операции), файлы с переводами строк
не как у большинства в проекте; модули не в UTF-8 пропускаются.

    py -3 tools/edt_recreate_check.py <каталог src проекта EDT> [<вид>=ОбщийМодуль]
"""

import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.acl import mapping  # noqa: E402
from meta.acl.vocabulary import BOOLEAN  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.infra import serializer  # noqa: E402
from meta.infra.edt_dump import EdtDump  # noqa: E402

UUID = re.compile(rb'uuid="([0-9a-f-]{36})"')
IDS = re.compile(rb'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"')


def main(argv):
    root = argv[0]
    вид = argv[1] if len(argv) > 1 else "ОбщийМодуль"
    площадка = EdtDump(root)
    каталог = os.path.join(root, mapping.container_of(вид))
    итог, примеры = collections.Counter(), {}
    for имя in sorted(os.listdir(каталог)):
        путь = os.path.join(каталог, имя, имя + ".mdo")
        было = open(путь, "rb").read()
        if b"<objectBelonging>" in было:
            итог["заимствован — пропущен"] += 1
            continue
        spec, _ = площадка.read_spec([(вид, имя)])
        модуль = os.path.join(каталог, имя, "Module.bsl")
        if вид == "ОбщийМодуль" and os.path.isfile(модуль):
            try:
                spec.fields["текст"] = open(модуль, encoding="utf-8-sig", newline="").read().replace("\r\n", "\n")
            except UnicodeDecodeError:              # модуль не в UTF-8 (встречается UTF-16)
                итог["модуль не UTF-8 — пропущен"] += 1
                continue
        # EDT не пишет значение, равное умолчанию EMF: нет флага — он выключен,
        # а не «не задан». Иначе дополнение умолчаниями вида включило бы его.
        for поле in mapping._schema(вид).fields:
            if поле.value_kind == BOOLEAN and поле.domain not in spec.fields:
                spec.fields[поле.domain] = False
        полная = kind_of(вид).fill(spec)
        # порождаемые типы, реквизиты и прочее с идентификаторами получают их
        # из файла по порядку: сверяется запись, а не случайные uuid
        свои = iter(m.decode() for m in IDS.findall(было)[1:])
        card = площадка.translate_card(полная, UUID.search(было).group(1).decode(),
                                       new_id=lambda свои=свои: next(свои, "00000000-0000-0000-0000-000000000000"))
        текст = площадка.tree.serialize(площадка.tree.build(serializer.card_to_node(card)))
        стало = площадка._edt_text(текст, lambda *_: None).replace("\n", площадка.eol).encode("utf-8")
        if стало != было:
            итог["карточка расходится"] += 1
            примеры.setdefault("карточка", имя)
            continue
        if вид == "ОбщийМодуль" and os.path.isfile(модуль):
            текст_модуля = spec.fields["текст"]
            if площадка._encode(текст_модуля) != open(модуль, "rb").read():
                итог["модуль расходится"] += 1
                примеры.setdefault("модуль", имя)
                continue
        итог["совпало"] += 1
    print(dict(итог))
    for что, пример in примеры.items():
        print(f"   {что}: например {пример}")


if __name__ == "__main__":
    main(sys.argv[1:])
