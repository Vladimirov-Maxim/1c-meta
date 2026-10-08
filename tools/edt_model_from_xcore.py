"""Таблица метамодели EDT из её исходников `xcore` — для писателя проекта EDT.

EDT хранит объект метаданных как объект EMF и пишет его по правилам EMF:
свойства идут в порядке `eAllStructuralFeatures` (сначала свойства
суперклассов, затем свои), свойство, равное умолчанию EMF, не пишется вовсе,
служебные (`transient`, `derived`, `volatile`) не пишутся никогда. Порядок и
умолчания не угадываются по образцам — они берутся из той же метамодели, по
которой пишет сам EDT.

Метамодель лежит в jar-ах установленного EDT (`model/*.xcore`); отсюда
снимается таблица `meta/acl/edt_metamodel.py` — модулем, а не файлом данных:
перекладка (`acl`) диска не читает:

    пакеты:   адрес пространства имён -> пакет (`mdclass:` -> `…metadata.mdclass`)
    классы:   полное имя -> {абстрактный, суперклассы, свойства по порядку}
    свойство: имя, тип (полное имя или примитив), род (атрибут | содержит |
              ссылается), много ли, обязательно ли, умолчание, служебное ли,
              unsettable ли, id ли (EMF пишет его атрибутом XML)
    перечисления: полное имя -> литералы по порядку (умолчание — первый)
    типы-обёртки: полное имя -> что оборачивают

Имена — полные: одно и то же короткое имя (`Field`, `Parameter`, `EnumValue`)
бывает в разных пакетах, и тип свойства разрешается по импортам своего файла.

Запуск: `py -3 tools/edt_model_from_xcore.py [<каталог plugins EDT>]`; без
каталога — пул p2 пользователя (`%USERPROFILE%\\.p2\\pool\\plugins`).
"""

import glob
import json
import os
import sys
import zipfile

#: jar-ы с метамоделями, которые нужны писателю: метаданные, ядро, формы, права, СКД.
JARS = ("com._1c.g5.v8.dt.metadata_", "com._1c.g5.v8.dt.mcore_", "com._1c.g5.v8.dt.form.model_",
        "com._1c.g5.v8.dt.rights.model_", "com._1c.g5.v8.dt.dcs.model_")

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "meta", "acl",
                   "edt_metamodel.py")

#: Модификаторы свойства, после которых свойство не сохраняется в файл.
SERVICE = {"transient", "derived", "volatile"}
MODIFIERS = SERVICE | {"unsettable", "readonly", "id", "local", "resolving", "unordered", "unique"}


def tokens(text):
    """Текст xcore -> лексемы: строки целиком, комментарии отброшены, переводы
    строк — отдельной лексемой «\\n» (свойство класса — одна строка)."""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            yield "\n"
            i += 1
        elif ch.isspace():
            i += 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            i = n if i < 0 else i
        elif text.startswith("/*", i):
            i = text.find("*/", i + 2)
            i = n if i < 0 else i + 2
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            yield text[i:j + 1]
            i = j + 1
        elif ch.isalnum() or ch in "_^$":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_^$."):
                j += 1
            yield text[i:j]
            i = j
        else:
            yield ch
            i += 1


class Tokens:
    """Лексемы с возвратом одной назад: у операции тело бывает, а бывает нет."""

    def __init__(self, items):
        self.items, self.back = iter(items), []

    def __iter__(self):
        return self

    def __next__(self):
        return self.back.pop() if self.back else next(self.items)

    def push(self, t):
        self.back.append(t)


def nxt(it):
    """Следующая лексема заголовка: переводы строк в заголовках не значат ничего."""
    t = next(it)
    while t == "\n":
        t = next(it)
    return t


def skip_group(it, open_, close):
    """Пропустить сбалансированную группу; открывающая уже прочитана."""
    depth = 1
    for t in it:
        if t == open_:
            depth += 1
        elif t == close:
            depth -= 1
            if depth == 0:
                return


