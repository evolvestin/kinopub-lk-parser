import logging

from django.conf import settings
from redis import Redis

from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Forcefully resets all Redis locks used by the application.'

    def handle(self, *args, **options):
        lock_keys = [
            'selenium_global_lock',
            'backup_lock',
            'cookies_backup_lock',
            'sync_poiskkino_ratings',
        ]

        try:
            r = Redis.from_url(settings.CELERY_BROKER_URL)
            removed_count = 0

            for key in lock_keys:
                # В redis-py ключи блокировок обычно имеют префикс, но мы удаляем по именам
                # Если используется стандартный lock(), ключ в Redis называется так же.
                if r.delete(key):
                    removed_count += 1
                    logging.info(f'Lock "{key}" has been reset.')

            if removed_count == 0:
                logging.info('No active locks found in Redis.')
            else:
                logging.info(f'Successfully reset {removed_count} lock(s).')

        except Exception as e:
            logging.error(f'Failed to reset locks: {e}')
