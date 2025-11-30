import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from redis import Redis

from app import history_parser, telegram_bot
from app.gdrive_backup import BackupManager
from app.models import Code, LogEntry
import io
import shlex
from contextlib import redirect_stdout, redirect_stderr

from celery import shared_task
from django.core.management import call_command
from django.utils import timezone

from app.models import TaskRun


@shared_task
def run_history_parser_task():
    logging.info('Starting periodic history parser task.')
    try:
        history_parser.run_parser_session()
    except Exception as e:
        logging.error('Celery task: history parser run failed: %s', e, exc_info=True)


@shared_task
def run_full_scan_task():
    logging.info('Starting quarterly full scan task.')
    try:
        call_command('runfullscan')
    except Exception as e:
        logging.error('Celery task: full scan run failed: %s', e, exc_info=True)


@shared_task
def expire_codes_task():
    logging.debug('Running periodic check for expired codes...')
    try:
        expiration_threshold = timezone.now() - timedelta(
            minutes=settings.CODE_LIFETIME_MINUTES
        )
        expired_codes = Code.objects.filter(received_at__lt=expiration_threshold)
        if expired_codes.exists():
            logging.info('Found %d expired codes to process.', expired_codes.count())
            for code in expired_codes:
                telegram_bot.edit_message_to_expired(code.telegram_message_id)
                code.delete()
            BackupManager().schedule_backup()
    except Exception as e:
        logging.error('Celery task: Error in expire_codes_task: %s', e)


@shared_task
def delete_old_logs_task():
    logging.info('Running periodic check for old log entries...')
    try:
        cutoff_date = timezone.now() - timedelta(days=settings.LOG_RETENTION_DAYS)
        deleted_count, _ = LogEntry.objects.filter(created_at__lt=cutoff_date).delete()
        if deleted_count > 0:
            logging.info('Deleted %d old log entries.', deleted_count)
    except Exception as e:
        logging.error('Celery task: Error in delete_old_logs_task: %s', e)


@shared_task
def backup_database():
    redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
    lock = redis_client.lock('backup_lock', timeout=300)  # 5 min timeout
    if lock.acquire(blocking=False):
        try:
            BackupManager().perform_backup()
        finally:
            lock.release()
    else:
        logging.debug('Backup already in progress. Skipping.')


@shared_task
def backup_cookies():
    redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
    lock = redis_client.lock('cookies_backup_lock', timeout=60)
    if lock.acquire(blocking=False):
        try:
            BackupManager().perform_cookies_backup()
        finally:
            lock.release()
    else:
        logging.debug('Cookies backup already in progress. Skipping.')


@shared_task(bind=True)
def run_admin_command(self, task_run_id):
    try:
        task_run = TaskRun.objects.get(id=task_run_id)
        task_run.status = 'RUNNING'
        task_run.celery_task_id = self.request.id
        task_run.save()

        cmd_args = shlex.split(task_run.arguments) if task_run.arguments else []
        
        out_buffer = io.StringIO()
        err_buffer = io.StringIO()

        try:
            with redirect_stdout(out_buffer), redirect_stderr(err_buffer):
                call_command(task_run.command, *cmd_args)
            
            task_run.output = out_buffer.getvalue() + "\n" + err_buffer.getvalue()
            task_run.status = 'SUCCESS'
        except KeyboardInterrupt:
            # Обработка остановки задачи (SIGINT)
            task_run.output = out_buffer.getvalue() + "\nProcess interrupted by user."
            task_run.status = 'STOPPED'
        except Exception as e:
            task_run.output = out_buffer.getvalue()
            task_run.error_message = str(e)
            task_run.status = 'FAILURE'
        
        task_run.updated_at = timezone.now()
        task_run.save()

    except TaskRun.DoesNotExist:
        pass