def annotation(it):
    """Аннотация после «@»: (имя, {ключ: строка}); без скобок — пустые аргументы."""
    имя = next(it)
    t = next(it)
    if t != "(":
        it.push(t)
        return имя, {}
    аргументы, глубина, ключ, prev = {}, 1, None, None
    for t in it:
        if t == "(":
            глубина += 1
        elif t == ")":
            глубина -= 1
            if глубина == 0:
                break
        elif t == "=" and prev:
            ключ = prev
        elif t.startswith('"') and ключ:
            аргументы[ключ] = t.strip('"')
            ключ = None
        prev = t
    return имя, аргументы


def parse(text, files):
    """Один файл xcore -> контекст файла с сырыми классами, перечислениями, типами."""
    it = Tokens(list(tokens(text)))
    файл = {"package": None, "nsURI": None, "imports": {}, "classes": {}, "enums": {}, "datatypes": {}}
    for t in it:
        if t == "\n":
            continue
        if t == "@":
            имя, аргументы = annotation(it)
            if имя == "Ecore" and "nsURI" in аргументы:
                файл["nsURI"] = аргументы["nsURI"]
            continue
        if t == "package":
            файл["package"] = nxt(it).replace("^", "")
        elif t == "import":
            полное = nxt(it).replace("^", "")
            файл["imports"][полное.rsplit(".", 1)[-1]] = полное
        elif t == "type":
            имя = nxt(it)
            nxt(it)                                   # wraps
            файл["datatypes"][имя] = nxt(it)
        elif t == "enum":
            имя = nxt(it)
            assert nxt(it) == "{", имя
            литералы = []
            for lt in it:
                if lt == "\n" or lt in ("=", ","):
                    continue
                if lt == "}":
                    break
                if lt == "@":
                    annotation(it)
                    continue
                if lt[0].isdigit() or lt[0] == "-" or lt[0] == '"':
                    continue
                литералы.append(lt.replace("^", ""))
            файл["enums"][имя] = литералы
        elif t in ("class", "interface", "abstract"):
            абстрактный = t != "class"
            if t == "abstract":
                nxt(it)                               # class | interface
            имя = nxt(it).replace("^", "")
            суперы, обёртка = [], None
            t2 = nxt(it)
            if t2 == "<":                             # параметры типа
                skip_group(it, "<", ">")
                t2 = nxt(it)
            while t2 != "{":
                if t2 == "extends":
                    t2 = nxt(it)
                    while True:
                        суперы.append(t2.replace("^", ""))
                        t2 = nxt(it)
                        if t2 == "<":
                            skip_group(it, "<", ">")
                            t2 = nxt(it)
                        if t2 != ",":
                            break
                        t2 = nxt(it)
                elif t2 == "wraps":
                    обёртка = nxt(it)
                    t2 = nxt(it)
                else:
                    t2 = nxt(it)
            файл["classes"][имя] = {"abstract": абстрактный, "supers": суперы, "wraps": обёртка,
                                    "features": parse_body(it)}
    files.append(файл)


def parse_body(it):
    """Тело класса -> свойства по порядку: одно свойство — одна строка;
    операции с телом и аннотации пропускаются."""
    features, line = [], []

    def flush():
        feature = make_feature(line)
        if feature:
            features.append(feature)
        line.clear()

    for t in it:
        if t == "\n":
            flush()
        elif t == "}":
            flush()
            return features
        elif t == "@" and not line:
            annotation(it)
        elif t == "op" and not line:
            # op Тип имя(…) — с телом { … } на той же или следующей строке, или без него
            for t2 in it:
                if t2 == "(":
                    skip_group(it, "(", ")")
                    break
            t2 = nxt(it)
            if t2 == "{":
                skip_group(it, "{", "}")
            else:
                it.push(t2)
        else:
            line.append(t)
    return features


