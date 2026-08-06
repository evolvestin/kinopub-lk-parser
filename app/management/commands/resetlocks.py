import logging
import subprocess

from django.conf import settings
from django.core.cache import cache
from redis import Redis

from app.management.base import LoggableBaseCommand
from app.models import TaskRun
from kinopub_parser import celery_app
from shared.constants import TaskRunStatus


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
            r_broker = Redis.from_url(settings.CELERY_BROKER_URL)
            removed_locks_count = 0

            # Ищем ВООБЩЕ ВСЕ ключи блокировок по паттернам
            all_keys = set()
            for p in ['*lock*', '*queue*']:
                all_keys.update(r_broker.keys(p))

            for key in all_keys:
                if r_broker.delete(key):
                    removed_locks_count += 1
                    logging.info(
                        f'Key "{key.decode() if isinstance(key, bytes) else key}" '
                        f'deleted from broker.'
                    )

            try:
                cache.clear()
                logging.info('Django cache (Redis DB 1) cleared successfully.')
            except Exception as cache_err:
                logging.warning(f'Failed to clear Django cache: {cache_err}')

            stuck_tasks = TaskRun.objects.filter(
                status__in=[TaskRunStatus.RUNNING, TaskRunStatus.QUEUED]
            )
            stuck_count = stuck_tasks.count()
            if stuck_count > 0:
                stuck_tasks.update(
                    status=TaskRunStatus.FAILURE,
                    error_message='Forced reset via resetlocks. Check logs for TimeLimitExceeded.',
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
