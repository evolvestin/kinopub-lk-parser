"""Backup orchestration used by scheduled tasks and management commands."""

import logging
import os
import subprocess
import tempfile

from django.conf import settings
from django.db.models import Max

from app.models import (
    Code,
    Country,
    Genre,
    Person,
    Show,
    ShowDuration,
    ViewHistory,
    ViewUser,
    ViewUserGroup,
)

from .models import TelegramBackup
from .telegram_backup import (
    TelegramBackupError,
    TelegramBotApi,
    download_backup,
    download_manifest_backup,
    upload_backup,
)


class BackupManager:
    """Create PostgreSQL custom dumps and store them in Telegram."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def schedule_backup(self):
        if settings.LOCAL_RUN or settings.DEBUG or settings.ENVIRONMENT != 'PROD':
            logging.info('Backup scheduling is disabled outside production.')
            return
        logging.info('Database backup requested; hourly Celery schedule will check it.')

    @staticmethod
    def _database_changed_since(last_backup_timestamp):
        check_models = [
            Code,
            Country,
            Genre,
            Person,
            Show,
            ShowDuration,
            ViewHistory,
            ViewUser,
            ViewUserGroup,
        ]
        max_updated_at = None
        for model in check_models:
            timestamp = model.objects.aggregate(max_ts=Max('updated_at')).get('max_ts')
            if timestamp and (max_updated_at is None or timestamp > max_updated_at):
                max_updated_at = timestamp
        return max_updated_at, bool(
            max_updated_at and max_updated_at.timestamp() > last_backup_timestamp
        )

    def perform_backup(self, *, force=False):
        data_dir = settings.TELEGRAM_BACKUP_SHARED_DIR
        os.makedirs(data_dir, exist_ok=True)
        last_timestamp_file = os.path.join(data_dir, 'last_db_backup_ts')
        last_backup_timestamp = 0.0
        if os.path.exists(last_timestamp_file):
            try:
                with open(last_timestamp_file, encoding='utf-8') as timestamp_file:
                    last_backup_timestamp = float(timestamp_file.read().strip())
            except (TypeError, ValueError, OSError):
                pass

        max_updated_at, changed = self._database_changed_since(last_backup_timestamp)
        if not force and not changed:
            logging.info('Database has not changed since last backup. Skipping.')
            return None

        logging.info('Starting PostgreSQL backup for Telegram.')
        TelegramBotApi()
        db_conf = settings.DATABASES['default']
        dump_dir = data_dir if settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE else None
        fd, backup_file_path = tempfile.mkstemp(suffix='.dump', dir=dump_dir)
        os.close(fd)
        if settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE:
            os.chmod(backup_file_path, 0o644)

        try:
            result = subprocess.run(
                [
                    'pg_dump',
                    '--format=custom',
                    '--file',
                    backup_file_path,
                    db_conf['NAME'],
                ],
                env={
                    **os.environ,
                    'PGPASSWORD': db_conf.get('PASSWORD', ''),
                    'PGHOST': db_conf.get('HOST', ''),
                    'PGPORT': str(db_conf.get('PORT', '5432')),
                    'PGUSER': db_conf.get('USER', ''),
                },
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError('pg_dump failed: ' + result.stderr[-500:])
            if not os.path.exists(backup_file_path) or os.path.getsize(backup_file_path) == 0:
                raise RuntimeError('pg_dump produced no backup file')

            try:
                backup = upload_backup(
                    backup_file_path,
                    source_filename=settings.TELEGRAM_BACKUP_SOURCE_FILENAME,
                )
            except TelegramBackupError as error:
                raise RuntimeError(f'Telegram backup failed: {error}') from error

            if max_updated_at:
                with open(last_timestamp_file, 'w', encoding='utf-8', newline='\n') as timestamp_file:
                    timestamp_file.write(str(max_updated_at.timestamp()))
            logging.info(
                'Telegram backup uploaded: backup=%s parts=%d bytes=%d',
                backup.id,
                backup.part_count,
                backup.size_bytes,
            )
            return backup
        finally:
            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)

    def restore_from_backup(self, reference=None):
        """Download a verified dump, without invoking destructive pg_restore."""
        if reference and not reference.strip().isdigit() and not reference.strip().startswith(('http://', 'https://')):
            fd, path = tempfile.mkstemp(suffix='.dump')
            os.close(fd)
            try:
                download_manifest_backup(reference.strip(), path)
                return path
            except Exception:
                if os.path.exists(path):
                    os.unlink(path)
                raise

        backup = self._select_indexed_backup(reference)
        fd, path = tempfile.mkstemp(suffix='.dump')
        os.close(fd)
        try:
            download_backup(backup, path)
            return path
        except Exception:
            if os.path.exists(path):
                os.unlink(path)
            raise

    @staticmethod
    def _select_indexed_backup(reference=None):
        if not reference:
            backup = TelegramBackup.objects.filter(status=TelegramBackup.Status.UPLOADED).first()
            if backup is None:
                raise TelegramBackupError('No uploaded Telegram backup was found in the database')
            return backup

        value = reference.strip()
        if value.isdigit():
            message_id = int(value)
        else:
            from urllib.parse import urlparse

            parsed = urlparse(value)
            path_parts = [part for part in parsed.path.split('/') if part]
            if (
                parsed.scheme not in ('http', 'https')
                or parsed.netloc not in ('t.me', 'www.t.me', 'telegram.me', 'www.telegram.me')
                or len(path_parts) != 3
                or path_parts[0] != 'c'
                or not path_parts[1].isdigit()
                or not path_parts[2].isdigit()
                or str(settings.TELEGRAM_BACKUP_CHAT_ID) != f'-100{path_parts[1]}'
            ):
                raise TelegramBackupError('Reference must be a message id or a URL for the backup channel')
            message_id = int(path_parts[2])

        backup = (
            TelegramBackup.objects.filter(status=TelegramBackup.Status.UPLOADED)
            .filter(parts__message_id=message_id)
            .first()
        )
        if backup is None:
            backup = TelegramBackup.objects.filter(
                status=TelegramBackup.Status.UPLOADED,
                manifest_message_id=message_id,
            ).first()
        if backup is None:
            raise TelegramBackupError(f'Telegram message {message_id} is not indexed in this database')
        return backup
