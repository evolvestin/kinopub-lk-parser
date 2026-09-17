"""Controlled Telegram backup smoke test.

This script talks to the configured KinoPub bot and channel, but never runs
pg_restore.  It is intentionally explicit and is not a scheduled task.
"""

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

import django


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kinopub_parser.settings')
django.setup()

from django.conf import settings  # noqa: E402

from app.telegram_backup import (  # noqa: E402
    TelegramBackupError,
    TelegramBotApi,
    download_manifest_backup,
    upload_backup,
)
from app.models import TelegramBackup  # noqa: E402


def digest(path):
    checksum = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def run_case(name, content, part_size):
    settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE = False
    settings.TELEGRAM_BACKUP_API_BASE_URL = 'https://api.telegram.org'
    settings.TELEGRAM_BACKUP_PART_SIZE_BYTES = part_size
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / f'{name}.dump'
        destination = Path(directory) / f'{name}.restored'
        source.write_bytes(content)
        backup = upload_backup(str(source), source_filename=f'{name}.dump')
        download_manifest_backup(backup.manifest_file_id, str(destination))
        if destination.stat().st_size != source.stat().st_size or digest(destination) != digest(source):
            raise RuntimeError(f'{name}: restored file differs from source')
        print(f'PASS {name}: {backup.part_count} part(s), {source.stat().st_size} bytes')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-large', action='store_true')
    parser.add_argument('--local-restore-latest', action='store_true')
    args = parser.parse_args()

    if args.local_large:
        run_local_large_case()
        return
    if args.local_restore_latest:
        restore_latest_local_case()
        return

    # This is deliberately a hosted-only smoke path for small fixtures.  The
    # normal settings remain local Bot API mode for production-sized dumps.
    original_mode = settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE
    original_base_url = settings.TELEGRAM_BACKUP_API_BASE_URL
    try:
        settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE = False
        settings.TELEGRAM_BACKUP_API_BASE_URL = 'https://api.telegram.org'
        chat = TelegramBotApi().probe()
        print(f"PASS getChat: {chat.get('title') or chat.get('username') or 'channel reachable'}")
        run_case('binary-one-part', bytes(range(256)) * 8, 1024 * 1024)
        run_case('text-three-parts', b'kinopub-backup\n' * 37, 64)
        run_case('eleven-parts-two-groups', b'k' * (11 * 1024), 1024)
        try:
            with tempfile.NamedTemporaryFile() as empty:
                upload_backup(empty.name, source_filename='empty.dump')
        except TelegramBackupError:
            print('PASS empty-file rejection')
        else:
            raise RuntimeError('empty-file rejection did not fire')
    finally:
        settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE = original_mode
        settings.TELEGRAM_BACKUP_API_BASE_URL = original_base_url


def run_local_large_case():
    settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE = True
    settings.TELEGRAM_BACKUP_API_BASE_URL = 'http://telegram-bot-api:8081'
    settings.TELEGRAM_BACKUP_PART_SIZE_BYTES = 1_900 * 1024 * 1024
    size = 700 * 1024 * 1024
    chunk = b'kinopub-synthetic-backup\n' * (1024 * 1024 // 25)
    with tempfile.TemporaryDirectory(dir=settings.TELEGRAM_BACKUP_SHARED_DIR) as directory:
        source = Path(directory) / 'synthetic-700mb.dump'
        destination = Path(directory) / 'synthetic-700mb.restored'
        os.chmod(directory, 0o755)
        with open(source, 'wb') as output:
            for _ in range(size // len(chunk)):
                output.write(chunk)
            output.write(chunk[: size % len(chunk)])
        os.chmod(source, 0o644)
        backup = upload_backup(str(source), source_filename=source.name)
        download_manifest_backup(backup.manifest_file_id, str(destination))
        if destination.stat().st_size != source.stat().st_size or digest(destination) != digest(source):
            raise RuntimeError('local-large: restored file differs from source')
        print(f'PASS local-large: {backup.part_count} part(s), {source.stat().st_size} bytes')


def restore_latest_local_case():
    settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE = True
    settings.TELEGRAM_BACKUP_API_BASE_URL = 'http://telegram-bot-api:8081'
    backup = TelegramBackup.objects.filter(status=TelegramBackup.Status.UPLOADED).first()
    if backup is None:
        raise RuntimeError('local-restore-latest: no uploaded backup found')
    with tempfile.TemporaryDirectory(dir=settings.TELEGRAM_BACKUP_SHARED_DIR) as directory:
        destination = Path(directory) / 'latest.restored'
        download_manifest_backup(backup.manifest_file_id, str(destination))
        if destination.stat().st_size != backup.size_bytes or digest(destination) != backup.sha256:
            raise RuntimeError('local-restore-latest: restored file differs from manifest')
        print(f'PASS local-restore-latest: {backup.part_count} part(s), {backup.size_bytes} bytes')


if __name__ == '__main__':
    main()
