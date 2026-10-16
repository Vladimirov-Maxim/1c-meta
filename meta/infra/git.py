"""git над выгрузкой: один способ его звать.

stdin закрыт намеренно: у сервера MCP это канал сообщений, и git на Windows,
унаследовав его, ждал бы, пока по каналу придёт следующее сообщение, — сервер
вставал бы целиком. Ответ git — по-английски
(`LC_ALL=C`): его разбирают, а не показывают. Пути — без экранирования
кириллицы (`core.quotepath=off`).
"""

import os
import subprocess

from ..domain.model import Refuse

#: Секунд на ответ git. Обычно он отвечает за доли секунды; дольше — признак
#: сбоя, и честнее отказать, чем гадать.
TIMEOUT = 30


def run(root, *args, why, timeout=None):
    """`git -C root …` -> завершённый процесс; git нет — None; не ответил в срок — отказ."""
    timeout = timeout or TIMEOUT
    try:
        return subprocess.run(
            ["git", "-C", root, "-c", "core.quotepath=off", *args],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
            env=dict(os.environ, LC_ALL="C"))
    except OSError:
        return None
    except subprocess.TimeoutExpired:
        raise Refuse(f"git не ответил за {timeout} с — {why}; повторите вызов") from None


def said(done):
    """Что git сказал об ошибке — одной строкой."""
    return done.stderr.decode("utf-8", "replace").strip() or f"код {done.returncode}"


def unquote(path):
    """Путь, который git всё же взял в кавычки (кавычка, обратная косая или
    управляющий знак в имени), — обратно в имя."""
    if len(path) < 2 or not (path.startswith('"') and path.endswith('"')):
        return path
    body, out, i = path[1:-1], bytearray(), 0
    замены = {"\\": b"\\", '"': b'"', "t": b"\t", "n": b"\n", "r": b"\r", "a": b"\a",
              "b": b"\b", "f": b"\f", "v": b"\v"}
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in замены:
                out += замены[nxt]
                i += 2
                continue
            if nxt.isdigit() and i + 3 < len(body) + 1:
                out.append(int(body[i + 1:i + 4], 8))
                i += 4
                continue
        out += ch.encode("utf-8")
        i += 1
    return out.decode("utf-8", "replace")


def setting(root, key):
    """Значение настройки git в нижнем регистре; не задана или git нет — None."""
    done = run(root, "config", "--get", key, why=f"не могу прочитать настройку {key}")
    if done is None or done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", "replace").strip().lower() or None


def checkout_eol(root, path):
    """Какими переводами строк git кладёт текстовый файл `path` (от `root`) в
    рабочую копию: «CRLF», «LF» или None — git переводы строк не трогает
    (`-text`; ни `core.autocrlf`, ни атрибутов) или git нет.

    Так и должен лежать файл, который пишет инструмент: с другими переводами
    `git add` при `core.safecrlf=true` откажет («LF would be replaced by
    CRLF») — преобразование было бы необратимым."""
    return checkout_eols(root, [path]).get(path)


#: Сколько путей отдавать `git check-attr` за один вызов: длина командной строки
#: Windows ограничена.
ATTR_BATCH = 200


def checkout_eols(root, paths):
    """{путь: «CRLF» | «LF» | None} — `checkout_eol` для многих путей: настройки
    читаются один раз, атрибуты — пачками."""
    paths = list(paths)
    атрибуты = {путь: {} for путь in paths}
    for начало in range(0, len(paths), ATTR_BATCH):
        пачка = paths[начало:начало + ATTR_BATCH]
        done = run(root, "check-attr", "text", "eol", "--", *пачка, why="не могу прочитать атрибуты файлов")
        if done is None or done.returncode != 0:
            return {путь: None for путь in paths}
        for строка in done.stdout.decode("utf-8", "replace").splitlines():
            части = строка.rsplit(": ", 2)
            if len(части) == 3 and unquote(части[0]) in атрибуты:
                атрибуты[unquote(части[0])][части[1]] = части[2]
    autocrlf = setting(root, "core.autocrlf") if paths else None
    родной = None
    итог = {}
    for путь, свои in атрибуты.items():
        text, eol = свои.get("text", "unspecified"), свои.get("eol", "unspecified")
        if text == "unset":
            итог[путь] = None
        elif eol in ("crlf", "lf"):
            итог[путь] = eol.upper()
        elif autocrlf == "true":
            итог[путь] = "CRLF"
        elif autocrlf == "input":
            итог[путь] = "LF"
        elif text in ("set", "auto"):
            родной = родной or setting(root, "core.eol") or "native"
            итог[путь] = "CRLF" if родной == "crlf" or (родной == "native" and os.name == "nt") else "LF"
        else:
            итог[путь] = None
    return итог


def strict_eol(root):
    """`core.safecrlf=true`: файл не в тех переводах строк, что кладёт git,
    `git add` не примет."""
    return setting(root, "core.safecrlf") == "true"
