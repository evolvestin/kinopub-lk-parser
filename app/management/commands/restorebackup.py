import logging
import multiprocessing
import os
import subprocess
import time

from django.conf import settings
from django.db import connection, connections

from app.gdrive_backup import BackupManager
from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Restores data from a Google Drive backup using pg_restore (binary format).'

    def handle(self, *args, **options):
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if handler.__class__.__name__ == 'DatabaseLogHandler':
                root_logger.removeHandler(handler)

        logging.info('Starting restore process...')
        manager = BackupManager()
        backup_file_path = manager.restore_from_backup()

        if not backup_file_path or not os.path.exists(backup_file_path):
            logging.error('Backup file not found on Google Drive. Aborting.')
            return

        try:
            db_conf = settings.DATABASES['default']
            db_name = db_conf['NAME']

            logging.info('Terminating other connections and dropping schema...')

            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{db_name}'
                      AND pid <> pg_backend_pid();
                """)

                time.sleep(2)

                cursor.execute('DROP SCHEMA public CASCADE;')
                cursor.execute('CREATE SCHEMA public;')

            connections.close_all()

            env = os.environ.copy()
            env['PGPASSWORD'] = db_conf['PASSWORD']
            env['PGOPTIONS'] = (
                '-c maintenance_work_mem=128MB '
                '-c synchronous_commit=off '
                '-c client_min_messages=warning'
            )

            jobs = max(2, multiprocessing.cpu_count())
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
                '-j',
                str(jobs),
                '--no-owner',
                '--no-privileges',
                '-v',
                backup_file_path,
            ]

            logging.info(f'Executing pg_restore with {jobs} parallel jobs...')

            process = subprocess.Popen(
                cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )

            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        logging.info(f'[pg_restore] {line}')

            retcode = process.wait()

            if retcode >= 2:
                logging.error(f'pg_restore failed with exit code {retcode}')
                raise subprocess.CalledProcessError(retcode, cmd)

            logging.info('Restore successful.')

        except Exception as e:
            logging.error(f'Restore failed: {e}')
            raise e
        finally:
            if os.path.exists(backup_file_path):
                os.remove(backup_file_path)
