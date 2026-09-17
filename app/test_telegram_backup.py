import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import TestCase

from app.management.commands.restorebackup import Command as RestoreCommand
from app.models import TelegramBackup
from app.telegram_backup import (
    MANIFEST_FORMAT,
    TelegramBackupError,
    TelegramBotApi,
    TelegramDocument,
    download_backup,
    download_manifest_backup,
    load_manifest,
    upload_backup,
)


class FakeTelegramClient:
    downloaded_files = {}
    media_group_sizes = []
    captions = {}
    deleted_message_ids = []

    def __init__(self):
        self.next_message_id = 100

    def send_document(self, path, *, filename, caption=''):
        message_id = self.next_message_id
        self.next_message_id += 1
        file_id = f'file-{message_id}'
        type(self).downloaded_files[file_id] = Path(path).read_bytes()
        type(self).captions[message_id] = caption
        return TelegramDocument(message_id, file_id, f'unique-{message_id}')

    def send_media_group(self, paths, *, filenames, file_ids=None, captions=None):
        type(self).media_group_sizes.append(len(paths))
        documents = []
        for index, (path, filename) in enumerate(zip(paths, filenames)):
            caption = captions[index] if captions is not None else ''
            if file_ids is not None and file_ids[index]:
                message_id = self.next_message_id
                self.next_message_id += 1
                type(self).captions[message_id] = caption
                documents.append(
                    TelegramDocument(message_id, file_ids[index], f'unique-{message_id}')
                )
            else:
                documents.append(self.send_document(path, filename=filename, caption=caption))
        return documents

    def edit_message_caption(self, message_id, caption):
        type(self).captions[message_id] = caption

    def delete_message(self, message_id):
        type(self).deleted_message_ids.append(message_id)

    def download_file(self, file_id, destination):
        Path(destination).write_bytes(type(self).downloaded_files[file_id])


