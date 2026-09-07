import datetime
import datetime
import email
import logging
import re
from contextlib import contextmanager
from email.utils import parsedate_to_datetime

import imaplib2
from django.conf import settings
from django.utils import timezone

from app.gdrive_backup import BackupManager
from app.models import Code
from app.telegram_bot import TelegramSender
from shared.html_helper import code


@contextmanager
def imap_connection():
    """Context manager for IMAP connection using imaplib2."""
    mail = None
    try:
        mail = imaplib2.IMAP4_SSL(settings.IMAP_HOST, timeout=settings.IMAP_TIMEOUT)
        mail.login(settings.GMAIL_EMAIL, settings.GMAIL_PASSWORD)
        mail.select(settings.IMAP_FOLDER, readonly=not settings.MARK_AS_SEEN)
        logging.info('IMAP connection established, folder %s selected.', settings.IMAP_FOLDER)
        yield mail
    except (imaplib2.IMAP4.error, OSError) as e:
        logging.error('IMAP connection error: %s', e)
        raise
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
                logging.info('IMAP connection closed.')
            except (imaplib2.IMAP4.error, OSError):
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


def _source_uid(uid) -> str:
    """Return a stable database key for an email in the selected IMAP folder."""
    if isinstance(uid, bytes):
        uid = uid.decode('ascii', errors='replace')
    return f'{settings.IMAP_FOLDER}:{uid}'


def _mark_seen(mail, uid):
    if not settings.MARK_AS_SEEN:
        return
    status, _ = mail.uid('STORE', uid, '+FLAGS', r'(\Seen)')
    if status != 'OK':
        logging.warning('Could not mark email uid=%s as seen.', uid)


def process_emails(mail, shutdown_flag):
    try:
        status, data = mail.uid('SEARCH', None, 'UNSEEN', 'FROM', f'"{settings.ALLOWED_SENDER}"')
        if status != 'OK':
            logging.error('Failed to search for unseen emails from %s.', settings.ALLOWED_SENDER)
            return
        unseen_uids = data[0].split()
        if not unseen_uids:
            logging.debug('No new messages from %s.', settings.ALLOWED_SENDER)
            return

        logging.info(
            'Found %d unseen message(s) from %s.',
            len(unseen_uids),
            settings.ALLOWED_SENDER,
        )
        for uid in unseen_uids:
            if shutdown_flag.is_set():
                break

            status, msg_data = mail.uid('FETCH', uid, '(BODY.PEEK[HEADER.FIELDS (DATE)])')
            received_at_dt = timezone.now()

            if status == 'OK' and msg_data and isinstance(msg_data[0], tuple):
                try:
                    date_header = msg_data[0][1].decode('utf-8').split(':', 1)[1].strip()
                    dt = parsedate_to_datetime(date_header)
                    received_at_dt = dt.astimezone(datetime.UTC)
                except (ValueError, TypeError, IndexError, AttributeError) as e:
                    logging.warning(
                        'Could not parse date for uid=%s (%s). Using current time.', uid, e
                    )
            else:
                logging.warning('Could not fetch date for uid=%s. Using current time.', uid)

            status, msg_data = mail.uid('FETCH', uid, '(RFC822)')
            if status != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
                logging.warning('Could not fetch full message for uid=%s. Skipping.', uid)
                continue

            email_msg = email.message_from_bytes(msg_data[0][1])
            body = get_message_body(email_msg)
            if not body:
                logging.warning('Empty body extracted (uid=%s). Will not mark as seen.', uid)
                continue

            code_match = re.search(settings.REGEX_CODE, body)
            if code_match:
                code_str = code_match.group(0)
                source_uid = _source_uid(uid)
                code_obj, created = Code.objects.get_or_create(
                    source_uid=source_uid,
                    defaults={
                        'code': code_str,
                        # The parser must be able to use the code even when
                        # Telegram's response is lost after delivery.
                        'telegram_message_id': -1,
                        'received_at': received_at_dt,
                    },
                )
                if not created:
                    logging.info(
                        'Code email uid=%s was already processed (code id=%s); '
                        'marking it seen without resending.',
                        uid,
                        code_obj.id,
                    )
                    _mark_seen(mail, uid)
                    continue

                logging.info('Found code %s in email (uid=%s)', code_str, uid)
                message_id = None
                try:
                    message_id = TelegramSender().send_message(code(code_str))
                except Exception as exc:
                    # The code is already durable and available to the
                    # parser.  Do not leave the email unseen: a timeout can
                    # mean Telegram accepted the message already.
                    logging.error(
                        'Telegram delivery failed for code id=%s, keeping the code for the '
                        'parser without retrying the email: %s',
                        code_obj.id,
                        exc,
                    )

                if message_id:
                    Code.objects.filter(pk=code_obj.pk).update(telegram_message_id=message_id)
                    logging.info(
                        'Code %s (msg_id: %d) added to the database.', code_str, message_id
                    )
                else:
                    logging.warning(
                        'Telegram message id was not returned for code id=%s; '
                        'the code remains available to KinoPub and will not be resent.',
                        code_obj.id,
                    )
                BackupManager().schedule_backup()
                _mark_seen(mail, uid)
            else:
                logging.info('No 6-digit code found in message (uid=%s). Marking as seen.', uid)
                _mark_seen(mail, uid)

    except (imaplib2.IMAP4.error, OSError) as e:
        logging.error('Error processing emails: %s', e)
        raise
