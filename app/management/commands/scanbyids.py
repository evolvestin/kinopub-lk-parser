import logging
import os
import time

from django.conf import settings

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    is_fatal_selenium_error,
    process_show_durations,
    update_show_details,
)
from app.management.base import LoggableBaseCommand
from app.models import Show


class Command(LoggableBaseCommand):
    help = 'Scans specific Show IDs (creates/updates metadata, plot, and durations).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            type=str,
            help='Comma-separated list of specific Show IDs to scan.',
        )
        parser.add_argument(
            '--file',
            type=str,
            default='verified_gaps.txt',
            help='Filename inside /data/ directory to read IDs from.',
        )

    def handle(self, *args, **options):
        ids_to_scan = []

        if options.get('ids'):
            for sid in options['ids'].split(','):
                if sid.strip().isdigit():
                    ids_to_scan.append(int(sid.strip()))

        if not ids_to_scan and options.get('file'):
            file_path = os.path.join('/data', options['file'])
            if os.path.exists(file_path):
                with open(file_path, encoding='utf-8') as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line.isdigit():
                            ids_to_scan.append(int(clean_line))
            else:
                logging.warning(f'File not found: {file_path}')

        # Дедубликация и сортировка
        ids_to_scan = sorted(list(set(ids_to_scan)))

        if not ids_to_scan:
            self.stdout.write(self.style.ERROR('No valid IDs provided for scanning.'))
            return

        self.stdout.write(self.style.NOTICE(f'Found {len(ids_to_scan)} IDs to process.'))

        driver = None
        processed_count = 0

        try:
            for index, show_id in enumerate(ids_to_scan, start=1):
                if driver is None:
                    logging.info('Initializing Selenium driver (aux account)...')
                    driver = initialize_driver_session(session_type='aux')
                    if not driver:
                        self.stdout.write(self.style.ERROR('Failed to initialize driver.'))
                        return

                logging.info(f'[{index}/{len(ids_to_scan)}] Processing Show ID: {show_id}')

                try:
                    try:
                        _ = driver.current_url
                    except Exception as e:
                        raise Exception(f'Driver unresponsive: {e}') from e

                    update_show_details(driver, show_id, force=True)

                    try:
                        show = Show.objects.get(id=show_id)
                        process_show_durations(driver, show)
                    except Show.DoesNotExist:
                        logging.warning(f'Show {show_id} does not exist after details update.')

                    processed_count += 1
                    time.sleep(settings.FULL_SCAN_PAGE_DELAY_SECONDS)

                except Exception as e:
                    if is_fatal_selenium_error(e):
                        logging.error('Selenium driver is dead. Restarting session...')
                        close_driver(driver)
                        driver = None
                        continue

                    logging.error(f'Error processing Show ID {show_id}: {e}', exc_info=True)
                    continue

            if processed_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully processed {processed_count} shows.')
                )
                BackupManager().schedule_backup()
            else:
                self.stdout.write(self.style.WARNING('No shows were successfully processed.'))

        finally:
            close_driver(driver)
