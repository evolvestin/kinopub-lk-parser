import logging
import os

from django.apps import apps
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

        patched_fields = []
        for model in apps.get_app_config('app').get_models():
            for field in model._meta.local_fields:
                if getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
                    patched_fields.append((field, field.auto_now, field.auto_now_add))
                    field.auto_now = False
                    field.auto_now_add = False

        try:
            logging.info('Flushing existing data before restore...')
            call_command('flush', interactive=False, reset_sequences=True)

            logging.info('Loading data from JSON backup...')
            call_command('loaddata', backup_file_path)
            logging.info('Restore process completed successfully.')
            manager.schedule_backup()

        except Exception as e:
            logging.error(
                f'A critical error occurred during backup restoration: {e}', exc_info=True
            )
        finally:
            for field, auto_now, auto_now_add in patched_fields:
                field.auto_now = auto_now
                field.auto_now_add = auto_now_add

            if os.path.exists(backup_file_path):
                os.remove(backup_file_path)
                logging.info(f'Removed temporary backup file: {backup_file_path}')
