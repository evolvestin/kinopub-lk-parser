import logging
import subprocess

from django.conf import settings
from redis import Redis

from app.management.base import LoggableBaseCommand
from app.models import TaskRun
from kinopub_parser import celery_app


class Command(LoggableBaseCommand):
    help = 'Forcefully resets all Redis locks and cleans up stuck tasks in the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--purge',
            action='store_true',
            help='Purge all pending tasks from Redis queue.',
        )

    def handle(self, *args, **options):
        try:
            r = Redis.from_url(settings.CELERY_BROKER_URL)
            removed_locks_count = 0

            # Ищем ВООБЩЕ ВСЕ ключи блокировок по паттернам
            all_keys = set()
            for p in ['*lock*', '*queue*']:
                all_keys.update(r.keys(p))

            for key in all_keys:
                if r.delete(key):
                    removed_locks_count += 1
                    logging.info(
                        f'Key "{key.decode() if isinstance(key, bytes) else key}" deleted.'
                    )

            # Сбрасываем все зависшие TaskRun
            stuck_tasks = TaskRun.objects.filter(status__in=['RUNNING', 'QUEUED'])
            stuck_count = stuck_tasks.count()
            if stuck_count > 0:
                stuck_tasks.update(
                    status='FAILURE',
                    error_message='Forced reset via resetlocks. Check worker logs for TimeLimitExceeded.',
                )
                logging.info(f'Marked {stuck_count} tasks as FAILURE.')

            if options.get('purge'):
                celery_app.control.purge()
                logging.info('Celery queues purged.')

            # Очистка зомби-процессов Chrome
            subprocess.run(['pkill', '-f', 'chromium'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'chromedriver'], stderr=subprocess.DEVNULL)

            logging.info(
                f'Cleanup finished. Keys reset: {removed_locks_count}. Tasks: {stuck_count}.'
            )

        except Exception as e:
            logging.error(f'Failed reset: {e}')
            raise e
