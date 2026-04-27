import logging
import os
import signal
import threading
import time

import imaplib2
from django.conf import settings

from app import email_processor
from app.management.base import LoggableBaseCommand
from app.utils import update_heartbeat

shutdown_flag = threading.Event()


def _handle_signal(signum, _):
    logging.warning('Received signal %s, shutting down email listener...', signum)
    shutdown_flag.set()


def _watchdog(stop_event):
    threshold = 300
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
                    os._exit(1)
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
            update_heartbeat()
            mail.idle(timeout=settings.IDLE_TIMEOUT)
        except (imaplib2.IMAP4.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


def run_email_listener(current_shutdown_flag):
    while not current_shutdown_flag.is_set():
        update_heartbeat()
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
        update_heartbeat()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _handle_signal)

        if settings.DEBUG:
            logging.info('DEBUG mode detected. Email listener disabled (idling).')
            update_heartbeat()
            while not shutdown_flag.is_set():
                shutdown_flag.wait(30)
                update_heartbeat()
            return

        threading.Thread(target=_watchdog, args=(shutdown_flag,), daemon=True).start()

        logging.info('Starting email listener with Watchdog enabled...')
        update_heartbeat()
        run_email_listener(shutdown_flag)
        logging.info('Email listener stopped.')
