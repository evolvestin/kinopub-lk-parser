import functools
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
from app.models import Code, LogEntry, Show, TaskRun
from app.services.error_aggregator import ErrorAggregator
from app.telegram_bot import TelegramSender


@contextmanager
def _redis_lock(lock_name, timeout):
    redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
    lock = redis_client.lock(lock_name, timeout=timeout)
    acquired = lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.release()
            except Exception as e:
                logging.warning(f'Failed to release lock {lock_name}: {e}')


def single_instance_task(lock_name, timeout):
    """Декоратор для задач, требующих блокировки для предотвращения параллельного запуска."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with _redis_lock(lock_name, timeout) as acquired:
                if not acquired:
                    logging.warning(f'Skipping task {func.__name__}: Resource {lock_name} is busy.')
                    return
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.error(f'Celery task {func.__name__} failed: {e}', exc_info=True)

        return wrapper

    return decorator


def safe_execution(func):
    """Декоратор для безопасного выполнения задач с логированием ошибок."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f'Celery task: {func.__name__} failed: {e}', exc_info=True)

    return wrapper


@shared_task
@single_instance_task(lock_name='selenium_global_lock', timeout=7200)
def run_history_parser_task():
    logging.info('Starting periodic history parser task.')
    history_parser.run_parser_session()


@shared_task
@safe_execution
def run_full_scan_task():
    logging.info('Starting quarterly full scan task.')
    call_command('runfullscan')


@shared_task
@safe_execution
def expire_codes_task():
    logging.debug('Running periodic check for expired codes...')
    expiration_threshold = timezone.now() - timedelta(minutes=settings.CODE_LIFETIME_MINUTES)

    expired_codes = list(
        Code.objects.filter(received_at__lt=expiration_threshold).exclude(telegram_message_id=-1)
    )

    if expired_codes:
        logging.info('Found %d expired codes to mark in Telegram.', len(expired_codes))

        telegram_ids = [c.telegram_message_id for c in expired_codes]
        sender = TelegramSender()
        for telegram_id in telegram_ids:
            sender.edit_message_to_expired(telegram_id)

        Code.objects.filter(id__in=[c.id for c in expired_codes]).update(telegram_message_id=-1)

        BackupManager().schedule_backup()


@shared_task
@safe_execution
def delete_old_logs_task():
    logging.info('Running periodic cleanup of logs and data...')
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
    LogEntry.objects.filter(created_at__lt=cutoff_error, level__in=['ERROR', 'CRITICAL']).delete()

    # 2. Очистка кодов
    # Коды храним 3 месяца (90 дней)
    cutoff_codes = now - timedelta(days=90)
    deleted_codes, _ = Code.objects.filter(received_at__lt=cutoff_codes).delete()

    logging.info('Cleanup completed. Deleted old codes: %d', deleted_codes)

    # Если были удаления, можно запланировать бэкап (опционально)
    if deleted_codes > 0:
        BackupManager().schedule_backup()


@shared_task
@single_instance_task(lock_name='backup_lock', timeout=300)
def backup_database():
    BackupManager().perform_backup()


@shared_task
@single_instance_task(lock_name='cookies_backup_lock', timeout=60)
def backup_cookies():
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

                        if len(full_log) > 10000:
                            log_msg = (
                                f'{full_log[:5000]}\n... [middle truncated] ...\n{full_log[-5000:]}'
                            )
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
            logging.error(
                f'Internal error executing command {task_run.command}: {e}', exc_info=True
            )
            task_run.status = 'FAILURE'
            task_run.error_message = f'Worker exception: {str(e)}'
            task_run.save()


@shared_task
@single_instance_task(lock_name='selenium_global_lock', timeout=3600)
def run_new_episodes_task():
    logging.info('Starting daily new episodes parser task.')
    call_command('runnewepisodes')


@shared_task
@single_instance_task(lock_name='selenium_global_lock', timeout=14400)
def run_daily_sync_task():
    logging.info('Starting Daily Synchronization Task via Celery.')
    call_command('rundailysync')


def _process_batch_from_queue(queue_name, session_type, process_func, batch_size=50):
    """
    Универсальная функция для обработки пакета ID из Redis очереди.
    """
    redis_client = Redis.from_url(settings.CELERY_BROKER_URL)

    count = redis_client.scard(queue_name)
    if count == 0:
        return

    logging.info(f'Found {count} items in {queue_name}. Starting batch processing...')

    raw_ids = redis_client.spop(queue_name, count=batch_size)
    if not raw_ids:
        return

    show_ids = [int(id_bytes) for id_bytes in raw_ids]
    logging.info(f'Processing batch of {len(show_ids)} shows: {show_ids}')

    driver = history_parser.initialize_driver_session(headless=True, session_type=session_type)
    if not driver:
        logging.error('Failed to init driver. Returning items to queue.')
        redis_client.sadd(queue_name, *show_ids)
        return

    processed_count = 0
    try:
        for show_id in show_ids:
            try:
                _ = driver.current_url

                if session_type == 'aux':
                    process_func(driver, show_id)
                else:
                    try:
                        show = Show.objects.get(id=show_id)
                        process_func(driver, show)
                    except Show.DoesNotExist:
                        logging.warning(f'Show {show_id} not found in DB, skipping.')
                        continue

                processed_count += 1
            except Exception as e:
                logging.error(f'Error processing show {show_id} in batch: {e}')
                if history_parser.is_fatal_selenium_error(e):
                    logging.critical('Fatal driver error. Stopping batch.')
                    break

        if processed_count > 0:
            logging.info(f'Batch finished. Processed {processed_count}/{len(show_ids)} items.')
            BackupManager().schedule_backup()

    finally:
        history_parser.close_driver(driver)


@shared_task
@single_instance_task(lock_name='selenium_global_lock', timeout=3600)
def process_queues_task():
    """
    Объединенная задача для последовательной обработки очередей Redis.
    Сначала обрабатывает детали (aux аккаунт), затем длительности (main аккаунт).
    """
    logging.info('Starting Unified Queue Processing Task.')

    # 1. Processing Details (Aux account)
    try:
        _process_batch_from_queue(
            queue_name='queue:update_details',
            session_type='aux',
            process_func=history_parser.update_show_details,
        )
    except Exception as e:
        logging.error(f'Error during details processing phase: {e}', exc_info=True)

    # Небольшая пауза между сессиями для очистки ресурсов
    time.sleep(5)

    # 2. Processing Durations (Main account)
    try:
        _process_batch_from_queue(
            queue_name='queue:update_durations',
            session_type='main',
            process_func=history_parser.process_show_durations,
        )
    except Exception as e:
        logging.error(f'Error during durations processing phase: {e}', exc_info=True)

    logging.info('Unified Queue Processing Task Finished.')


@shared_task
@safe_execution
def process_error_queue_task():
    """
    Периодическая задача для отправки накопленных ошибок в Telegram.
    Срабатывает раз в N минут (настраивается в агрегаторе), но запускается
    планировщиком чаще для проверки готовности.
    """

    aggregator = ErrorAggregator()
    batch = aggregator.get_batch_to_send()

    if batch:
        logging.info(f'Sending batch of {len(batch)} errors to Telegram.')
        TelegramSender().send_batch_logs(batch)
