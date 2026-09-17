"""Portable PostgreSQL backups stored as Telegram documents.

The manifest is the source of truth for portable restores.  The local Django
models are only an operational index and are not required when restoring from
the manifest file id.
"""

import hashlib
from html import escape
import json
import math
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import requests
from django.conf import settings

from .models import TelegramBackup, TelegramBackupPart


MANIFEST_FORMAT = 'kinopub-telegram-backup-v2'


class TelegramBackupError(RuntimeError):
    """Raised when Telegram cannot accept or return a backup artifact."""


@dataclass(frozen=True)
class TelegramDocument:
    message_id: int
    file_id: str
    file_unique_id: str


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class TelegramBotApi:
    def __init__(self, *, token: str | None = None, base_url: str | None = None, session=None):
        self.token = token or settings.BOT_TOKEN
        self.base_url = (base_url or settings.TELEGRAM_BACKUP_API_BASE_URL).rstrip('/')
        self.session = session or requests.Session()
        if not self.token:
            raise TelegramBackupError('Telegram backup bot token is not configured')
        if settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE and (
            not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH
        ):
            raise TelegramBackupError(
                'Local Telegram Bot API requires TELEGRAM_API_ID and TELEGRAM_API_HASH'
            )

    def _url(self, method: str) -> str:
        return f'{self.base_url}/bot{self.token}/{method}'

    def _call(self, method: str, *, data=None, files=None):
        for attempt in range(3):
            if files:
                for file_data in files.values():
                    if isinstance(file_data, tuple) and len(file_data) > 1:
                        stream = file_data[1]
                        if hasattr(stream, 'seek'):
                            stream.seek(0)
            try:
                response = self.session.post(
                    self._url(method),
                    data=data,
                    files=files,
                    timeout=(15, 3600),
                )
            except requests.RequestException as error:
                # Do not include the exception text: requests may include the
                # URL, which contains the bot token.
                raise TelegramBackupError(
                    f'Telegram {method} request failed: {error.__class__.__name__}'
                ) from None
            try:
                payload = response.json()
            except ValueError as error:
                raise TelegramBackupError(
                    f'Telegram {method} returned invalid JSON (HTTP {response.status_code})'
                ) from error
            if payload.get('ok'):
                if 'result' not in payload:
                    raise TelegramBackupError(f'Telegram {method} returned no result')
                return payload['result']
            if response.status_code == 429 and attempt < 2:
                retry_after = payload.get('parameters', {}).get('retry_after', 1)
                try:
                    retry_after = max(1, min(int(retry_after), 60))
                except (TypeError, ValueError):
                    retry_after = 1
                time.sleep(retry_after)
                continue
            description = payload.get('description', 'unknown Telegram error')
            raise TelegramBackupError(
                f'Telegram {method} failed (HTTP {response.status_code}): {description}'
            )

    def probe(self) -> dict:
        result = self._call('getChat', data={'chat_id': settings.TELEGRAM_BACKUP_CHAT_ID})
        if not isinstance(result, dict):
            raise TelegramBackupError('Telegram getChat returned an invalid response')
        return result

    def send_document(self, path: str, *, filename: str, caption: str = '') -> TelegramDocument:
        data = {
            'chat_id': str(settings.TELEGRAM_BACKUP_CHAT_ID),
            'caption': caption,
        }
        if settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE:
            # The local Bot API reads this path from the shared Docker volume.
            data['document'] = Path(path).as_uri()
            result = self._call('sendDocument', data=data)
        else:
            if os.path.getsize(path) > 50 * 1024 * 1024:
                raise TelegramBackupError(
                    'Large Telegram files require the local Bot API server'
                )
            with open(path, 'rb') as source:
                result = self._call(
                    'sendDocument',
                    data=data,
                    files={'document': (filename, source, 'application/octet-stream')},
                )
        document = result.get('document') if isinstance(result, dict) else None
        if not isinstance(document, dict) or not document.get('file_id'):
            raise TelegramBackupError('Telegram sendDocument returned no document')
        return TelegramDocument(
            message_id=int(result['message_id']),
            file_id=document['file_id'],
            file_unique_id=document.get('file_unique_id', ''),
        )

    def send_media_group(
        self,
        paths: list[str],
        *,
        filenames: list[str],
        file_ids: list[str | None] | None = None,
        captions: list[str] | None = None,
    ) -> list[TelegramDocument]:
        if (
            not 2 <= len(paths) <= 10
            or len(paths) != len(filenames)
            or (file_ids is not None and len(file_ids) != len(paths))
            or (captions is not None and len(captions) != len(paths))
        ):
            raise TelegramBackupError('Telegram media group must contain 2-10 documents')

        media = []
        opened = []
        files = {}
        result = None
        try:
            for index, (path, filename) in enumerate(zip(paths, filenames)):
                existing_file_id = file_ids[index] if file_ids is not None else None
                caption = captions[index] if captions is not None else ''
                if existing_file_id:
                    media_path = existing_file_id
                elif settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE:
                    media_path = Path(path).as_uri()
                else:
                    if os.path.getsize(path) > 50 * 1024 * 1024:
                        raise TelegramBackupError(
                            'Large Telegram files require the local Bot API server'
                        )
                    field_name = f'document{index}'
                    source = open(path, 'rb')
                    opened.append(source)
                    files[field_name] = (filename, source, 'application/octet-stream')
                    media_path = f'attach://{field_name}'
                media_item = {
                    'type': 'document',
                    'media': media_path,
                    'disable_content_type_detection': True,
                }
                if caption:
                    media_item['caption'] = caption
                media.append(media_item)
            result = self._call(
                'sendMediaGroup',
                data={
                    'chat_id': str(settings.TELEGRAM_BACKUP_CHAT_ID),
                    'media': json.dumps(media, separators=(',', ':')),
                },
                files=files or None,
            )
        finally:
            for source in opened:
                source.close()

        if not isinstance(result, list) or len(result) != len(paths):
            raise TelegramBackupError('Telegram sendMediaGroup returned an invalid response')
        documents = []
        for message in result:
            document = message.get('document') if isinstance(message, dict) else None
            if not isinstance(document, dict) or not document.get('file_id'):
                raise TelegramBackupError('Telegram sendMediaGroup returned a non-document')
            documents.append(
                TelegramDocument(
                    message_id=int(message['message_id']),
                    file_id=document['file_id'],
                    file_unique_id=document.get('file_unique_id', ''),
                )
            )
        return documents

    def edit_message_caption(self, message_id: int, caption: str) -> None:
        self._call(
            'editMessageCaption',
            data={
                'chat_id': str(settings.TELEGRAM_BACKUP_CHAT_ID),
                'message_id': str(message_id),
                'caption': caption,
                'parse_mode': 'HTML',
            },
        )

    def delete_message(self, message_id: int) -> None:
        self._call(
            'deleteMessage',
            data={
                'chat_id': str(settings.TELEGRAM_BACKUP_CHAT_ID),
                'message_id': str(message_id),
            },
        )

    def get_file_path(self, file_id: str) -> str:
        result = self._call('getFile', data={'file_id': file_id})
        file_path = result.get('file_path') if isinstance(result, dict) else None
        if not file_path:
            raise TelegramBackupError('Telegram getFile returned no file path')
        return file_path

    def download_file(self, file_id: str, destination: str | os.PathLike[str]) -> None:
        file_path = self.get_file_path(file_id)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if settings.TELEGRAM_BACKUP_LOCAL_FILE_MODE and os.path.isabs(file_path):
            try:
                shutil.copyfile(file_path, destination)
                return
            except OSError:
                pass

        url = f'{self.base_url}/file/bot{self.token}/{file_path.lstrip("/")}'
        try:
            with self.session.get(url, stream=True, timeout=(15, 3600)) as response:
                response.raise_for_status()
                with open(destination, 'wb') as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
        except requests.RequestException as error:
            raise TelegramBackupError(
                f'Telegram file download failed: {error.__class__.__name__}'
            ) from None


