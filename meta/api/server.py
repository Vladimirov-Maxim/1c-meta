"""Сервер MCP: инструменты агента поверх контроллера.

Транспорт и ничего больше: принять запрос, отдать контроллеру, ответ
отрисовать языком ответов. Отказ инструмента возвращается текстом «ОТКАЗ: …»,
а не исключением: агент читает ответ и может исправить задание сам, а на
ошибке транспорта видит только, что что-то не получилось.
"""

import json
from functools import wraps
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import TextContent
from pydantic import Field, ValidationError

from ..domain.conventions import НЕЙТРАЛЬНЫЕ
from ..domain.model import Refuse
from ..report import Подсказки
from ..report.code import code_lines
from ..report.forms import element_properties, shown_form
from ..report.normalize import normalize_lines
from ..report.objects import shown_object
from ..report.plan import plan_check_lines, plan_emit_json
from ..report.reference import CODE_WORDS, code_rules, is_a_type_word, kind_fields, overview, types
from ..report.result import result_lines
from ..report.verify import verify_lines
from .models import (
    AtomicRoles,
    AttributeAddition,
    ChildAddition,
    CodeModule,
    Deletion,
    FieldChange,
    FormJob,
    MetadataObject,
    MethodMove,
    ObjectRename,
    PlanObject,
    метаданные_в_язык_заданий,
)

ИНСТРУКЦИЯ = """Инструмент исходников конфигурации 1С: пишет объекты метаданных и формы
так же, как конфигуратор (выгрузка в файлы) или 1C:EDT (проект EDT), — без
ручной правки XML. Формат определяется по каталогу `repo` сам: выгрузка —
каталог с Configuration.xml, проект EDT — каталог `src` проекта (с
Configuration/Configuration.mdo); задания одни и те же. Иной каталог —
внешние обработки (виды ВнешняяОбработка, ВнешнийОтчет).

Порядок работы: show — посмотреть, что уже есть (форма — деревом элементов:
имена, привязки, обработчики — оттуда берутся места вставки); fields —
какие поля принимает вид; *_check — просмотр задания: находки и план, на
диск не пишется ничего; *_apply — то же задание с записью. Файлы пишутся все
разом или ни один.

Формы — forms_check / forms_apply. Объекты и их части — metadata_check /
metadata_apply: одна операция из objects, attributes, additions, changes,
deletions, renames, atomic_roles. Задания описаны типами; тип значения
пишется так же, как его печатает show («Строка(50)», «Справочник.Имя»).
Код BSL — code_check / code_apply: правка вставками — метки
ИЗМЕНЕН/ДОБАВЛЕН/УДАЛЕН с датой, задачей и автором ставит инструмент; модуль
называется адресом, как у bsl-ls; правила разбора — fields(kind="Код").
Проверка правок задачи — verify: файлы, которые задача добавила и изменила
против базы (git или пара каталогов «эталон — копия»), по правилам меток
вставок, формата файлов и прав на новые объекты; normalize_check /
normalize_apply возвращают этим файлам формат выгрузки. План изменений —
plan_check (план против факта задачи) и plan_emit (факт в формате плана).
Писать можно только в выгрузки, разрешённые настройкой сервера. Задание,
которое не выполнится, отвечает строкой «ОТКАЗ: …»."""


def инструкция(соглашения):
    """Инструкция сервера с соглашениями команды: приставку, метку команды и
    язык кода формы агент узнаёт до первого задания, а не из отказа."""
    код_форм = соглашения.код_форм
    язык = код_форм.диалект.описание(код_форм.словарь)
    части = []
    if соглашения.приставка:
        части.append(f"приставка доработок — «{соглашения.приставка}»: типовую форму (без "
                     "приставки у объекта и формы) инструмент в XML не правит, с «код»: true "
                     f"он выдаёт фрагмент кода доработки формы — {язык}")
    else:
        части.append("приставки доработок нет — правила о ней не применяются, любая форма "
                     "правится в XML")
    if соглашения.тег_меток:
        части.append(f"метка команды в метках вставок — «{соглашения.тег_меток}»")
    return ИНСТРУКЦИЯ + "\n\nСоглашения команды (профиль): " + "; ".join(части) + "."


