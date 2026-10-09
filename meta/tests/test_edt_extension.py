"""Расширение конфигурации в формате EDT — на синтетическом проекте по образцу
расширения тестов (YAxUnit).

У расширения свой реестр: заимствованная конфигурация (`objectBelonging`
Adopted), блок `extension` в пространстве `mdclassExtension`, приставка имён;
заимствованные объекты ссылаются на объект основной конфигурации
(`extendedConfigurationObject`). Репозиторий расширения хранит файлы с CRLF.

Проверяется: карточки расширения проходят переходник туда и обратно без
потерь; собственный общий модуль создаётся рядом с соседями — карточка,
модуль, одна строка в реестре, переводы строк проекта — и проверка правок
записанное принимает. Заимствование объектов инструмент не делает.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.acl import edt_model as _edt_model  # noqa: E402
from meta.add import main  # noqa: E402
from meta.infra.edt_dump import EdtDump  # noqa: E402

pytestmark = pytest.mark.skipif(not _edt_model.available(), reason="таблица метамодели EDT не сгенерирована: "
                                "py -3 tools/edt_model_from_xcore.py")

ПРОФИЛЬ = {"приставка": ["ОМ_мой_", "мой_"], "метки": {"тег": "#TEAM"}}
ОБЪЯВЛЕНИЯ = ('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              'xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" '
              'xmlns:mdclassExtension="http://g5.1c.ru/v8/dt/metadata/mdclass/extension"')

РЕЕСТР = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Configuration {ОБЪЯВЛЕНИЯ} uuid="8ebe57d7-1182-4eea-bdda-375c1e0262e4">
  <name>Тесты</name>
  <synonym>
    <key>ru</key>
    <value>Тесты</value>
  </synonym>
  <objectBelonging>Adopted</objectBelonging>
  <extension xsi:type="mdclassExtension:ConfigurationExtension">
    <managedApplicationModule>Extended</managedApplicationModule>
    <ordinaryApplicationModule>Extended</ordinaryApplicationModule>
  </extension>
  <containedObjects classId="9cd510cd-abfc-11d4-9434-004095e12fc7" objectId="7aac7ebc-1c41-419f-aac1-52a9be0908ba"/>
  <keepMappingToExtendedConfigurationObjectsByIDs>true</keepMappingToExtendedConfigurationObjectsByIDs>
  <namePrefix>ЮТ</namePrefix>
  <configurationExtensionCompatibilityMode>8.3.10</configurationExtensionCompatibilityMode>
  <configurationExtensionPurpose>AddOn</configurationExtensionPurpose>
  <scriptVariant>Russian</scriptVariant>
  <languages uuid="b8fdae66-bc14-47de-9a8d-e0323e0d9ce8">
    <name>Русский</name>
    <objectBelonging>Adopted</objectBelonging>
    <extension xsi:type="mdclassExtension:LanguageExtension">
      <languageCode>Checked</languageCode>
    </extension>
    <languageCode>ru</languageCode>
  </languages>
  <commonModules>CommonModule.ЮТест</commonModules>
  <catalogs>Catalog.Договоры</catalogs>
</mdclass:Configuration>
"""

ЗАИМСТВОВАННЫЙ = f"""<?xml version="1.0" encoding="UTF-8"?>
<mdclass:Catalog {ОБЪЯВЛЕНИЯ} uuid="12e6afee-813e-4304-840b-460b335b5a48" \
extendedConfigurationObject="b9e5871f-258c-4beb-bed7-481bf362ae45">
  <producedTypes>
    <objectType typeId="da7fead1-aabd-4531-8841-f9da9a99ea8b" valueTypeId="24bd9b10-95a5-408f-81b4-5e70dfe093c0"/>
    <refType typeId="2fb1cf68-6c78-4c42-9b84-b50255a037b6" valueTypeId="ad6af665-991d-4a73-bc10-a214f9cbbf7a"/>
    <selectionType typeId="b7e0cb2d-0245-4069-86ee-d510c9961224" valueTypeId="7c08a90f-40ad-45df-a7b5-650e582696ab"/>
    <listType typeId="917d5770-9502-4537-9149-47b928a8ddea" valueTypeId="f5165ad3-acac-4e66-a4c6-e873762f5f0e"/>
    <managerType typeId="c4f28c36-7a99-4e60-bc06-1b88280c731f" valueTypeId="01890d12-acf2-4254-b618-af481e00d68f"/>
  </producedTypes>
  <name>Договоры</name>
  <objectBelonging>Adopted</objectBelonging>
  <extension xsi:type="mdclassExtension:CatalogExtension">
    <extendedConfigurationObject>Checked</extendedConfigurationObject>
    <managerModule>Extended</managerModule>
  </extension>
</mdclass:Catalog>
"""

СВОЙ = """<?xml version="1.0" encoding="UTF-8"?>
<mdclass:CommonModule xmlns:mdclass="http://g5.1c.ru/v8/dt/metadata/mdclass" \
uuid="00657e40-f22c-4638-ae35-a322d57470cc">
  <name>ЮТест</name>
  <synonym>
    <key>ru</key>
    <value>Тест</value>
  </synonym>
  <clientManagedApplication>true</clientManagedApplication>
  <server>true</server>
  <clientOrdinaryApplication>true</clientOrdinaryApplication>
</mdclass:CommonModule>
"""

