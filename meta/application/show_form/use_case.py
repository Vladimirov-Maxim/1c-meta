"""Показать форму: что в ней уже есть и где она лежит."""

from ...domain import forms as fm
from ...domain.conventions import NEUTRAL
from ...domain.model import Refuse


class ShowFormUseCase:
    """Прочитать форму и вернуть её вид словами домена.

    Это чтение: ничего не проверяет и ничего не пишет. Ответ — на вопрос
    задания «куда вставлять»: имена элементов, их привязки и обработчики.
    """

    def __init__(self, platform, conventions=NEUTRAL):
        self.platform = platform
        self.conventions = conventions

    def execute(self, owner, name):
        """(хозяин, имя) -> (вид формы, файл описания, файл модуля или None, своя ли).

        «Своя» — по соглашению команды о приставке: типовую форму правят только
        кодом, и показ говорит об этом сразу."""
        view = self.platform.read_form(owner, name)
        if view is None:
            address = f"{owner[0]}.{owner[1]}.{name}" if owner else f"Общая.{name}"
            raise Refuse(f"формы «{address}» в выгрузке нет")
        form_file, module_file = self.platform.form_files(owner, name)
        своя = fm.is_ours(owner[1] if owner else None, name, self.conventions.prefixes or None)
        return view, form_file, module_file, своя
