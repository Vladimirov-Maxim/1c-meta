"""Управляемая форма -> HTML: третье отображение той же модели.

Платформа отображает дерево формы дважды: толстый и тонкий клиент рисуют его
сами (Cairo, FreeType, HarfBuzz), а веб-клиент разворачивает то же дерево
в DOM обычного браузера. Здесь третье отображение, самое грубое: структура
верна, пиксели нет.

Зачем оно. Модель формы — не раскладка, а дерево групп и полей, где геометрию
решает платформа; посмотреть на результат без загрузки в базу нельзя, и правка
формы идёт вслепую. HTML эту петлю замыкает: страницу видно сразу.

Почему это выполнимо. Замер по всем 11 042 формам реальной выгрузки: видов
элементов всего 31, пять из них покрывают 78 % (`InputField`, `UsualGroup`,
`LabelDecoration`, `LabelField`, `Button`), двенадцать — 95 %. В обычной форме
используется пять видов, у 90 % форм не больше десяти. Соответствие с HTML
выходит один в один, а не натяжкой.

Неизвестное не выбрасывается: незнакомый вид элемента остаётся в выводе
видимым блоком с его именем. Молча потерять элемент здесь хуже, чем показать
его некрасиво.
"""

#: Направление потока группы. У 1С это «поток», у флексбокса
#: `flex-direction` — понятие одно и то же.
#: Замер по 60 331 группе: `Vertical` 22 466, `Horizontal` 21 892,
#: `AlwaysHorizontal` 9145, `HorizontalIfPossible` 6796. Четыре значения,
#: и пропустить любое значит нарисовать раскладку неверно.
НАПРАВЛЕНИЕ = {"Vertical": "Вертикальная",
               "Horizontal": "Горизонтальная",
               "AlwaysHorizontal": "Горизонтальная",
               "HorizontalIfPossible": "Горизонтальная"}

#: Элементы, которые платформа заводит сама у каждого поля: контекстное меню
#: и расширенная подсказка. В дереве они есть всегда, смысла для взгляда
#: не несут — 331 254 и 190 509 штук на корпусе, то есть чистый шум.
СПУТНИКИ = ("ContextMenu", "ExtendedTooltip", "SearchStringAddition",
            "SearchControlAddition", "ViewStatusAddition")

#: Вид элемента -> тег и класс. Покрытие каждого — из замера по корпусу.
ЭЛЕМЕНТЫ = {
    "UsualGroup": ("div", "группа"),            # 60 331, 21.6 %
    "InputField": ("label", "поле"),            # 64 848, 23.2 %
    "LabelDecoration": ("span", "надпись"),     # 34 783, 12.4 %
    "LabelField": ("label", "поле-надпись"),    # 30 081, 10.8 %
    "Button": ("button", "кнопка"),             # 27 906, 10.0 %
    "Page": ("section", "страница"),            # 9 676
    "CheckBoxField": ("label", "флажок"),       # 9 541
    "Table": ("div", "таблица"),                # 9 192
    "PictureDecoration": ("span", "картинка"),  # 7 274
    "ColumnGroup": ("div", "колонки"),          # 5 490
    "Pages": ("div", "вкладки"),                # 3 913
    "ButtonGroup": ("div", "кнопки"),           # 3 727
    "CommandBar": ("div", "панель"),            # 3 391
    "Popup": ("div", "подменю"),                # 2 319
    "RadioButtonField": ("label", "переключатель"),
    "PictureField": ("span", "поле-картинка"),
    # Листовые поля-документы. Структуры в них нет — для взгляда это
    # прямоугольник с именем, и этого достаточно: их 2464 формы на корпусе,
    # из них 2078 приходится на табличный документ.
    "SpreadSheetDocumentField": ("div", "документ табличный"),
    "HTMLDocumentField": ("div", "документ html"),
    "TextDocumentField": ("div", "документ текстовый"),
    "FormattedDocumentField": ("div", "документ форматированный"),
    "PDFDocumentField": ("div", "документ pdf"),
    "GraphicalSchemaField": ("div", "документ графсхема"),
    "ChartField": ("div", "документ диаграмма"),
    "GanttChartField": ("div", "документ диаграмма"),
    "PlannerField": ("div", "документ планировщик"),
    "CalendarField": ("div", "документ календарь"),
    "ProgressBarField": ("div", "документ индикатор"),
    "TrackBarField": ("div", "документ регулятор"),
    "PeriodField": ("div", "документ период"),
}


def _текст(узел):
    """Многоязычное значение -> строка. Берём первую попавшуюся часть."""
    for item in узел.children:
        по_тегам = {_хвост(c.tag): c for c in item.children}
        содержимое = по_тегам.get("content")
        if содержимое is not None and содержимое.text:
            return содержимое.text
    return узел.text or ""


def _хвост(tag):
    return tag.split(":")[-1]


