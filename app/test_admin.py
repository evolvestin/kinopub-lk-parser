from django.test import TestCase
from django.test.client import RequestFactory

from app.admin import TelegramLogAdmin, TelegramLogChatIdFilter
from app.admin_site import admin_site
from app.models import TelegramLog


class TelegramLogAdminTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/admin/app/telegramlog/')
        self.model_admin = TelegramLogAdmin(TelegramLog, admin_site)
        TelegramLog.objects.create(
            raw_data={'message': {'chat': {'id': -100123}, 'message_id': 77}}
        )
        TelegramLog.objects.create(raw_data={'message': {'text': 'without chat'}})

    def test_json_ids_are_cast_to_strings_in_admin_queryset(self):
        queryset = self.model_admin.get_queryset(self.request)

        self.assertEqual(
            queryset.filter(_chat_id_sort='-100123').values_list(
                '_chat_id_sort', '_message_id_sort'
            ).get(),
            ('-100123', '77'),
        )

    def test_chat_id_filter_uses_the_annotated_string_value(self):
        queryset = self.model_admin.get_queryset(self.request)
        chat_filter = TelegramLogChatIdFilter(
            self.request, {'chat_id': ['-100123']}, TelegramLog, self.model_admin
        )

        self.assertEqual(chat_filter.value(), '-100123')
        self.assertEqual(chat_filter.queryset(self.request, queryset).count(), 1)