class TelegramBackupTests(TestCase):
    def setUp(self):
        FakeTelegramClient.downloaded_files = {}
        FakeTelegramClient.media_group_sizes = []
        FakeTelegramClient.captions = {}
        FakeTelegramClient.deleted_message_ids = []

    def test_small_backup_is_part_plus_manifest(self):
        source = self._temp_file(b'backup-content')
        with tempfile.TemporaryDirectory() as workdir:
            with self.settings(
                TELEGRAM_BACKUP_PART_SIZE_BYTES=100,
                TELEGRAM_BACKUP_SHARED_DIR=workdir,
            ):
                with patch('app.telegram_backup.TelegramBotApi', FakeTelegramClient):
                    backup = upload_backup(source, source_filename='kinopub.dump')
        self.assertEqual(backup.status, TelegramBackup.Status.UPLOADED)
        self.assertEqual(backup.part_count, 1)
        self.assertEqual(FakeTelegramClient.media_group_sizes, [2])
        self.assertEqual(FakeTelegramClient.deleted_message_ids, [100])
        self.assertEqual(FakeTelegramClient.captions[102], '<code>file-102</code>')

    def test_split_backup_uses_multiple_groups_without_single_remainder(self):
        source = self._temp_file(b'abcdefghijk')
        with tempfile.TemporaryDirectory() as workdir:
            with self.settings(
                TELEGRAM_BACKUP_PART_SIZE_BYTES=1,
                TELEGRAM_BACKUP_SHARED_DIR=workdir,
            ):
                with patch('app.telegram_backup.TelegramBotApi', FakeTelegramClient):
                    backup = upload_backup(source, source_filename='kinopub.dump')
        self.assertEqual(backup.part_count, 11)
        self.assertEqual(FakeTelegramClient.media_group_sizes, [10, 2])
        self.assertTrue(all(2 <= size <= 10 for size in FakeTelegramClient.media_group_sizes))

    def test_manifest_restore_does_not_need_local_backup_index(self):
        source = self._temp_file(b'backup-content')
        with tempfile.TemporaryDirectory() as workdir:
            with self.settings(
                TELEGRAM_BACKUP_PART_SIZE_BYTES=4,
                TELEGRAM_BACKUP_SHARED_DIR=workdir,
            ):
                with patch('app.telegram_backup.TelegramBotApi', FakeTelegramClient):
                    backup = upload_backup(source, source_filename='kinopub.dump')
                    TelegramBackup.objects.filter(pk=backup.pk).delete()
                    destination = self._temp_file(b'')
                    download_manifest_backup(backup.manifest_file_id, destination)
        self.assertEqual(Path(destination).read_bytes(), b'backup-content')

    def test_indexed_restore_reassembles_and_checks_hashes(self):
        source = self._temp_file(b'backup-content')
        with tempfile.TemporaryDirectory() as workdir:
            with self.settings(TELEGRAM_BACKUP_SHARED_DIR=workdir):
                with patch('app.telegram_backup.TelegramBotApi', FakeTelegramClient):
                    backup = upload_backup(source, source_filename='kinopub.dump')
                    destination = self._temp_file(b'')
                    download_backup(backup, destination)
        self.assertEqual(Path(destination).read_bytes(), b'backup-content')

    def test_tampered_part_is_rejected(self):
        source = self._temp_file(b'backup-content')
        with tempfile.TemporaryDirectory() as workdir:
            with self.settings(TELEGRAM_BACKUP_SHARED_DIR=workdir):
                with patch('app.telegram_backup.TelegramBotApi', FakeTelegramClient):
                    backup = upload_backup(source, source_filename='kinopub.dump')
                    part = backup.parts.get(part_number=1)
                    FakeTelegramClient.downloaded_files[part.file_id] = b'tampered'
                    with self.assertRaises(TelegramBackupError):
                        download_manifest_backup(backup.manifest_file_id, self._temp_file(b''))

    def test_manifest_rejects_invalid_format_and_part_sizes(self):
        invalid = (
            '{"format":"%s","backup_id":"00000000-0000-0000-0000-000000000001",'
            '"source_filename":"x.dump","size_bytes":2,"sha256":"%s",'
            '"parts":[{"part_number":1,"filename":"x","size_bytes":1,"sha256":"%s",'
            '"file_id":"file-1"}]}'
            % ('unknown', 'a' * 64, 'b' * 64)
        )
        path = self._temp_file(invalid.encode())
        with self.assertRaises(TelegramBackupError):
            load_manifest(path)

        valid_format_but_bad_sizes = invalid.replace('unknown', MANIFEST_FORMAT)
        path = self._temp_file(valid_format_but_bad_sizes.encode())
        with self.assertRaises(TelegramBackupError):
            load_manifest(path)

    def test_token_is_not_exposed_in_api_errors(self):
        class FakeResponse:
            status_code = 400

            def json(self):
                return {'ok': False, 'description': 'chat not found'}

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse()

        with self.settings(TELEGRAM_BACKUP_LOCAL_FILE_MODE=False):
            client = TelegramBotApi(
                token='secret-bot-token',
                base_url='http://telegram',
                session=FakeSession(),
            )
            with self.assertRaises(TelegramBackupError) as raised:
                client.probe()
        self.assertNotIn('secret-bot-token', str(raised.exception))

    def test_multipart_stream_is_rewound_after_rate_limit(self):
        class Response:
            def __init__(self, payload, status_code):
                self.payload = payload
                self.status_code = status_code

            def json(self):
                return self.payload

        class Session:
            def __init__(self):
                self.payload_sizes = []

            def post(self, *args, **kwargs):
                stream = kwargs['files']['document'][1]
                self.payload_sizes.append(len(stream.read()))
                if len(self.payload_sizes) == 1:
                    return Response({'ok': False, 'parameters': {'retry_after': 1}}, 429)
                return Response(
                    {
                        'ok': True,
                        'result': {
                            'message_id': 1,
                            'document': {'file_id': 'file-1'},
                        },
                    },
                    200,
                )

        source = self._temp_file(b'payload')
        session = Session()
        with self.settings(TELEGRAM_BACKUP_LOCAL_FILE_MODE=False):
            with patch('app.telegram_backup.time.sleep'):
                document = TelegramBotApi(
                    token='test-token',
                    base_url='http://telegram',
                    session=session,
                ).send_document(source, filename='backup.dump')
        self.assertEqual(document.file_id, 'file-1')
        self.assertEqual(session.payload_sizes, [7, 7])

    def test_restore_requires_confirmation(self):
        with self.assertRaises(CommandError):
            RestoreCommand().handle()

    @staticmethod
    def _temp_file(content):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        Path(path).write_bytes(content)
        return path