def _copy_part(source: BinaryIO, destination: str, limit: int) -> int:
    written = 0
    with open(destination, 'wb') as output:
        while written < limit:
            chunk = source.read(min(1024 * 1024, limit - written))
            if not chunk:
                break
            output.write(chunk)
            written += len(chunk)
    os.chmod(destination, 0o644)
    return written


def _part_paths(path: str, workdir: str, part_size: int) -> list[tuple[int, str, int]]:
    total_size = os.path.getsize(path)
    if total_size == 0:
        raise TelegramBackupError('Cannot upload an empty backup file')
    if part_size <= 0:
        raise TelegramBackupError('Telegram backup part size must be positive')
    count = math.ceil(total_size / part_size)
    if count == 1:
        return [(1, path, total_size)]

    parts = []
    with open(path, 'rb') as source:
        for number in range(1, count + 1):
            part_path = os.path.join(workdir, f'part-{number:04d}')
            size = _copy_part(source, part_path, part_size)
            parts.append((number, part_path, size))
    return parts


def upload_backup(path: str, *, source_filename: str | None = None) -> TelegramBackup:
    source_filename = source_filename or os.path.basename(path)
    size_bytes = os.path.getsize(path)
    if size_bytes <= 0:
        raise TelegramBackupError('Cannot upload an empty backup file')

    backup = TelegramBackup.objects.create(
        source_filename=source_filename,
        size_bytes=size_bytes,
        sha256=sha256_file(path),
    )
    os.makedirs(settings.TELEGRAM_BACKUP_SHARED_DIR, exist_ok=True)
    workdir = None
    client = None
    staged_message_ids = []
    try:
        client = TelegramBotApi()
        workdir = tempfile.mkdtemp(
            prefix=f'{backup.id}-', dir=settings.TELEGRAM_BACKUP_SHARED_DIR
        )
        os.chmod(workdir, 0o755)
        part_paths = _part_paths(path, workdir, settings.TELEGRAM_BACKUP_PART_SIZE_BYTES)
        backup.part_count = len(part_paths)
        backup.save(update_fields=('part_count', 'updated_at'))
        part_metadata = []
        for number, part_path, part_size in part_paths:
            part_metadata.append(
                (
                    number,
                    part_path,
                    part_size,
                    sha256_file(part_path),
                    f'{source_filename}.part-{number:04d}',
                )
            )

        staged_documents = []
        for _number, part_path, _part_size, _part_hash, filename in part_metadata:
            document = client.send_document(part_path, filename=filename)
            staged_documents.append(document)
            staged_message_ids.append(document.message_id)

        manifest = {
            'format': MANIFEST_FORMAT,
            'backup_id': str(backup.id),
            'source_filename': source_filename,
            'size_bytes': backup.size_bytes,
            'sha256': backup.sha256,
            'parts': [
                {
                    'part_number': number,
                    'filename': filename,
                    'size_bytes': part_size,
                    'sha256': part_hash,
                    'file_id': staged_document.file_id,
                }
                for (number, _part_path, part_size, part_hash, filename), staged_document in zip(
                    part_metadata, staged_documents
                )
            ],
        }
        manifest_path = os.path.join(workdir, f'{source_filename}.manifest.json')
        with open(manifest_path, 'w', encoding='utf-8', newline='\n') as manifest_file:
            json.dump(
                manifest,
                manifest_file,
                ensure_ascii=False,
                sort_keys=True,
                separators=(',', ':'),
            )
        os.chmod(manifest_path, 0o644)

        final_items = [
            {
                'path': '',
                'filename': filename,
                'file_id': staged_document.file_id,
                'caption': '',
                'part_number': number,
            }
            for (number, _part_path, _part_size, _part_hash, filename), staged_document in zip(
                part_metadata, staged_documents
            )
        ]
        final_items.append(
            {
                'path': manifest_path,
                'filename': f'{source_filename}.manifest.json',
                'file_id': None,
                'caption': '-',
                'part_number': None,
            }
        )
        groups = [
            final_items[group_start : group_start + 10]
            for group_start in range(0, len(final_items), 10)
        ]
        if len(groups) > 1 and len(groups[-1]) == 1:
            groups[-1].insert(0, groups[-2].pop())

        final_part_documents = {}
        manifest_document = None
        for group in groups:
            group_documents = client.send_media_group(
                [item['path'] for item in group],
                filenames=[item['filename'] for item in group],
                file_ids=[item['file_id'] for item in group],
                captions=[item['caption'] for item in group],
            )
            for item, document in zip(group, group_documents):
                if item['part_number'] is None:
                    manifest_document = document
                else:
                    final_part_documents[item['part_number']] = document

        if manifest_document is None or len(final_part_documents) != len(part_metadata):
            raise TelegramBackupError('Telegram final media groups returned incomplete backup')

        for message_id in staged_message_ids:
            try:
                client.delete_message(message_id)
            except TelegramBackupError:
                # The final group is already valid; staging duplicates are harmless.
                pass
        staged_message_ids = []

        for number, _part_path, part_size, part_hash, filename in part_metadata:
            document = final_part_documents[number]
            TelegramBackupPart.objects.create(
                backup=backup,
                part_number=number,
                filename=filename,
                size_bytes=part_size,
                sha256=part_hash,
                message_id=document.message_id,
                file_id=document.file_id,
                file_unique_id=document.file_unique_id,
            )

        # The caption is the only human-visible recovery hint.  Do not mark
        # the backup uploaded until it has been edited successfully.
        client.edit_message_caption(
            manifest_document.message_id,
            f'<code>{escape(manifest_document.file_id)}</code>',
        )
        backup.manifest_message_id = manifest_document.message_id
        backup.manifest_file_id = manifest_document.file_id
        backup.status = TelegramBackup.Status.UPLOADED
        backup.save(
            update_fields=(
                'manifest_message_id',
                'manifest_file_id',
                'status',
                'updated_at',
            )
        )
        return backup
    except Exception as error:
        backup.status = TelegramBackup.Status.FAILED
        backup.error_message = str(error)[-2000:]
        backup.save(update_fields=('status', 'error_message', 'updated_at'))
        raise
    finally:
        if client is not None:
            for message_id in staged_message_ids:
                try:
                    client.delete_message(message_id)
                except TelegramBackupError:
                    pass
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)


