import logging
import os
import subprocess

from django.conf import settings
from django.db import connection

from app.gdrive_backup import BackupManager
from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Restores data from a Google Drive backup using pg_restore (binary format).'

    def handle(self, *args, **options):
        logging.info('Starting restore from backup process...')
        manager = BackupManager()
        backup_file_path = manager.restore_from_backup()

        if not backup_file_path or not os.path.exists(backup_file_path):
            logging.warning('No backup file found. Aborting restore.')
            return

        logging.info(f'Using backup file at {backup_file_path}')

        try:
            db_conf = settings.DATABASES['default']
            db_name = db_conf['NAME']

            logging.info('Terminating existing connections and cleaning schema...')
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{db_name}'
                      AND pid <> pg_backend_pid();
                    """
                )
                cursor.execute('DROP SCHEMA public CASCADE;')
                cursor.execute('CREATE SCHEMA public;')

            env = os.environ.copy()
            env['PGPASSWORD'] = db_conf['PASSWORD']

            cmd = [
                'pg_restore',
                '-h',
                db_conf['HOST'],
                '-p',
                str(db_conf['PORT']),
                '-U',
                db_conf['USER'],
                '-d',
                db_name,
                '--no-owner',
                '-v',
                backup_file_path,
            ]

            logging.info('Restoring database using pg_restore...')
            result = subprocess.run(cmd, env=env, check=False)

            if result.returncode > 1:
                raise subprocess.CalledProcessError(result.returncode, cmd)

            logging.info('Restore process completed successfully.')
            manager.schedule_backup()

        finally:
            if os.path.exists(backup_file_path):
                os.remove(backup_file_path)
                logging.info(f'Removed temporary backup file: {backup_file_path}')
