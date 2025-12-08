import logging
import os
import signal
import threading
import time

import imaplib2
from django.conf import settings

from app import email_processor
from app.management.base import LoggableBaseCommand

shutdown_flag = threading.Event()


def _handle_signal(signum, _):
    logging.warning('Received signal %s, shutting down email listener...', signum)
    shutdown_flag.set()


def _update_heartbeat():
    if settings.LOCAL_RUN:
        return
    try:
        with open(settings.HEARTBEAT_FILE, 'a'):
            os.utime(settings.HEARTBEAT_FILE, None)
    except Exception as e:
        logging.warning('Could not update heartbeat file: %s', e)


def _watchdog(stop_event):
    """
    Фоновый поток, который принудительно убивает процесс, если heartbeat завис.
    Это необходимо, чтобы Docker увидел падение процесса и перезапустил контейнер.
    """
    threshold = 300  # 5 минут (должно быть больше тайм-аута healthcheck)
    while not stop_event.is_set():
        time.sleep(30)
        try:
            if os.path.exists(settings.HEARTBEAT_FILE):
                stat = os.stat(settings.HEARTBEAT_FILE)
                age = time.time() - stat.st_mtime
                if age > threshold:
                    logging.error(
                        f'Watchdog: Heartbeat stuck ({age:.1f}s > {threshold}s).'
                        f' Killing process to force restart.'
                    )
                    os._exit(1)  # Принудительный выход из интерпретатора
        except Exception as e:
            logging.error(f'Watchdog error: {e}')


def run_idle_loop(mail, current_shutdown_flag):
    while not current_shutdown_flag.is_set():
        try:
            email_processor.process_emails(mail, current_shutdown_flag)
            if current_shutdown_flag.is_set():
                break
            logging.debug(
                'Entering IDLE mode. Waiting for updates for %d seconds...',
                settings.IDLE_TIMEOUT,
            )
            _update_heartbeat()
            mail.idle(timeout=settings.IDLE_TIMEOUT)
        except (imaplib2.IMAP4.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


def run_email_listener(current_shutdown_flag):
    """The main loop for the email listener, including connection and reconnect logic."""
    while not current_shutdown_flag.is_set():
        _update_heartbeat()
        try:
            with email_processor.imap_connection() as mail:
                run_idle_loop(mail, current_shutdown_flag)
        except (imaplib2.IMAP4.error, OSError) as e:
            logging.error('A critical error occurred in the email listener: %s', e)

        if not current_shutdown_flag.is_set():
            logging.info('Will attempt to reconnect in %d seconds...', settings.RECONNECT_DELAY)
            current_shutdown_flag.wait(settings.RECONNECT_DELAY)


class Command(LoggableBaseCommand):
    help = 'Runs the email listener service to process incoming 2FA codes.'

    def handle(self, *args, **options):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _handle_signal)

        threading.Thread(target=_watchdog, args=(shutdown_flag,), daemon=True).start()

        logging.info('Starting email listener with Watchdog enabled...')
        _update_heartbeat()
        run_email_listener(shutdown_flag)
        logging.info('Email listener stopped.')
