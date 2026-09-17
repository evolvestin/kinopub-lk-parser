from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.telegram_backup_manager import BackupManager


class Command(BaseCommand):
    help = 'Create a PostgreSQL custom dump and upload it to the KinoPub Telegram channel.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Allow an explicit local/non-production backup run and ignore the change check.',
        )

    def handle(self, *args, **options):
        force = options['force']
        if (settings.DEBUG or settings.ENVIRONMENT != 'PROD') and not force:
            raise CommandError(
                'Backup is restricted outside production; pass --force for an explicit local run'
            )
        if not settings.TELEGRAM_BACKUP_ENABLED and not force:
            raise CommandError('Telegram backup is disabled')

        try:
            backup = BackupManager().perform_backup(force=force)
        except Exception as error:
            raise CommandError(str(error)) from error
        if backup is None:
            self.stdout.write('Database has not changed since the last backup; skipped.')
            return
        self.stdout.write(
            self.style.SUCCESS(
                f'Uploaded Telegram backup {backup.id} '
                f'({backup.size_bytes} bytes, {backup.part_count} part(s))'
            )
        )
