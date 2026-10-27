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

from ..domain.conventions import NEUTRAL
from ..domain.model import Refuse
from ..report import Hints
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
    metadata_to_job_language,
)

INSTRUCTIONS = """Инструмент исходников конфигурации 1С: пишет объекты метаданных и формы
так же, как конфигуратор (выгрузка в файлы) или 1C:EDT (проект EDT), — без
ручной правки XML. Формат определяется по каталогу `repo` сам: выгрузка —
каталог с Configuration.xml, проект EDT — каталог `src` проекта (с
Configuration/Configuration.mdo); задания одни и те же. Иной каталог —
внешние обработки. `accepted` помечает предупреждение принятым.

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
Писать — только в каталоги, разрешённые сервером. Задание,
которое не выполнится, отвечает строкой «ОТКАЗ: …»."""


def instructions(conventions):
    """Инструкция сервера с соглашениями команды: приставку, метку команды и
    язык кода формы агент узнаёт до первого задания, а не из отказа."""
    form_code = conventions.form_code
    language = form_code.dialect.description(form_code.vocabulary)
    parts = []
    if conventions.prefix:
        parts.append(f"приставка доработок — «{conventions.prefix}»: типовую форму (без "
                     "приставки у объекта и формы) инструмент в XML не правит, с «код»: true "
                     f"он выдаёт фрагмент кода доработки формы — {language}")
    else:
        parts.append("приставки доработок нет — правила о ней не применяются, любая форма "
                     "правится в XML")
    if conventions.marker_tag:
        parts.append(f"метка команды в метках вставок — «{conventions.marker_tag}»")
    return INSTRUCTIONS + "\n\nСоглашения команды (профиль): " + "; ".join(parts) + "."


def _hints(write):
    return Hints(
        fields='fields(kind="{вид}")',
        write=write,
        detailed="verbose=true",
        code="code_check, затем code_apply",
        overview_footer=(
            '\nПоля вида:  fields(kind="<Вид>")        Описание типа:  fields(kind="Тип")'
            '        Правка кода:  fields(kind="Код")',
            "Что лежит в выгрузке:  show(repo, address[, element])\n"
            "   объект — «Справочник.мой_Эталон», "
            "форма — «Документ.мой_Заявка.ФормаДокумента»",
        ),
        module_key="module",
        # Формы у MCP — свои инструменты, а не операция рядом с objects:
        # формат задания терминала в эту справку не переносится.
        forms="Формы — не операция metadata_*: их заводят и дополняют инструменты "
              "forms_check / forms_apply, задание на формы описано их схемой; свойства "
              'элемента — fields(kind="ПолеВвода") и т. п.',
        branch="«element»",
    )


FORMS = _hints("вызовите forms_apply с тем же заданием")
CODE = _hints("вызовите code_apply с тем же заданием")
METADATA = _hints("вызовите metadata_apply с тем же заданием")

# Описания параметров: без них формат даты и смысл `repo` приходится угадывать.
Dump = Annotated[str, Field(description="полный путь к корню исходников (что это — в инструкции "
                                            "сервера)")]
Task = Annotated[str, Field(description="ИД задачи для меток вставок, например ЗАДАЧА-123")]
# Пустое умолчание у даты и автора читается как «необязательны», поэтому
# сказано прямо: обязательны они для любой правки, пусты — только у отката.
Date = Annotated[str, Field(description="дата меток, дд.мм.гггг — обязательна для правок, "
                                        "переименования и переноса; пустой — только у "
                                        "чистого отката")]
Author = Annotated[str, Field(description="автор меток: только имя — метку команды и ИД "
                                         "задачи ставит инструмент; обязателен для правок, "
                                         "переименования и переноса; пустой — только у "
                                         "чистого отката")]

GitDump = Annotated[str | None, Field(description="полный путь к исходникам под git — выгрузке "
                                                          "(Configuration.xml) или каталогу src проекта "
                                                          "EDT; или пара baseline + target")]