def _подсказки(записать):
    return Подсказки(
        поля='fields(kind="{вид}")',
        записать=записать,
        подробно="verbose=true",
        код="code_check, затем code_apply",
        подвал_обзора=(
            '\nПоля вида:  fields(kind="<Вид>")        Описание типа:  fields(kind="Тип")'
            '        Правка кода:  fields(kind="Код")',
            "Что лежит в выгрузке:  show(repo, address[, element])\n"
            "   объект — «Справочник.мой_Эталон», "
            "форма — «Документ.мой_Заявка.ФормаДокумента»",
        ),
        ключ_модуля="module",
        # Формы у MCP — свои инструменты, а не операция рядом с objects:
        # формат задания терминала в эту справку не переносится.
        формы="Формы — не операция metadata_*: их заводят и дополняют инструменты "
              "forms_check / forms_apply, задание на формы описано их схемой; свойства "
              'элемента — fields(kind="ПолеВвода") и т. п.',
        ветвь="«element»",
    )


ФОРМЫ = _подсказки("вызовите forms_apply с тем же заданием")
КОД = _подсказки("вызовите code_apply с тем же заданием")
МЕТАДАННЫЕ = _подсказки("вызовите metadata_apply с тем же заданием")

# Описания параметров: без них формат даты и смысл `repo` приходится угадывать.
Выгрузка = Annotated[str, Field(description="полный путь к корню исходников: выгрузки (каталог с "
                                            "Configuration.xml), проекта EDT (каталог src) или "
                                            "внешних обработок (каталог с их карточками; пустой — "
                                            "под новую); работать можно только в разрешённых "
                                            "настройкой сервера")]
Задача = Annotated[str, Field(description="ИД задачи для меток вставок, например ЗАДАЧА-123")]
# Пустое умолчание у даты и автора читается как «необязательны», поэтому
# сказано прямо: обязательны они для любой правки, пусты — только у отката.
Дата = Annotated[str, Field(description="дата меток, дд.мм.гггг — обязательна для правок, "
                                        "переименования и переноса; пустой — только у "
                                        "чистого отката")]
Автор = Annotated[str, Field(description="автор меток: только имя — метку команды и ИД "
                                         "задачи ставит инструмент; обязателен для правок, "
                                         "переименования и переноса; пустой — только у "
                                         "чистого отката")]

ВыгрузкаПодGit = Annotated[str | None, Field(description="полный путь к исходникам под git — выгрузке "
                                                          "(Configuration.xml) или каталогу src проекта "
                                                          "EDT; или пара baseline + target")]
База = Annotated[str, Field(description="база сверки — ревизия до задачи (коммит), по умолчанию HEAD")]
Ревизия = Annotated[str | None, Field(description="ревизия с правками задачи вместо рабочей копии")]
Эталон = Annotated[str | None, Field(description="каталог «до» — эталон обработки вне репозитория")]
Копия = Annotated[str | None, Field(description="каталог «после» — правленая копия; вместе с baseline")]
ЗадачаПроверки = Annotated[str | None, Field(description="ИД задачи: без него правка внутри чужой "
                                                         "вставки не проверяется")]
Только = Annotated[list[str] | None, Field(description="коды правил, находки которых нужны; пусто — все")]
ОбъектыПлана = Annotated[list[PlanObject], Field(description="объекты плана — по объекту на "
                                                           "то, что задача создаёт, меняет или удаляет")]

# Смысл `verbose` у каждого инструмента свой — и описание у каждого своё.
ПодробноПоказ = Annotated[bool, Field(description="показать и спутников элементов формы — "
                                                  "меню, подсказки, дополнения таблиц")]
ПодробноФормы = Annotated[bool, Field(description="показать XML формы, который будет записан")]
ПодробноКод = Annotated[bool, Field(description="длинные блоки показа — целиком, а не краями")]
ПодробноЗапись = Annotated[bool, Field(description="показать записанный текст, а не только "
                                                   "номера строк")]
ПодробноМетаданные = Annotated[bool, Field(description="показать все поля, включая решённые "
                                                       "за вас, и XML, который будет записан")]
Принято = Annotated[list[str] | None, Field(
    description="коды предупреждений, принятых осознанно, — как в ответе, без скобок: "
                "[\"РОЛЬ-ШАБЛОН-НЕ-ПРАВИЛО\"]; запись предупреждение не останавливает, "
                "«принято» лишь помечает его, ошибку принять нельзя")]


def словами(работа):
    """Отказ инструмента — ответ, а не поломка вызова. Слово то же, что в терминале."""
    @wraps(работа)
    def обёртка(*args, **named):
        try:
            return работа(*args, **named)
        except Refuse as отказ:
            return f"ОТКАЗ: {отказ}"
    return обёртка


def текст(строки):
    return "\n".join(строки)


