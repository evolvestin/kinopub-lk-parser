import logging
import os
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Performs a health check by checking the heartbeat file.'

    def handle(self, *args, **options):
        heartbeat_file = settings.HEARTBEAT_FILE
        threshold = 60
        try:
            stat = os.stat(heartbeat_file)
            age = time.time() - stat.st_mtime
            if age <= threshold:
                sys.exit(0)
            else:
                logging.error(
                    f'Heartbeat stale: {age:.1f}s > {threshold}s (file: {heartbeat_file})'
                )
                sys.exit(1)
        except FileNotFoundError:
            logging.error(f'Heartbeat not found (file: {heartbeat_file})')
            sys.exit(1)
        except Exception as e:
            logging.error(f'Healthcheck error: {e}')
            sys.exit(1)
