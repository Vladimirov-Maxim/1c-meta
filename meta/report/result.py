"""Результат сценария: находки, разобранное, фрагмент кода и план."""

import difflib
import json

from ..domain.forms import FormEdits, form_module_address
from ..domain.model import presentation
from . import БЕЗ_КАНАЛА
from .forms import describe_form
from .objects import describe


def result_lines(result, принято=(), detailed=False, apply_now=False,
                 подсказки=БЕЗ_КАНАЛА, куда_код=None, файлы=False):
    """Ответ на задание целиком.

    `принято` — коды предупреждений, принятых в задании осознанно;
    `куда_код` — {адрес формы: строка о том, куда канал положил фрагмент кода}
    (у терминала это файл рядом с заданием, у MCP фрагмент живёт в самом
    ответе). Что было записано на диск, знает результат, а не рендер.
    `файлы` — показать тексты, которые будут записаны: новые целиком,
    изменённые — разницей с текущими.
    """
    lines = []
    пиши = lines.append
    # Предупреждение, принятое осознанно, помечается принятым, а не
    # повторяется при каждом запуске вперемешку с новыми. Ошибку принять
    # нельзя: она про то, что платформа не возьмёт, и договориться тут не
    # с кем. Список кодов — в самом задании, чтобы решение хранилось рядом
    # с тем, к чему относится, а не в памяти запускающего.
    принято = set(принято or ())
    непринятые = [к for к in принято
                  if not any(f.code == к and not f.blocking
                             for _, obj_findings in result.per_object for f in obj_findings)]
    if непринятые:
        пиши("в «принято» коды, которых нет среди предупреждений: "
             + ", ".join(sorted(непринятые)))
    for spec, findings in result.per_object:
        if isinstance(spec, FormEdits):
            если_новая = (f" — создать ({spec.create.assignment}"
                          f"{', основная' if spec.create.default else ''})"
                          if spec.create else "")
            пиши(f"Форма {spec.address}{если_новая}")
        else:
            пиши(f"{spec.kind} {presentation(spec)}")
        for finding in findings:
            если_принято = finding.code in принято and not finding.blocking
            level = "принято" if если_принято else finding.level
            пиши(f"   {level:<14} {finding}")
        if not findings:
            пиши("   замечаний нет")
        if isinstance(spec, FormEdits):
            lines.extend(describe_form(spec))
        else:
            describe(spec, detailed=detailed, подсказки=подсказки, lines=lines)

    if not result.ok:
        # Счёт назван словами: голое «(1)» не говорит, одна это ошибка или
        # один объект, а рядом стоят ещё и предупреждения.
        how_many = f"ошибок {len(result.errors)}"
        if result.warnings:
            how_many += f", предупреждений {len(result.warnings)}"
        объектов = len({id(spec) for spec, obj_findings in result.per_object
                        if any(f.blocking for f in obj_findings)})
        if len(result.per_object) > 1:
            # Счёт — по объектам, считая порождённые заданием (атомарные роли):
            # «1 из 3 пунктов» при одном пункте задания сбивает с толку.
            how_many += (f"; с ошибками — {объектов} из {len(result.per_object)} объектов, "
                        "считая порождённые заданием")
        # Первой строкой и словом «ОТКАЗ», как у отказа задания: так его находит
        # поиск по «ОТКАЗ:», а «НЕ ВЫПОЛНЕНО» у просмотра звучало бы странно —
        # он ничего не выполняет.
        lines.insert(0, f"ОТКАЗ: {how_many} — "
                      + ("ничего не записано" if apply_now else "задание не пройдёт")
                      + "; находки ниже")
        return lines

    правки = {spec.address: spec for spec, _ in result.per_object if isinstance(spec, FormEdits)}
    название, purpose = getattr(result, "code_language", None) or ("Код доработки формы", "")
    for address, text in (getattr(result, "code", None) or {}).items():
        # Готовая процедура с настоящими табуляциями, вызов и адрес модуля
        # формы: без них приходится угадывать, куда класть фрагмент и что такое
        # «Форма» (в обработчике модуля формы её нет), набирать табуляции руками
        # и искать адрес модуля для задания на код.
        edits = правки.get(address)
        procedure = (edits.code_procedure_name if edits
                     else f"{address.split('.')[-1]}_ПриСозданииНаСервере")
        module = edits.code_module_name if edits else None
        модуль_формы = form_module_address(address)
        места = (getattr(result, "code_places", None) or {}).get(address) or []
        what = {м.what: м for м in места}
        call = f"{module or '<Модуль>'}.{procedure}(ЭтотОбъект);"
        if "дополнение" in what:
            # Процедура доработки уже есть: в неё дописывается код — вторая
            # процедура задвоила бы доработку.
            extension = what["дополнение"]
            place = extension.where or "код перед её «КонецПроцедуры»"
            пиши(f"\n{название} для «{address}» — дополнение процедуры «{procedure}» "
                 f"общего модуля «ОбщийМодуль.{module}»: {place} (строка {extension.line}). "
                 f"Внести с метками — {подсказки.code}.")
            пиши("")
            # Пустая строка после дописанного кода — как между блоками в процедуре:
            # внутри своей вставки разделителей инструмент не ставит, и без неё
            # код лёг бы вплотную к строке, перед которой его дописывают.
            code = ["\t" + line if line.strip() else "\t"
                   for line in text.rstrip("\n").split("\n")] + ["\t"]
        else:
            destination = (f"общего модуля «ОбщийМодуль.{module}»" if module
                    else "своего общего модуля")
            пиши(f"\n{название} для «{address}» — процедура для {destination} "
                 "(в область, где у модуля лежит его программный интерфейс или обработчики "
                 f"форм) и вызов её в конце ПриСозданииНаСервере модуля формы «{модуль_формы}». "
                 f"Внести с метками — {подсказки.code}.")
            пиши("")
            # Описание — как у любого метода программного интерфейса: иначе
            # его пришлось бы дописывать самому. Без длинного тире: в BSL
            # его отвергает bsl-ls (InvalidCharacterInFile), а стояло бы оно в
            # каждом выданном фрагменте. Кавычки прямые: в коде ёлочкам не
            # место, и фрагмент, внесённый дословно, не прошёл бы проверку
            # кода. Что процедура делает, а не почему она есть: постоянное
            # «типовая форма правится только кодом» описанием метода не
            # является. Без перечня элементов: дополнение процедуры описание не
            # трогает, и перечень устаревал бы со второй доработкой, а с
            # длинными именами строка выходила бы за 120 знаков.
            code = [
                f'// Дорабатывает форму "{address}"{purpose}.',
                "//",
                "// Параметры:",
                "//  Форма - ФормаКлиентскогоПриложения - дорабатываемая форма.",
                "//",
                f"Процедура {procedure}(Форма) Экспорт",
                "\t",
                *("\t" + line for line in text.rstrip("\n").split("\n")),
                "\t",
                "КонецПроцедуры",
            ]
        lines.extend(code)
        if "вызов есть" not in what:
            пиши("")
            пиши(f"Вызов в ПриСозданииНаСервере формы:  {call}")
        for пояснение in (getattr(result, "code_notes", None) or {}).get(address) or []:
            пиши(f"   {пояснение}")
        процедура_есть = "процедура" in what or "дополнение" in what
        вызов_есть = "вызов" in what or "вызов есть" in what
        if module and процедура_есть and вызов_есть:
            lines.extend(готовые_правки(места, "\n".join(code), call, подсказки))
        обработчики = (getattr(result, "handlers", None) or {}).get(address) or []
        if обработчики:
            # Имена — те же, что в коде формы (приставка «Подключаемый_»),
            # сигнатуры — по корпусу: иначе процедуру пришлось бы угадывать.
            пиши(f"\nПроцедуры-обработчики — в модуль формы «{модуль_формы}», тоже с метками:")
            for where, name, directive, parameters in обработчики:
                пиши(f"   {directive} Процедура {name}({parameters})   — {where}")
        if куда_код and address in куда_код:
            пиши(куда_код[address])

    if result.plan is None:
        if apply_now and getattr(result, "code", None):
            # С «код»: true запись не пишет ничего, и сказать это надо прямо:
            # иначе вывод ничем не отличается от просмотра.
            пиши("\nЗаписи нет: типовая форма в XML не правится — внесите код заданием на код.")
        elif getattr(result, "code", None):
            # Порядок «просмотр, затем запись» подталкивает вызвать запись и
            # здесь, хотя писать в XML нечего.
            пиши("\nЗапись формы не нужна: с «код» в XML не пишется ничего — код вносится "
                 f"заданием на код ({подсказки.code}).")
        return lines
    пиши("\nПлан:")
    for line in result.plan.describe():
        пиши("   " + line)
    if файлы and not apply_now:
        lines.extend(тексты_файлов(result.plan))
    if apply_now:
        пиши(f"\nЗаписано файлов: {len(result.written)}")
        пиши("ConfigDumpInfo.xml не изменялся — его пересоберёт платформа.")
    else:
        пиши(f"\nПросмотр: ничего не записано. Для записи {подсказки.записать}.")
    return lines


