"""Полная проверка инструмента: ruff и pytest.

    py -3 check.py [--fast]

Сверка с выгрузкой реальной конфигурации идёт, когда задана переменная
`META_CORPUS` (путь к выгрузке). `--fast` пропускает её и при заданной: это
минуты чтения десятков тысяч карточек; остаётся всё, что от выгрузки не зависит.

Отключается она указанием несуществующего корпуса, а не списком имён тестов:
список пришлось бы дополнять при каждой новой сверке, и он неизбежно отстаёт.
Тесты сами помечаются пропущенными, когда выгрузки нет, и это то же самое
условие.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

def run(title, args, env=None):
    print(f"--- {title}")
    # Вывод читается как UTF-8, а дочерний Python без режима UTF-8 пишет в канал
    # в кодировке консоли (на Windows — cp1251), и кириллица пришла бы «���».
    env = dict(env or os.environ, PYTHONUTF8="1")
    outcome = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=env)
    for line in ((outcome.stdout or "") + (outcome.stderr or "")).rstrip().split("\n"):
        if line.strip():
            print("   " + line)
    return outcome.returncode


def main(argv):
    fast = "--fast" in argv
    codes = [run("ruff", [sys.executable, "-m", "ruff", "check", "."])]
    pytest_args = [sys.executable, "-m", "pytest", "-q"]
    env = None
    if fast:
        env = dict(os.environ, META_CORPUS=os.path.join(ROOT, "нет-такой-выгрузки"))
    codes.append(run("pytest" + (" (--fast)" if fast else ""), pytest_args, env))
    failed = sum(1 for code in codes if code != 0)
    print(f"\nитог: проверок {len(codes)}, провалов {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
