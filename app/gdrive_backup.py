import json
import logging
import os
import sys
import time

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

from kinopub_parser import celery_app


class BackupManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackupManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._cached_file_ids = {}
            self._drive = None
            self._initialized = True

    def schedule_backup(self):
        celery_app.send_task('app.tasks.backup_database')
        logging.info('Database backup scheduled via Celery.')

    def _get_drive_service(self):
        if self._drive:
            return self._drive
        if not settings.GOOGLE_DRIVE_CREDENTIALS_JSON:
            logging.error('Google Drive credentials are not configured.')
            return None
        try:
            creds_dict = json.loads(settings.GOOGLE_DRIVE_CREDENTIALS_JSON)
            gauth = GoogleAuth()
            scope = ['https://www.googleapis.com/auth/drive']
            gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self._drive = GoogleDrive(gauth)
            return self._drive
        except Exception as e:
            logging.error(f'Failed to authenticate with Google Drive: {e}')
            return None

    def _get_file_id(self, drive, filename):
        if filename in self._cached_file_ids:
            return self._cached_file_ids[filename]
        query = f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and title = '{filename}' and trashed = false"
        file_list = drive.ListFile({'q': query}).GetList()
        if file_list:
            file_id = file_list[0]['id']
            self._cached_file_ids[filename] = file_id
            return file_id
        return None

    def _upload_file(self, drive, local_path, remote_name):
        try:
            file_id = self._get_file_id(drive, remote_name)
            g_file = (
                drive.CreateFile({'id': file_id})
                if file_id
                else drive.CreateFile(
                    {
                        'title': remote_name,
                        'parents': [{'id': settings.GOOGLE_DRIVE_FOLDER_ID}],
                    }
                )
            )
            g_file.SetContentFile(local_path)
            g_file.Upload()
            self._cached_file_ids[remote_name] = g_file['id']
            logging.info('Successfully uploaded %s to Google Drive.', remote_name)
        except Exception as e:
            logging.error(f'An error occurred during upload of {remote_name}: {e}')
            if remote_name in self._cached_file_ids:
                del self._cached_file_ids[remote_name]

    def _download_file(self, drive, remote_name, local_path):
        try:
            file_id = self._get_file_id(drive, remote_name)
            if not file_id:
                logging.warning('Backup file %s not found on Google Drive.', remote_name)
                return False
            g_file = drive.CreateFile({'id': file_id})
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            g_file.GetContentFile(local_path)
            logging.info('Successfully restored %s to %s.', remote_name, local_path)
            return True
        except Exception as e:
            logging.error(f'An error occurred during restore of {remote_name}: {e}')
            return False

    def perform_backup(self):
        original_handlers = logging.root.handlers[:]
        console_handler = next(
            (h for h in original_handlers if isinstance(h, logging.StreamHandler)), None
        )

        try:
            if console_handler:
                logging.root.handlers = [console_handler]

            logging.info('Starting backup process...')
            drive = self._get_drive_service()
            if not drive:
                logging.error('Could not get Google Drive service. Backup aborted.')
                return

            backup_db_path = os.path.join('/data', f'backup_{int(time.time())}.db')

            logging.info(f'Creating temporary SQLite backup at {backup_db_path}')

            connections.databases['backup_sqlite'] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': backup_db_path,
                'TIME_ZONE': settings.TIME_ZONE,
                'CONN_HEALTH_CHECKS': False,
                'CONN_MAX_AGE': 0,
                'OPTIONS': {},
                'AUTOCOMMIT': True,
                'ATOMIC_REQUESTS': False,
            }

            call_command('migrate', database='backup_sqlite', verbosity=0, interactive=False)

            connections['backup_sqlite'].ensure_connection()

            models_to_backup = [
                m for m in apps.get_models() if m._meta.app_label == 'app' and not m._meta.proxy
            ]

            for model in models_to_backup:
                table_name = model._meta.db_table
                sys.stdout.write(f'Backing up table: {table_name}\n')
                sys.stdout.flush()

                created_at_field = next(
                    (f for f in model._meta.fields if f.name == 'created_at'), None
                )
                updated_at_field = next(
                    (f for f in model._meta.fields if f.name == 'updated_at'), None
                )
                original_auto_now_add = created_at_field.auto_now_add if created_at_field else None
                original_auto_now = updated_at_field.auto_now if updated_at_field else None

                try:
                    if created_at_field:
                        created_at_field.auto_now_add = False
                    if updated_at_field:
                        updated_at_field.auto_now = False

                    queryset = model.objects.using('default').all()
                    total_count = queryset.count()
                    sys.stdout.write(f'Found {total_count} records to backup for {table_name}\n')
                    sys.stdout.flush()

                    if total_count > 0:
                        batch_size = 2000
                        for offset in range(0, total_count, batch_size):
                            batch = list(queryset[offset : offset + batch_size])
                            if batch:
                                model.objects.using('backup_sqlite').bulk_create(
                                    batch, batch_size=batch_size, ignore_conflicts=True
                                )
                        sys.stdout.write(
                            f'Successfully backed up {total_count} records for {table_name}\n'
                        )
                        sys.stdout.flush()
                finally:
                    if created_at_field and original_auto_now_add is not None:
                        created_at_field.auto_now_add = original_auto_now_add
                    if updated_at_field and original_auto_now is not None:
                        updated_at_field.auto_now = original_auto_now

            for model in models_to_backup:
                for field in model._meta.many_to_many:
                    m2m_model = field.remote_field.through
                    if not m2m_model._meta.auto_created:
                        continue
                    table_name = m2m_model._meta.db_table
                    sys.stdout.write(f'Backing up M2M table: {table_name}\n')
                    sys.stdout.flush()

                    queryset = m2m_model.objects.using('default').all()
                    total_count = queryset.count()

                    if total_count > 0:
                        batch_size = 5000
                        for offset in range(0, total_count, batch_size):
                            batch = list(queryset[offset : offset + batch_size])
                            if batch:
                                m2m_model.objects.using('backup_sqlite').bulk_create(
                                    batch, batch_size=batch_size, ignore_conflicts=True
                                )
                        sys.stdout.write(
                            f'Successfully backed up {total_count} M2M records for {table_name}\n'
                        )
                        sys.stdout.flush()

            connections['backup_sqlite'].close()
            del connections.databases['backup_sqlite']

            file_size = os.path.getsize(backup_db_path)
            logging.info(f'Backup database created successfully, size: {file_size} bytes')

            self._upload_file(drive, backup_db_path, settings.DB_BACKUP_FILENAME)

            if os.path.exists(settings.COOKIES_FILE_PATH):
                self._upload_file(
                    drive,
                    settings.COOKIES_FILE_PATH,
                    settings.COOKIES_BACKUP_FILENAME,
                )

        except Exception as e:
            logging.error(f'An error occurred during backup process: {e}', exc_info=True)
        finally:
            logging.root.handlers = original_handlers

            if 'backup_sqlite' in connections.databases:
                if connections['backup_sqlite'].connection:
                    connections['backup_sqlite'].close()
                del connections.databases['backup_sqlite']
            if 'backup_db_path' in locals() and os.path.exists(backup_db_path):
                os.remove(backup_db_path)
                logging.info(f'Removed temporary backup file: {backup_db_path}')

    def restore_from_backup(self):
        logging.info('Attempting to download files from Google Drive for restore...')
        drive = self._get_drive_service()
        if not drive:
            logging.error('Could not get Google Drive service. Restore aborted.')
            return None

        data_dir = os.path.join(settings.BASE_DIR, 'data')
        os.makedirs(data_dir, exist_ok=True)
        db_backup_path = os.path.join(data_dir, settings.DB_BACKUP_FILENAME)

        if not self._download_file(drive, settings.DB_BACKUP_FILENAME, db_backup_path):
            logging.warning(
                'Database backup file not found on Google Drive. Restore cannot proceed.'
            )
            return None

        self._download_file(drive, settings.COOKIES_BACKUP_FILENAME, settings.COOKIES_FILE_PATH)
        return db_backup_path
