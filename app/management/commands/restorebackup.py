from django.core.management.base import BaseCommand
import logging
from app.gdrive_backup import BackupManager


class Command(BaseCommand):
    help = 'Restores database and cookies from Google Drive backup.'

    def handle(self, *args, **options):
        logging.info("Executing restore from backup command...")
        try:
            BackupManager().restore_from_backup()
            logging.info("Restore from backup command finished successfully.")
        except Exception as e:
            logging.error(f"An error occurred during backup restoration: {e}")
