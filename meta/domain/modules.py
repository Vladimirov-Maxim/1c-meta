"""Модуль как его называет задание: адресом по метаданным или путём файла.

Адрес — тот же, каким модули называет bsl-ls: `ОбщийМодуль.мой_X`,
`Документ.мой_Заявка.МодульОбъекта`, `Обработка.X.Форма.Форма`,
`Документ.X.Команда.Печать`. Один модуль — одно имя во всех инструментах;
путь к файлу из него выводит площадка.

Здесь только грамматика: сколько частей, какие слова на каких местах. Какие
виды бывают у модулей и в каких каталогах они лежат — знание формата
выгрузки, оно в перекладке (`acl.modules`). Путь файла (`path`) тоже
принимается: сценарий ссылку не раскрывает в любом случае.
"""

from dataclasses import dataclass

from .model import Refuse

#: Собственные модули объекта — третьим словом адреса.
OWN_MODULES = ("МодульОбъекта", "МодульМенеджера", "МодульНабораЗаписей",
               "МодульМенеджераЗначения")
#: Маркеры вложенного модуля: за ними — имя формы или команды.
FORM_MARK = "Форма"
COMMAND_MARK = "Команда"
#: Виды, у которых модуль один, и адрес из двух частей его однозначно называет.
SINGLE_MODULE = {"ОбщийМодуль": "Модуль", "WebСервис": "Модуль", "HTTPСервис": "Модуль",
                 "ОбщаяКоманда": "МодульКоманды", "ОбщаяФорма": FORM_MARK}
#: Модули самой конфигурации: `Конфигурация.МодульСеанса`.
CONFIGURATION = "Конфигурация"
CONFIGURATION_MODULES = ("МодульСеанса", "МодульУправляемогоПриложения",
                         "МодульОбычногоПриложения", "МодульВнешнегоСоединения")


@dataclass(frozen=True)
class ModuleAddress:
    """Адрес модуля по метаданным.

    `kind`, `name` — вид и имя объекта (у модуля конфигурации имени нет);
    `module` — какой модуль: слово из `OWN_MODULES`, «Модуль» у общего модуля
    и сервисов, «МодульКоманды» у общей команды, `FORM_MARK`/`COMMAND_MARK`
    у формы и команды, слово из `CONFIGURATION_MODULES`; `sub` — имя формы
    или команды объекта.
    """

    kind: str
    name: str
    module: str
    sub: str = None

    def __str__(self):
        if self.kind == CONFIGURATION:
            return f"{CONFIGURATION}.{self.module}"
        if self.kind in SINGLE_MODULE:
            return f"{self.kind}.{self.name}"
        if self.sub:
            return f"{self.kind}.{self.name}.{self.module}.{self.sub}"
        return f"{self.kind}.{self.name}.{self.module}"

    @classmethod
    def parse(cls, text):
        """Текст адреса -> адрес. Неоднозначный или битый — отказ с подсказкой."""
        parts = [p for p in (text or "").split(".") if p]
        if len(parts) < 2 or any(not p.strip() for p in parts):
            raise Refuse(f"адрес модуля «{text}» — пишется «Вид.Имя[.Модуль]», "
                         "например «ОбщийМодуль.мой_X» или «Документ.мой_Заявка.МодульОбъекта»")
        kind, name, rest = parts[0], parts[1], parts[2:]
        if kind == CONFIGURATION:
            if rest or name not in CONFIGURATION_MODULES:
                raise Refuse(f"у конфигурации модули: {', '.join(CONFIGURATION_MODULES)}; "
                             f"получено «{text}»")
            return cls(CONFIGURATION, "", name)
        if kind in SINGLE_MODULE:
            if rest:
                raise Refuse(f"у вида «{kind}» модуль один — адрес «{kind}.{name}» без "
                             f"продолжения; получено «{text}»")
            return cls(kind, name, SINGLE_MODULE[kind])
        if not rest:
            raise Refuse(
                f"у «{kind}.{name}» модулей может быть несколько — назовите нужный: "
                f"{kind}.{name}.МодульОбъекта, {kind}.{name}.МодульМенеджера, "
                f"{kind}.{name}.Форма.<ИмяФормы>, {kind}.{name}.Команда.<ИмяКоманды>")
        if rest[0] in OWN_MODULES and len(rest) == 1:
            return cls(kind, name, rest[0])
        # Форма пишется и как «…Форма.Имя», и как «…Форма.Имя.Форма» —
        # второе принимает bsl-ls, и один адрес должен работать везде.
        if rest[0] == FORM_MARK and (len(rest) == 2 or (len(rest) == 3 and rest[2] == FORM_MARK)):
            return cls(kind, name, FORM_MARK, rest[1])
        if rest[0] == COMMAND_MARK and len(rest) == 2:
            return cls(kind, name, COMMAND_MARK, rest[1])
        # «Вид.Имя.ИмяФормы» — так форму называют инструменты форм; один
        # модуль должен звать одним адресом везде.
        # Если это не форма, площадка откажет и назовёт модули объекта.
        if (len(rest) == 1 and rest[0] not in (FORM_MARK, COMMAND_MARK)
                and not rest[0].startswith("Модуль")):      # «Модуль…» — промах в слове модуля
            return cls(kind, name, FORM_MARK, rest[0])
        raise Refuse(
            f"адрес модуля «{text}» не разобран: третьим словом бывает "
            f"{', '.join(OWN_MODULES)}, «{FORM_MARK}.<Имя>» или «{COMMAND_MARK}.<Имя>»")


