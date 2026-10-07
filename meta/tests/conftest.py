"""Тесты идут с профилем соглашений тестовой команды.

Фикстуры написаны на соглашениях одной команды — приставка «мой_» и так далее.
Профиль подключается тем же способом, что у живых каналов, — переменной
`META_PROFILE`; задаётся жёстко, а не «если не задано»: профиль из окружения
разработчика менял бы поведение тестов. Тесты домена, которые зовут виды и
проверки форм напрямую, берут те же соглашения из `ТЕСТ`.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ПРОФИЛЬ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "профиль-тестов.json")
os.environ["META_PROFILE"] = ПРОФИЛЬ

# Фикстуры коммитят во временные репозитории git. Настройки git разработчика —
# подпись коммитов, свои хуки — роняли бы их на чужой машине, поэтому тесты
# идут без глобального и системного конфига. Переменные, которые git ставит
# хуку (`GIT_INDEX_FILE` и прочие), снимаются: запущенные из хука, тесты иначе
# писали бы во внешний репозиторий.
os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
for _переменная in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG_PARAMETERS",
                    "GIT_CONFIG_COUNT", "GIT_PREFIX"):
    os.environ.pop(_переменная, None)


def _тест():
    import json

    from meta.jobs.profile import соглашения
    with open(ПРОФИЛЬ, encoding="utf-8") as файл:
        return соглашения(json.load(файл), "профиль тестов")


#: Соглашения тестовой команды — для тестов, которые зовут домен напрямую.
ТЕСТ = _тест()
