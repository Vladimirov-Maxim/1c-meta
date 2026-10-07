"""Показать, что лежит в выгрузке, на языке задания."""


class ShowUseCase:
    """Прочитать карточку и вернуть её спецификацией.

    Ничего не проверяет и ничего не пишет: это чтение. Инварианты здесь
    были бы не к месту — они судят намерение, а тут уже свершившееся.
    """

    def __init__(self, platform):
        self.platform = platform

    def execute(self, path):
        return self.platform.read_spec(path)
