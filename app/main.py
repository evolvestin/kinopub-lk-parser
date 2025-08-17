import imaplib2
import email.utils
import re
import time
import requests
import logging
import os
import signal
import socket
from contextlib import contextmanager

GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
ALLOWED_SENDER = os.getenv('ALLOWED_SENDER')

IMAP_HOST = 'imap.gmail.com'
IMAP_FOLDER = 'INBOX'
REGEX_CODE = r'\d{6}'
MARK_AS_SEEN = True
HEARTBEAT_FILE = os.getenv('HEARTBEAT_FILE', '/tmp/kinopub-parser_heartbeat')

REQUEST_TIMEOUT = 10
IMAP_TIMEOUT = 30
IDLE_TIMEOUT = 24 * 60
MAX_RETRIES = 5
RECONNECT_DELAY = 15

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

shutdown_flag = False


def _handle_signal(signum, _):
    global shutdown_flag
    logging.warning('Received signal %s, shutting down gracefully...', signum)
    shutdown_flag = True


for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _handle_signal)


def validate_config():
    """Validates the presence of all required environment variables."""
    missing = [key for key in ('GMAIL_EMAIL', 'GMAIL_PASSWORD', 'BOT_TOKEN', 'CHAT_ID', 'ALLOWED_SENDER') if
               not globals()[key]]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def heartbeat():
    """Updates the heartbeat file for healthcheck."""
    try:
        with open(HEARTBEAT_FILE, 'w') as f:
            f.write(str(int(time.time())))
    except IOError as e:
        logging.warning('Failed to update heartbeat: %s', e)


def send_to_telegram(message: str) -> None:
    """Sends a message to Telegram with retries."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error('BOT_TOKEN or CHAT_ID is not set.')
        return
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {'chat_id': CHAT_ID, 'text': message}
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            logging.info('Sent to Telegram: %s', message)
            return
        except requests.RequestException as e:
            logging.error('Telegram send error (attempt %d/%d): %s', attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    logging.error('Failed to send to Telegram after %d retries.', MAX_RETRIES)


@contextmanager
def imap_connection():
    """Context manager for IMAP connection using imaplib2."""
    mail = None
    try:
        mail = imaplib2.IMAP4_SSL(IMAP_HOST, timeout=IMAP_TIMEOUT)
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select(IMAP_FOLDER, readonly=not MARK_AS_SEEN)
        logging.info('IMAP connection established, folder %s selected.', IMAP_FOLDER)
        yield mail
    except (imaplib2.IMAP4.error, socket.error, OSError) as e:
        logging.error('IMAP connection error: %s', e)
        raise
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
                logging.info('IMAP connection closed.')
            except (imaplib2.IMAP4.error, socket.error, OSError):
                pass


def process_emails(mail):
    """Searches and processes all unread emails."""
    try:
        search_criteria = f'(UNSEEN FROM "{ALLOWED_SENDER}")'
        status, data = mail.search(None, search_criteria)
        if status != 'OK':
            logging.error('Failed to search for unseen emails from %s.', ALLOWED_SENDER)
            return
        unseen_uids = data[0].split()
        if not unseen_uids:
            logging.debug('No new messages from %s.', ALLOWED_SENDER)
            return

        logging.info('Found %d unseen message(s) from %s.', len(unseen_uids), ALLOWED_SENDER)
        for uid in unseen_uids:
            if shutdown_flag:
                break
            _, msg_data = mail.fetch(uid, '(RFC822)')
            if not msg_data or not msg_data[0] or not isinstance(msg_data[0], tuple):
                continue

            email_msg = email.message_from_bytes(msg_data[0][1])
            sender = email.utils.parseaddr(email_msg.get('From'))[1] or 'Unknown Sender'

            if sender != ALLOWED_SENDER:
                logging.warning("Found a message not from the allowed sender, skipping. Sender: %s", sender)
                continue

            body = ''
            if email_msg.is_multipart():
                for part in email_msg.walk():
                    if part.get_content_type() == 'text/plain':
                        try:
                            body = part.get_payload(decode=True).decode(errors='ignore')
                            break
                        except (UnicodeDecodeError, AttributeError):
                            continue
            else:
                try:
                    body = email_msg.get_payload(decode=True).decode(errors='ignore')
                except (UnicodeDecodeError, AttributeError):
                    body = ''

            code_match = re.search(REGEX_CODE, body)
            if code_match:
                code = code_match.group(0)
                logging.info('Found code %s in email from %s', code, sender)
                send_to_telegram(code)

            if MARK_AS_SEEN:
                mail.store(uid, '+FLAGS', '\\Seen')
    except (imaplib2.IMAP4.error, socket.error, OSError) as e:
        logging.error('Error processing emails: %s', e)
        raise


def run_idle_loop(mail):
    """Main loop for operating in IDLE mode using imaplib2."""
    while not shutdown_flag:
        heartbeat()
        try:
            process_emails(mail)
            if shutdown_flag:
                break

            logging.debug('Entering IDLE mode. Waiting for updates for %d seconds...', IDLE_TIMEOUT)
            responses = mail.idle(timeout=IDLE_TIMEOUT)
            logging.debug('Received response from IDLE: %s', responses)

            status, _ = mail.noop()
            if status != 'OK':
                logging.warning('NOOP command failed. Connection might be stale.')
                break

        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.warning('Connection lost in IDLE mode. Reconnecting. Error: %s', e)
            break


def main_loop():
    """Main loop managing the connection."""
    logging.info('Starting bot...')
    validate_config()

    while not shutdown_flag:
        try:
            with imap_connection() as mail:
                run_idle_loop(mail)
        except (imaplib2.IMAP4.error, socket.error, OSError) as e:
            logging.error('A critical error occurred in the main loop: %s', e)

        if not shutdown_flag:
            logging.info('Will attempt to reconnect in %d seconds...', RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)

    logging.info('Bot stopped.')


if __name__ == '__main__':
    main_loop()