def тексты_файлов(plan):
    """Что окажется в файлах: новые — целиком, изменённые — разницей.

    По плану из одних размеров не проверить, то ли запишется, не записав и
    не открыв файл.
    """
    texts, с_uuid = [], False
    for path, before, станет in plan.contents():
        if станет is None:
            texts.append(f"\n── удалить {path}")
        elif before is None:
            texts.append(f"\n── создать {path}:")
            texts.extend("   " + line for line in станет.splitlines())
            с_uuid = с_uuid or 'uuid="' in станет
        else:
            texts.append(f"\n── изменить {path}:")
            разница = list(difflib.unified_diff(before.splitlines(), станет.splitlines(),
                                                lineterm="", n=2))[2:]
            texts.extend("   " + line for line in разница)
            с_uuid = с_uuid or any(с.startswith("+") and 'uuid="' in с for с in разница)
            if not разница:
                texts.append("   (текст тот же)")
    # Показ выглядит как точный diff, а uuid в нём не те, что запишутся: сверка
    # с записанным нашла бы расхождение. Оговорка — только когда новые uuid в
    # показанном есть: у правки формы их нет.
    return (["\nТексты файлов (uuid новых объектов порождаются при каждом вызове — "
             "в записи они будут другими):"] if с_uuid else ["\nТексты файлов:"]) + texts


def готовые_правки(места, procedure, call, подсказки):
    """Правки задания на код по местам кода формы — готовым текстом.

    Иначе двадцать строк процедуры, номера строк и тексты якорей пришлось бы
    переносить из ответа в задание на код руками и при переносе можно было бы
    исказить код. Ключ модуля — слово канала: у MCP «module», в задании
    терминала «модуль». Вызов дан без отступа, и это сказано: иначе неясно,
    ставить ли табуляцию самому.
    """
    code = {"процедура": procedure, "дополнение": procedure, "вызов": call}
    modules = [{подсказки.ключ_модуля: м.module,
               "edits": [{"line": м.line, "lines": 0, "first_line": м.anchor,
                          "code": code[м.what]}]}
              for м in места if м.what in code]
    lines = [f"\nГотовые правки для задания на код ({подсказки.code}) — «modules» как есть, "
              "task, date и author — свои; номера строк — по файлам сейчас; отступ "
              "вызова до уровня места ставит инструмент:",
              '{"modules": [']
    for number, module in enumerate(modules):
        tail = "," if number < len(modules) - 1 else ""
        lines.append("  " + json.dumps(module, ensure_ascii=False) + tail)
    lines.append("]}")
    return lines
