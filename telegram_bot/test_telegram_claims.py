import unittest

from handlers.commands import _is_viewer_in_show_history
from keyboards import get_claim_mode_keyboard


class TelegramClaimFlowTests(unittest.TestCase):
    def test_group_menu_offers_unclaim_for_current_viewer(self):
        keyboard = get_claim_mode_keyboard(
            view_id=42,
            groups=[{'id': 7, 'name': 'Team'}],
            is_viewer=True,
        )

        self.assertEqual(keyboard.inline_keyboard[0][0].text, '🗑 Убрать только себя')
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, 'unclaim_42')

    def test_group_menu_keeps_claim_for_new_viewer(self):
        keyboard = get_claim_mode_keyboard(
            view_id=42,
            groups=[{'id': 7, 'name': 'Team'}],
            is_viewer=False,
        )

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, 'claim_self_42')

    def test_viewer_status_is_read_from_show_history(self):
        show_data = {'view_history': [{'id': 42, 'is_viewer': True}]}

        self.assertTrue(_is_viewer_in_show_history(show_data, 42))
        self.assertFalse(_is_viewer_in_show_history(show_data, 7))
        self.assertFalse(_is_viewer_in_show_history(None, 42))


if __name__ == '__main__':
    unittest.main()