import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from threading import Event
from unittest.mock import Mock, call, patch

from django.test import TestCase, override_settings

from app.email_processor import process_emails
from app.models import Code


@override_settings(
    ALLOWED_SENDER='noreply@kinopub.test',
    IMAP_FOLDER='INBOX',
    MARK_AS_SEEN=True,
)
class EmailProcessorTests(TestCase):
    def _mail(self, uid=b'100', message_body='KinoPub code: 123456'):
        message = EmailMessage()
        message['Date'] = format_datetime(datetime.datetime.now(datetime.UTC))
        message['From'] = 'noreply@kinopub.test'
        message.set_content(message_body)

        mail = Mock()

        def uid_call(command, *args):
            if command == 'SEARCH':
                return 'OK', [uid]
            if command == 'FETCH' and args[1].startswith('(BODY.PEEK'):
                return 'OK', [(b'header', f'Date: {message["Date"]}'.encode())]
            if command == 'FETCH':
                return 'OK', [(b'header', message.as_bytes())]
            if command == 'STORE':
                return 'OK', [b'']
            raise AssertionError(f'Unexpected IMAP call: {command} {args}')

        mail.uid.side_effect = uid_call
        return mail

    @patch('app.email_processor.BackupManager')
    @patch('app.email_processor.TelegramSender')
    def test_timeout_result_is_persisted_and_email_is_not_resent(
        self, sender_class, backup_class
    ):
        sender_class.return_value.send_message.return_value = None
        mail = self._mail()

        process_emails(mail, Event())

        saved = Code.objects.get(source_uid='INBOX:100')
        self.assertEqual(saved.code, '123456')
        self.assertEqual(saved.telegram_message_id, -1)
        sender_class.return_value.send_message.assert_called_once()
        backup_class.return_value.schedule_backup.assert_called_once()
        self.assertIn(
            call('STORE', b'100', '+FLAGS', r'(\Seen)'),
            mail.uid.call_args_list,
        )

        sender_class.return_value.send_message.reset_mock()
        mail.uid.reset_mock()
        process_emails(mail, Event())

        sender_class.return_value.send_message.assert_not_called()
        self.assertEqual(Code.objects.filter(source_uid='INBOX:100').count(), 1)
        self.assertIn(
            call('STORE', b'100', '+FLAGS', r'(\Seen)'),
            mail.uid.call_args_list,
        )
