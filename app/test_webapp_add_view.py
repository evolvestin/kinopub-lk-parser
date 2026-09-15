import json
from datetime import date
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from app.models import Show, ViewHistory, ViewUser, ViewUserGroup
from app.views import webapp_add_view


class WebappAddViewTests(TestCase):
    def setUp(self):
        self.owner = ViewUser.objects.create(telegram_id=101, name='Alice')
        self.member = ViewUser.objects.create(telegram_id=102, name='Bob')
        self.group = ViewUserGroup.objects.create(name='Team')
        self.group.users.add(self.owner, self.member)
        self.show = Show.objects.create(title='A title', original_title='A title', type='movie')

    @patch('app.views.send_view_confirmation_task.delay')
    @patch('app.views.get_webapp_user')
    def test_add_view_with_group_adds_all_group_members(self, get_user, _send_confirmation):
        get_user.return_value = self.owner
        request = RequestFactory().post(
            '/api/webapp/add_view/',
            data=json.dumps(
                {
                    'show_id': self.show.id,
                    'season': 0,
                    'episode': 0,
                    'date_mode': 'exact',
                    'date_val': date(2026, 9, 15).isoformat(),
                    'target_me': False,
                    'target_group': True,
                }
            ),
            content_type='application/json',
        )

        response = webapp_add_view(request)

        self.assertEqual(response.status_code, 200)
        history = ViewHistory.objects.get(show=self.show)
        self.assertSetEqual(
            set(history.users.values_list('id', flat=True)),
            {self.owner.id, self.member.id},
        )
