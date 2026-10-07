"""Изменение свойств: адрес, правка на месте, отчёт «было → стало».

Главное свойство операции проверяется здесь буквально: правка одного значения
меняет в файле одну строку. Держится это на устройстве, а не на аккуратности:
все операции правят одно дерево карточки, и нетронутое остаётся байт в байт.
"""

import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from meta.application.change_property.use_case import ChangePropertyUseCase  # noqa: E402
from meta.domain.kinds import kind_of  # noqa: E402
from meta.domain.model import Refuse  # noqa: E402
from meta.infra.designer import DesignerDump  # noqa: E402
from meta.jobs import dialect as job_dialect  # noqa: E402
from meta.tests import corpus  # noqa: E402

CARD = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.21">
\t<Catalog uuid="c1">
\t\t<Properties>
\t\t\t<Name>мой_Проба</Name>
\t\t\t<Comment>не трогать</Comment>
\t\t\t<CodeLength>9</CodeLength>
\t\t</Properties>
\t\t<ChildObjects>
\t\t\t<Attribute uuid="a1">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Код</Name>
\t\t\t\t\t<Synonym>
\t\t\t\t\t\t<v8:item>
\t\t\t\t\t\t\t<v8:lang>ru</v8:lang>
\t\t\t\t\t\t\t<v8:content>Код</v8:content>
\t\t\t\t\t\t</v8:item>
\t\t\t\t\t</Synonym>
\t\t\t\t\t<Indexing>DontIndex</Indexing>
\t\t\t\t</Properties>
\t\t\t</Attribute>
\t\t\t<TabularSection uuid="t1">
\t\t\t\t<Properties>
\t\t\t\t\t<Name>Строки</Name>
\t\t\t\t</Properties>
\t\t\t\t<ChildObjects>
\t\t\t\t\t<Attribute uuid="a2">
\t\t\t\t\t\t<Properties>
\t\t\t\t\t\t\t<Name>Сумма</Name>
\t\t\t\t\t\t\t<FillChecking>DontCheck</FillChecking>
\t\t\t\t\t\t</Properties>
\t\t\t\t\t</Attribute>
\t\t\t\t</ChildObjects>
\t\t\t</TabularSection>
\t\t</ChildObjects>
\t</Catalog>
</MetaDataObject>"""

REGISTRY = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
            "\t<Configuration>\n\t\t<ChildObjects>\n"
            "\t\t\t<Catalog>мой_Проба</Catalog>\n"
            "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")


@pytest.fixture
def dump():
    root = tempfile.mkdtemp(prefix="meta-change-")
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(REGISTRY)
    os.makedirs(os.path.join(root, "Catalogs"))
    open(os.path.join(root, "Catalogs", "мой_Проба.xml"), "w",
         encoding="utf-8-sig", newline="").write(CARD)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def card_of(root):
    return open(os.path.join(root, "Catalogs", "мой_Проба.xml"),
                encoding="utf-8-sig").read().replace("\r\n", "\n")


def change(root, path, fields, apply_now=True):
    return ChangePropertyUseCase(DesignerDump(root)).execute(
        [(job_dialect.path_from_json(path), fields)], apply_now=apply_now)


def test_one_property_changes_one_line(dump):
    """Соседние строки обязаны остаться теми же байтами."""
    before = card_of(dump).split("\n")
    change(dump, "Справочник.мой_Проба.Реквизит.Код",
           {"индексирование": "Индексировать"})
    after = card_of(dump).split("\n")
    assert len(before) == len(after)
    different = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert len(different) == 1, [before[i] + " -> " + after[i] for i in different]
    assert after[different[0]].strip() == "<Indexing>Index</Indexing>"


@pytest.mark.parametrize("path, fields, expected", [
    ("Справочник.мой_Проба", {"длинаКода": "12"}, "<CodeLength>12</CodeLength>"),
    ("Справочник.мой_Проба.Реквизит.Код", {"индексирование": "Индексировать"},
     "<Indexing>Index</Indexing>"),
    ("Справочник.мой_Проба.ТабличнаяЧасть.Строки.Реквизит.Сумма",
     {"проверкаЗаполнения": "ВыдаватьОшибку"}, "<FillChecking>ShowError</FillChecking>"),
])
def test_address_reaches_every_depth(dump, path, fields, expected):
    """Объект, его реквизит, реквизит его табличной части — один механизм."""
    change(dump, path, fields)
    assert expected in card_of(dump)


def test_a_change_preview_names_the_change_and_not_defaults(dump):
    """Правка показывает, что меняется, и не говорит про умолчания.

    Неназванные поля существующего объекта остаются такими, какие записаны;
    строка «ещё N полей не названо — значения по умолчанию» из просмотра
    создания про правку была бы неправдой.
    """
    from meta.report.result import result_lines

    сказано = "\n".join(result_lines(change(
        dump, "Справочник.мой_Проба", {"длинаКода": "12"}, apply_now=False)))
    assert 'длинаКода: "12"' in сказано, сказано
    assert "по умолчанию" not in сказано, сказано


def test_multilang_property_is_replaced_whole(dump):
    """Синоним — не строка, а поддерево; заменяется целиком и с отступами."""
    change(dump, "Справочник.мой_Проба.Реквизит.Код", {"синоним": "Новый"})
    text = card_of(dump)
    assert "<v8:content>Новый</v8:content>" in text
    assert "<v8:content>Код</v8:content>" not in text
    assert "\t\t\t\t\t\t\t<v8:content>Новый</v8:content>\n" in text


def test_report_shows_the_value_not_the_markup(dump):
    """«Было → стало» про значение: разметка топит собой то, ради чего отчёт."""
    result = change(dump, "Справочник.мой_Проба.Реквизит.Код",
                    {"индексирование": "Индексировать"}, apply_now=False)
    said = "\n".join(result.plan.describe())
    # Значение названо и как в задании, и как ляжет в файл: задание
    # пишется по-русски, и одно «стало Index» заставило бы переводить
    # обратно в голове, чтобы убедиться, что просил именно это.
    assert "было DontIndex стало Индексировать (Index)" in said, said
    assert "xmlns" not in said


def test_preview_writes_nothing(dump):
    before = card_of(dump)
    change(dump, "Справочник.мой_Проба", {"длинаКода": "12"}, apply_now=False)
    assert card_of(dump) == before


def test_rename_is_refused_as_a_different_operation(dump):
    """Имя живёт ещё в реестре, порождаемых типах и чужих карточках."""
    result = change(dump, "Справочник.мой_Проба.Реквизит.Код", {"имя": "Другое"},
                    apply_now=False)
    assert [f.code for f in result.errors] == ["МД-ПЕРЕИМЕНОВАНИЕ"]
    assert "Код" in card_of(dump)


def test_unknown_field_is_refused_with_the_known_ones(dump):
    result = change(dump, "Справочник.мой_Проба.Реквизит.Код",
                    {"индексация": "Индексировать"}, apply_now=False)
    assert [f.code for f in result.errors] == ["МД-ПОЛЕ-НЕИЗВЕСТНО"]
    assert "индексирование" in result.errors[0].message


def test_missing_target_is_refused(dump):
    with pytest.raises(Refuse) as refusal:
        change(dump, "Справочник.мой_Проба.Реквизит.НетТакого", {"синоним": "х"})
    assert "нет «Реквизит.НетТакого»" in str(refusal.value)


def test_unknown_enum_value_is_refused_with_the_allowed_ones(dump):
    with pytest.raises(Refuse) as refusal:
        change(dump, "Справочник.мой_Проба.Реквизит.Код",
               {"индексирование": "Как-нибудь"})
    assert "допустимо: НеИндексировать, Индексировать" in str(refusal.value)


def test_property_absent_in_the_card_is_refused(dump):
    """Менять то, чего в карточке нет, нельзя: это уже добавление свойства."""
    with pytest.raises(Refuse) as refusal:
        change(dump, "Справочник.мой_Проба.Реквизит.Код", {"маска": "999"})
    assert "нет свойства" in str(refusal.value)


@pytest.mark.parametrize("bad", [
    "Справочник", "Справочник.мой_Проба.Реквизит", "", "..",
])
def test_address_must_come_in_pairs(bad):
    with pytest.raises(Refuse) as refusal:
        job_dialect.path_from_json(bad)
    assert "парами" in str(refusal.value)


def test_two_changes_in_one_file_do_not_overwrite_each_other(dump):
    """Две правки одной карточки обязаны лечь в одно изменение."""
    ChangePropertyUseCase(DesignerDump(dump)).execute([
        (job_dialect.path_from_json("Справочник.мой_Проба"), {"длинаКода": "12"}),
        (job_dialect.path_from_json("Справочник.мой_Проба.Реквизит.Код"),
         {"индексирование": "Индексировать"}),
    ], apply_now=True)
    text = card_of(dump)
    assert "<CodeLength>12</CodeLength>" in text
    assert "<Indexing>Index</Indexing>" in text


def test_check_change_does_not_demand_a_whole_object():
    """Частичная правка не обязана выглядеть как полная спецификация.

    Проверка по неполным данным полными правилами дала бы «поле обязательно
    и не заполнено» на каждое незаданное поле — и операция стала бы невозможна.
    """
    assert kind_of("Реквизит").check_change({"синоним": "Новый"}) == []


def test_a_real_card_keeps_its_own_line_endings(tmp_path):
    """Байты против байтов на копии настоящей карточки.

    Тесты на фикстурах сравнивают приведённые тексты: фикстуры пишутся с LF,
    а `card_of` снимает `\r\n`, — и запись, навязавшая CRLF всему файлу, их
    не уронит. А карточки замеренной выгрузки лежат с LF, и такая запись
    переписала бы при правке одного свойства все 1615 строк: человек,
    переносящий правку в базу, увидел бы diff во весь файл и не смог бы
    прочитать, что изменилось.

    Здесь сравниваются именно байты, и источник — настоящая карточка, а не
    фикстура: подогнать её переводы строк под удобные нельзя.
    """
    if not corpus.available():
        pytest.skip(f"пропущен: нет выгрузки {corpus.CORPUS}")
    source = os.path.join(corpus.CORPUS, "Catalogs", "БанковскиеСчета.xml")
    if not os.path.isfile(source):
        pytest.skip(f"пропущен: нет {source}")

    root = str(tmp_path)
    open(os.path.join(root, "Configuration.xml"), "w",
         encoding="utf-8-sig", newline="").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject>\n'
        "\t<Configuration>\n\t\t<ChildObjects>\n"
        "\t\t\t<Catalog>БанковскиеСчета</Catalog>\n"
        "\t\t</ChildObjects>\n\t</Configuration>\n</MetaDataObject>")
    os.makedirs(os.path.join(root, "Catalogs"))
    target = os.path.join(root, "Catalogs", "БанковскиеСчета.xml")
    shutil.copy2(source, target)

    before = open(target, "rb").read().split(b"\n")
    ChangePropertyUseCase(DesignerDump(root)).execute(
        [job_dialect.change_job_from_json(
            {"путь": "Справочник.БанковскиеСчета",
             "поля": {"комментарий": "проба"}})], apply_now=True)
    after = open(target, "rb").read().split(b"\n")

    assert len(before) == len(after)
    same = sum(1 for a, b in zip(before, after, strict=True) if a == b)
    assert same == len(before) - 1, (
        f"побайтно совпало {same} строк из {len(before)} — "
        "правка одного свойства переписала файл")

