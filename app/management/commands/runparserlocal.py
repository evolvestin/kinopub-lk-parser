import logging
import os
import sys
import threading
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from app import history_parser
from app.gdrive_backup import BackupManager
from app.history_parser import update_show_details
from app.management.commands.runemail_listener import run_email_listener, shutdown_flag
from app.models import Show


class Command(BaseCommand):
    help = 'Runs a single parser or updater session locally with a foreground browser.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account',
            type=str,
            choices=['main', 'aux'],
            default='main',
            help='The account to use for the session.',
        )
        parser.add_argument(
            '--task',
            type=str,
            choices=['history', 'details'],
            default='history',
            help='Task to perform: "history" (view history) or "details" (update show details).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='The maximum number of items to process for the "details" task.',
        )

    def _run_details_update_task(self, driver, limit, account_type):
        self.stdout.write(f'Searching for up to {limit} shows with missing year information...')

        show_ids_to_update = list(
            Show.objects.filter(year__isnull=True).values_list('id', flat=True)[:limit]
        )

        if not show_ids_to_update:
            self.stdout.write(self.style.SUCCESS('No shows with missing year found.'))
            return

        self.stdout.write(f'Found {len(show_ids_to_update)} shows to update.')

        updated_count = 0
        base_url = settings.SITE_AUX_URL if account_type == 'aux' else settings.SITE_URL

        for i, show_id in enumerate(show_ids_to_update):
            logging.info(f'Processing show {i + 1}/{len(show_ids_to_update)} (ID: {show_id})...')
            try:
                show_url = f'{base_url}/item/view/{show_id}'
                driver.get(show_url)
                time.sleep(1)
                update_show_details(driver, show_id)
                logging.info(f'Successfully updated details for show ID {show_id}.')
                updated_count += 1
            except Exception as e:
                logging.error(f'Failed to update show ID {show_id}: {e}')
                continue

        self.stdout.write(self.style.SUCCESS(f'Finished updating {updated_count} show details.'))

    def handle(self, *args, **options):
        account = options['account']
        task = options['task']
        limit = options['limit']

        if account == 'aux' and task == 'history':
            self.stderr.write(
                self.style.ERROR(
                    'The "aux" account does not support "history" task. Use "details" instead.'
                )
            )
            sys.exit(1)

        logging.info(f'--- Starting local script (Account: {account}, Task: {task}) ---')

        email_thread = None
        backup_file_path = None
        driver = None

        try:
            logging.info('Restoring database from Google Drive for local run...')
            backup_file_path = BackupManager().restore_from_backup()

            logging.info('Running migrations for local database...')
            call_command('migrate', interactive=False, verbosity=1)

            if backup_file_path and os.path.exists(backup_file_path):
                logging.info(f'Loading data from backup: {backup_file_path}')
                try:
                    call_command('loaddata', backup_file_path)
                except Exception as e:
                    logging.error(f'Failed to load backup data: {e}')
            else:
                self.stdout.write(self.style.WARNING('No backup found. Starting with empty DB.'))

            logging.info('Starting email listener in background for 2FA codes...')
            email_thread = threading.Thread(
                target=run_email_listener,
                args=(shutdown_flag,),
                daemon=True,
                name='EmailListenerThread',
            )
            email_thread.start()
            time.sleep(5)

            driver = history_parser.initialize_driver_session(
                headless=False, session_type=account
            )

            if driver is None:
                self.stderr.write(self.style.ERROR('Failed to initialize Selenium driver.'))
                sys.exit(1)

            if task == 'history':
                logging.info('--- Starting history parser session in local mode ---')
                history_parser.run_parser_session(headless=False, driver_instance=driver)
            elif task == 'details':
                logging.info('--- Starting details update session in local mode ---')
                self._run_details_update_task(driver, limit, account)

        except Exception as e:
            logging.error(f'A critical error occurred during local execution: {e}', exc_info=True)
            sys.exit(1)
        finally:
            if driver:
                logging.info('Closing Selenium driver.')
                driver.quit()
            if email_thread:
                logging.info('Stopping email listener thread...')
                shutdown_flag.set()
                email_thread.join(timeout=5)
            if backup_file_path and os.path.exists(backup_file_path):
                logging.info(f'Removing temporary backup file: {backup_file_path}')
                os.remove(backup_file_path)

        logging.info('--- Local script finished successfully ---')
