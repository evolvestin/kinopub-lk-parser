import logging
import signal
import socket
import threading

import imaplib2
from django.conf import settings
from django.core.management.base import BaseCommand

from app import email_processor

shutdown_flag = threading.Event()


def _handle_signal(signum, _):
    logging.warning('Received signal %s, shutting down email listener...', signum)
    shutdown_flag.set()


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
            mail.idle(timeout=settings.IDLE_TIMEOUT)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


def run_email_listener(current_shutdown_flag):
    """The main loop for the email listener, including connection and reconnect logic."""
    while not current_shutdown_flag.is_set():
        try:
            with email_processor.imap_connection() as mail:
                run_idle_loop(mail, current_shutdown_flag)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.error('A critical error occurred in the email listener: %s', e)

        if not current_shutdown_flag.is_set():
            logging.info('Will attempt to reconnect in %d seconds...', settings.RECONNECT_DELAY)
            current_shutdown_flag.wait(settings.RECONNECT_DELAY)


class Command(BaseCommand):
    help = 'Runs the email listener service to process incoming 2FA codes.'

    def handle(self, *args, **options):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _handle_signal)

        logging.info('Starting email listener...')
        run_email_listener(shutdown_flag)
        logging.info('Email listener stopped.')
