import json
import logging
import os
import subprocess
import time

from django.conf import settings
from django.db.models import Max
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

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
        if settings.LOCAL_RUN:
            logging.info('Local run detected, skipping Celery backup task scheduling.')
            return
        celery_app.send_task('app.tasks.backup_database')
        logging.info('Database backup scheduled via Celery.')

    def _get_drive_service(self):
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
        query = (
            f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' "
            f"in parents and title = '{filename}' and trashed = false"
        )
        file_list = drive.ListFile({'q': query}).GetList()
        if file_list:
            file_id = file_list[0]['id']
            self._cached_file_ids[filename] = file_id
            return file_id
        return None

    def _upload_file(self, drive, local_path, remote_name):
        try:
            file_id = self._get_file_id(drive, remote_name)
            if not file_id:
                logging.error(
                    (
                        'File "%s" not found on Google Drive and creation is not supported.'
                        ' Upload aborted.'
                    ),
                    remote_name,
                )
                return

            g_file = drive.CreateFile({'id': file_id})
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
        data_dir = str(settings.COOKIES_FILE_PATH_MAIN.parent)

        last_ts_file = os.path.join(data_dir, 'last_db_backup_ts')
        last_backup_ts = 0.0
        if os.path.exists(last_ts_file):
            try:
                with open(last_ts_file, 'r') as f:
                    last_backup_ts = float(f.read().strip())
            except ValueError:
                pass

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
            res = model.objects.aggregate(max_ts=Max('updated_at'))
            ts = res.get('max_ts')
            if ts:
                if max_updated_at is None or ts > max_updated_at:
                    max_updated_at = ts

        if max_updated_at and max_updated_at.timestamp() <= last_backup_ts:
            logging.info('Database has not changed since last backup. Skipping.')
            return

        logging.info('Starting backup process (pg_dump binary format)...')
        drive = self._get_drive_service()
        if not drive:
            logging.error('Could not get Google Drive service. Backup aborted.')
            return

        backup_file_path = os.path.join(data_dir, f'backup_{int(time.time())}.dump')

        try:
            db_conf = settings.DATABASES['default']
            env = os.environ.copy()
            env['PGPASSWORD'] = db_conf['PASSWORD']

            cmd = [
                'pg_dump',
                '-h',
                db_conf['HOST'],
                '-p',
                str(db_conf['PORT']),
                '-U',
                db_conf['USER'],
                '-F',
                'c',
                '-b',
                '-v',
                '-f',
                backup_file_path,
                db_conf['NAME'],
            ]

            logging.info(f'Dumping database to {backup_file_path}...')
            subprocess.run(cmd, env=env, check=True)

            if os.path.exists(backup_file_path):
                file_size = os.path.getsize(backup_file_path)
                logging.info(f'Backup file created successfully, size: {file_size} bytes')

                if settings.ENVIRONMENT == 'DEV':
                    logging.info('Dev environment detected. Skipping upload to Google Drive.')
                else:
                    self._upload_file(drive, backup_file_path, settings.DB_BACKUP_FILENAME)

                if max_updated_at:
                    with open(last_ts_file, 'w') as f:
                        f.write(str(max_updated_at.timestamp()))
            else:
                logging.error(f'Backup file {backup_file_path} was not found after creation.')

        except subprocess.CalledProcessError as e:
            logging.error(f'pg_dump failed: {e}')
        except Exception as e:
            logging.error(f'An error occurred during backup process: {e}', exc_info=True)
        finally:
            if backup_file_path and os.path.exists(backup_file_path):
                os.remove(backup_file_path)
                logging.info(f'Removed temporary backup file: {backup_file_path}')

    def perform_cookies_backup(self):
        logging.info('Starting cookies backup process...')
        drive = self._get_drive_service()
        if not drive:
            logging.error('Could not get Google Drive service. Cookies backup aborted.')
            return

        cookie_files = [
            (settings.COOKIES_FILE_PATH_MAIN, settings.COOKIES_BACKUP_FILENAME_MAIN),
            (settings.COOKIES_FILE_PATH_AUX, settings.COOKIES_BACKUP_FILENAME_AUX),
        ]

        for local_path, remote_name in cookie_files:
            if os.path.exists(local_path):
                self._upload_file(drive, local_path, remote_name)
            else:
                logging.warning(f'Cookies file {local_path} not found locally. Skipping.')

    def restore_from_backup(self):
        logging.info('Attempting to download files from Google Drive for restore...')
        drive = self._get_drive_service()
        if not drive:
            logging.error('Could not get Google Drive service. Restore aborted.')
            return None

        data_dir = str(settings.COOKIES_FILE_PATH_MAIN.parent)
        os.makedirs(data_dir, exist_ok=True)
        db_backup_path = os.path.join(data_dir, settings.DB_BACKUP_FILENAME)

        if not self._download_file(drive, settings.DB_BACKUP_FILENAME, db_backup_path):
            logging.warning(
                'Database backup file not found on Google Drive. Restore cannot proceed.'
            )
            return None

        self._download_file(
            drive, settings.COOKIES_BACKUP_FILENAME_MAIN, settings.COOKIES_FILE_PATH_MAIN
        )
        self._download_file(
            drive, settings.COOKIES_BACKUP_FILENAME_AUX, settings.COOKIES_FILE_PATH_AUX
        )

        return db_backup_path
