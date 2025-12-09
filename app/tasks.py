import logging
import shlex
import subprocess
import sys
import tempfile
import time
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
        expired_codes = Code.objects.filter(received_at__lt=expiration_threshold)
        if expired_codes.exists():
            logging.info('Found %d expired codes to process.', expired_codes.count())
            for code in expired_codes:
                TelegramSender().edit_message_to_expired(code.telegram_message_id)
                code.delete()
            BackupManager().schedule_backup()
    except Exception as e:
        logging.error('Celery task: Error in expire_codes_task: %s', e)


@shared_task
def delete_old_logs_task():
    logging.info('Running periodic check for old log entries...')
    try:
        cutoff_date = timezone.now() - timedelta(days=settings.LOG_RETENTION_DAYS)
        deleted_count, _ = (
            LogEntry.objects.filter(created_at__lt=cutoff_date)
            .exclude(message__contains='New Episodes Parser Finished')
            .delete()
        )
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
    except TaskRun.DoesNotExist:
        return

    task_run.status = 'RUNNING'
    task_run.celery_task_id = self.request.id
    task_run.save()

    # Формируем команду запуска через manage.py в отдельном процессе
    cmd = [sys.executable, 'manage.py', task_run.command]
    if task_run.arguments:
        cmd.extend(shlex.split(task_run.arguments))

    # Используем временные файлы для буферизации вывода, чтобы не зависеть от переполнения пайпов
    with (
        tempfile.TemporaryFile(mode='w+') as stdout_f,
        tempfile.TemporaryFile(mode='w+') as stderr_f,
    ):
        process = subprocess.Popen(
            cmd, stdout=stdout_f, stderr=stderr_f, cwd=settings.BASE_DIR, text=True
        )

        try:
            while True:
                # 1. Проверяем, не попросил ли пользователь остановить задачу
                task_run.refresh_from_db()
                if task_run.status == 'STOPPED':
                    process.terminate()  # Посылаем SIGTERM (мягкая остановка)
                    try:
                        process.wait(timeout=10)  # Даем 10 сек на завершение (cleanup)
                    except subprocess.TimeoutExpired:
                        process.kill()  # SIGKILL, если завис

                    # Сохраняем логи
                    stdout_f.seek(0)
                    stderr_f.seek(0)
                    output = stdout_f.read() + '\n' + stderr_f.read()
                    task_run.output = output + '\n\n[System] Process terminated by user request.'
                    task_run.save()
                    return

                # 2. Проверяем, не завершился ли процесс сам
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
                        
                        # Дублируем ошибку в системный лог, чтобы её было видно в Dashboard
                        log_msg = err_text.strip() or out_text.strip() or 'No output captured'
                        logging.error(f"Task '{task_run.command}' failed (code {retcode}): {log_msg}")

                    task_run.updated_at = timezone.now()
                    task_run.save()
                    return

                # Пауза перед следующей проверкой
                time.sleep(1)

        except Exception as e:
            # Если что-то пошло не так в самом воркере, убиваем процесс
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
