import logging

from django.core.management.base import BaseCommand


class LoggableBaseCommand(BaseCommand):
    """
    Базовый класс для команд, который перехватывает любые исключения
    и записывает их в системный лог (LogEntry) перед падением.
    """

    def execute(self, *args, **options):
        try:
            return super().execute(*args, **options)
        except Exception as e:
            # Записываем ошибку в БД с полным трейсбеком
            logging.error(f'Command failed: {e}', exc_info=True)
            # Пробрасываем ошибку дальше, чтобы Celery/TaskRun пометили задачу как FAILURE
            raise e
