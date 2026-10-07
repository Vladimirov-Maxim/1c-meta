r"""Точка входа терминала.

    py -3 meta/add.py <задание.json> [--apply] [--профиль <профиль.json>]
    py -3 meta/add.py --поля [Вид]
    py -3 meta/add.py --показать <выгрузка> <адрес> [<элемент формы>]
    py -3 meta/add.py --проверить <выгрузка> [--база <ревизия>] [--json <файл>]
    py -3 meta/add.py --нормализовать <выгрузка> [--база <ревизия>] [--apply]
    py -3 meta/add.py --сверить-план <выгрузка> --план <план.json> [--база <ревизия>]
    py -3 meta/add.py --план-по-факту <выгрузка> [--база <ревизия>]

Справка — `--help`. Здесь только запуск корня сборки: разбор ключей и файла —
канал терминала (`meta/cli`), сборка — `meta/composition`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.composition import run_terminal, terminal  # noqa: E402


def main(argv):
    """Терминал с отказом через `Refuse` — так его зовут тесты и скрипты."""
    return terminal(argv)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(run_terminal(sys.argv[1:]))
