r"""Точка входа MCP-сервера (stdio).

В `.mcp.json` проекта:

    "1c-meta": {"type": "stdio", "command": "py",
                "args": ["-3", "C:/путь/к/1c-meta/meta/mcp_server.py"],
                "env": {"META_ROOTS": "C:/путь/к/выгрузке/cf;..."}}

`META_ROOTS` — куда серверу разрешено писать, через «;». Пусто — никуда.

Имя файла не `mcp.py` намеренно: запущенный скриптом, такой файл затеняет сам
пакет `mcp` — `import mcp` находит себя же, и сервер падает на первой строке.
Здесь только запуск корня сборки; инструменты — `meta/api`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.composition import mcp_server  # noqa: E402

if __name__ == "__main__":
    mcp_server().run()
