# app/management/commands/runparserlocal.py
import logging
import os
import sys
import threading
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

from app import history_parser
from app.gdrive_backup import BackupManager
from app.management.commands.runemail_listener import run_email_listener, shutdown_flag


class Command(BaseCommand):
    help = 'Runs a single history parser session locally with a foreground browser.'

    def handle(self, *args, **options):
        logging.info('--- Starting local history parser script ---')
        email_thread = None
        backup_file_path = None

        try:
            logging.info('Attempting to restore database from Google Drive backup for local run...')
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
                self.stdout.write(
                    self.style.WARNING('No backup file found. Starting with empty DB.')
                )

            logging.info('Starting email listener in the background for 2FA codes...')
            email_thread = threading.Thread(
                target=run_email_listener,
                args=(shutdown_flag,),
                daemon=True,
                name='EmailListenerThread',
            )
            email_thread.start()
            time.sleep(5)

            logging.info('--- Starting history parser session in local mode ---')
            history_parser.run_parser_session(headless=False)

        except Exception as e:
            logging.error('A critical error occurred during local execution: {e}', exc_info=True)
            sys.exit(1)
        finally:
            if email_thread:
                logging.info('Stopping email listener thread...')
                shutdown_flag.set()
                email_thread.join(timeout=5)
            if backup_file_path and os.path.exists(backup_file_path):
                logging.info(f'Removing temporary backup file: {backup_file_path}')
                os.remove(backup_file_path)
        logging.info('--- Local history parser script finished successfully ---')
