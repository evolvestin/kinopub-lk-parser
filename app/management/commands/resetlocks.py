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

            try:
                i = celery_app.control.inspect()
                active_tasks = i.active() or {}
                for worker_name, tasks in active_tasks.items():
                    for task in tasks:
                        task_id = task.get('id')
                        if task_id:
                            celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
                            logging.info(f'Revoked active Celery task {task_id} on {worker_name}')
            except Exception:
                pass

            all_keys = set()
            for p in ['*lock*', '*queue*', 'celery*']:
                all_keys.update(r_broker.keys(p))

            for key in all_keys:
                if r_broker.delete(key):
                    removed_locks_count += 1
                    logging.info(
                        f'Key "{key.decode() if isinstance(key, bytes) else key}" deleted from broker.'
                    )

            try:
                cache.clear()
                logging.info('Django cache (Redis DB 1) cleared successfully.')
            except Exception:
                pass

            stuck_tasks = TaskRun.objects.filter(
                status__in=[TaskRunStatus.RUNNING, TaskRunStatus.QUEUED]
            )
            stuck_count = stuck_tasks.count()
            if stuck_count > 0:
                stuck_tasks.update(
                    status=TaskRunStatus.FAILURE,
                    error_message='Forced reset via resetlocks.',
                )
                logging.info(f'Marked {stuck_count} tasks as FAILURE.')

            if options.get('purge'):
                try:
                    celery_app.control.purge()
                    logging.info('Celery queues purged.')
                except Exception:
                    pass

            # Очистка зомби-процессов Chrome
            subprocess.run(['pkill', '-f', 'chromium'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'chromedriver'], stderr=subprocess.DEVNULL)

            logging.info(
                f'Cleanup finished. Keys reset: {removed_locks_count}. Tasks: {stuck_count}.'
            )

        except Exception as e:
            logging.error(f'Failed reset: {e}')
            raise e