def download_backup(backup: TelegramBackup, destination: str) -> None:
    parts = list(backup.parts.order_by('part_number'))
    if (
        backup.status != TelegramBackup.Status.UPLOADED
        or not parts
        or len(parts) != backup.part_count
        or [part.part_number for part in parts] != list(range(1, backup.part_count + 1))
    ):
        raise TelegramBackupError(f'Telegram backup {backup.id} is not complete')
    client = TelegramBotApi()
    os.makedirs(settings.TELEGRAM_BACKUP_SHARED_DIR, exist_ok=True)
    tempdir = tempfile.mkdtemp(
        prefix=f'restore-{backup.id}-', dir=settings.TELEGRAM_BACKUP_SHARED_DIR
    )
    try:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        with open(destination, 'wb') as output:
            for part in parts:
                part_path = os.path.join(tempdir, part.filename)
                client.download_file(part.file_id, part_path)
                actual_size = os.path.getsize(part_path)
                actual_hash = sha256_file(part_path)
                if actual_size != part.size_bytes or actual_hash != part.sha256:
                    raise TelegramBackupError(
                        f'Telegram backup part {part.part_number} failed integrity check'
                    )
                with open(part_path, 'rb') as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if os.path.getsize(destination) != backup.size_bytes or sha256_file(destination) != backup.sha256:
            raise TelegramBackupError(f'Telegram backup {backup.id} failed integrity check')
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def _validate_manifest_file_id(file_id: object) -> str:
    max_length = TelegramBackupPart._meta.get_field('file_id').max_length
    if not isinstance(file_id, str) or not file_id or len(file_id) > max_length or any(
        char.isspace() for char in file_id
    ):
        raise TelegramBackupError('Telegram manifest contains an invalid file_id')
    return file_id


