import json
from datetime import date
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from app.models import Show, ViewHistory, ViewUser, ViewUserGroup
from app.views import bot_unassign_group_view


@override_settings(BOT_TOKEN='test-bot-token')
class BotViewAssignmentTests(TestCase):
    def test_unassign_group_removes_all_assigned_group_members(self):
        owner = ViewUser.objects.create(telegram_id=101, name='Alice')
        member = ViewUser.objects.create(telegram_id=102, name='Bob')
        group = ViewUserGroup.objects.create(name='Team')
        group.users.add(owner, member)
        show = Show.objects.create(title='A title', original_title='A title', type='movie')
        view = ViewHistory.objects.create(show=show, view_date=date(2026, 9, 28))
        view.users.add(owner, member)

        request = RequestFactory().post(
            '/api/bot/unassign_group_view/',
            data=json.dumps(
                {'telegram_id': owner.telegram_id, 'group_id': group.id, 'view_id': view.id}
            ),
            content_type='application/json',
            HTTP_X_BOT_TOKEN='test-bot-token',
        )

        with patch('app.views.TelegramSender.update_history_message'):
            response = bot_unassign_group_view(request)

        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['removed_count'], 2)
        self.assertEqual(response_data['remaining_user_ids'], [])
        self.assertFalse(view.users.exists())
