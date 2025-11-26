import logging
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from app.gdrive_backup import BackupManager


class Command(BaseCommand):
    help = 'Restores data from a Google Drive backup using loaddata (JSON).'

    def handle(self, *args, **options):
        logging.info('Starting restore from backup process...')
        manager = BackupManager()
        backup_file_path = manager.restore_from_backup()

        if not backup_file_path or not os.path.exists(backup_file_path):
            logging.warning('No backup file found. Aborting restore.')
            return

        logging.info(f'Using backup file at {backup_file_path}')

        try:
            logging.info('Loading data from JSON backup...')
            call_command('loaddata', backup_file_path)
            logging.info('Restore process completed successfully.')
            manager.schedule_backup()

        except Exception as e:
            logging.error(
                f'A critical error occurred during backup restoration: {e}', exc_info=True
            )
        finally:
            if os.path.exists(backup_file_path):
                os.remove(backup_file_path)
                logging.info(f'Removed temporary backup file: {backup_file_path}')
