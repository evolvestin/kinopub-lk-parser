import os
import subprocess
import tempfile
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from app.management.base import LoggableBaseCommand
from app.models import TelegramBackup
from app.telegram_backup import TelegramBackupError, download_backup, download_manifest_backup


class Command(LoggableBaseCommand):
    help = 'Restore PostgreSQL from a Telegram backup. Destructive.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true')
        parser.add_argument(
            '--manifest-file-id',
            help='Telegram file_id of the JSON manifest; local DB metadata is not required',
        )
        parser.add_argument(
            'reference',
            nargs='?',
            help='Manifest file_id, message id, private-channel URL, or omitted for latest indexed backup',
        )

    def handle(self, *args, **options):
        if not options.get('confirm', False):
            raise CommandError('Refusing restore: pass --confirm')
        if not settings.TELEGRAM_BACKUP_ENABLED:
            raise CommandError('Telegram backup is disabled')

        manifest_file_id = options['manifest_file_id']
        reference = options['reference']
        if manifest_file_id and reference:
            raise CommandError('Use either --manifest-file-id or a reference, not both')
        if reference and not self._is_message_reference(reference):
            manifest_file_id = reference.strip()

        fd, path = tempfile.mkstemp(suffix='.dump')
        os.close(fd)
        try:
            try:
                if manifest_file_id:
                    download_manifest_backup(manifest_file_id, path)
                else:
                    backup = self._select_backup(reference)
                    download_backup(backup, path)
            except TelegramBackupError as error:
                raise CommandError(f'Telegram restore download failed: {error}') from error

            db_conf = settings.DATABASES['default']
            env = {
                **os.environ,
                'PGPASSWORD': db_conf.get('PASSWORD', ''),
                'PGHOST': db_conf.get('HOST', ''),
                'PGPORT': str(db_conf.get('PORT', '5432')),
                'PGUSER': db_conf.get('USER', ''),
            }
            result = subprocess.run(
                [
                    'pg_restore',
                    '--clean',
                    '--if-exists',
                    '--no-owner',
                    '--dbname',
                    db_conf['NAME'],
                    path,
                ],
                env=env,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise CommandError('pg_restore failed: ' + result.stderr[-500:])
            self.stdout.write(self.style.SUCCESS('Restore complete'))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    @staticmethod
    def _is_message_reference(reference):
        value = reference.strip()
        if value.isdigit():
            return True
        parsed = urlparse(value)
        return parsed.scheme in ('http', 'https') and parsed.netloc in (
            't.me',
            'www.t.me',
            'telegram.me',
            'www.telegram.me',
        )

    @staticmethod
    def _parse_message_reference(reference):
        reference = reference.strip()
        if reference.isdigit():
            return int(reference)
        parsed = urlparse(reference)
        if parsed.scheme not in ('http', 'https') or parsed.netloc not in (
            't.me',
            'www.t.me',
            'telegram.me',
            'www.telegram.me',
        ):
            raise CommandError('Reference must be a Telegram message id or t.me URL')
        parts = [part for part in parsed.path.split('/') if part]
        if len(parts) != 3 or parts[0] != 'c' or not parts[1].isdigit() or not parts[2].isdigit():
            raise CommandError('Only private-channel URLs like https://t.me/c/4321355963/10 are supported')
        if str(settings.TELEGRAM_BACKUP_CHAT_ID) != f'-100{parts[1]}':
            raise CommandError('Telegram URL points to a different channel')
        return int(parts[2])

    def _select_backup(self, reference):
        if not reference:
            backup = TelegramBackup.objects.filter(
                status=TelegramBackup.Status.UPLOADED
            ).first()
            if backup is None:
                raise CommandError('No uploaded Telegram backup was found in the database')
            return backup

        message_id = self._parse_message_reference(reference)
        backup = (
            TelegramBackup.objects.filter(status=TelegramBackup.Status.UPLOADED)
            .filter(Q(parts__message_id=message_id) | Q(manifest_message_id=message_id))
            .distinct()
            .first()
        )
        if backup is None:
            raise CommandError(
                f'Telegram message {message_id} is not indexed in this database; '
                'use the manifest file_id for a portable restore'
            )
        return backup