Base = Annotated[str, Field(description="база сверки — ревизия до задачи (коммит), по умолчанию HEAD")]
Revision = Annotated[str | None, Field(description="ревизия с правками задачи вместо рабочей копии")]
Baseline = Annotated[str | None, Field(description="каталог «до» — эталон обработки вне репозитория")]
CopyDir = Annotated[str | None, Field(description="каталог «после» — правленая копия; вместе с baseline")]
CheckTask = Annotated[str | None, Field(description="ИД задачи: без него правка внутри чужой "
                                                         "вставки не проверяется")]
Only = Annotated[list[str] | None, Field(description="коды правил, находки которых нужны "
                                                     "(«ФАЙЛ-БЕЗ-BOM», не номера пунктов); пусто — все; "
                                                     "неизвестный код — отказ")]
Files = Annotated[list[str] | None, Field(description="какие файлы правок проверять: путь, каталог или маска "
                                                    "от корня исходников; пусто — все")]
PlanObjects = Annotated[list[PlanObject], Field(description="объекты плана — по объекту на "
                                                           "то, что задача создаёт, меняет или удаляет")]

# Смысл `verbose` у каждого инструмента свой — и описание у каждого своё.
DetailedShow = Annotated[bool, Field(description="показать и спутников элементов формы — "
                                                  "меню, подсказки, дополнения таблиц; у объекта — "
                                                  "длинные тексты (запрос набора данных) целиком")]
DetailedForms = Annotated[bool, Field(description="показать XML формы, который будет записан")]
DetailedCode = Annotated[bool, Field(description="длинные блоки показа — целиком, а не краями")]
DetailedWrite = Annotated[bool, Field(description="показать записанный текст, а не только "
                                                   "номера строк")]
DetailedMetadata = Annotated[bool, Field(description="показать все поля, включая решённые "
                                                       "за вас, и XML, который будет записан")]
Accepted = Annotated[list[str] | None, Field(
    description="коды предупреждений, принятых осознанно, без скобок: [\"РОЛЬ-ШАБЛОН-НЕ-ПРАВИЛО\"]")]


def in_words(work):
    """Отказ инструмента — ответ, а не поломка вызова. Слово то же, что в терминале."""
    @wraps(work)
    def wrapper(*args, **named):
        try:
            return work(*args, **named)
        except Refuse as refusal:
            return f"ОТКАЗ: {refusal}"
    return wrapper


def text(lines):
    return "\n".join(lines)


def with_dump(repo, lines):
    """Строка «Выгрузка: …» перед ответом — но не перед «ОТКАЗ: …»: ответ,
    который не выполнится, начинается этим словом, как и отказ задания, и
    агент узнаёт его по первой строке."""
    if lines and lines[0].startswith("ОТКАЗ:"):
        return [lines[0], f"Выгрузка: {repo}", *lines[1:]]
    return [f"Выгрузка: {repo}", *lines]


#: Куда идти с параметром, который принадлежит другому инструменту.
WRONG_TOOL = {
    "forms": "формы — инструментами forms_check и forms_apply",
    "modules": "код — инструментами code_check и code_apply",
    "move_method": "код — инструментами code_check и code_apply",
    "job": "задание описано параметрами — их перечень в схеме инструмента",
    "принято": "принятые предупреждения — параметр accepted",
}

#: Ошибки формы запроса словами: валидатор транспорта говорит по-английски.
EXPECTED = {"list_type": "нужен список пунктов [{…}, {…}]", "dict_type": "нужен объект {…}",
             "string_type": "нужна строка", "int_type": "нужно целое число",
             "int_parsing": "нужно целое число", "bool_type": "нужно true или false",
             "bool_parsing": "нужно true или false", "missing": "не задано, а оно обязательно",
             "model_type": "нужен объект {…}"}