ФАЙЛЫ = {"Configuration/Configuration.mdo": РЕЕСТР,
         "Catalogs/Договоры/Договоры.mdo": ЗАИМСТВОВАННЫЙ,
         "CommonModules/ЮТест/ЮТест.mdo": СВОЙ,
         "CommonModules/ЮТест/Module.bsl": "Процедура Проба() Экспорт\nКонецПроцедуры\n"}


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def написать(src, rel, текст, eol):
    путь = os.path.join(str(src), *rel.split("/"))
    os.makedirs(os.path.dirname(путь), exist_ok=True)
    with open(путь, "wb") as файл:
        файл.write(текст.replace("\n", eol).encode("utf-8"))


def прочитать(src, rel):
    with open(os.path.join(str(src), *rel.split("/")), "rb") as файл:
        return файл.read()


@pytest.fixture
def расширение(tmp_path):
    """Исходники расширения в git-репозитории, файлы с CRLF (`* -text`)."""
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    git(repo, "init", "-q")
    for ключ, значение in (("user.email", "t@example.local"), ("user.name", "Фикстуры"),
                           ("core.autocrlf", "false"), ("core.quotepath", "false")):
        git(repo, "config", ключ, значение)
    (repo / ".gitattributes").write_bytes(b"* -text\n")
    for rel, текст in ФАЙЛЫ.items():
        написать(src, rel, текст, "\r\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "база")
    return src


@pytest.fixture
def профиль(tmp_path):
    путь = tmp_path / "профиль.json"
    путь.write_text(json.dumps(ПРОФИЛЬ, ensure_ascii=False), encoding="utf-8")
    return str(путь)


def test_extension_cards_go_through_the_adapter_and_back_unchanged(расширение):
    """Реестр расширения, заимствованный и собственный объект: карточка ->
    дерево выгрузки -> карточка даёт те же байты — блок `extension`,
    `objectBelonging` и `extendedConfigurationObject` не теряются."""
    площадка = EdtDump(str(расширение))
    for rel in ФАЙЛЫ:
        if not rel.endswith(".mdo"):
            continue
        было = прочитать(расширение, rel)
        дерево = площадка._designer_text(было)
        стало = площадка._edt_text(дерево, lambda *_: None).replace("\n", площадка.eol).encode("utf-8")
        assert стало == было, rel


def test_a_common_module_is_created_in_the_extension_beside_its_neighbours(расширение, tmp_path, capsys, профиль):
    """Свой общий модуль расширения: карточка и модуль с CRLF, как соседи;
    в реестре — одна новая строка после соседей того же вида, остальное
    (блок `extension`, заимствованные объекты) не тронуто; проверка правок
    записанное принимает."""
    реестр_до = прочитать(расширение, "Configuration/Configuration.mdo")
    задание = {"repo": str(расширение),
               "objects": [{"вид": "ОбщийМодуль", "поля": {
                   "имя": "ОМ_мой_Проба", "синоним": "Проба", "сервер": True,
                   "текст": "Процедура Проба() Экспорт\nКонецПроцедуры\n"}}]}
    путь = tmp_path / "задание.json"
    путь.write_text(json.dumps(задание, ensure_ascii=False), encoding="utf-8")
    assert main([str(путь), "--apply", "--профиль", профиль]) == 0

    карточка = прочитать(расширение, "CommonModules/ОМ_мой_Проба/ОМ_мой_Проба.mdo")
    модуль = прочитать(расширение, "CommonModules/ОМ_мой_Проба/Module.bsl")
    for данные in (карточка, модуль):
        assert b"\r\n" in данные and b"\n" not in данные.replace(b"\r\n", b"")
        assert not данные.startswith(b"\xef\xbb\xbf")
    assert "<name>ОМ_мой_Проба</name>" in карточка.decode("utf-8")
    assert b"objectBelonging" not in карточка and b"mdclassExtension" not in карточка

    реестр = прочитать(расширение, "Configuration/Configuration.mdo")
    строка = "  <commonModules>CommonModule.ОМ_мой_Проба</commonModules>\r\n".encode()
    сосед = "  <commonModules>CommonModule.ЮТест</commonModules>\r\n".encode()
    assert реестр == реестр_до.replace(сосед, сосед + строка)

    ответ = tmp_path / "ответ.json"
    capsys.readouterr()
    main(["--проверить", str(расширение), "--задача", "TASK-1", "--профиль", профиль, "--json", str(ответ)])
    данные = json.loads(ответ.read_text(encoding="utf-8"))
    assert данные["находки"] == [], capsys.readouterr().out


@pytest.mark.parametrize("реестр, карточки, ожидание", [
    ("\r\n", "\r\n", "\r\n"),           # расширение тестов: всё в CRLF
    ("\n", "\n", "\n"),                 # основная конфигурация: всё в LF
    ("\r\n", "\n", "\n"),               # autocrlf: перевыгруженный реестр с CRLF среди LF
])
def test_new_files_take_the_line_endings_of_the_project_cards(tmp_path, реестр, карточки, ожидание):
    src = tmp_path / "src"
    написать(src, "Configuration/Configuration.mdo", РЕЕСТР, реестр)
    написать(src, "Catalogs/Договоры/Договоры.mdo", ЗАИМСТВОВАННЫЙ, карточки)
    написать(src, "CommonModules/ЮТест/ЮТест.mdo", СВОЙ, карточки)
    assert EdtDump(str(src)).eol == ожидание


def test_without_object_cards_line_endings_follow_the_registry(tmp_path):
    src = tmp_path / "src"
    написать(src, "Configuration/Configuration.mdo", РЕЕСТР, "\r\n")
    assert EdtDump(str(src)).eol == "\r\n"
