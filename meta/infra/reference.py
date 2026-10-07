"""Справка по видам из описаний формата выгрузки.

Самостоятельность вида и словари значений описаны в перекладке (`acl.schema`),
потому что это знание о том, как вид лежит в выгрузке. Каналу туда нельзя —
он получает то же самое через порт `KindReference`.
"""

from ..acl.schema import SCHEMA
from ..application.ports import KindReference


class DesignerReference(KindReference):
    def standalone(self, kind_name):
        schema = SCHEMA.get(kind_name)
        return bool(schema and schema.container)

    def dictionaries(self, kind_name):
        schema = SCHEMA.get(kind_name)
        return {field.domain: field.dictionary
                for field in (schema.fields if schema else []) if field.dictionary}
