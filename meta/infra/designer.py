"""Platform «выгрузка конфигуратора»: реализация договора из `application/ports`.

Здесь сходятся две внешние подробности — словарь формата (`acl/mapping`) и файлы
(`infra/repository`). Приложение о них не знает; оно видит только `Platform`.

Вторая площадка делается рядом и точно так же: класс, реализующий тот же договор
`Platform` (перевести, подготовить, ответить на вопросы домена о конфигурации).
Например, выгрузка EDT — другой формат и другая раскладка каталогов, но тот же
договор, и ни одной правки в сценариях.
"""

import os

from ..acl import mapping, platform_code
from ..application.ports import Platform
from ..domain.edits import DECLARATION
from ..domain.form_events import existing_handler
from ..domain.forms import code_handler_name
from ..domain.model import Refuse
from ..domain.modules import region_place
from .format import FORMAT_VERSION
from .forms import registry as form_formats
from .repository import PreparedForm, Repository, _read_text


class DesignerDump(Repository, Platform):
    """Иерархическая выгрузка конфигуратора, формат 2.21.

    Складывает две подробности: словарь формата (`acl/mapping`) — что как
    называется в XML, и файлы (`infra/repository`) — где что лежит и как
    пишется. Своего у неё только перекладка: всё остальное унаследовано.
    """

    def translate_card(self, spec, uuid, new_id=None):
        return mapping.translate(spec, uuid, new_id=new_id,
                                 configuration=self.configuration_name())

    def translate_node_for(self, spec, uuid, host, owner=None, new_id=None):
        return mapping.translate_node(spec, uuid, host, owner, new_id)

    def read_form(self, owner, name):
        text = self.read_form_text(owner, name)
        if text is None:
            return None
        implementation = form_formats.for_text(text)
        view = implementation.view(implementation.load(text), owner, name)
        # Какие процедуры в модуле есть — чтобы показ отметил обработчик без
        # процедуры: форма со ссылкой в никуда иначе выглядела бы исправной.
        _, _, module_path = self.form_paths(owner, name)
        if os.path.isfile(module_path):
            view.procedures = {m.group(1) for m in map(DECLARATION.match,
                                                       _read_text(module_path).split("\n")) if m}
        return view

    def prepare_form_edits(self, items, new_id):
        """Правки форм -> план. Реализация формата: у новой формы — по версии
        выгрузки, у существующей — по самому файлу."""
        self._writable()
        prepared = []
        for edits, owner_spec, uuid in items:
            if edits.create is not None:
                implementation = form_formats.for_version(FORMAT_VERSION)
                card, document = implementation.born(edits.create, uuid, new_id)
            else:
                text = self.read_form_text(edits.owner, edits.name)
                if text is None:
                    raise Refuse(f"формы «{edits.address}» в выгрузке нет")
                implementation = form_formats.for_text(text)
                card, document = None, implementation.load(text)
            notes, handlers = implementation.apply(document, edits, owner_spec, new_id)
            module = None
            # Модуль пишется, когда его ещё нет: у новой формы и у формы,
            # заведённой без обработчиков. Такой модуль создан текущей задачей,
            # и меток вставок он не несёт.
            if edits.create is not None or (handlers and not self.form_module_exists(
                    edits.owner, edits.name)):
                module, module_notes = implementation.module_text(handlers, edits)
                notes = list(notes) + list(module_notes)
            elif handlers:
                # В существующий модуль процедуры кладёт задание на код — с
                # метками; здесь — что именно ему предстоит положить. Строка
                # «в модуль формы: Процедура …» читалась бы как «будет записано»,
                # поэтому сказано, что пишет задание на код и где у модуля
                # нужная область.
                notes = list(notes)
                _, _, module_path = self.form_paths(edits.owner, edits.name)
                module_text = _read_text(module_path) if os.path.isfile(module_path) else ""
                for region, name, directive, parameters in implementation.handler_procedures(
                        handlers, edits):
                    # Процедура уже есть — заводить не нужно, и подсказка не зовёт
                    # завести существующую. Не годится она обработчиком — это
                    # находка сценария, а не пояснение.
                    есть = existing_handler(module_text.splitlines(), name)
                    if есть is not None:
                        notes.append(f"обработчик {name}: процедура в модуле формы уже есть "
                                     f"(строка {есть.line}) — заводить не нужно")
                        continue
                    # Не «области нет — заведите её», а куда; три сообщения —
                    # отдельными фразами, а заготовка в конце названа заготовкой.
                    where = region_place(module_text.splitlines(), region)
                    notes.append(f"обработчик {name}: в существующий модуль формы инструмент "
                                 "процедуру не пишет — внесите её заданием на код. Где: "
                                 f"{where}. Заготовка: «{directive} Процедура {name}({parameters})»")
            prepared.append(PreparedForm(edits, card, implementation.dump(document),
                                         module, handlers, notes))
        return self.prepare_form_files(prepared)

    @staticmethod
    def _handlers(edits):
        """(где, событие, процедура, элемент) обработчиков задания — тем же
        счётом, что у заготовок: у кода формы имена с приставкой
        «Подключаемый_» — и у событий элементов, и у действий команд: обоих он
        назначает программно."""
        имя = code_handler_name if edits.as_code else (lambda handler: handler)
        handlers = [("таблица" if e.kind == "ТаблицаФормы" else "надпись" if e.kind == "Надпись"
                     else "элемент", event, имя(handler), e.name)
                    for e in edits.all_elements() for event, handler in e.events.items()]
        handlers += [("форма", event, handler, None) for event, handler in edits.events.items()]
        handlers += [("команда", None, имя(c.action), c.name) for c in edits.commands if c.action]
        return handlers

    def handler_signatures(self, edits):
        handlers = self._handlers(edits)
        if not handlers:
            return []
        # Пустые параметры — сигнатура не замерена: у замеренных они есть всегда.
        return [(name, directive, parameters or None) for _, name, directive, parameters
                in form_formats.for_version(FORMAT_VERSION).handler_procedures(handlers, edits)]

    def render_form_code(self, edits, view=None, код_форм=None):
        """(текст кода доработки формы, процедуры-обработчики для модуля формы).

        Язык — по соглашениям команды: методы платформы пишет перекладка,
        другой язык — его файл-диалект.

        Процедуры — с теми же сигнатурами корпуса, что у своих форм, и с теми
        же именами, что в коде (приставка «Подключаемый_»): без них процедуру
        пришлось бы угадывать. Действия команд — тоже: код их назначает,
        а процедуры в модуле не было бы.
        """
        handlers = self._handlers(edits)
        procedures = (form_formats.for_version(FORMAT_VERSION).handler_procedures(handlers, edits)
                      if handlers else [])
        # Где у модуля формы нужная область — или куда её завести: первым
        # элементом вместо имени области; процедура уже есть — так и сказано.
        _, _, module_path = self.form_paths(edits.owner, edits.name)
        module_lines = (_read_text(module_path).splitlines() if os.path.isfile(module_path)
                        else [])

        def где(region, name):
            есть = existing_handler(module_lines, name)
            if есть is not None:
                return f"уже есть в модуле формы (строка {есть.line}) — заводить не нужно"
            return region_place(module_lines, region)

        procedures = [(где(region, name), name, directive, parameters)
                      for region, name, directive, parameters in procedures]
        if код_форм is None or код_форм.встроенный:
            код = platform_code.render(edits, view)
        else:
            код = код_форм.диалект.код(edits, view, код_форм.словарь)
        return код, procedures
