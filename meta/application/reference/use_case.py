"""Справка по видам: что можно завести и какие у вида поля."""

from ...domain.kinds import REGISTRY


class ReferenceUseCase:
    """Состав видов и полей — из живых описаний домена и формата.

    Справка печатается по тем же описаниям, по которым инструмент и работает,
    а не по тексту: так ей не с чем разойтись.
    """

    def __init__(self, reference):
        self.reference = reference

    def kinds(self):
        """[(имя вида, описание вида, самостоятельный ли)] — в порядке реестра."""
        return [(name, kind, self.reference.standalone(name))
                for name, kind in REGISTRY.items()]

    def kind(self, name):
        """(описание вида, словари его полей) или `None`, если вида нет."""
        kind = REGISTRY.get(name)
        if kind is None:
            return None
        return kind, self.reference.dictionaries(name)

    @staticmethod
    def names():
        return list(REGISTRY)
