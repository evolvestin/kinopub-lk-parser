import logging

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
            revoked_tasks_count = 0

            try:
                i = celery_app.control.inspect()
                active_tasks = i.active() or {}
                for _, tasks in active_tasks.items():
                    for task in tasks:
                        task_id = task.get('id')
                        if task_id:
                            celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
                            revoked_tasks_count += 1
            except Exception:
                pass

            all_keys = set()
            for p in ['lock:*', 'queue:*']:
                all_keys.update(r_broker.keys(p))

            for key in all_keys:
                if r_broker.delete(key):
                    removed_locks_count += 1

            try:
                cache.clear()
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

            if options.get('purge'):
                try:
                    celery_app.control.purge()
                except Exception:
                    pass

            logging.info(
                f'Resetlocks completed. Keys deleted: {removed_locks_count}, '
                f'Revoked tasks: {revoked_tasks_count}, DB tasks reset: {stuck_count}.'
            )

        except Exception as e:
            logging.error(f'Failed reset: {e}')
            raise e
