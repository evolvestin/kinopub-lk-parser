import logging
import os
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Performs a health check by checking the heartbeat file.'

    def handle(self, *args, **options):
        if getattr(settings, 'LOCAL_RUN', False):
            sys.exit(0)

        heartbeat_file = settings.HEARTBEAT_FILE
        threshold = 120
        try:
            stat = os.stat(heartbeat_file)
            age = time.time() - stat.st_mtime
            if age <= threshold:
                sys.exit(0)
            else:
                logging.error(
                    f'Healthcheck: Heartbeat stale. Last update: {age:.1f}s ago '
                    f'(threshold: {threshold}s, file: {heartbeat_file})'
                )
                sys.exit(1)
        except FileNotFoundError:
            logging.error(f'Healthcheck: Heartbeat file not found: {heartbeat_file}')
            sys.exit(1)
        except Exception as e:
            logging.error(f'Healthcheck: Unexpected error: {e}')
            sys.exit(1)