def own_qualifiers(address):
    """Слова, которые перед точкой означают сам этот модуль.

    `мой_X.Метод()` внутри общего модуля `мой_X`, `Документы.Имя.Метод()` в
    модуле менеджера, `ЭтотОбъект.Метод()` в модулях объекта и формы — вызовы
    своего метода; всё прочее через точку — чужого. Адрес неизвестен (модуль
    назван путём вне шаблонов) — остаются только `ЭтотОбъект` и `ЭтаФорма`:
    в модуле, где их нет, они и не встретятся.
    """
    own = {"ЭтотОбъект", "ЭтаФорма"}
    if address is not None and (address.kind == "ОбщийМодуль" or address.module == "МодульМенеджера"):
        own.add(address.name)
    return own


@dataclass(frozen=True)
class ModuleRef:
    """Модуль в задании: адрес по метаданным или путь файла — ровно одно.

    Сценарий эту ссылку не раскрывает: передаёт площадке и печатает в ответе.
    """

    address: ModuleAddress = None
    path: str = None

    def __str__(self):
        return str(self.address) if self.address is not None else self.path


# --- области модуля формы ---------------------------------------------------------

#: Порядок областей модуля формы — шаблон стандарта «Структура модуля»
#: (#std455, п. 1.6). Областей таблиц бывает несколько: имя — приставка и
#: имя таблицы формы.
FORM_MODULE_REGIONS = ("ОписаниеПеременных", "ОбработчикиСобытийФормы",
                       "ОбработчикиСобытийЭлементовШапкиФормы",
                       "ОбработчикиСобытийЭлементовТаблицыФормы",
                       "ОбработчикиКомандФормы", "СлужебныеПроцедурыИФункции")
_TABLE_REGION = "ОбработчикиСобытийЭлементовТаблицыФормы"


def top_regions(lines):
    """Области верхнего уровня: [(имя, строка «#Область», строка «#КонецОбласти»)].

    Номера с единицы. Незакрытая область кончается концом модуля.
    """
    found, depth, open_at = [], 0, None
    for number, line in enumerate(lines, start=1):
        слово = line.strip()
        if слово.startswith("#Область"):
            if depth == 0:
                open_at = (слово[len("#Область"):].strip(), number)
            depth += 1
        elif слово.startswith("#КонецОбласти") and depth:
            depth -= 1
            if depth == 0 and open_at:
                found.append((open_at[0], open_at[1], number))
                open_at = None
    if open_at:
        found.append((open_at[0], open_at[1], len(lines)))
    return found


def regions(lines):
    """Все области модуля, вложенные тоже: [(имя, строка «#Область», строка
    «#КонецОбласти»)] по порядку начала. Незакрытая кончается концом модуля."""
    found, stack = [], []
    for number, line in enumerate(lines, start=1):
        слово = line.strip()
        if слово.startswith("#Область"):
            stack.append((слово[len("#Область"):].strip(), number))
        elif слово.startswith("#КонецОбласти") and stack:
            имя, начало = stack.pop()
            found.append((имя, начало, number))
    found.extend((имя, начало, len(lines)) for имя, начало in stack)
    return sorted(found, key=lambda область: область[1])


def _rank(region):
    for место, имя in enumerate(FORM_MODULE_REGIONS):
        if region == имя or (имя == _TABLE_REGION and region.startswith(имя)):
            return место
    return None


def region_place(lines, region):
    """Где в модуле формы область и где её завести, если её нет, — словами.

    Одно «области нет — заведите её» не говорит, куда: место пришлось бы
    искать самому. Соседи — по шаблону стандарта, номера строк — по модулю
    как есть.
    """
    области = top_regions(lines)
    for имя, начало, конец in области:
        if имя == region:
            return f"в область «{region}» (строки {начало}-{конец})"
    место = _rank(region)
    известные = [(имя, начало, конец) for имя, начало, конец in области
                 if _rank(имя) is not None]
    if место is None or not известные:
        return (f"области «{region}» в модуле нет — заведите её; областей шаблона "
                "стандарта #std455 в модуле нет, место — по смыслу")
    раньше = [о for о in известные if _rank(о[0]) <= место]
    позже = [о for о in известные if _rank(о[0]) > место]
    куда = []
    if раньше:
        куда.append(f"после «{раньше[-1][0]}» (её #КонецОбласти — строка {раньше[-1][2]})")
    if позже:
        куда.append(f"перед «{позже[0][0]}» (строка {позже[0][1]})")
    return (f"области «{region}» в модуле нет — заведите её {', '.join(куда)}: "
            "порядок областей модуля формы — шаблон стандарта #std455")