def load_manifest(path: str | os.PathLike[str]) -> dict:
    try:
        with open(path, encoding='utf-8') as source:
            manifest = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise TelegramBackupError('Telegram manifest is not valid JSON') from error

    if not isinstance(manifest, dict) or manifest.get('format') != MANIFEST_FORMAT:
        raise TelegramBackupError('Telegram manifest has an unsupported format')
    try:
        UUID(str(manifest['backup_id']))
        total_size = manifest['size_bytes']
    except (KeyError, TypeError, ValueError) as error:
        raise TelegramBackupError('Telegram manifest has invalid backup metadata') from error
    if (
        not isinstance(manifest.get('source_filename'), str)
        or not manifest['source_filename']
        or isinstance(total_size, bool)
        or not isinstance(total_size, int)
        or total_size <= 0
        or not isinstance(manifest.get('sha256'), str)
        or not re.fullmatch(r'[0-9a-f]{64}', manifest['sha256'])
        or not isinstance(manifest.get('parts'), list)
        or not manifest['parts']
    ):
        raise TelegramBackupError('Telegram manifest has invalid backup metadata')

    parts = []
    for expected_number, part in enumerate(manifest['parts'], start=1):
        if not isinstance(part, dict):
            raise TelegramBackupError('Telegram manifest contains an invalid part')
        number = part.get('part_number')
        size = part.get('size_bytes')
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or isinstance(size, bool)
            or not isinstance(size, int)
            or number != expected_number
            or size <= 0
            or not isinstance(part.get('filename'), str)
            or not part['filename']
            or not isinstance(part.get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', part['sha256'])
        ):
            raise TelegramBackupError('Telegram manifest contains invalid part metadata')
        parts.append(
            {
                'part_number': number,
                'filename': part['filename'],
                'size_bytes': size,
                'sha256': part['sha256'],
                'file_id': _validate_manifest_file_id(part.get('file_id')),
            }
        )
    if sum(part['size_bytes'] for part in parts) != total_size:
        raise TelegramBackupError('Telegram manifest part sizes do not match total size')
    return {
        'format': MANIFEST_FORMAT,
        'backup_id': str(manifest['backup_id']),
        'source_filename': manifest['source_filename'],
        'size_bytes': total_size,
        'sha256': manifest['sha256'],
        'parts': parts,
    }


