import logging
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from redis import Redis

from app import history_parser
from app.gdrive_backup import BackupManager
from app.models import Code, LogEntry, TaskRun
from app.telegram_bot import TelegramSender


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
        expiration_threshold = timezone.now() - timedelta(minutes=settings.CODE_LIFETIME_MINUTES)

        expired_codes = list(
            Code.objects.filter(received_at__lt=expiration_threshold).exclude(
                telegram_message_id=-1
            )
        )

        if expired_codes:
            logging.info('Found %d expired codes to mark in Telegram.', len(expired_codes))

            telegram_ids = [c.telegram_message_id for c in expired_codes]
            sender = TelegramSender()
            for telegram_id in telegram_ids:
                sender.edit_message_to_expired(telegram_id)

            Code.objects.filter(id__in=[c.id for c in expired_codes]).update(telegram_message_id=-1)

            BackupManager().schedule_backup()

    except Exception as e:
        logging.error('Celery task: Error in expire_codes_task: %s', e)


@shared_task
def delete_old_logs_task():
    logging.info('Running periodic cleanup of logs and data...')
    try:
        now = timezone.now()

        # 1. Очистка логов по уровням
        # INFO и DEBUG: храним 1 месяц (30 дней)
        cutoff_info = now - timedelta(days=30)
        LogEntry.objects.filter(created_at__lt=cutoff_info, level__in=['INFO', 'DEBUG']).exclude(
            message__contains='New Episodes Parser Finished'
        ).delete()

        # WARNING: храним 2 месяца (60 дней)
        cutoff_warning = now - timedelta(days=60)
        LogEntry.objects.filter(created_at__lt=cutoff_warning, level='WARNING').delete()

        # ERROR и CRITICAL: храним 3 месяца (90 дней)
        cutoff_error = now - timedelta(days=90)
        LogEntry.objects.filter(
            created_at__lt=cutoff_error, level__in=['ERROR', 'CRITICAL']
        ).delete()

        # 2. Очистка кодов
        # Коды храним 3 месяца (90 дней)
        cutoff_codes = now - timedelta(days=90)
        deleted_codes, _ = Code.objects.filter(received_at__lt=cutoff_codes).delete()

        logging.info('Cleanup completed. Deleted old codes: %d', deleted_codes)

        # Если были удаления, можно запланировать бэкап (опционально)
        if deleted_codes > 0:
            BackupManager().schedule_backup()

    except Exception as e:
        logging.error('Celery task: Error in delete_old_logs_task: %s', e)


@contextmanager
def _redis_lock(lock_name, timeout):
    redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
    lock = redis_client.lock(lock_name, timeout=timeout)
    if lock.acquire(blocking=False):
        try:
            yield
        finally:
            lock.release()
    else:
        logging.debug(f'{lock_name} already in progress. Skipping.')


@shared_task
def backup_database():
    with _redis_lock('backup_lock', 300):
        BackupManager().perform_backup()


@shared_task
def backup_cookies():
    with _redis_lock('cookies_backup_lock', 60):
        BackupManager().perform_cookies_backup()


@shared_task(bind=True)
def run_admin_command(self, task_run_id):
    try:
        task_run = TaskRun.objects.get(id=task_run_id)
    except TaskRun.DoesNotExist:
        return

    task_run.status = 'RUNNING'
    task_run.celery_task_id = self.request.id
    task_run.save()

    cmd = [sys.executable, 'manage.py', task_run.command]
    if task_run.arguments:
        cmd.extend(shlex.split(task_run.arguments))

    with (
        tempfile.TemporaryFile(mode='w+') as stdout_f,
        tempfile.TemporaryFile(mode='w+') as stderr_f,
    ):
        process = subprocess.Popen(
            cmd, stdout=stdout_f, stderr=stderr_f, cwd=settings.BASE_DIR, text=True
        )

        try:
            while True:
                task_run.refresh_from_db()
                if task_run.status == 'STOPPED':
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()

                    stdout_f.seek(0)
                    stderr_f.seek(0)
                    output = stdout_f.read() + '\n' + stderr_f.read()
                    task_run.output = output + '\n\n[System] Process terminated by user request.'
                    task_run.save()
                    return

                retcode = process.poll()
                if retcode is not None:
                    stdout_f.seek(0)
                    stderr_f.seek(0)
                    out_text = stdout_f.read()
                    err_text = stderr_f.read()

                    task_run.output = (out_text + '\n' + err_text).strip()

                    if retcode == 0:
                        task_run.status = 'SUCCESS'
                    else:
                        task_run.status = 'FAILURE'
                        task_run.error_message = f'Exit code: {retcode}'

                        full_log = err_text.strip() or out_text.strip() or 'No output captured'
                        if len(full_log) > 2000:
                            log_msg = f'... [truncated] ...\n{full_log[-2000:]}'
                        else:
                            log_msg = full_log

                        logging.error(
                            f"Task '{task_run.command}' failed (code {retcode}): {log_msg}"
                        )

                    task_run.updated_at = timezone.now()
                    task_run.save()
                    return

                time.sleep(1)

        except Exception as e:
            if process.poll() is None:
                process.kill()
            task_run.status = 'FAILURE'
            task_run.error_message = f'Worker exception: {str(e)}'
            task_run.save()


@shared_task
def run_new_episodes_task():
    logging.info('Starting daily new episodes parser task.')
    try:
        call_command('runnewepisodes')
    except Exception as e:
        logging.error('Celery task: new episodes run failed: %s', e, exc_info=True)
