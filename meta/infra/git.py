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
