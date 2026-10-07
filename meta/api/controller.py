"""Контроллер MCP: запрос агента -> модель приложения -> сценарий.

Как и у терминала, сценариев он не создаёт и инфраструктуры не знает: корень
сборки передаёт ему фабрики, потому что выгрузка приходит в каждом запросе.
Модель запроса MCP (`api.models`) до сценария не доходит — контроллер
переводит её в модель приложения языком заданий.
"""

from ..domain.model import Refuse
from ..jobs import dialect, families
from ..jobs.plan import план_из_json
from .models import в_язык_заданий, код_в_язык_заданий, план_в_язык_плана


class Controller:
    """Переводчик MCP.

    `scenarios` — {семья операций: фабрика(выгрузка) -> сценарий};
    `show`, `show_form` — фабрики сценариев чтения; `reference` — справка;
    `verify`, `normalize`, `plan_check`, `plan_emit` — фабрики проверки правок,
    нормализации формата и сценариев плана изменений по источнику (выгрузка и
    база или пара каталогов).
    """

    def __init__(self, scenarios, show, show_form, reference, verify=None, normalize=None,
                 plan_check=None, plan_emit=None):
        self.scenarios = scenarios
        self.show_object = show
        self.show_form = show_form
        self.reference = reference
        self.verify_case = verify
        self.normalize_case = normalize
        self.plan_check_case = plan_check
        self.plan_emit_case = plan_emit

    def forms(self, repo, формы, apply_now=False):
        """Задание на формы моделями -> результат сценария."""
        return self._execute({"repo": repo, "forms": в_язык_заданий(формы)}, apply_now)

    def code(self, repo, task, date, author, модули, перенос=None, apply_now=False):
        """Задание на код моделями -> результат сценария правки вставками."""
        job = {"repo": repo, "task": task, "date": date, "author": author}
        job.update(код_в_язык_заданий(модули, перенос))
        return self._execute(job, apply_now)

    def metadata(self, job, apply_now=False):
        """Задание на метаданные словарём -> результат сценария.

        Формы сюда не принимаются: у них свой инструмент с описанной типами
        моделью, и два пути к одной операции разошлись бы в первой же правке.
        """
        if isinstance(job, dict) and job.get("forms"):
            raise Refuse("формы — инструментами forms_check и forms_apply, "
                         "здесь задания на объекты и их части")
        if isinstance(job, dict) and any(job.get(ключ) for ключ in
                                         ("modules", "модуль", "path", "move_method")):
            raise Refuse("код — инструментами code_check и code_apply, "
                         "здесь задания на объекты и их части")
        return self._execute(job, apply_now)

    def _execute(self, job, apply_now):
        repo = families.repo_of(job)
        family, works = families.parse(job)
        return self.scenarios[family](repo).execute(works, apply_now=apply_now)

    def show(self, repo, address):
        """Что лежит по адресу: ("форма", вид, имя, файл, модуль, своя) или ("объект", spec, файл)."""
        if dialect.looks_like_a_form(address):
            owner, name = dialect.form_address(address)
            view, form_file, module_file, своя = self.show_form(repo).execute(owner, name)
            return "форма", view, name, form_file, module_file, своя
        spec, файл = self.show_object(repo).execute(dialect.path_from_json(address))
        return "объект", spec, файл

    def verify(self, repo=None, base="HEAD", rev=None, baseline=None, target=None, task=None,
               only=None):
        """Проверка правок задачи: выгрузка под git против базы или пара каталогов."""
        сценарий = self.verify_case(repo=repo, base=base, rev=rev, baseline=baseline, target=target)
        return сценарий.execute(task=task or None, only=list(only) if only else None)

    def normalize(self, repo=None, base="HEAD", baseline=None, target=None, apply_now=False):
        """Нормализация формата файлов задачи: просмотр или запись."""
        сценарий = self.normalize_case(repo=repo, base=base, baseline=baseline, target=target)
        return сценарий.execute(apply_now=apply_now)

    def plan_check(self, objects, repo=None, base="HEAD", rev=None, baseline=None, target=None):
        """Сверка плана с фактом: объекты плана моделями -> язык плана -> сценарий."""
        план = план_из_json({"объекты": план_в_язык_плана(objects)})
        сценарий = self.plan_check_case(repo=repo, base=base, rev=rev, baseline=baseline, target=target)
        return сценарий.execute(план)

    def plan_emit(self, repo=None, base="HEAD", rev=None, baseline=None, target=None):
        """План по факту задачи."""
        return self.plan_emit_case(repo=repo, base=base, rev=rev, baseline=baseline,
                                   target=target).execute()

    def kinds(self):
        return self.reference.kinds()

    def kind(self, name):
        return self.reference.kind(name)

    def kind_names(self):
        return self.reference.names()