def _экранировать(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class _Элемент:
    """Разобранный элемент формы: вид, имя, свойства и дети."""

    def __init__(self, узел):
        self.kind = _хвост(узел.tag)
        self.name = узел.attrs.get("name", "")
        self.свойства = {}
        self.дети = []
        for ребёнок in узел.children:
            tk = _хвост(ребёнок.tag)
            if tk == "ChildItems":
                self.дети = [_Элемент(vv) for vv in ребёнок.children
                             if _хвост(vv.tag) not in СПУТНИКИ]
            elif tk in СПУТНИКИ:
                continue
            elif ребёнок.children:
                self.свойства[tk] = _текст(ребёнок)
            else:
                self.свойства[tk] = ребёнок.text or ""

    def подпись(self, реквизиты, извне=None):
        """Что платформа напишет слева от поля.

        В самом элементе подписи чаще всего нет: у поля `СкладОтбор` она
        лежит на реквизите формы, а у `Объект.Ответственный` — в синониме
        реквизита документа, то есть вообще в другом файле. Отсюда цепочка,
        и имя элемента в ней — последнее средство, а не первое:

        1. собственный `Title` элемента;
        2. `Title` реквизита формы, названного в `DataPath`;
        3. синоним реквизита объекта — его подставляет вызывающий, потому
           что читать карточки — не дело перекладки;
        4. последняя часть пути: «Объект.Ответственный» -> «Ответственный».
           Хуже подписи платформы, но много ближе, чем имя элемента.
        """
        own_one = self.свойства.get("Title")
        if own_one:
            return own_one
        path = self.свойства.get("DataPath", "")
        if not path:
            return self.name
        parts = path.split(".")
        if len(parts) == 1:
            return реквизиты.get(path, {}).get("Title") or path
        снаружи = извне(path) if извне else None
        return снаружи or parts[-1]


def _атрибуты_данных(element):
    """Привязки, ради которых форма и существует: путь и команда."""
    chunks = []
    for свойство, атрибут in (("DataPath", "data-путь"),
                              ("CommandName", "data-команда")):
        value = element.свойства.get(свойство)
        if value:
            chunks.append(f' {атрибут}="{_экранировать(value)}"')
    return "".join(chunks)


#: Виды, у которых подпись показывается слева от поля ввода.
ПОЛЯ_С_ПОДПИСЬЮ = ("InputField", "LabelField", "CheckBoxField",
                   "RadioButtonField", "PictureField")

#: Группы и контейнеры: собственного содержимого у них нет, только дети.
КОНТЕЙНЕРЫ = ("UsualGroup", "Pages", "ColumnGroup", "ButtonGroup",
              "CommandBar", "Popup", "Page", "Table")


def _разметка(element, indent=2, реквизиты=None, извне=None):
    """Один элемент формы -> строки HTML.

    Что показывать, а что нет, решено замером, а не вкусом: у 52 279 групп
    из 60 331 `Representation` равно `None` — рамки у них нет вовсе,
    а `ShowTitle` выключен у 54 984. Рисовать рамку вокруг каждой группы
    и печатать имя каждого элемента значит показывать не форму, а её разбор.
    """
    fields = "  " * indent
    тег, класс = ЭЛЕМЕНТЫ.get(element.kind, ("div", "неизвестный"))
    own = _атрибуты_данных(element)
    if element.kind not in ЭЛЕМЕНТЫ:
        # Незнакомое показывается, а не теряется: вид написан прямо в выводе.
        own += f' data-вид="{_экранировать(element.kind)}"'
    подпись = element.подпись(реквизиты or {}, извне)
    if element.kind in ("UsualGroup", "ColumnGroup", "ButtonGroup", "CommandBar"):
        # Направление потока — это и есть раскладка: у 1С «поток», в HTML флекс.
        # `AlwaysHorizontal` — 9145 групп, и без него каждая шестая группа
        # рисовалась бы вертикально вместо горизонтальной.
        поток = element.свойства.get("Group", "")
        направление = НАПРАВЛЕНИЕ.get(
            поток, "Горизонтальная" if element.kind != "UsualGroup"
            else "Вертикальная")
        own += f' data-направление="{_экранировать(направление)}"'
        класс += " по-горизонтали" if направление == "Горизонтальная" else ""
        рамка = element.свойства.get("Representation", "None")
        if рамка and рамка != "None":
            класс += " в-рамке"
            own += f' data-рамка="{_экранировать(рамка)}"'
    lines = [f'{fields}<{тег} class="{класс}"{own}>']
    if element.kind in ПОЛЯ_С_ПОДПИСЬЮ:
        # Подпись прячется, когда её прячет и платформа: `TitleLocation`
        # равно `None` у 6534 полей ввода и 2788 полей-надписей.
        where = element.свойства.get("TitleLocation", "Left")
        if where != "None" and подпись:
            класс_подписи = "подпись сверху" if where == "Top" else "подпись"
            lines.append(f'{fields}  <span class="{класс_подписи}">'
                          f"{_экранировать(подпись)}</span>")
        lines.append(f'{fields}  <input class="ввод" readonly value="">')
    elif element.kind in ("LabelDecoration", "Button"):
        lines.append(f"{fields}  {_экранировать(подпись)}")
    elif element.kind in КОНТЕЙНЕРЫ:
        # Платформа пишет `ShowTitle` только чтобы **спрятать** заголовок:
        # `false` стоит явно у 54 984 групп, а отсутствует тег у 5347 — и
        # у них заголовок виден. Трактовать отсутствие как «не показывать»
        # значило бы потерять заголовок у каждой одиннадцатой группы.
        видно = element.свойства.get("ShowTitle", "true") != "false"
        own_one = element.свойства.get("Title")
        if видно and own_one:
            сворачивается = element.свойства.get("Behavior") == "Collapsible"
            значок = "▾ " if сворачивается else ""
            lines.append(f'{fields}  <span class="заголовок">'
                          f"{значок}{_экранировать(own_one)}</span>")
    else:
        lines.append(f'{fields}  <span class="имя">'
                      f'{_экранировать(подпись or element.kind)}</span>')
    for ребёнок in element.дети:
        lines.extend(_разметка(ребёнок, indent + 1, реквизиты, извне))
    lines.append(f"{fields}</{тег}>")
    return lines


СТИЛЬ = """  :root { color-scheme: light dark; }
  body { font: 13px/1.45 "Segoe UI", system-ui, sans-serif; margin: 16px; }
  .форма { border: 1px solid #8884; border-radius: 6px; padding: 10px; }
  .группа, .колонки, .кнопки, .панель, .вкладки {
            display: flex; flex-direction: column; gap: 4px; }
  .по-горизонтали { flex-direction: row; align-items: center; }
  .в-рамке { border: 1px solid #8884; border-radius: 4px; padding: 6px; }
  .заголовок { font-weight: 600; }
  .подпись.сверху { text-align: left; min-width: 0; }
  .поле, .поле-надпись, .флажок, .переключатель {
            display: flex; gap: 6px; align-items: center; }
  .подпись { min-width: 12em; text-align: right; opacity: .8; }
  .ввод { flex: 1; min-width: 6em; border: 1px solid #8886; border-radius: 3px;
          padding: 2px 4px; background: #8881; }
  .кнопка { align-self: flex-start; padding: 3px 10px; }
  .вкладки { display: flex; flex-direction: column; gap: 4px; }
  .страница { border: 1px solid #8884; border-radius: 4px; padding: 6px; }
  .неизвестный { border: 2px solid #c33; border-radius: 4px; padding: 4px; }
  .неизвестный::before { content: "не знаю: " attr(data-вид); color: #c33; }
  .имя { opacity: .6; }
  .документ { border: 1px solid #8886; border-radius: 4px; padding: 10px;
              background: #8881; min-height: 3em; }
  .документ::before { content: attr(class); opacity: .5; font-size: 11px; }"""


def _реквизиты_формы(узел):
    """Реквизиты формы: имя -> заголовок и тип.

    Отсюда берутся подписи полей, у которых своего заголовка нет, — а таких
    большинство: у `СкладОтбор` подпись «Склад» лежит именно здесь.
    """
    собрано = {}
    for раздел in узел.children:
        if _хвост(раздел.tag) != "Attributes":
            continue
        for attribute in раздел.children:
            name = attribute.attrs.get("name")
            if not name:
                continue
            own = {}
            for свойство in attribute.children:
                tk = _хвост(свойство.tag)
                if tk == "Title":
                    own["Title"] = _текст(свойство)
                elif tk == "Type":
                    own["Type"] = " ".join(
                        (c.text or "").strip() for c in свойство.children)
            собрано[name] = own
    return собрано


def html_from_node(узел, title="", извне=None):
    """Разобранная форма -> страница HTML.

    Заголовок пишется в шапку, чтобы по вкладке браузера было видно,
    на какую форму смотришь.
    """
    composition = [c for c in узел.children if _хвост(c.tag) == "ChildItems"]
    верх = []
    for ребёнок in (composition[0].children if composition else []):
        if _хвост(ребёнок.tag) not in СПУТНИКИ:
            верх.append(_Элемент(ребёнок))
    направление = "по-горизонтали" if any(
        _хвост(c.tag) == "Group" and c.text == "Horizontal"
        for c in узел.children) else ""
    lines = [
        "<!doctype html>", '<html lang="ru"><head><meta charset="utf-8">',
        f"<title>{_экранировать(title or 'Форма')}</title>",
        "<style>", СТИЛЬ, "</style></head><body>",
        f"<h1>{_экранировать(title or 'Форма')}</h1>",
        f'<div class="форма группа {направление}">',
    ]
    реквизиты = _реквизиты_формы(узел)
    for element in верх:
        lines.extend(_разметка(element, 1, реквизиты, извне))
    lines += ["</div>", "</body></html>"]
    return "\n".join(lines)


def kinds_of(узел):
    """Виды элементов, встреченные в форме, — для замера покрытия."""
    found = set()

    def обойти(element):
        found.add(element.kind)
        for ребёнок in element.дети:
            обойти(ребёнок)

    composition = [c for c in узел.children if _хвост(c.tag) == "ChildItems"]
    for ребёнок in (composition[0].children if composition else []):
        if _хвост(ребёнок.tag) not in СПУТНИКИ:
            обойти(_Элемент(ребёнок))
    return found
