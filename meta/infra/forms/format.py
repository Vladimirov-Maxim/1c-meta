"""Договор реализации формата форм — одна реализация на версию выгрузки.

Сценарий говорит словами домена: «прочитай форму», «примени правки», «роди
форму». Как форма лежит в файле — теги, порядок, идентификаторы, спутники —
знает только реализация, и у каждой версии формата она своя. Выбор
реализации — реестр (`registry.py`), а не ветвление по версии в коде.

Документ для сценария непрозрачен: что вернул `load`, то и уходит обратно
в `view`, `apply`, `dump`, и внутрь никто не заглядывает.
"""


class FormFormat:
    #: версия формата, как она записана в атрибуте `version` корня формы
    version = None

    def matches(self, text):
        """Этот ли формат у файла. Смотрит корень и версию, не разбирая всё."""
        raise NotImplementedError

    def load(self, text):
        """Текст `Form.xml` -> документ."""
        raise NotImplementedError

    def dump(self, document):
        """Документ -> текст. Нетронутые части — символ в символ."""
        raise NotImplementedError

    def view(self, document, owner, name):
        """Документ -> `domain.forms.FormView`."""
        raise NotImplementedError

    def apply(self, document, edits, owner_spec=None, new_id=None):
        """Внести правки в документ. Возвращает пояснения к плану и перечень
        обработчиков, которые должны появиться в модуле."""
        raise NotImplementedError

    def born(self, form, uuid, new_id=None):
        """Новая форма: (узел карточки, документ описания формы)."""
        raise NotImplementedError

    def module_text(self, handlers, edits):
        """Заготовки обработчиков для модуля новой формы; `None` — писать нечего."""
        raise NotImplementedError

    def handler_procedures(self, handlers, edits):
        """[(область модуля, имя, директива, параметры)] — что должно появиться
        в модуле существующей формы; кладёт их туда задание на код."""
        raise NotImplementedError
