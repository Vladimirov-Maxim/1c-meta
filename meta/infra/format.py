"""Факты о формате выгрузки: пространства имён, версия, объявление, BOM.

Вынесены отдельно, потому что нужны двоим сразу — тому, кто описывает карточку
(`serializer`), и тому, кто превращает её в байты (`tree_lxml`). Это не
подробность библиотеки: другая реализация договора `CardTree` возьмёт отсюда
ровно то же самое.

Все числа сняты с реальной выгрузки, а не приняты на глаз (639 карточек подписок,
все одинаковы): BOM есть, отступ — табуляция, **финального перевода строки
нет**, пустое значение пишется одиночным тегом `<Comment/>`. Служебные файлы
устроены иначе — `Configuration.xml` идёт с CRLF, — поэтому перевод строки
задаётся снаружи, а не зашит здесь.
"""

from ..acl import vocabulary

# Пространства имён шапки карточки: по умолчанию первым, дальше по алфавиту
# префикса. Собирается из таблицы, а не хранится строкой на тысячу символов;
# совпадение с настоящей карточкой закреплено тестом.
NAMESPACES = (
    ("", "http://v8.1c.ru/8.3/MDClasses"),
    ("app", "http://v8.1c.ru/8.2/managed-application/core"),
    ("cfg", "http://v8.1c.ru/8.1/data/enterprise/current-config"),
    ("cmi", "http://v8.1c.ru/8.2/managed-application/cmi"),
    ("ent", "http://v8.1c.ru/8.1/data/enterprise"),
    ("lf", "http://v8.1c.ru/8.2/managed-application/logform"),
    ("pal", "http://v8.1c.ru/8.1/data/ui/colors/palette"),
    ("style", "http://v8.1c.ru/8.1/data/ui/style"),
    ("sys", "http://v8.1c.ru/8.1/data/ui/fonts/system"),
    ("v8", "http://v8.1c.ru/8.1/data/core"),
    ("v8ui", "http://v8.1c.ru/8.1/data/ui"),
    ("web", "http://v8.1c.ru/8.1/data/ui/colors/web"),
    ("win", "http://v8.1c.ru/8.1/data/ui/colors/windows"),
    ("xen", "http://v8.1c.ru/8.3/xcf/enums"),
    ("xpr", "http://v8.1c.ru/8.3/xcf/predef"),
    ("xr", "http://v8.1c.ru/8.3/xcf/readable"),
    ("xs", "http://www.w3.org/2001/XMLSchema"),
    ("xsi", "http://www.w3.org/2001/XMLSchema-instance"),
)

#: префикс -> адрес пространства имён; пустой префикс — пространство по умолчанию
URI = dict(NAMESPACES)

FORMAT_VERSION = vocabulary.FORMAT_VERSION
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
BOM = "﻿"
INDENT = "\t"

#: корень документа -> его пространства имён
ROOT_NAMESPACES = {
    "MetaDataObject": NAMESPACES,
    "DataCompositionSchema": vocabulary.SCHEMA_NAMESPACES,
    # Управляемой формы здесь нет намеренно: её пространства имён — знание
    # реализации формата форм, и корень формы несёт их сам, атрибутами узла.
}

# Только именованные префиксы: пространство по умолчанию у схемы своё,
# и подмена им общего увела бы все карточки не туда.
URI.update({prefix: uri for prefix, uri in vocabulary.SCHEMA_NAMESPACES if prefix})
