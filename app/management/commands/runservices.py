import logging
import signal
import socket
import time
import threading
import imaplib2
from datetime import datetime, timedelta, timezone, date

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

from app import email_processor, history_parser, telegram_bot
from app.gdrive_backup import BackupManager
from app.models import Code, LogEntry

shutdown_flag = threading.Event()
QUARTERLY_SCAN_DATES = {(1, 1), (4, 1), (7, 1), (10, 1)}
last_scan_trigger_date = None


def _handle_signal(signum, _):
    logging.warning('Received signal %s, shutting down gracefully...', signum)
    BackupManager().stop()
    shutdown_flag.set()


def heartbeat():
    try:
        with open(settings.HEARTBEAT_FILE, 'w') as f:
            f.write(str(int(time.time())))
    except IOError as e:
        logging.warning('Failed to update heartbeat: %s', e)


def expire_codes_periodically():
    while not shutdown_flag.wait(settings.EXPIRATION_CHECK_INTERVAL_SECONDS):
        try:
            logging.debug('Running periodic check for expired codes...')
            expiration_threshold = datetime.now(timezone.utc) - timedelta(minutes=settings.CODE_LIFETIME_MINUTES)
            expired_codes = Code.objects.filter(received_at__lt=expiration_threshold)
            if expired_codes.exists():
                logging.info('Found %d expired codes to process.', expired_codes.count())
                for code in expired_codes:
                    telegram_bot.edit_message_to_expired(code.telegram_message_id)
                    code.delete()
                    BackupManager().schedule_backup()
        except Exception as e:
            logging.error('Error in expiration thread: %s', e)


def delete_old_logs_periodically():
    interval_seconds = settings.LOG_DELETION_INTERVAL_HOURS * 3600
    while not shutdown_flag.wait(interval_seconds):
        try:
            logging.info('Running periodic check for old log entries...')
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.LOG_RETENTION_DAYS)
            deleted_count, _ = LogEntry.objects.filter(timestamp__lt=cutoff_date).delete()
            if deleted_count > 0:
                logging.info('Deleted %d old log entries.', deleted_count)
        except Exception as e:
            logging.error('Error in log deletion thread: %s', e)


def run_history_parser_periodically():
    logging.info(
        'History parser thread started. Will run every %d hours.',
        settings.HISTORY_PARSER_INTERVAL_HOURS
    )
    try:
        history_parser.run_parser_session()
    except Exception as e:
        logging.error('Initial history parser run failed: %s', e, exc_info=True)

    interval_seconds = settings.HISTORY_PARSER_INTERVAL_HOURS * 3600
    while not shutdown_flag.wait(interval_seconds):
        try:
            history_parser.run_parser_session()
        except Exception as e:
            logging.error('Periodic history parser run failed: %s', e, exc_info=True)


def run_full_scan_periodically():
    global last_scan_trigger_date
    logging.info('Quarterly catalog scanner thread started.')

    while not shutdown_flag.wait(3600):
        try:
            today = date.today()
            current_date_tuple = (today.month, today.day)

            if current_date_tuple in QUARTERLY_SCAN_DATES and today != last_scan_trigger_date:
                logging.info(
                    'Scheduled date %s reached. Starting full catalog scan.',
                    today.strftime('%Y-%m-%d')
                )
                call_command('runfullscan')
                last_scan_trigger_date = today
                logging.info('Full catalog scan command finished.')
        except Exception as e:
            logging.error('An error occurred in the quarterly scanner thread: %s', e, exc_info=True)


def run_idle_loop(mail):
    while not shutdown_flag.is_set():
        heartbeat()
        try:
            email_processor.process_emails(mail, shutdown_flag)
            if shutdown_flag.is_set():
                break
            logging.debug('Entering IDLE mode. Waiting for updates for %d seconds...', settings.IDLE_TIMEOUT)
            mail.idle(timeout=settings.IDLE_TIMEOUT)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


def run_email_listener(shutdown_event: threading.Event):
    while not shutdown_event.is_set():
        try:
            with email_processor.imap_connection() as mail:
                run_idle_loop(mail)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.error('A critical error occurred in the email listener: %s', e)
        if not shutdown_event.is_set():
            logging.info('Will attempt to reconnect in %d seconds...', settings.RECONNECT_DELAY)
            shutdown_event.wait(settings.RECONNECT_DELAY)


class Command(BaseCommand):
    help = 'Runs the main application loop with all background services.'

    def handle(self, *args, **options):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _handle_signal)

        logging.info('Starting background services...')
        BackupManager().start()

        threading.Thread(target=expire_codes_periodically, daemon=True, name='CodeExpirationThread').start()
        threading.Thread(target=delete_old_logs_periodically, daemon=True, name='LogDeletionThread').start()
        threading.Thread(target=run_history_parser_periodically, daemon=True, name='HistoryParserThread').start()
        threading.Thread(target=run_full_scan_periodically, daemon=True, name='FullScanThread').start()
        threading.Thread(
            target=run_email_listener,
            args=(shutdown_flag,),
            daemon=True,
            name='EmailListenerThread'
        ).start()

        try:
            while not shutdown_flag.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            _handle_signal('SIGINT', None)

        logging.info('Application stopped.')
