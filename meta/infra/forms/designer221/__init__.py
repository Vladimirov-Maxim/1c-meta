"""Формат управляемой формы 2.21 — реализация договора `FormFormat`."""

from ....acl.mapping import Node
from ....domain.model import Refuse
from ...tree_lxml import LxmlCardTree
from . import birth, editor, module
from . import vocabulary as voc

TREE = LxmlCardTree()


class Format221:
    version = voc.FORMAT_VERSION

    def matches(self, text):
        head = text[:4096]
        return "<Form " in head and f'version="{self.version}"' in head

    def load(self, text):
        return TREE.parse(text)

    def dump(self, document):
        return TREE.serialize(document)

    def view(self, document, owner, name):
        return editor.view(document, owner, name)

    def apply(self, document, edits, owner_spec=None, new_id=None):
        return editor.Editor(document, edits, owner_spec, new_id).apply()

    def born(self, form, uuid, new_id=None):
        card = birth.card_node(form, uuid)
        skeleton = TREE.build(birth.skeleton_node(form, new_id))
        return card, skeleton

    def document_text(self, node):
        """Узел корня формы (`Form` с детьми) -> текст `Form.xml`: с объявлениями
        пространств имён и версией, как у формы, которую рождает инструмент."""
        attrs = {("xmlns" if not prefix else f"xmlns:{prefix}"): uri for prefix, uri in voc.NAMESPACES}
        attrs["version"] = voc.FORMAT_VERSION
        return TREE.serialize(TREE.build(Node("Form", attrs=attrs, children=node.children)))

    def module_text(self, handlers, edits):
        return module.module_text(handlers, edits)

    def handler_procedures(self, handlers, edits):
        return module.procedures(handlers, edits)[0]

    def __repr__(self):
        return f"Format221({self.version})"


__all__ = ["Format221", "Refuse"]
