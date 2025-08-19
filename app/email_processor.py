import email
import email.utils
import re
import logging
import socket
import imaplib2
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

import config
import database
import telegram_bot


@contextmanager
def imap_connection():
    """Context manager for IMAP connection using imaplib2."""
    mail = None
    try:
        mail = imaplib2.IMAP4_SSL(config.IMAP_HOST, timeout=config.IMAP_TIMEOUT)
        mail.login(config.GMAIL_EMAIL, config.GMAIL_PASSWORD)
        mail.select(config.IMAP_FOLDER, readonly=not config.MARK_AS_SEEN)
        logging.info('IMAP connection established, folder %s selected.', config.IMAP_FOLDER)
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


def get_message_body(email_msg) -> str:
    """Returns the message body: prefers text/html if available, otherwise text/plain."""
    if email_msg.is_multipart():
        plain_body = None
        html_body = None
        for part in email_msg.walk():
            ctype = part.get_content_type()
            if ctype in ('text/plain', 'text/html'):
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    text = payload.decode(charset, errors='ignore')
                except (UnicodeDecodeError, AttributeError):
                    text = ''

                if ctype == 'text/plain' and not plain_body:
                    plain_body = text
                elif ctype == 'text/html' and not html_body:
                    html_body = text
        return html_body or plain_body or ''
    else:
        try:
            payload = email_msg.get_payload(decode=True)
            return payload.decode(email_msg.get_content_charset() or 'utf-8', errors='ignore')
        except (UnicodeDecodeError, AttributeError):
            return ''


def process_emails(mail, shutdown_flag):
    """Searches and processes all unread emails."""
    try:
        status, data = mail.uid('SEARCH', None, 'UNSEEN', 'FROM', f'"{config.ALLOWED_SENDER}"')
        if status != 'OK':
            logging.error('Failed to search for unseen emails from %s.', config.ALLOWED_SENDER)
            return
        unseen_uids = data[0].split()
        if not unseen_uids:
            logging.debug('No new messages from %s.', config.ALLOWED_SENDER)
            return

        logging.info('Found %d unseen message(s) from %s.', len(unseen_uids), config.ALLOWED_SENDER)
        for uid in unseen_uids:
            if shutdown_flag.is_set():
                break

            status, msg_data = mail.uid('FETCH', uid, '(BODY.PEEK[HEADER.FIELDS (DATE)])')
            received_at = datetime.now(timezone.utc).isoformat()
            if status == 'OK' and msg_data and msg_data[0]:
                date_header = msg_data[0][1].decode('utf-8').split(':', 1)[1].strip()
                date_tuple = email.utils.parsedate_tz(date_header)
                if date_tuple:
                    tz_offset_seconds = date_tuple[9] or 0
                    tz = timezone(timedelta(seconds=tz_offset_seconds))
                    dt_aware = datetime(*date_tuple[:6], tzinfo=tz)
                    received_at = dt_aware.astimezone(timezone.utc).isoformat()
            else:
                logging.warning('Could not fetch date for uid=%s. Using current time.', uid)

            status, msg_data = mail.uid('FETCH', uid, '(RFC822)')
            if status != 'OK' or not msg_data or not msg_data[0]:
                logging.warning('Could not fetch full message for uid=%s. Skipping.', uid)
                continue

            email_msg = email.message_from_bytes(msg_data[0][1])
            body = get_message_body(email_msg)
            if not body:
                logging.warning('Empty body extracted (uid=%s). Will not mark as seen.', uid)
                continue

            code_match = re.search(config.REGEX_CODE, body)
            if code_match:
                code = code_match.group(0)
                logging.info('Found code %s in email (uid=%s)', code, uid)

                message_id = telegram_bot.send_message(code)
                if message_id:
                    database.add_code(code, message_id, received_at)
                    if config.MARK_AS_SEEN:
                        mail.uid('STORE', uid, '+FLAGS', r'(\Seen)')
            else:
                logging.info('No 6-digit code found in message (uid=%s). Leaving UNSEEN.', uid)

    except (imaplib2.IMAP4.error, socket.error, OSError) as e:
        logging.error('Error processing emails: %s', e)
        raise