def download_manifest_backup(manifest_file_id: str, destination: str) -> None:
    manifest_file_id = _validate_manifest_file_id(manifest_file_id)
    client = TelegramBotApi()
    os.makedirs(settings.TELEGRAM_BACKUP_SHARED_DIR, exist_ok=True)
    tempdir = tempfile.mkdtemp(prefix='restore-manifest-', dir=settings.TELEGRAM_BACKUP_SHARED_DIR)
    try:
        manifest_path = os.path.join(tempdir, 'manifest.json')
        client.download_file(manifest_file_id, manifest_path)
        manifest = load_manifest(manifest_path)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        with open(destination, 'wb') as output:
            for part in manifest['parts']:
                part_path = os.path.join(tempdir, f"part-{part['part_number']:04d}")
                client.download_file(part['file_id'], part_path)
                if (
                    os.path.getsize(part_path) != part['size_bytes']
                    or sha256_file(part_path) != part['sha256']
                ):
                    raise TelegramBackupError(
                        f"Telegram manifest part {part['part_number']} failed integrity check"
                    )
                with open(part_path, 'rb') as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if (
            os.path.getsize(destination) != manifest['size_bytes']
            or sha256_file(destination) != manifest['sha256']
        ):
            raise TelegramBackupError('Telegram manifest assembled backup failed integrity check')
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
