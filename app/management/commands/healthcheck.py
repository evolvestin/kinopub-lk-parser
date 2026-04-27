import logging
import os
import socket
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from app.utils import update_heartbeat


class Command(BaseCommand):
    help = 'Performs a health check by checking the unique heartbeat file for this container.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--touch',
            action='store_true',
            help='Update the heartbeat file for this container before checking age.',
        )

    def handle(self, *args, **options):
        if getattr(settings, 'LOCAL_RUN', False):
            sys.exit(0)

        if options['touch']:
            update_heartbeat()

        heartbeat_file = settings.HEARTBEAT_FILE
        hostname = socket.gethostname()
        threshold = 60
        try:
            stat = os.stat(heartbeat_file)
            age = time.time() - stat.st_mtime
            if age <= threshold:
                sys.exit(0)
            else:
                logging.error(
                    f'Healthcheck FAILED for {hostname}: Heartbeat stale. '
                    f'Last update: {age:.1f}s ago (threshold: {threshold}s)'
                )
                sys.exit(1)
        except FileNotFoundError:
            logging.error(f'Healthcheck FAILED for {hostname}: File not found: {heartbeat_file}')
            sys.exit(1)
        except Exception as e:
            logging.error(f'Healthcheck CRITICAL error on {hostname}: {e}')
            sys.exit(1)
