from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from selenium.common.exceptions import StaleElementReferenceException

from app import history_parser


class HistoryParserRecoveryTests(SimpleTestCase):
    @patch('app.history_parser._update_show_details_once')
    def test_show_update_reacquires_the_whole_page_after_browser_recovery(self, update_once):
        update_once.side_effect = [
            StaleElementReferenceException(
                'browser element reference was invalidated by session recovery'
            ),
            'updated',
        ]
        driver = Mock()

        result = history_parser.update_show_details(
            driver,
            1775,
            force=True,
            session_type='main',
        )

        self.assertEqual(result, 'updated')
        self.assertEqual(update_once.call_count, 2)
        self.assertEqual(update_once.call_args_list[0], update_once.call_args_list[1])
