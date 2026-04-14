import logging

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
        lock_keys_patterns = [
            'selenium_global_lock',
            'backup_lock',
            'cookies_backup_lock',
            'sync_poiskkino_ratings',
            'lock:selenium_global_lock',
            'lock:backup_lock',
        ]

        try:
            r = Redis.from_url(settings.CELERY_BROKER_URL)
            removed_locks_count = 0

            for pattern in lock_keys_patterns:
                keys = r.keys(f'*{pattern}*')
                for key in keys:
                    if r.delete(key):
                        removed_locks_count += 1
                        logging.info(f'Lock "{key.decode() if isinstance(key, bytes) else key}" has been reset.')

            stuck_tasks = TaskRun.objects.filter(status__in=['RUNNING', 'QUEUED'])
            stuck_count = stuck_tasks.count()
            if stuck_count > 0:
                stuck_tasks.update(
                    status='FAILURE',
                    error_message='Forced reset via resetlocks command.'
                )
                logging.info(f'Marked {stuck_count} stuck tasks as FAILURE in database.')

            if options.get('purge'):
                logging.info('Purging Celery queues in Redis...')
                celery_app.control.purge()
                logging.info('Redis queue purged successfully.')

            if removed_locks_count == 0 and stuck_count == 0:
                logging.info('No active locks or stuck tasks found.')
            else:
                logging.info(f'Cleanup finished. Locks reset: {removed_locks_count}. Tasks reset: {stuck_count}.')

        except Exception as e:
            logging.error(f'Failed to perform full reset: {e}')
            raise e