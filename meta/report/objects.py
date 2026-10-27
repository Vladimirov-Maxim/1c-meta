"""Объект словами задания: что разобрано и что лежит на диске."""

from ..domain.kinds import REGISTRY
from ..domain.model import ValueType, type_record
from . import NO_CHANNEL


def humanly(value):
    """Значение поля для человека, а не `repr` объекта Python.

    Иначе в просмотре у подписки печаталось бы
    `источник: [<meta.domain.model.TypeRef object at 0x…>]` — а это
    единственное поле, ради которого просмотр подписки и смотрят.
    """
    # `True`, `False` и `None` — питоновские написания, а задание пишется
    # в JSON, где это `true`, `false` и отсутствие поля. В остальном вывод
    # русский, и одно английское слово в нём заставляет спотыкаться.
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "не задано"
    if value and isinstance(value, (list, tuple)) and all(
            isinstance(x, ValueType) for x in value):
        # Составной тип — краткой записью задания, через «|»: так его и
        # вставляют обратно в задание.
        return type_record(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(humanly(x) for x in value) or "(пусто)"
    if isinstance(value, dict):
        return ", ".join(f"{kk}: {humanly(vv)}"
                         for kk, vv in value.items()) or "(пусто)"
    # Длины и разрядности записываются текстом, а голым числом печатались бы
    # ровно в том виде, в каком инструмент их и отвергает, если это число.
    # Кавычки снимают вопрос «а что он записал».
    if isinstance(value, str) and value.isdigit():
        return f'"{value}"'
    return str(value)


#: Многострочное значение длиннее стольких строк печатается сводкой: текст
#: модуля в 58 КБ или запрос набора данных в пять тысяч токенов съедают
#: контекст агента, а сверить их помогают счётчики, контрольная сумма и начало.
SUMMARY_FROM_LINES = 15
SUMMARY_START = 3


def _summary(value, indent, hints):
    """Длинный многострочный текст — счётчиками, контрольной суммой и началом."""
    import hashlib

    lines = value.split("\n")
    total_sum = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    out = [f"{len(lines)} строк, {len(value)} знаков, sha1 {total_sum} — целиком: {hints.detailed}"]
    out += [f"{indent}   │ {line}" for line in lines[:SUMMARY_START]]
    out.append(f"{indent}   │ …")
    return out


def describe(spec, indent="   ", top=True, show_all=False, detailed=False,
             hints=NO_CHANNEL, lines=None, fully=None):
    """Что разобрано из задания: имена детей и их типы.

    Просмотр, который печатает только пути и размеры файлов, не отвечает
    на главный вопрос — то ли записано, что задумано. Ошибка в имени ключа
    типа может дать план, побайтно совпадающий с правильным.
    """
    lines = [] if lines is None else lines
    emit = lines.append
    fully = detailed if fully is None else fully
    kind = REGISTRY.get(spec.kind)
    other_count = 0
    if top:
        # Свойства самого объекта, а не только его детей: иначе просмотр
        # молчал бы про иерархию, длину кода и длину наименования — то есть
        # про половину задания, — «замечаний нет» относилось бы только к
        # детям, а проверить остальное можно было бы лишь вскрыв уже
        # записанный файл.
        # Печатается то, что назвал человек, — всё, включая синоним и
        # включая совпавшее с умолчанием: отбор «только отличное от
        # умолчания» отвечал бы на вопрос «что тут необычного», а нужен
        # ответ на «то ли я заказал». Заодно видно, принято ли поле вообще:
        # его отсутствие в выводе означает, что оно не разобрано.
        child_fields = dict(getattr(kind, "child_fields", ()) or ())
        named = (frozenset(spec.fields) if show_all
                  else getattr(spec, "asked", frozenset(spec.fields)))

        # В чтении с диска пустые свойства не печатаются: их у карточки
        # три десятка, и за ними теряется то, ради чего смотрят. В просмотре
        # задания наоборот — там пустое значение человек написал сам.
        def worth_printing(field_name):
            if field_name in child_fields or field_name == "имя":
                return False
            if field_name in getattr(kind, "derived", ()):
                return False
            if detailed:
                # Кроме названного печатается и то, что решено за человека:
                # за строкой «ещё N полей» прячутся как раз решения —
                # периодичность регистра, режим записи, включённый
                # полнотекстовый поиск.
                return spec.get(field_name) not in (None, "", [], {})
            if not show_all:
                return field_name in named
            value = spec.get(field_name)
            return value not in (None, "", [], {})

        own = [] if kind is None else [
            (field_name, spec.get(field_name)) for field_name in kind.fields
            if worth_printing(field_name)]
        for field_name, value in own:
            if (isinstance(value, list) and value
                    and all(isinstance(x, dict) and "объект" in x for x in value)):
                # Права роли — по строке на объект: одной строкой через запятую
                # границы между объектами не видно. Объекты, где не выдано
                # ничего, — одной строкой счётом: файл прав роли называет их
                # явным «false», у иной роли их сто тысяч, и показ вышел бы в
                # миллионы знаков строками «(пусто)».
                granted = [vv for vv in value if vv.get("права")]
                emit(f"{indent}{field_name}:")
                for grant in granted:
                    emit(f"{indent}   {grant['объект']}: {humanly(grant['права'])}")
                empty_count = len(value) - len(granted)
                if empty_count:
                    emit(f"{indent}   (ещё объектов: {empty_count} — названы в файле прав, но ни "
                         "одного права на них не выдано; не показаны)")
                continue
            if (not fully and isinstance(value, str)
                    and value.count("\n") >= SUMMARY_FROM_LINES):
                first, *rest = _summary(value, indent, hints)
                emit(f"{indent}{field_name}: {first}")
                lines.extend(rest)
                continue
            emit(f"{indent}{field_name}: {humanly(value)}")
        # Про остальное сказано одной строкой — иначе молчание двусмысленно:
        # «поле не названо» и «поле проглочено» выглядят одинаково.
        other_count = 0 if kind is None else len(
            [pt for pt in kind.fields if not worth_printing(pt)
             and pt not in child_fields and pt != "имя"
             and pt not in getattr(kind, "derived", ())])
    for field, child_kind in (getattr(kind, "child_fields", ()) or ()):
        children = spec.get(field) or []
        if not children:
            continue
        parts = []
        for child in children:
            vtype = child.get("тип")
            synonym = child.get("синоним")
            # Синоним ребёнка — половина задания у перечисления и единственное,
            # что увидит пользователь в интерфейсе; без него в просмотре
            # опечатка в «На согласовании» прошла бы молча.
            # Показывается всегда, когда задан, — даже совпадающий с именем.
            # Пряча совпадающий, вывод сделал бы «синоним задан» и «синоним
            # забыт» неотличимыми: строка вышла бы побайтно одинаковой у
            # карточек, различающихся на 401 байт.
            chunks = str(child.get("имя"))
            if synonym:
                chunks += f" «{synonym}»"
            # Через `humanly`, а не `str`: у составного типа это список,
            # и `str(список)` печатает элементы через `repr` — адресами
            # в памяти: измерение с пятью `DocumentRef` вышло бы в просмотре
            # как `[<TypeRef object at 0x…>]`, и единственная точка сверки
            # состава до записи стала бы бесполезной.
            if vtype is not None:
                chunks += f" ({humanly(vtype)})"
            parts.append(chunks)
        emit("{}{}: {}".format(indent, field, ", ".join(parts)))
        for child in children:
            nested = (REGISTRY[child_kind].child_fields
                         if REGISTRY.get(child_kind) else ())
            if any(child.get(f) for f, _ in nested or ()):
                # Имя ребёнка — заголовком: восемь строк «реквизиты: …» подряд
                # не говорят, какой табличной части какие.
                emit(f"{indent}   {child.get('имя')}:")
                describe(child, indent + "      ", top=False, show_all=show_all,
                         detailed=detailed, hints=hints, lines=lines, fully=fully)
    # Про остальное сказано одной строкой и в самом низу: иначе она вклинивается
    # между свойствами объекта и его детьми. Молчание без неё двусмысленно —
    # «поле не названо» и «поле проглочено» выглядят одинаково. У объекта,
    # который уже есть, умолчаний нет: неназванное остаётся как записано.
    if top and other_count and not getattr(spec, "existing", False):
        field_word = ("поле" if other_count % 10 == 1 and other_count % 100 != 11
                      else "поля" if other_count % 10 in (2, 3, 4)
                      and other_count % 100 not in (12, 13, 14) else "полей")
        empty = "пусто" if field_word == "поле" else "пусты"
        # Без подробностей в счёт идут и решённые за человека значения, с
        # подробностями они напечатаны выше: иначе «ещё 25 — по умолчанию» и
        # «ещё 11 пусты» об одном объекте читались бы как расхождение.
        not_named = "не названо" if field_word == "поле" else "не названы"
        tail = (empty if show_all or detailed
                 else f"{not_named} в задании — значения по умолчанию; показать их — "
                      f"{hints.detailed}, поля вида — " + hints.fields.format(вид=spec.kind))
        emit(f"{indent}(ещё {other_count} {field_word} {tail})")
    return lines


def shown_object(spec, file, hints=NO_CHANNEL, fully=False):
    """Карточка с диска тем же языком, что просмотр задания.

    Просмотр задания отвечает на вопрос «то ли я заказал» — про намерение.
    Этот показ отвечает на «то ли записалось»: без него проверяли бы чтением
    XML глазами — ровно тем знанием формата, ради избавления от которого
    инструмент и заведён.
    """
    lines = [f"{spec.kind} {spec.get('имя')}   ({file})"]
    describe(spec, show_all=True, hints=hints, lines=lines, fully=fully)
    # Формы — чтобы узнать их, не открывая каталог. Основные помечены.
    forms = spec.get("формы") or []
    if forms:
        def role(name):
            roles = [word for field, word in MAIN_FORMS
                    if str(spec.get(field) or "").endswith((f".Form.{name}", f".Форма.{name}"))]
            return f" ({', '.join(roles)})" if roles else ""
        lines.append("   формы: " + ", ".join(name + role(name) for name in forms))
        lines.append(f"   форма — show по адресу «{spec.kind}.{spec.get('имя')}.<Имя формы>»")
    return lines


#: Поле основной формы -> как её назвать в перечне форм.
MAIN_FORMS = (("основнаяФормаОбъекта", "основная объекта"),
                  ("основнаяФормаГруппы", "основная группы"),
                  ("основнаяФормаСписка", "основная списка"),
                  ("основнаяФормаВыбора", "основная выбора"),
                  ("основнаяФормаВыбораГруппы", "основная выбора группы"),
                  ("основнаяФормаЗаписи", "основная записи"),
                  ("основнаяФорма", "основная"))
