# Сторонние компоненты

## Словарь свойств элементов формы — «Накидка» (md_design)

Откуда: проект «Накидка», https://github.com/crimsongoldteam/md_design — макет
`src/MDDesign/Templates/Свойства` обработки MDDesign в состоянии коммита `a07bfc3`
(27.11.2025, последняя правка макета на день снятия). Снят в
`tools/md_design_properties.tsv`; из него сценарий `tools/form_properties_from_md_design.py`
собирает `meta/domain/form_properties.py` (русские и английские имена свойств, типы
значений, умолчания, значения перечислений).

Лицензия — MIT, текст дословно из `LICENSE.md` проекта:

```
MIT License

Copyright (c) `2025` `Zherebtsov Nikita <nikita@crimsongold.ru>`

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Платформа 1С:Предприятие

Имена типов, свойств, событий и перечислений платформы — факты из синтакс-помощника
1С:Предприятия 8.5; код платформы и её документация в инструмент не входят.

Проект не связан с фирмой «1С» и ею не одобрен. «1С», «1С:Предприятие» и «1C:EDT» —
товарные знаки фирмы «1С»; прочие названия принадлежат их владельцам.

## Зависимости

Ставятся менеджером пакетов и в репозиторий не входят:

| Пакет | Зачем | Лицензия |
|---|---|---|
| lxml | разбор и сборка файлов выгрузки — нужна всегда | BSD-3-Clause |
| mcp | MCP-сервер для агентов (`meta/mcp_server.py`); терминалу не нужна | MIT |
| pydantic | схемы инструментов MCP-сервера; ставится вместе с `mcp` | MIT |
| pytest, ruff | проверки (`check.py`); работе инструмента не нужны | MIT |
