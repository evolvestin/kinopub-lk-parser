import logging
import sys
import threading
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

from app import history_parser
from app.gdrive_backup import BackupManager
from app.management.commands.runservices import run_email_listener, shutdown_flag


class Command(BaseCommand):
    help = 'Runs a single history parser session locally with a foreground browser.'

    def handle(self, *args, **options):
        logging.info('--- Starting local history parser script ---')
        email_thread = None
        try:
            BackupManager().restore_from_backup()

            call_command('migrate', interactive=False, verbosity=1)

            logging.info("Starting email listener in the background for 2FA codes...")
            email_thread = threading.Thread(
                target=run_email_listener,
                args=(shutdown_flag,),
                daemon=True,
                name="EmailListenerThread"
            )
            email_thread.start()
            time.sleep(5)

            logging.info("--- Starting history parser session in local mode ---")
            history_parser.run_parser_session(headless=False)
        except Exception as e:
            logging.error('A critical error occurred during local execution: %s', e, exc_info=True)
            sys.exit(1)
        finally:
            if email_thread:
                logging.info("Stopping email listener thread...")
                shutdown_flag.set()
                email_thread.join(timeout=5)
        logging.info('--- Local history parser script finished successfully ---')
