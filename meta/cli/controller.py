"""Контроллер терминала: задание и ключи -> модель приложения -> сценарий.

Сценариев он не создаёт и инфраструктуры не знает: корень сборки передаёт ему
фабрики — «сценарий для этой выгрузки», потому что выгрузка приходит в каждом
запросе. Контроллер переводит модель канала в модель приложения и зовёт
сценарий; текст ответа делает язык ответов, печать — `app`.
"""

from ..jobs import dialect, families
from ..jobs.plan import план_из_json


class Controller:
    """Переводчик терминала.

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

    def execute(self, job, apply_now=False):
        """Задание словарём -> результат сценария."""
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

    def plan_check(self, plan, repo=None, base="HEAD", rev=None, baseline=None, target=None):
        """Сверка плана с фактом: план JSON-ом (словарь или текст) -> язык плана -> сценарий."""
        план = план_из_json(plan)
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
