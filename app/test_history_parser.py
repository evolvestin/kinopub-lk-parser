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

    def test_login_url_comparison_ignores_query_and_trailing_slash(self):
        self.assertTrue(
            history_parser._is_login_url(
                'https://kinopub.example/user/login?returnUrl=%2Fhistory',
                'https://kinopub.example/user/login',
            )
        )

    def test_login_state_reports_visible_two_factor_form(self):
        driver = Mock()
        driver.current_url = 'https://kinopub.example/user/login'

        def find_elements(by, selector):
            if selector == 'login-form-formcode':
                code = Mock()
                code.is_displayed.return_value = True
                return [code]
            return []

        driver.find_elements.side_effect = find_elements

        self.assertEqual(
            history_parser._wait_for_login_state(
                driver,
                'https://kinopub.example/user/login',
                timeout=1,
            ),
            '2fa',
        )

    def test_empty_remote_document_is_detected(self):
        driver = Mock()
        driver.page_source = '<html><head></head><body></body></html>'

        self.assertTrue(history_parser.is_empty_browser_page(driver))

    def test_two_factor_submission_sets_value_and_submits_the_form(self):
        driver = Mock()
        code_input = Mock()
        code_input.get_attribute.return_value = '650665'
        submit_btn = Mock()

        history_parser._submit_two_factor_code(driver, code_input, submit_btn, ' 650665 ')

        code_input.clear.assert_called_once_with()
        code_input.send_keys.assert_called_once_with('650665')
        driver.execute_script.assert_called_once()
        submit_btn.click.assert_not_called()
        self.assertIn('requestSubmit', driver.execute_script.call_args.args[0])

    def test_two_factor_submission_falls_back_to_click_for_old_gateway(self):
        driver = Mock()
        driver.execute_script.side_effect = RuntimeError('unsupported script arguments')
        code_input = Mock()
        code_input.get_attribute.return_value = None
        submit_btn = Mock()

        history_parser._submit_two_factor_code(driver, code_input, submit_btn, '650665')

        self.assertEqual(driver.execute_script.call_count, 2)
        submit_btn.click.assert_called_once_with()

    @patch('app.history_parser.close_driver')
    @patch('app.history_parser.initialize_driver_session', return_value=None)
    def test_parser_run_fails_when_driver_initialization_fails(self, _initialize, close_driver):
        with self.assertRaisesRegex(RuntimeError, 'Failed to initialize'):
            history_parser.run_parser_session()

        close_driver.assert_called_once_with(None)
