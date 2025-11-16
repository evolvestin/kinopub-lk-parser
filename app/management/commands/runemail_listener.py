import logging
import signal
import socket
import threading
import imaplib2

from django.core.management.base import BaseCommand
from django.conf import settings
from app import email_processor

shutdown_flag = threading.Event()


def _handle_signal(signum, _):
    logging.warning('Received signal %s, shutting down email listener...', signum)
    shutdown_flag.set()


def run_idle_loop(mail):
    while not shutdown_flag.is_set():
        try:
            email_processor.process_emails(mail, shutdown_flag)
            if shutdown_flag.is_set():
                break
            logging.debug('Entering IDLE mode. Waiting for updates for %d seconds...', settings.IDLE_TIMEOUT)
            mail.idle(timeout=settings.IDLE_TIMEOUT)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


class Command(BaseCommand):
    help = 'Runs the email listener service to process incoming 2FA codes.'

    def handle(self, *args, **options):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _handle_signal)

        self.stdout.write("Starting email listener...")
        while not shutdown_flag.is_set():
            try:
                with email_processor.imap_connection() as mail:
                    run_idle_loop(mail)
            except (imaplib2.IMAP4.error, socket.error, OSError) as e:
                logging.error('A critical error occurred in the email listener: %s', e)

            if not shutdown_flag.is_set():
                logging.info('Will attempt to reconnect in %d seconds...', settings.RECONNECT_DELAY)
                shutdown_flag.wait(settings.RECONNECT_DELAY)

        self.stdout.write("Email listener stopped.")