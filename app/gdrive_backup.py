import threading
import queue
import logging
import json
import os
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

from django.conf import settings


class BackupManager:
    """
    Manages database backups to Google Drive using a background thread.
    Ensures only one backup is scheduled at a time.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackupManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._backup_queue = queue.Queue(maxsize=1)
            self._shutdown_flag = threading.Event()
            self._backup_thread = None
            self._cached_file_ids = {}
            self._drive = None
            self._initialized = True

    def schedule_backup(self):
        """Non-blocking function to schedule a database backup."""
        if self._backup_queue.empty():
            try:
                self._backup_queue.put_nowait('backup')
                logging.info('Database backup scheduled.')
            except queue.Full:
                logging.debug('Backup is already scheduled.')

    def _get_drive_service(self):
        """Authenticates with Google Drive using service account and returns the drive object."""
        if self._drive:
            return self._drive

        if not settings.GOOGLE_DRIVE_CREDENTIALS_JSON:
            logging.error('Google Drive credentials are not configured in environment variables.')
            return None

        try:
            creds_dict = json.loads(settings.GOOGLE_DRIVE_CREDENTIALS_JSON)
            gauth = GoogleAuth()
            scope = ['https://www.googleapis.com/auth/drive']
            gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self._drive = GoogleDrive(gauth)
            return self._drive
        except json.JSONDecodeError:
            logging.error('Failed to parse GOOGLE_DRIVE_CREDENTIALS_JSON. Ensure it\'s a valid JSON string.')
            return None
        except Exception as e:
            logging.error(f'Failed to authenticate with Google Drive: {e}')
            return None

    def _find_backup_file(self, drive, filename):
        """Finds a specific backup file on Google Drive and returns its ID."""
        if filename in self._cached_file_ids:
            return self._cached_file_ids[filename]

        query = f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and title = '{filename}' and trashed = false"
        file_list = drive.ListFile({'q': query}).GetList()

        if file_list:
            if len(file_list) > 1:
                logging.warning(f'Multiple files found for {filename}. Using the first one.')
            file_id = file_list[0]['id']
            self._cached_file_ids[filename] = file_id
            logging.info(f'Found existing backup file {filename} with id {file_id}.')
            return file_id
        else:
            logging.info(f'Backup file {filename} not found in the specified Google Drive folder.')
            return None

    def _perform_backup(self):
        """Performs the actual upload of database and cookies to Google Drive."""
        logging.info('Starting backup process...')
        drive = self._get_drive_service()
        if not drive:
            logging.error('Could not get Google Drive service. Backup aborted.')
            return

        files_to_backup = [
            (settings.DB_PATH, settings.DB_BACKUP_FILENAME),
            (settings.COOKIES_FILE_PATH, settings.COOKIES_BACKUP_FILENAME),
        ]

        for local_path, remote_name in files_to_backup:
            if not os.path.exists(local_path):
                logging.warning('File not found at %s. Skipping backup for this file.', local_path)
                continue

            try:
                file_id = self._find_backup_file(drive, remote_name)
                if file_id:
                    g_file = drive.CreateFile({'id': file_id})
                else:
                    g_file = drive.CreateFile({
                        'title': remote_name,
                        'parents': [{'id': settings.GOOGLE_DRIVE_FOLDER_ID}]
                    })

                g_file.SetContentFile(local_path)
                g_file.Upload()
                self._cached_file_ids[remote_name] = g_file['id']
                logging.info('Successfully uploaded %s to Google Drive.', remote_name)
            except Exception as e:
                logging.error(f'An error occurred during backup of {remote_name}: {e}')
                if remote_name in self._cached_file_ids:
                    del self._cached_file_ids[remote_name]

    def _backup_worker(self):
        """Worker thread that waits for signals in the queue and runs the backup process."""
        while not self._shutdown_flag.is_set():
            try:
                self._backup_queue.get(timeout=1)
                self._perform_backup()
                self._backup_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f'An exception occurred in the backup worker: {e}')

    def start(self):
        """Starts the background thread for managing backups."""
        if self._backup_thread is None or not self._backup_thread.is_alive():
            self._shutdown_flag.clear()
            self._backup_thread = threading.Thread(target=self._backup_worker, daemon=True, name='BackupThread')
            self._backup_thread.start()
            logging.info('Backup thread started.')

    def stop(self):
        """Stops the background backup thread."""
        logging.info('Stopping backup thread...')
        self._shutdown_flag.set()
        if self._backup_thread and self._backup_thread.is_alive():
            self._backup_thread.join(timeout=5)
        logging.info('Backup thread stopped.')

    def restore_from_backup(self):
        """Downloads database and cookies from Google Drive if they don't exist locally."""
        logging.info('Attempting to restore files from Google Drive...')
        drive = self._get_drive_service()
        if not drive:
            logging.error('Could not get Google Drive service. Restore aborted.')
            return

        files_to_restore = [
            (settings.DB_PATH, settings.DB_BACKUP_FILENAME),
            (settings.COOKIES_FILE_PATH, settings.COOKIES_BACKUP_FILENAME),
        ]

        for local_path, remote_name in files_to_restore:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                logging.info('File already exists at %s and is not empty. No restore needed.', local_path)
                continue

            try:
                file_id = self._find_backup_file(drive, remote_name)
                if not file_id:
                    logging.warning('Backup file %s not found on Google Drive. Skipping.', remote_name)
                    continue

                logging.info(f'Found backup file {remote_name}. Downloading...')
                g_file = drive.CreateFile({'id': file_id})

                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                g_file.GetContentFile(local_path)
                logging.info('Successfully restored %s from Google Drive to %s.', remote_name, local_path)
            except Exception as e:
                logging.error(f'An error occurred during restore of {remote_name}: {e}')
