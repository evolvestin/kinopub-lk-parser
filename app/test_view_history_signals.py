from datetime import date
from unittest.mock import patch

from django.test import TestCase

from app.models import Show, ViewHistory, ViewUser
from app.signals import view_history_created


class ViewHistorySignalTests(TestCase):
    def setUp(self):
        self.user = ViewUser.objects.create(telegram_id=101, name='Alice')
        self.show = Show.objects.create(
            title='A title', original_title='A title', type='movie'
        )

    @patch('app.signals.TelegramSender.update_history_message')
    @patch('app.signals.TelegramSender.send_private_history_notification')
    @patch('app.signals.TelegramSender.send_history_notification')
    def test_empty_latest_view_blocks_copy_from_older_view(
        self, _send_history, _send_private, _update_history
    ):
        older_view = ViewHistory.objects.create(
            show=self.show, view_date=date(2026, 9, 1), episode_number=1
        )
        older_view.users.add(self.user)

        empty_latest_view = ViewHistory.objects.create(
            show=self.show, view_date=date(2026, 9, 2), episode_number=2
        )
        new_view = ViewHistory.objects.create(
            show=self.show, view_date=date(2026, 9, 3), episode_number=3
        )

        view_history_created.send(sender=ViewHistory, instance=new_view)

        self.assertFalse(empty_latest_view.users.exists())
        self.assertFalse(new_view.users.exists())

    @patch('app.signals.TelegramSender.update_history_message')
    @patch('app.signals.TelegramSender.send_private_history_notification')
    @patch('app.signals.TelegramSender.send_history_notification')
    def test_latest_non_empty_view_copies_participants(
        self, _send_history, _send_private, _update_history
    ):
        previous_view = ViewHistory.objects.create(
            show=self.show, view_date=date(2026, 9, 1), episode_number=1
        )
        previous_view.users.add(self.user)
        new_view = ViewHistory.objects.create(
            show=self.show, view_date=date(2026, 9, 2), episode_number=2
        )

        view_history_created.send(sender=ViewHistory, instance=new_view)

        self.assertSetEqual(set(new_view.users.all()), {self.user})