class Server(FastMCP):
    """FastMCP, который не теряет запрос молча и отвечает по-русски.

    Параметры инструментов описаны типами, и лишний ключ верхнего уровня
    FastMCP сам по себе просто отбрасывает: «принято» вместо `accepted`,
    «job»: {…} — задание ушло бы без них, и ответ этого не выдал бы. Ошибку
    формы («additions» объектом вместо списка) он возвращает текстом
    валидатора по-английски. Здесь лишний ключ и неверная форма — отказ
    «ОТКАЗ: …», как у языка заданий.
    """

    async def call_tool(self, name, arguments):
        known = next((list(tool.inputSchema.get("properties", {}))
                          for tool in await self.list_tools() if tool.name == name), None)
        extra = [key for key in arguments or {} if known is not None
                  and key not in known]
        if extra:
            advices = [WRONG_TOOL[key] for key in extra if key in WRONG_TOOL]
            return [TextContent(type="text", text=(
                f"ОТКАЗ: у {name} нет {'параметра' if len(extra) == 1 else 'параметров'} "
                + ", ".join(f"«{key}»" for key in extra)
                + f"; бывают: {', '.join(known)}"
                + "".join(f"; {advice}" for advice in dict.fromkeys(advices))))]
        try:
            return await super().call_tool(name, arguments)
        except ToolError as error:
            if not isinstance(error.__cause__, ValidationError):
                raise
            return [TextContent(type="text", text="ОТКАЗ: " + "; ".join(
                f"«{'.'.join(str(part) for part in e['loc'])}» — "
                + EXPECTED.get(e["type"], e["msg"])
                for e in error.__cause__.errors()))]


