"""Площадка «выгрузка внешней обработки или отчёта».

Внешняя обработка выгружается конфигуратором иначе, чем объект конфигурации:

    <Каталог>/<Имя>.xml                           карточка — корень выгрузки
    <Каталог>/<Имя>/Ext/ObjectModule.bsl          модуль объекта
    <Каталог>/<Имя>/Forms/<Форма>.xml             формы — как у обработки
    <Каталог>/<Имя>/Templates/<Макет>.xml         макеты — так же

`Configuration.xml` нет, реестра тоже: карточка сама называет себя корнем.
Формат текста тот же, что у выгрузки конфигурации (UTF-8 с BOM, CRLF,
версия 2.21) — площадка наследует её запись целиком и меняет только то, где
лежат карточки внешних видов и чего у такой выгрузки не бывает.

Всё, что здесь сказано о составе карточек, проверено кругом через
конфигуратор 8.5.1 на пустой базе: записали — загрузили командой
`/LoadExternalDataProcessorOrReportFromFiles` — выгрузили обратно
`/DumpExternalDataProcessorOrReportToFiles` — сверили байты
(`tools/epf_oracle.py`).
"""

import os
import re

from ..acl import vocabulary
from ..domain.model import Refuse
from .designer import DesignerDump

#: Корни карточек внешней выгрузки.
EXTERNAL_ROOTS = (b"<ExternalDataProcessor ", b"<ExternalReport ")


class ExternalDump(DesignerDump):
    """Каталог с выгрузками внешних обработок и отчётов (или пустой —
    под новую)."""

    def _check_root(self):
        if os.path.isfile(os.path.join(self.root, "Configuration.xml")):
            raise Refuse(f"«{self.root}» — выгрузка конфигурации, а не внешней обработки")

    # --- где что лежит ---

    def registry_path(self):
        return None

    def _folder(self, container):
        if container in vocabulary.EXTERNAL_CONTAINERS:
            return self.root
        вид = next((k for k, v in vocabulary.FOLDERS.items() if v == container), container)
        raise Refuse(f"в выгрузке внешней обработки объектов вида «{вид}» нет: "
                     "в ней только внешние обработка и отчёт и их части")

    def form_paths(self, owner, name):
        if owner is None:
            raise Refuse("у внешней обработки общих форм не бывает — форма называется "
                         "по хозяину: «ВнешняяОбработка.Имя.Форма»")
        return super().form_paths(owner, name)

    # --- что за выгрузка ---

    def external_cards(self):
        """Карточки внешних объектов в корне: [путь]."""
        найдено = []
        for имя in sorted(os.listdir(self.root)):
            путь = os.path.join(self.root, имя)
            if имя.lower().endswith(".xml") and os.path.isfile(путь):
                with open(путь, "rb") as source:
                    head = source.read(self.EOL_HEAD)
                if any(root in head for root in EXTERNAL_ROOTS):
                    найдено.append(путь)
        return найдено

    def configuration_name(self):
        return None

    def format_version(self):
        """Версия формата — у первой карточки в корне; пустой каталог — `None`."""
        for путь in self.external_cards():
            with open(путь, encoding="utf-8-sig") as source:
                found = self.VERSION.search(source.read(self.EOL_HEAD))
            if found:
                return found.group(1)
        return None

    # --- чего во внешней выгрузке не делают ---

    def prepare_deletion(self, paths):
        raise Refuse("удаление во внешней выгрузке не поддержано: удалите каталог "
                     "обработки вместе с её карточкой")

    def prepare_rename(self, renames):
        raise Refuse("переименование во внешней выгрузке не поддержано")


#: Признак: каталог похож на выгрузку внешней обработки по содержимому.
def is_external(root):
    """В корне есть карточка внешнего объекта."""
    if not os.path.isdir(root):
        return False
    for имя in os.listdir(root):
        путь = os.path.join(root, имя)
        if имя.lower().endswith(".xml") and os.path.isfile(путь):
            with open(путь, "rb") as source:
                if re.search(rb"<External(DataProcessor|Report) ", source.read(4096)):
                    return True
    return False