def с_выгрузкой(repo, строки):
    """Строка «Выгрузка: …» перед ответом — но не перед «ОТКАЗ: …»: ответ,
    который не выполнится, начинается этим словом, как и отказ задания, и
    агент узнаёт его по первой строке."""
    if строки and строки[0].startswith("ОТКАЗ:"):
        return [строки[0], f"Выгрузка: {repo}", *строки[1:]]
    return [f"Выгрузка: {repo}", *строки]


#: Куда идти с параметром, который принадлежит другому инструменту.
НЕ_ТОТ_ИНСТРУМЕНТ = {
    "forms": "формы — инструментами forms_check и forms_apply",
    "modules": "код — инструментами code_check и code_apply",
    "move_method": "код — инструментами code_check и code_apply",
    "job": "задание описано параметрами — их перечень в схеме инструмента",
    "принято": "принятые предупреждения — параметр accepted",
}

#: Ошибки формы запроса словами: валидатор транспорта говорит по-английски.
ОЖИДАЛОСЬ = {"list_type": "нужен список пунктов [{…}, {…}]", "dict_type": "нужен объект {…}",
             "string_type": "нужна строка", "int_type": "нужно целое число",
             "int_parsing": "нужно целое число", "bool_type": "нужно true или false",
             "bool_parsing": "нужно true или false", "missing": "не задано, а оно обязательно",
             "model_type": "нужен объект {…}"}


class Сервер(FastMCP):
    """FastMCP, который не теряет запрос молча и отвечает по-русски.

    Параметры инструментов описаны типами, и лишний ключ верхнего уровня
    FastMCP сам по себе просто отбрасывает: «принято» вместо `accepted`,
    «job»: {…} — задание ушло бы без них, и ответ этого не выдал бы. Ошибку
    формы («additions» объектом вместо списка) он возвращает текстом
    валидатора по-английски. Здесь лишний ключ и неверная форма — отказ
    «ОТКАЗ: …», как у языка заданий.
    """

    async def call_tool(self, name, arguments):
        известные = next((list(tool.inputSchema.get("properties", {}))
                          for tool in await self.list_tools() if tool.name == name), None)
        лишние = [ключ for ключ in arguments or {} if известные is not None
                  and ключ not in известные]
        if лишние:
            советы = [НЕ_ТОТ_ИНСТРУМЕНТ[ключ] for ключ in лишние if ключ in НЕ_ТОТ_ИНСТРУМЕНТ]
            return [TextContent(type="text", text=(
                f"ОТКАЗ: у {name} нет {'параметра' if len(лишние) == 1 else 'параметров'} "
                + ", ".join(f"«{ключ}»" for ключ in лишние)
                + f"; бывают: {', '.join(известные)}"
                + "".join(f"; {совет}" for совет in dict.fromkeys(советы))))]
        try:
            return await super().call_tool(name, arguments)
        except ToolError as ошибка:
            if not isinstance(ошибка.__cause__, ValidationError):
                raise
            return [TextContent(type="text", text="ОТКАЗ: " + "; ".join(
                f"«{'.'.join(str(часть) for часть in e['loc'])}» — "
                + ОЖИДАЛОСЬ.get(e["type"], e["msg"])
                for e in ошибка.__cause__.errors()))]