def build(controller, conventions=NEUTRAL):
    """Сервер с инструментами поверх данного контроллера."""
    server = Server("1c-meta", instructions=instructions(conventions))

    @server.tool(structured_output=False)
    @in_words
    def show(repo: Dump,
             address: Annotated[str, Field(description="«Справочник.мой_Эталон» или форма "
                                                       "«Документ.мой_Заявка.ФормаДокумента» "
                                                       "(или «…Форма.ФормаДокумента», как у bsl-ls)")],
             verbose: DetailedShow = False,
             element: Annotated[str | None, Field(
                 description="имя элемента формы: показать только его ветку и путь к ней — "
                             "у типовой формы дерево целиком бывает в сотни строк")] = None) -> str:
        """Что лежит в выгрузке по адресу.

        Объект — «Справочник.мой_Эталон»: карточка с полями и содержимым.
        Форма — «Документ.мой_Заявка.ФормаДокумента»: назначение, реквизиты
        с типами, команды, события и дерево элементов с привязками и
        обработчиками — ответ на вопрос «куда вставлять». `element` сужает
        показ до одной ветки дерева. `verbose` показывает спутников (меню,
        подсказки, дополнения таблиц), по умолчанию скрытых, а у объекта —
        длинные тексты (модуль, запрос набора данных) целиком, а не сводкой.
        """
        answer = controller.show(repo, address)
        if answer[0] == "форма":
            _, view, name, form_file, module_file, own_item = answer
            return text(shown_form(view, name, form_file, module_file, verbose, FORMS,
                                    branch=element, own_item=own_item))
        _, spec, file = answer
        surplus = ["«element» — ветка дерева формы; у объекта не применяется"] if element else []
        return text(shown_object(spec, file, METADATA, fully=verbose) + surplus)

    @server.tool(structured_output=False)
    @in_words
    def fields(kind: str = "") -> str:
        """Какие поля принимает вид объекта; без вида — операции и виды;
        «Тип» — как описывается тип значения; «Код» — правила правки кода
        вставками (метки, разбор, откат); вид элемента формы («ПолеВвода»,
        «ГруппаФормы»…) — его свойства для задания на формы."""
        if not kind:
            return text(overview(controller.kinds(), METADATA))
        if kind in ("Тип", "Типы"):
            return text(types())
        if kind in CODE_WORDS:
            return text(code_rules(CODE))
        found = controller.kind(kind)
        if found is not None:
            return text(kind_fields(kind, *found))
        props = element_properties(kind)
        if props is not None:
            return text(props)
        if is_a_type_word(kind):
            return text(types())
        raise Refuse("вида «{}» нет; есть: {}".format(kind, ", ".join(controller.kind_names())))

    def _forms(repo, forms, accepted, apply_now, verbose=False):
        result = controller.forms(repo, forms, apply_now)
        return text(with_dump(repo, result_lines(
            result, accepted=accepted, apply_now=apply_now, hints=FORMS, files=verbose)))

    @server.tool(structured_output=False)
    @in_words
    def forms_check(repo: Dump, forms: list[FormJob],
                    accepted: Accepted = None, verbose: DetailedForms = False) -> str:
        """Просмотр задания на формы: находки и план, на диск не пишется ничего.

        `repo` — полный путь к выгрузке, `forms` — пункты задания: завести
        форму («создать») или дополнить существующую — реквизиты, команды,
        элементы с родителем и местом («перед»/«после»), свойства по русским
        именам платформы, обработчики, события, удаление. `accepted` — коды
        предупреждений, принятых осознанно: предупреждение запись не
        останавливает, «принято» только помечает его осознанным; ошибку принять
        нельзя. `verbose` — показать XML, который будет записан.
        """
        return _forms(repo, forms, accepted, apply_now=False, verbose=verbose)

    @server.tool(structured_output=False)
    @in_words
    def forms_apply(repo: Dump, forms: list[FormJob],
                    accepted: Accepted = None) -> str:
        """То же задание на формы с записью. Файлы пишутся все разом или ни один.
        С «код» (типовая форма; и true, и с модулем) не пишет ничего — выдаёт тот
        же фрагмент кода доработки формы, что и forms_check."""
        return _forms(repo, forms, accepted, apply_now=True)

    def _code(repo, task, date, author, modules, move_method, apply_now, verbose=False, base="HEAD"):
        result = controller.code(repo, task, date, author, modules, move_method, apply_now,
                                 base=None if base in ("", "HEAD") else base)
        return text([f"Выгрузка: {repo}"] + code_lines(result, apply_now, CODE, whole=verbose))

    @server.tool(structured_output=False)
    @in_words
    def code_check(repo: Dump, task: Task, modules: list[CodeModule],
                   date: Date = "", author: Author = "",
                   move_method: MethodMove | None = None, verbose: DetailedCode = False,
                   base: Base = "HEAD") -> str:
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

        Внутри чужой вставки каждый фрагмент — своей вложенной меткой; обёртка
        снаружи — если правка задевает строку с её меткой или правки заменяют
        больше половины её строк кода. Отказ:
        символы, которые bsl-ls считает ошибкой, кавычки-ёлочки, повтор
        внесённого метода, вставки или области, устаревший якорь (ответ
        скажет, где строка сейчас). Задание атомарно: отказ по одной правке —
        не меняется ни один модуль. `revert` снимает вставки задачи и
        заведённые ею области, стыки сверяет с базой. `base` — ревизия до
        задачи, как у verify: модуля в ней нет — он создан задачей, меток в нём
        нет. `verbose` — длинные блоки целиком.

        Что считается меткой и все правила разбора — fields(kind="Код").
        """
        return _code(repo, task, date, author, modules, move_method, apply_now=False,
                    verbose=verbose, base=base)

    @server.tool(structured_output=False)
    @in_words
    def code_apply(repo: Dump, task: Task, modules: list[CodeModule],
                   date: Date = "", author: Author = "",
                   move_method: MethodMove | None = None, verbose: DetailedWrite = False,
                   base: Base = "HEAD") -> str:
        """То же задание на код с записью. Модули пишутся все разом или ни один.
        `verbose` — показать записанный текст, а не только номера строк."""
        return _code(repo, task, date, author, modules, move_method, apply_now=True,
                    verbose=verbose, base=base)

    def _metadata(repo, operations, accepted, apply_now, verbose=False):
        result = controller.metadata(metadata_to_job_language(repo, operations, accepted),
                                     apply_now)
        return text(with_dump(repo, result_lines(
            result, accepted=accepted, apply_now=apply_now, hints=METADATA,
            detailed=verbose, files=verbose)))

    @server.tool(structured_output=False)
    @in_words
    def metadata_check(repo: Dump,
                       objects: list[MetadataObject] | None = None,
                       attributes: list[AttributeAddition] | None = None,
                       additions: list[ChildAddition] | None = None,
                       changes: list[FieldChange] | None = None,
                       deletions: list[str | Deletion] | None = None,
                       renames: list[ObjectRename] | None = None,
                       atomic_roles: list[str | AtomicRoles] | None = None,
                       accepted: Accepted = None,
                       verbose: DetailedMetadata = False) -> str:
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
        return _metadata(repo, dict(objects=objects, attributes=attributes,
                                      additions=additions, changes=changes,
                                      deletions=deletions, renames=renames,
                                      atomic_roles=atomic_roles), accepted,
                           apply_now=False, verbose=verbose)

    @server.tool(structured_output=False)
    @in_words
    def metadata_apply(repo: Dump,
                       objects: list[MetadataObject] | None = None,
                       attributes: list[AttributeAddition] | None = None,
                       additions: list[ChildAddition] | None = None,
                       changes: list[FieldChange] | None = None,
                       deletions: list[str | Deletion] | None = None,
                       renames: list[ObjectRename] | None = None,
                       atomic_roles: list[str | AtomicRoles] | None = None,
                       accepted: Accepted = None) -> str:
        """То же задание на объекты с записью. Файлы пишутся все разом или ни один."""
        return _metadata(repo, dict(objects=objects, attributes=attributes,
                                      additions=additions, changes=changes,
                                      deletions=deletions, renames=renames,
                                      atomic_roles=atomic_roles), accepted, apply_now=True)

    @server.tool(structured_output=False)
    @in_words
    def verify(repo: GitDump = None, base: Base = "HEAD", rev: Revision = None,
               baseline: Baseline = None, target: CopyDir = None, task: CheckTask = None,
               only: Only = None, paths: Files = None) -> str:
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
        Уровни правил — из профиля команды. `only` и `paths` сужают проверку:
        ответ повторяет фильтр, и «чисто» при нём — чисто только по нему.
        """
        result = controller.verify(repo=repo, base=base, rev=rev, baseline=baseline,
                                   target=target, task=task, only=only, paths=paths)
        return text(verify_lines(result))

    @server.tool(structured_output=False)
    @in_words
    def normalize_check(repo: GitDump = None, base: Base = "HEAD",
                        baseline: Baseline = None, target: CopyDir = None) -> str:
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
        return text(normalize_lines(result, False, "вызовите normalize_apply с теми же параметрами"))

    @server.tool(structured_output=False)
    @in_words
    def normalize_apply(repo: GitDump = None, base: Base = "HEAD",
                        baseline: Baseline = None, target: CopyDir = None) -> str:
        """То же с записью: все файлы разом или ни один, только в разрешённых выгрузках."""
        result = controller.normalize(repo=repo, base=base, baseline=baseline, target=target,
                                      apply_now=True)
        return text(normalize_lines(result, True, ""))

    @server.tool(structured_output=False)
    @in_words
    def plan_check(objects: PlanObjects, repo: GitDump = None, base: Base = "HEAD",
                   rev: Revision = None, baseline: Baseline = None, target: CopyDir = None,
                   only_declared: Annotated[bool, Field(description="сверять только объекты плана: "
                                                                     "тронутые, но не заявленные — "
                                                                     "к сведению, не находкой")] = False
                   ) -> str:
        """Сверка плана изменений с фактом задачи — только чтение.

        План — намерение: объекты, которые задача создаёт, меняет или удаляет,
        их новые члены с типами и методы модулей. Факт — правки против `base`
        (или эталона). Расхождения в обе стороны: заявлено, но не сделано;
        сделано, но не заявлено; типы не совпали. Сверяется род типа, без длины
        и точности. Роль и подсистема, тронутые попутно, и экспортный метод
        вне плана — предупреждения. Уровни правил — из профиля команды.
        """
        result = controller.plan_check(objects, repo=repo, base=base, rev=rev, baseline=baseline,
                                       target=target, only_declared=only_declared)
        return text(plan_check_lines(result))

    @server.tool(structured_output=False)
    @in_words
    def plan_emit(repo: GitDump = None, base: Base = "HEAD", rev: Revision = None,
                  baseline: Baseline = None, target: CopyDir = None) -> str:
        """План по факту задачи — JSON того же формата, что принимает plan_check.

        Объекты, файлы которых задача тронула; их новые члены с типами записью
        показа; новые методы модулей — все, а не только экспортные. Чтобы
        увидеть сделанное целиком или начать план доработки существующей задачи;
        план новой задачи пишется до кода — это намерение, а не отчёт.
        """
        result = controller.plan_emit(repo=repo, base=base, rev=rev, baseline=baseline, target=target)
        return json.dumps(plan_emit_json(result), ensure_ascii=False, indent=1)

    # Схемы инструментов читает агент в каждом запуске, и служебное pydantic в
    # них — четверть объёма. Аргументы проверяются по модели функции, а не по
    # показанной схеме, так что сжатие меняет только то, что видит клиент.
    tools = {ii.name: ii for ii in server._tool_manager.list_tools()}
    for tool in tools.values():
        tool.parameters = compact_schema(tool.parameters)
    # Пара просмотр — запись: задание одно и то же, и вложенные модели задания
    # (объекты, формы, модули) запись повторяла бы целиком. У `*_apply` они
    # ссылаются на схему `*_check`, которую агент уже видел: перед записью он её
    # и вызывает. Проверяются аргументы записи по-прежнему полностью.
    for name, tool in tools.items():
        preview = tools.get(name.removesuffix("_apply") + "_check")
        if name.endswith("_apply") and preview is not None:
            tool.parameters = shared_schema(tool.parameters, preview.name)
    return server


