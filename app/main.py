import logging
import signal
import socket
import time
import threading
import imaplib2

import config
import database
import telegram_bot
import email_processor

shutdown_flag = threading.Event()


def _handle_signal(signum, _):
    logging.warning('Received signal %s, shutting down gracefully...', signum)
    shutdown_flag.set()


def heartbeat():
    """Updates the heartbeat file for healthcheck."""
    try:
        with open(config.HEARTBEAT_FILE, 'w') as f:
            f.write(str(int(time.time())))
    except IOError as e:
        logging.warning('Failed to update heartbeat: %s', e)


def expire_codes_periodically():
    """Periodically checks for and expires old codes."""
    while not shutdown_flag.wait(config.EXPIRATION_CHECK_INTERVAL_SECONDS):
        try:
            logging.debug('Running periodic check for expired codes...')
            expired_codes = database.get_expired_codes()
            if expired_codes:
                logging.info('Found %d expired codes to process.', len(expired_codes))
                for code_id, message_id in expired_codes:
                    telegram_bot.edit_message_to_expired(message_id)
                    database.delete_code(code_id)
        except Exception as e:
            logging.error('Error in expiration thread: %s', e)


def run_idle_loop(mail):
    """Main loop for operating in IDLE mode."""
    while not shutdown_flag.is_set():
        heartbeat()
        try:
            email_processor.process_emails(mail, shutdown_flag)
            if shutdown_flag.is_set():
                break

            logging.debug('Entering IDLE mode. Waiting for updates for %d seconds...', config.IDLE_TIMEOUT)
            mail.idle(timeout=config.IDLE_TIMEOUT)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


def main_loop():
    """Main loop managing the connection and threads."""
    logging.info('Starting bot...')
    config.validate_config()
    database.init_db()

    expiration_thread = threading.Thread(target=expire_codes_periodically, daemon=True)
    expiration_thread.start()

    while not shutdown_flag.is_set():
        try:
            with email_processor.imap_connection() as mail:
                run_idle_loop(mail)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.error('A critical error occurred in the main loop: %s', e)

        if not shutdown_flag.is_set():
            logging.info('Will attempt to reconnect in %d seconds...', config.RECONNECT_DELAY)
            shutdown_flag.wait(config.RECONNECT_DELAY)

    logging.info('Bot stopped.')


if __name__ == '__main__':
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)
    main_loop()
