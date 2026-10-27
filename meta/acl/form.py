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
DIRECTION = {"Vertical": "Вертикальная",
               "Horizontal": "Горизонтальная",
               "AlwaysHorizontal": "Горизонтальная",
               "HorizontalIfPossible": "Горизонтальная"}

#: Элементы, которые платформа заводит сама у каждого поля: контекстное меню
#: и расширенная подсказка. В дереве они есть всегда, смысла для взгляда
#: не несут — 331 254 и 190 509 штук на корпусе, то есть чистый шум.
SATELLITES = ("ContextMenu", "ExtendedTooltip", "SearchStringAddition",
            "SearchControlAddition", "ViewStatusAddition")

#: Вид элемента -> тег и класс. Покрытие каждого — из замера по корпусу.
ELEMENTS = {
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


def _text(node):
    """Многоязычное значение -> строка. Берём первую попавшуюся часть."""
    for item in node.children:
        by_tag = {_tail(c.tag): c for c in item.children}
        content = by_tag.get("content")
        if content is not None and content.text:
            return content.text
    return node.text or ""


def _tail(tag):
    return tag.split(":")[-1]


def _escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class _Element:
    """Разобранный элемент формы: вид, имя, свойства и дети."""

    def __init__(self, node):
        self.kind = _tail(node.tag)
        self.name = node.attrs.get("name", "")
        self.props = {}
        self.children = []
        for child in node.children:
            tk = _tail(child.tag)
            if tk == "ChildItems":
                self.children = [_Element(vv) for vv in child.children
                             if _tail(vv.tag) not in SATELLITES]
            elif tk in SATELLITES:
                continue
            elif child.children:
                self.props[tk] = _text(child)
            else:
                self.props[tk] = child.text or ""

    def caption(self, attributes, external=None):
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
        own_one = self.props.get("Title")
        if own_one:
            return own_one
        path = self.props.get("DataPath", "")
        if not path:
            return self.name
        parts = path.split(".")
        if len(parts) == 1:
            return attributes.get(path, {}).get("Title") or path
        outer = external(path) if external else None
        return outer or parts[-1]


def _data_attributes(element):
    """Привязки, ради которых форма и существует: путь и команда."""
    chunks = []
    for prop, xml_attr in (("DataPath", "data-путь"),
                              ("CommandName", "data-команда")):
        value = element.props.get(prop)
        if value:
            chunks.append(f' {xml_attr}="{_escape(value)}"')
    return "".join(chunks)


#: Виды, у которых подпись показывается слева от поля ввода.
CAPTIONED_FIELDS = ("InputField", "LabelField", "CheckBoxField",
                   "RadioButtonField", "PictureField")

#: Группы и контейнеры: собственного содержимого у них нет, только дети.
CONTAINERS = ("UsualGroup", "Pages", "ColumnGroup", "ButtonGroup",
              "CommandBar", "Popup", "Page", "Table")


def _markup(element, indent=2, attributes=None, external=None):
    """Один элемент формы -> строки HTML.

    Что показывать, а что нет, решено замером, а не вкусом: у 52 279 групп
    из 60 331 `Representation` равно `None` — рамки у них нет вовсе,
    а `ShowTitle` выключен у 54 984. Рисовать рамку вокруг каждой группы
    и печатать имя каждого элемента значит показывать не форму, а её разбор.
    """
    fields = "  " * indent
    tag, cls_name = ELEMENTS.get(element.kind, ("div", "неизвестный"))
    own = _data_attributes(element)
    if element.kind not in ELEMENTS:
        # Незнакомое показывается, а не теряется: вид написан прямо в выводе.
        own += f' data-вид="{_escape(element.kind)}"'
    caption = element.caption(attributes or {}, external)
    if element.kind in ("UsualGroup", "ColumnGroup", "ButtonGroup", "CommandBar"):
        # Направление потока — это и есть раскладка: у 1С «поток», в HTML флекс.
        # `AlwaysHorizontal` — 9145 групп, и без него каждая шестая группа
        # рисовалась бы вертикально вместо горизонтальной.
        stream = element.props.get("Group", "")
        direction = DIRECTION.get(
            stream, "Горизонтальная" if element.kind != "UsualGroup"
            else "Вертикальная")
        own += f' data-направление="{_escape(direction)}"'
        cls_name += " по-горизонтали" if direction == "Горизонтальная" else ""
        border = element.props.get("Representation", "None")
        if border and border != "None":
            cls_name += " в-рамке"
            own += f' data-рамка="{_escape(border)}"'
    lines = [f'{fields}<{tag} class="{cls_name}"{own}>']
    if element.kind in CAPTIONED_FIELDS:
        # Подпись прячется, когда её прячет и платформа: `TitleLocation`
        # равно `None` у 6534 полей ввода и 2788 полей-надписей.
        where = element.props.get("TitleLocation", "Left")
        if where != "None" and caption:
            caption_class = "подпись сверху" if where == "Top" else "подпись"
            lines.append(f'{fields}  <span class="{caption_class}">'
                          f"{_escape(caption)}</span>")
        lines.append(f'{fields}  <input class="ввод" readonly value="">')
    elif element.kind in ("LabelDecoration", "Button"):
        lines.append(f"{fields}  {_escape(caption)}")
    elif element.kind in CONTAINERS:
        # Платформа пишет `ShowTitle` только чтобы **спрятать** заголовок:
        # `false` стоит явно у 54 984 групп, а отсутствует тег у 5347 — и
        # у них заголовок виден. Трактовать отсутствие как «не показывать»
        # значило бы потерять заголовок у каждой одиннадцатой группы.
        visible = element.props.get("ShowTitle", "true") != "false"
        own_one = element.props.get("Title")
        if visible and own_one:
            collapses = element.props.get("Behavior") == "Collapsible"
            icon = "▾ " if collapses else ""
            lines.append(f'{fields}  <span class="заголовок">'
                          f"{icon}{_escape(own_one)}</span>")
    else:
        lines.append(f'{fields}  <span class="имя">'
                      f'{_escape(caption or element.kind)}</span>')
    for child in element.children:
        lines.extend(_markup(child, indent + 1, attributes, external))
    lines.append(f"{fields}</{tag}>")
    return lines


STYLE = """  :root { color-scheme: light dark; }
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


def _form_attributes(node):
    """Реквизиты формы: имя -> заголовок и тип.

    Отсюда берутся подписи полей, у которых своего заголовка нет, — а таких
    большинство: у `СкладОтбор` подпись «Склад» лежит именно здесь.
    """
    collected = {}
    for section in node.children:
        if _tail(section.tag) != "Attributes":
            continue
        for attribute in section.children:
            name = attribute.attrs.get("name")
            if not name:
                continue
            own = {}
            for prop in attribute.children:
                tk = _tail(prop.tag)
                if tk == "Title":
                    own["Title"] = _text(prop)
                elif tk == "Type":
                    own["Type"] = " ".join(
                        (c.text or "").strip() for c in prop.children)
            collected[name] = own
    return collected


def html_from_node(node, title="", external=None):
    """Разобранная форма -> страница HTML.

    Заголовок пишется в шапку, чтобы по вкладке браузера было видно,
    на какую форму смотришь.
    """
    composition = [c for c in node.children if _tail(c.tag) == "ChildItems"]
    top = []
    for child in (composition[0].children if composition else []):
        if _tail(child.tag) not in SATELLITES:
            top.append(_Element(child))
    direction = "по-горизонтали" if any(
        _tail(c.tag) == "Group" and c.text == "Horizontal"
        for c in node.children) else ""
    lines = [
        "<!doctype html>", '<html lang="ru"><head><meta charset="utf-8">',
        f"<title>{_escape(title or 'Форма')}</title>",
        "<style>", STYLE, "</style></head><body>",
        f"<h1>{_escape(title or 'Форма')}</h1>",
        f'<div class="форма группа {direction}">',
    ]
    attributes = _form_attributes(node)
    for element in top:
        lines.extend(_markup(element, 1, attributes, external))
    lines += ["</div>", "</body></html>"]
    return "\n".join(lines)


def kinds_of(node):
    """Виды элементов, встреченные в форме, — для замера покрытия."""
    found = set()

    def walk(element):
        found.add(element.kind)
        for child in element.children:
            walk(child)

    composition = [c for c in node.children if _tail(c.tag) == "ChildItems"]
    for child in (composition[0].children if composition else []):
        if _tail(child.tag) not in SATELLITES:
            walk(_Element(child))
    return found