def shared_schema(schema, preview):
    """Схема записи со ссылкой на просмотр: поля со вложенными моделями
    (`$ref`) — одной строкой «как у <просмотр>», общие `$defs` — прочь."""
    out = {key: value for key, value in schema.items() if key != "$defs"}
    out["properties"] = {
        name: ({"description": f"то же, что «{name}» у {preview}"} if "$ref" in json.dumps(field) else field)
        for name, field in (schema.get("properties") or {}).items()}
    return out


def compact_schema(schema):
    """Схема JSON без служебного pydantic: без `title` у каждого поля (он
    повторяет имя), без обёртки `anyOf: [X, null]` у необязательных полей и
    без `default: null` — необязательность и так видна по `required`."""
    if isinstance(schema, list):
        return [compact_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for key, value in schema.items():
        if key == "title" and isinstance(value, str):
            continue
        if key in ("properties", "$defs") and isinstance(value, dict):
            out[key] = {name: compact_schema(s) for name, s in value.items()}
        else:
            out[key] = compact_schema(value)
    variants = out.get("anyOf")
    if isinstance(variants, list) and {"type": "null"} in variants:
        variants = [x for x in variants if x != {"type": "null"}]
        if len(variants) == 1:
            out.pop("anyOf")
            for key, value in variants[0].items():
                out.setdefault(key, value)
        else:
            out["anyOf"] = variants
    if "default" in out and out["default"] is None:
        out.pop("default")
    return out