def make_feature(line):
    if not line:
        return None
    default = None
    if "=" in line:
        i = line.index("=")
        default = line[i + 1].strip('"')
        line = line[:i]
    род, модификаторы, rest = "attribute", set(), []
    for t in line:
        if t == "contains":
            род = "contains"
        elif t == "refers":
            род = "refers"
        elif t in MODIFIERS:
            модификаторы.add(t)
        else:
            rest.append(t.replace("^", ""))
    if len(rest) < 2:
        return None
    имя, тип_части = rest[-1], rest[:-1]
    if "<" in тип_части:                               # параметры типа: Map<K, V>
        закрыта = len(тип_части) - тип_части[::-1].index(">")
        тип_части = тип_части[:тип_части.index("<")] + тип_части[закрыта:]
    кратность = None                                   # текст между [ и ]: «», «1», «0..1», «*»
    if "[" in тип_части and "]" in тип_части:
        i, j = тип_части.index("["), тип_части.index("]")
        кратность = "".join(тип_части[i + 1:j])
    return {"name": имя, "type": тип_части[0], "kind": род,
            "many": кратность is not None and кратность not in ("1", "0..1", "?"),
            "required": кратность == "1" or (кратность or "").startswith("1.."),
            "default": default, "service": bool(модификаторы & SERVICE),
            "unsettable": "unsettable" in модификаторы, "id": "id" in модификаторы}


def resolve(files):
    """Сырые файлы -> таблица с полными именами: тип свойства и суперкласс
    разрешаются по импортам своего файла, затем по своему пакету."""
    известные = set()
    for файл in files:
        for раздел in ("classes", "enums", "datatypes"):
            известные |= {f"{файл['package']}.{имя}" for имя in файл[раздел]}

    def полное(имя, файл):
        if "." in имя:
            return имя
        if имя in файл["imports"]:
            return файл["imports"][имя]
        своё = f"{файл['package']}.{имя}"
        return своё if своё in известные else имя      # примитив или тип Ecore

    model = {"packages": {}, "classes": {}, "enums": {}, "datatypes": {}}
    for файл in files:
        пакет = файл["package"]
        if файл["nsURI"]:
            model["packages"][файл["nsURI"]] = пакет
        for имя, литералы in файл["enums"].items():
            model["enums"][f"{пакет}.{имя}"] = литералы
        for имя, обёртка in файл["datatypes"].items():
            model["datatypes"][f"{пакет}.{имя}"] = обёртка
        for имя, класс in файл["classes"].items():
            model["classes"][f"{пакет}.{имя}"] = {
                "abstract": класс["abstract"],
                "supers": [полное(с, файл) for с in класс["supers"]],
                "features": [dict(f, type=полное(f["type"], файл)) for f in класс["features"]]}
    return model


def main(argv):
    plugins = argv[0] if argv else os.path.join(os.path.expanduser("~"), ".p2", "pool", "plugins")
    files, source = [], []
    for приставка in JARS:
        найдено = sorted(glob.glob(os.path.join(plugins, приставка + "*.jar")))
        if not найдено:
            raise SystemExit(f"нет jar-а {приставка}* в {plugins}")
        jar = найдено[-1]
        source.append(os.path.basename(jar))
        with zipfile.ZipFile(jar) as z:
            for name in sorted(z.namelist()):
                if name.endswith(".xcore"):
                    parse(z.read(name).decode("utf-8"), files)
    model = resolve(files)
    model["source"] = source
    текст = json.dumps(model, ensure_ascii=False, sort_keys=True, indent=0)
    for js, py in ((": true", ": True"), (": false", ": False"), (": null", ": None")):
        текст = текст.replace(js, py)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Метамодель EDT — таблица, снятая `tools/edt_model_from_xcore.py`; руками не править."""\n\n')
        f.write("# ruff: noqa\n")
        f.write(f"METAMODEL = {текст}\n")
    print(f"классов {len(model['classes'])}, перечислений {len(model['enums'])} -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