def build(controller, соглашения=НЕЙТРАЛЬНЫЕ):
    """Сервер с инструментами поверх данного контроллера."""
    server = Сервер("1c-meta", instructions=инструкция(соглашения))

    @server.tool(structured_output=False)
    @словами
    def show(repo: Выгрузка,
             address: Annotated[str, Field(description="«Справочник.мой_Эталон» или форма "
                                                       "«Документ.мой_Заявка.ФормаДокумента» "
                                                       "(или «…Форма.ФормаДокумента», как у bsl-ls)")],
             verbose: ПодробноПоказ = False,
             element: Annotated[str | None, Field(
                 description="имя элемента формы: показать только его ветку и путь к ней — "
                             "у типовой формы дерево целиком бывает в сотни строк")] = None) -> str:
        """Что лежит в выгрузке по адресу.

        Объект — «Справочник.мой_Эталон»: карточка с полями и содержимым.
        Форма — «Документ.мой_Заявка.ФормаДокумента»: назначение, реквизиты
        с типами, команды, события и дерево элементов с привязками и
        обработчиками — ответ на вопрос «куда вставлять». `element` сужает
        показ до одной ветки дерева. `verbose` показывает спутников (меню,
        подсказки, дополнения таблиц), по умолчанию скрытых.
        """
        ответ = controller.show(repo, address)
        if ответ[0] == "форма":
            _, view, name, form_file, module_file, своя = ответ
            return текст(shown_form(view, name, form_file, module_file, verbose, ФОРМЫ,
                                    ветвь=element, своя=своя))
        _, spec, файл = ответ
        лишнее = ["«element» — ветка дерева формы; у объекта не применяется"] if element else []
        return текст(shown_object(spec, файл, МЕТАДАННЫЕ) + лишнее)

    @server.tool(structured_output=False)
    @словами
    def fields(kind: str = "") -> str:
        """Какие поля принимает вид объекта; без вида — операции и виды;
        «Тип» — как описывается тип значения; «Код» — правила правки кода
        вставками (метки, разбор, откат); вид элемента формы («ПолеВвода»,
        «ГруппаФормы»…) — его свойства для задания на формы."""
        if not kind:
            return текст(overview(controller.kinds(), МЕТАДАННЫЕ))
        if kind in ("Тип", "Типы"):
            return текст(types())
        if kind in CODE_WORDS:
            return текст(code_rules(КОД))
        found = controller.kind(kind)
        if found is not None:
            return текст(kind_fields(kind, *found))
        свойства = element_properties(kind)
        if свойства is not None:
            return текст(свойства)
        if is_a_type_word(kind):
            return текст(types())
        raise Refuse("вида «{}» нет; есть: {}".format(kind, ", ".join(controller.kind_names())))

    def _формы(repo, forms, accepted, apply_now, verbose=False):
        result = controller.forms(repo, forms, apply_now)
        return текст(с_выгрузкой(repo, result_lines(
            result, принято=accepted, apply_now=apply_now, подсказки=ФОРМЫ, файлы=verbose)))

    @server.tool(structured_output=False)
    @словами
    def forms_check(repo: Выгрузка, forms: list[FormJob],
                    accepted: Принято = None, verbose: ПодробноФормы = False) -> str:
        """Просмотр задания на формы: находки и план, на диск не пишется ничего.

        `repo` — полный путь к выгрузке, `forms` — пункты задания: завести
        форму («создать») или дополнить существующую — реквизиты, команды,
        элементы с родителем и местом («перед»/«после»), свойства по русским
        именам платформы, обработчики, события, удаление. `accepted` — коды
        предупреждений, принятых осознанно: предупреждение запись не
        останавливает, «принято» только помечает его осознанным; ошибку принять
        нельзя. `verbose` — показать XML, который будет записан.
        """
        return _формы(repo, forms, accepted, apply_now=False, verbose=verbose)

    @server.tool(structured_output=False)
    @словами
    def forms_apply(repo: Выгрузка, forms: list[FormJob],
                    accepted: Принято = None) -> str:
        """То же задание на формы с записью. Файлы пишутся все разом или ни один.
        С «код» (типовая форма; и true, и с модулем) не пишет ничего — выдаёт тот
        же фрагмент кода доработки формы, что и forms_check."""
        return _формы(repo, forms, accepted, apply_now=True)

    def _код(repo, task, date, author, modules, move_method, apply_now, verbose=False):
        result = controller.code(repo, task, date, author, modules, move_method, apply_now)
        return текст([f"Выгрузка: {repo}"] + code_lines(result, apply_now, КОД, целиком=verbose))

    @server.tool(structured_output=False)
    @словами
    def code_check(repo: Выгрузка, task: Задача, modules: list[CodeModule],
                   date: Дата = "", author: Автор = "",
                   move_method: MethodMove | None = None, verbose: ПодробноКод = False) -> str:
        """Просмотр правки кода вставками: решение по каждой
        правке — где она (метод или область) — и текст, который встанет на
        её место, с номерами строк нового модуля; на диск не пишется ничего.

        В `code` — только новый код, без меток: тип вставки (ИЗМЕНЕН,
        ДОБАВЛЕН, УДАЛЕН), метки с датой, задачей и автором, комментирование
        заменяемого и пустые строки снаружи ставит инструмент, а блок,
        пришедший мельче места правки, сдвигает на его уровень; отступы внутри
        кода — ваши, пустым строкам внутри отступ ставится сам, перевод строки
        в конце `code` отбрасывается. Описание метода, если оно есть, — в том
        же коде над ним;
        новая область — целиком с #Область/#КонецОбласти. Якорь — номер строки и её текст
        (`first_line`, у замены и `last_line`) из Read или Grep по файлу до
        задания, с ведущими табуляциями; `first_line` передавайте и у
        вставки. Метод в конец области — якорем её #КонецОбласти, код в
        конец процедуры — её КонецПроцедуры.

        Внутри чужой вставки решает число строк `lines`, закомментированные
        тоже: до двух — вложенная метка; больше, несколько правок в одной
        вставке или правка строки с её меткой — обёртка снаружи. Отказ:
        символы, которые bsl-ls считает ошибкой, кавычки-ёлочки, повтор
        внесённого метода, вставки или области, устаревший якорь (ответ
        скажет, где строка сейчас). Задание атомарно: отказ по одной правке —
        не меняется ни один модуль. `revert` снимает вставки задачи и
        заведённые ею области, стыки сверяет с HEAD. `verbose` — длинные
        блоки целиком.

        Что считается меткой и все правила разбора — fields(kind="Код").
        """
        return _код(repo, task, date, author, modules, move_method, apply_now=False,
                    verbose=verbose)

    @server.tool(structured_output=False)
    @словами
    def code_apply(repo: Выгрузка, task: Задача, modules: list[CodeModule],
                   date: Дата = "", author: Автор = "",
                   move_method: MethodMove | None = None, verbose: ПодробноЗапись = False) -> str:
        """То же задание на код с записью. Модули пишутся все разом или ни один.
        `verbose` — показать записанный текст, а не только номера строк."""
        return _код(repo, task, date, author, modules, move_method, apply_now=True,
                    verbose=verbose)

    def _метаданные(repo, операции, accepted, apply_now, verbose=False):
        result = controller.metadata(метаданные_в_язык_заданий(repo, операции, accepted),
                                     apply_now)
        return текст(с_выгрузкой(repo, result_lines(
            result, принято=accepted, apply_now=apply_now, подсказки=МЕТАДАННЫЕ,
            подробно=verbose, файлы=verbose)))

    @server.tool(structured_output=False)
    @словами
    def metadata_check(repo: Выгрузка,
                       objects: list[MetadataObject] | None = None,
                       attributes: list[AttributeAddition] | None = None,
                       additions: list[ChildAddition] | None = None,
                       changes: list[FieldChange] | None = None,
                       deletions: list[str | Deletion] | None = None,
                       renames: list[ObjectRename] | None = None,
                       atomic_roles: list[str | AtomicRoles] | None = None,
                       accepted: Принято = None,
                       verbose: ПодробноМетаданные = False) -> str:
        """Просмотр задания на объекты и их части: находки и план, без записи.

        Операция в задании одна — один из списков: objects (новые объекты),
        attributes (реквизиты в существующий объект), additions (части:
        табличные части, измерения, части схемы компоновки…), changes (поля существующего),
        deletions, renames, atomic_roles. Поля вида и их значения — fields(kind),
        тип — краткой записью, как его печатает show («Строка(50)»,
        «Справочник.Имя»), или объектом — fields(kind="Тип"). Лишний ключ —
        отказ. `accepted` — коды предупреждений, принятых осознанно:
        предупреждение запись не останавливает, «принято» только помечает его
        осознанным; ошибку принять нельзя. `verbose` — показать XML, который
        будет записан: новые файлы целиком, изменённые — разницей с текущими
        (uuid новых объектов порождаются при каждом вызове заново).
        """
        return _метаданные(repo, dict(objects=objects, attributes=attributes,
                                      additions=additions, changes=changes,
                                      deletions=deletions, renames=renames,
                                      atomic_roles=atomic_roles), accepted,
                           apply_now=False, verbose=verbose)

    @server.tool(structured_output=False)
    @словами
    def metadata_apply(repo: Выгрузка,
                       objects: list[MetadataObject] | None = None,
                       attributes: list[AttributeAddition] | None = None,
                       additions: list[ChildAddition] | None = None,
                       changes: list[FieldChange] | None = None,
                       deletions: list[str | Deletion] | None = None,
                       renames: list[ObjectRename] | None = None,
                       atomic_roles: list[str | AtomicRoles] | None = None,
                       accepted: Принято = None) -> str:
        """То же задание на объекты с записью. Файлы пишутся все разом или ни один."""
        return _метаданные(repo, dict(objects=objects, attributes=attributes,
                                      additions=additions, changes=changes,
                                      deletions=deletions, renames=renames,
                                      atomic_roles=atomic_roles), accepted, apply_now=True)

    @server.tool(structured_output=False)
    @словами
    def verify(repo: ВыгрузкаПодGit = None, base: База = "HEAD", rev: Ревизия = None,
               baseline: Эталон = None, target: Копия = None, task: ЗадачаПроверки = None,
               only: Только = None) -> str:
        """Проверка правок задачи против базы — только чтение.

        Источник один: выгрузка под git (`repo`: рабочая копия вместе с новыми
        файлами, или `rev` — ревизия) против `base`, либо пара каталогов
        `baseline` + `target` — обработка вне репозитория. Правила: новый объект
        с приставкой команды; метки вставок (тип, дата, ИД задачи, без «Ё»);
        правка существующего кода только внутри вставки, удалённое сохранено
        комментарием; правка внутри чужой вставки (с `task`); вставка закрыта,
        вставка вокруг метода — на КонецПроцедуры; служебный ConfigDumpInfo.xml
        вне правок; BOM и переводы строк; строка, заменённая на себя с другими
        пробелами; права на новый объект в своей роли. Находки — с кодом
        правила, файлом и строкой новой версии; правило, которое не
        проверялось, названо в «Пропущено»: «чисто» при пропусках не выдаётся.
        Уровни правил — из профиля команды.
        """
        result = controller.verify(repo=repo, base=base, rev=rev, baseline=baseline,
                                   target=target, task=task, only=only)
        return текст(verify_lines(result))

    @server.tool(structured_output=False)
    @словами
    def normalize_check(repo: ВыгрузкаПодGit = None, base: База = "HEAD",
                        baseline: Эталон = None, target: Копия = None) -> str:
        """Просмотр нормализации формата файлов задачи — на диск не пишется ничего.

        Что будет возвращено файлам, которые задача добавила и изменила против
        `base` (выгрузка под git) или эталона (пара `baseline` + `target`): BOM;
        переводы строк — принятые в репозитории (у пары — как у эталона);
        хвостовые пробелы строк, которые содержательно не менялись, — из базы;
        отступ пустых строк внутри методов — по уровню вложенности, только у
        строк, добавленных задачей; завершающий перевод строки — как в базе.
        Строки, где пробельный символ уже есть, не трогаются. Операция
        идемпотентна: после normalize_apply повтор находит ноль работы.
        """
        result = controller.normalize(repo=repo, base=base, baseline=baseline, target=target)
        return текст(normalize_lines(result, False, "вызовите normalize_apply с теми же параметрами"))

    @server.tool(structured_output=False)
    @словами
    def normalize_apply(repo: ВыгрузкаПодGit = None, base: База = "HEAD",
                        baseline: Эталон = None, target: Копия = None) -> str:
        """То же с записью: все файлы разом или ни один, только в разрешённых выгрузках."""
        result = controller.normalize(repo=repo, base=base, baseline=baseline, target=target,
                                      apply_now=True)
        return текст(normalize_lines(result, True, ""))

    @server.tool(structured_output=False)
    @словами
    def plan_check(objects: ОбъектыПлана, repo: ВыгрузкаПодGit = None, base: База = "HEAD",
                   rev: Ревизия = None, baseline: Эталон = None, target: Копия = None) -> str:
        """Сверка плана изменений с фактом задачи — только чтение.

        План — намерение: объекты, которые задача создаёт, меняет или удаляет,
        их новые члены с типами и методы модулей. Факт — правки против `base`
        (или эталона). Расхождения в обе стороны: заявлено, но не сделано;
        сделано, но не заявлено; типы не совпали. Сверяется род типа, без длины
        и точности. Роль и подсистема, тронутые попутно, и экспортный метод
        вне плана — предупреждения. Уровни правил — из профиля команды.
        """
        result = controller.plan_check(objects, repo=repo, base=base, rev=rev, baseline=baseline,
                                       target=target)
        return текст(plan_check_lines(result))

    @server.tool(structured_output=False)
    @словами
    def plan_emit(repo: ВыгрузкаПодGit = None, base: База = "HEAD", rev: Ревизия = None,
                  baseline: Эталон = None, target: Копия = None) -> str:
        """План по факту задачи — JSON того же формата, что принимает plan_check.

        Объекты, файлы которых задача тронула; их новые члены с типами записью
        показа; новые методы модулей — все, а не только экспортные. Чтобы
        увидеть сделанное целиком или начать план доработки существующей задачи;
        план новой задачи пишется до кода — это намерение, а не отчёт.
        """
        result = controller.plan_emit(repo=repo, base=base, rev=rev, baseline=baseline, target=target)
        return json.dumps(plan_emit_json(result), ensure_ascii=False, indent=1)

    return server
