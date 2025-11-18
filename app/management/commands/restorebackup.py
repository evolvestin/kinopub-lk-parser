import logging
import os

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, connections, transaction
from django.db.models import AutoField, BigAutoField, Max

from app.gdrive_backup import BackupManager
from app.models import LogEntry


class Command(BaseCommand):
    help = 'Restores data from a Google Drive backup, comparing tables and updating if necessary.'

    def _table_exists_in_backup(self, table_name):
        """Checks if a table exists in the restore_source (SQLite) database."""
        try:
            with connections['restore_source'].cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table_name]
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f'Error checking for table {table_name} in backup: {e}')
            return False

    def handle(self, *args, **options):
        logging.info('Starting restore from backup process...')
        manager = BackupManager()
        backup_db_path = manager.restore_from_backup()

        if not backup_db_path or not os.path.exists(backup_db_path):
            logging.warning('No backup file found. Aborting restore.')
            return

        logging.info(f'Using backup file at {backup_db_path}')

        try:
            connections.databases['restore_source'] = {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': backup_db_path,
                'TIME_ZONE': settings.TIME_ZONE,
                'CONN_HEALTH_CHECKS': False,
                'CONN_MAX_AGE': 0,
                'OPTIONS': {},
                'AUTOCOMMIT': True,
                'ATOMIC_REQUESTS': False,
            }

            self.process_logs()

            models_to_process = [
                m
                for m in apps.get_models()
                if m._meta.app_label == 'app' and not m._meta.proxy and m is not LogEntry
            ]

            for model in models_to_process:
                self.process_table(model)

            for model in models_to_process:
                for field in model._meta.many_to_many:
                    m2m_model = field.remote_field.through
                    if m2m_model._meta.auto_created:
                        self.process_m2m_table(m2m_model)

            logging.info('Restore process completed successfully.')
            manager.schedule_backup()
        except Exception as e:
            logging.error(
                f'A critical error occurred during backup restoration: {e}',
                exc_info=True,
            )
            logging.error('An error occurred during restore. Check logs.')
        finally:
            if 'restore_source' in connections.databases:
                connections['restore_source'].close()
                del connections.databases['restore_source']
            if os.path.exists(backup_db_path):
                os.remove(backup_db_path)
                logging.info(f'Removed temporary backup file: {backup_db_path}')

    def process_m2m_table(self, m2m_model):
        table_name = m2m_model._meta.db_table
        logging.info(f'Processing M2M table: {table_name}')

        if not self._table_exists_in_backup(table_name):
            logging.warning(f"M2M table '{table_name}' not found in backup file. Skipping.")
            return

        try:
            with transaction.atomic(using='default'):
                with connection.cursor() as cursor:
                    logging.info(f'Truncating M2M table {table_name}...')
                    cursor.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE;')

                logging.info(f'Copying data from backup for M2M table {table_name}...')
                queryset = m2m_model.objects.using('restore_source').all().iterator(chunk_size=2000)
                batch = []
                for item in queryset:
                    batch.append(item)
                    if len(batch) >= 2000:
                        m2m_model.objects.using('default').bulk_create(
                            batch, batch_size=2000, ignore_conflicts=True
                        )
                        batch = []
                if batch:
                    m2m_model.objects.using('default').bulk_create(
                        batch, batch_size=2000, ignore_conflicts=True
                    )

                if connection.vendor == 'postgresql':
                    pk = m2m_model._meta.pk
                    if isinstance(pk, (AutoField, BigAutoField)):
                        pk_name = pk.name
                        sequence_sql = f"""
                            SELECT setval(
                                pg_get_serial_sequence('"{table_name}"', '{pk_name}'),
                                COALESCE(MAX("{pk_name}"), 1),
                                MAX("{pk_name}") IS NOT NULL
                            ) FROM "{table_name}";
                        """
                        with connection.cursor() as cursor:
                            cursor.execute(sequence_sql)
                        logging.info(f'Sequence for {table_name}.{pk_name} has been reset.')

            logging.info(f"Successfully restored M2M table '{table_name}'.")
        except Exception as e:
            logging.error(f'Failed to restore M2M table {table_name}: {e}', exc_info=True)
            logging.error(f"Error restoring M2M table '{table_name}'.")

    def process_table(self, model):
        table_name = model._meta.db_table
        logging.info(f'Processing table: {table_name}')

        if not self._table_exists_in_backup(table_name):
            logging.warning(f"Table '{table_name}' not found in backup file. Skipping.")
            return

        if not hasattr(model, 'updated_at'):
            logging.warning(f"Model {model.__name__} has no 'updated_at' field. Skipping.")
            return

        latest_local = model.objects.using('default').aggregate(max_updated=Max('updated_at'))[
            'max_updated'
        ]
        latest_backup = model.objects.using('restore_source').aggregate(
            max_updated=Max('updated_at')
        )['max_updated']

        logging.info(f'Latest local: {latest_local}, Latest backup: {latest_backup}')

        if latest_backup and (not latest_local or latest_backup > latest_local):
            logging.info(
                f"Backup is newer for '{table_name}'. Restoring full table with original timestamps."
            )

            created_at_field = model._meta.get_field('created_at')
            updated_at_field = model._meta.get_field('updated_at')
            original_auto_now_add = created_at_field.auto_now_add
            original_auto_now = updated_at_field.auto_now

            try:
                backup_objects = list(model.objects.using('restore_source').all().iterator())

                created_at_field.auto_now_add = False
                updated_at_field.auto_now = False

                with transaction.atomic(using='default'):
                    with connection.cursor() as cursor:
                        logging.info(f'Truncating table {table_name}...')
                        cursor.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE;')

                    if backup_objects:
                        logging.info(
                            f'Bulk creating {len(backup_objects)} records for {table_name}...'
                        )
                        model.objects.using('default').bulk_create(
                            backup_objects, batch_size=2000, ignore_conflicts=True
                        )
                logging.info(f"Successfully restored table '{table_name}'.")
            except Exception as e:
                logging.error(f'Failed to restore table {table_name}: {e}', exc_info=True)
                logging.error(f"Error restoring table '{table_name}'.")
            finally:
                created_at_field.auto_now_add = original_auto_now_add
                updated_at_field.auto_now = original_auto_now
        else:
            logging.info(f"Local data for '{table_name}' is up-to-date. Skipping.")

        if connection.vendor == 'postgresql':
            pk = model._meta.pk
            if isinstance(pk, (AutoField, BigAutoField)):
                pk_name = pk.name
                sequence_sql = f"""
                    SELECT setval(
                        pg_get_serial_sequence('"{table_name}"', '{pk_name}'),
                        COALESCE(MAX("{pk_name}"), 1),
                        MAX("{pk_name}") IS NOT NULL
                    ) FROM "{table_name}";
                """
                with connection.cursor() as cursor:
                    cursor.execute(sequence_sql)
                logging.info(f'Sequence for {table_name}.{pk_name} has been reset.')

    def process_logs(self):
        model = LogEntry
        table_name = model._meta.db_table
        logging.info(f'Processing special table: {table_name}')

        if not self._table_exists_in_backup(table_name):
            logging.warning(f"Table '{table_name}' not found in backup file. Skipping.")
            return

        try:
            latest_local_log_ts = model.objects.using('default').aggregate(
                max_created=Max('created_at')
            )['max_created']

            backup_queryset = model.objects.using('restore_source').order_by('created_at')

            if latest_local_log_ts:
                logging.info(
                    f'Newest local log is from {latest_local_log_ts}. Adding newer logs from backup.'
                )
                backup_queryset = backup_queryset.filter(created_at__gt=latest_local_log_ts)
            else:
                logging.info('No local logs found. Restoring all logs from backup.')

            logs_to_add = list(backup_queryset)
            total_added = len(logs_to_add)

            if total_added > 0:
                created_at_field = model._meta.get_field('created_at')
                updated_at_field = model._meta.get_field('updated_at')
                original_auto_now_add = created_at_field.auto_now_add
                original_auto_now = updated_at_field.auto_now
                try:
                    created_at_field.auto_now_add = False
                    updated_at_field.auto_now = False
                    with transaction.atomic(using='default'):
                        model.objects.using('default').bulk_create(
                            logs_to_add, batch_size=5000, ignore_conflicts=True
                        )
                    logging.info(
                        f'Successfully supplemented {total_added} log entries from backup.'
                    )
                except Exception as e:
                    logging.error(f'Failed to restore logs: {e}', exc_info=True)
                finally:
                    created_at_field.auto_now_add = original_auto_now_add
                    updated_at_field.auto_now = original_auto_now
            else:
                logging.info('Log entries are up-to-date. No new logs to add.')

        finally:
            if connection.vendor == 'postgresql':
                pk = model._meta.pk
                if isinstance(pk, (AutoField, BigAutoField)):
                    pk_name = pk.name
                    sequence_sql = f"""
                        SELECT setval(
                            pg_get_serial_sequence('"{table_name}"', '{pk_name}'),
                            COALESCE(MAX("{pk_name}"), 1),
                            MAX("{pk_name}") IS NOT NULL
                        ) FROM "{table_name}";
                    """
                    with connection.cursor() as cursor:
                        cursor.execute(sequence_sql)
                    logging.info(f'Sequence for {table_name}.{pk_name} has been reset.')
