"""Итог сценария: находки, план, что записано, и где споткнулись."""

from contextlib import contextmanager

from ..domain.model import Refuse


@contextmanager
def при(что):
    """Отказ изнутри дополняется адресом пункта задания.

    Имена полей проверяет домен и собирает все находки разом; значения полей
    проверяет перекладка, и первое же неизвестное слово рвёт задание
    исключением. Само по себе это верно — записать неверно хуже, — но без
    адреса сообщение не говорит, на каком пункте: в задании из двадцати
    отборов «не знаю, как записать „Равнo“» отправляет искать опечатку глазами.
    """
    try:
        yield
    except Refuse as отказ:
        raise Refuse(f"{что}: {отказ}") from отказ


class Result:
    """Что вышло: находки по каждому объекту, план изменений, писали или смотрели."""

    def __init__(self, per_object, plan=None, written=None, code=None, handlers=None,
                 code_notes=None, code_places=None, code_language=None):
        self.per_object = list(per_object)      # (спецификация, находки)
        self.plan = plan
        self.written = list(written or [])
        #: адрес -> текст кода, когда сценарий выдаёт код вместо правки файлов
        #: (типовая форма: её XML не правится — только программно)
        self.code = dict(code or {})
        # адрес формы -> [(область, имя, директива, параметры)] обработчиков кода формы
        self.handlers = dict(handlers or {})
        # адрес формы -> пояснения к коду формы (как «после» стало «перед»)
        self.code_notes = dict(code_notes or {})
        # адрес формы -> [domain.forms.CodePlace]: куда ложатся процедура и вызов
        self.code_places = dict(code_places or {})
        #: (заголовок фрагмента, хвост описания процедуры) — слова языка кода
        #: формы: «Код доработки формы» у платформы, своё у диалекта команды
        self.code_language = code_language or ("Код доработки формы", "")

    @property
    def findings(self):
        return [f for _, findings in self.per_object for f in findings]

    @property
    def errors(self):
        return [f for f in self.findings if f.blocking]

    @property
    def warnings(self):
        return [f for f in self.findings if not f.blocking]

    @property
    def ok(self):
        return not self.errors


class CodeResult:
    """Что вышло с заданием на код: решения по каждому модулю и план записи.

    Отказа здесь не бывает: задание на код атомарно, и любой отказ рвёт его
    целиком исключением, не записав ни одного модуля.
    """

    def __init__(self, signature, per_module, plan=None, written=None, notes=(), formats=None):
        self.signature = signature
        self.per_module = list(per_module)      # (ссылка на модуль, решения)
        self.plan = plan
        self.written = list(written or [])
        self.notes = list(notes)                # примечания ко всему заданию
        self.formats = dict(formats or {})      # ссылка словами -> «CRLF, BOM»

    @property
    def ok(self):
        return True


class VerifyResult:
    """Что нашла проверка правок задачи.

    `source` — что с чем сравнивалось, словами; `files` — файлы задачи
    (`domain.changes.FileChange`); `findings` — находки (`FileFinding`);
    `skipped` — [(что, почему)] правил, которые не проверялись: «чисто» при
    пропусках не выдаётся; `notes` — пояснения, не меняющие вердикта.
    """

    def __init__(self, source, files, findings, skipped=(), notes=()):
        self.source = source
        self.files = list(files)
        self.findings = list(findings)
        self.skipped = list(skipped)
        self.notes = list(notes)

    @property
    def errors(self):
        return [f for f in self.findings if f.blocking]

    @property
    def warnings(self):
        return [f for f in self.findings if not f.blocking]

    @property
    def ok(self):
        return not self.errors


class NormalizeResult:
    """Что нормализация вернёт файлам задачи.

    `fixes` — [(путь, [что исправлено словами])] у файлов, которым нужна
    правка; `plan` — перезапись этих файлов; `written` — записанное, если
    писали; `notes` — пояснения (переводы строк не сверяются и т. п.).
    """

    def __init__(self, source, files, fixes, plan=None, written=None, notes=()):
        self.source = source
        self.files = list(files)
        self.fixes = list(fixes)
        self.plan = plan
        self.written = list(written or [])
        self.notes = list(notes)

    @property
    def ok(self):
        return not self.fixes


class PlanCheckResult:
    """Что дала сверка плана изменений с фактом.

    `source` — что с чем сравнивалось, словами; `plan` — план (`domain.plan.План`);
    `touched` — объекты, файлы которых задача тронула, [(вид, имя)];
    `findings` — расхождения (`domain.plan.НаходкаПлана`); `notes` — пояснения.
    """

    def __init__(self, source, plan, touched, findings, notes=()):
        self.source = source
        self.plan = plan
        self.touched = list(touched)
        self.findings = list(findings)
        self.notes = list(notes)

    @property
    def errors(self):
        return [f for f in self.findings if f.blocking]

    @property
    def warnings(self):
        return [f for f in self.findings if not f.blocking]

    @property
    def ok(self):
        return not self.errors


class PlanEmitResult:
    """План по факту: `source` — что с чем сравнивалось; `plan` — `domain.plan.План`."""

    def __init__(self, source, plan):
        self.source = source
        self.plan = plan
