from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from app.remote_browser import RemoteBrowserDriver


class RemoteBrowserDriverTests(TestCase):
    @staticmethod
    def response(payload, status=200):
        result = Mock()
        result.status_code = status
        result.text = ''
        result.json.return_value = payload
        return result

    @patch('app.remote_browser.requests.Session')
    def test_session_open_and_element_operations_use_queued_tasks(self, session_cls):
        http = session_cls.return_value
        http.post.return_value = self.response(
            {'session_id': 'session-1', 'task_id': 'task-open', 'status': 'queued'}
        )
        http.get.side_effect = [
            self.response({'status': 'succeeded', 'result': None}),
            self.response({'status': 'succeeded', 'result': {'element_id': 'element-1'}}),
            self.response({'status': 'succeeded', 'result': 'Title'}),
            self.response({'status': 'succeeded', 'result': True}),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )
        element = driver.find_element('css selector', '.title')

        self.assertEqual(element.text, 'Title')
        self.assertTrue(element.is_enabled())
        self.assertEqual(http.post.call_count, 4)
        self.assertEqual(
            http.post.call_args_list[1].kwargs['json'],
            {
                'command': 'find_element',
                'payload': {'by': 'css selector', 'value': '.title'},
            },
        )

    @patch('app.remote_browser.requests.Session')
    def test_restart_keeps_the_same_remote_session(self, session_cls):
        http = session_cls.return_value
        http.post.side_effect = [
            self.response({'session_id': 'session-1', 'task_id': 'task-open', 'status': 'queued'}),
            self.response({'task_id': 'task-restart', 'status': 'queued'}, status=202),
        ]
        http.get.side_effect = [
            self.response({'status': 'succeeded', 'result': None}),
            self.response(
                {
                    'status': 'succeeded',
                    'result': {'current_url': 'https://kinopub.example/'},
                }
            ),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )
        driver.restart()

        self.assertEqual(driver.session_id, 'session-1')
        self.assertEqual(
            http.post.call_args_list[1].kwargs['json'],
            {'command': 'restart', 'payload': {'url': 'https://kinopub.example/'}},
        )

    @patch('app.remote_browser.requests.Session')
    def test_remote_no_such_element_is_mapped_to_selenium_exception(self, session_cls):
        http = session_cls.return_value
        http.post.return_value = self.response(
            {'session_id': 'session-1', 'task_id': 'task-open', 'status': 'queued'}
        )
        http.get.side_effect = [
            self.response({'status': 'succeeded', 'result': None}),
            self.response(
                {
                    'status': 'failed',
                    'error': {
                        'type': 'selenium.common.exceptions.NoSuchElementException',
                        'message': 'missing',
                    },
                }
            ),
        ]
        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )

        with self.assertRaises(NoSuchElementException):
            driver.find_element('id', 'missing')

    @patch('app.remote_browser.requests.Session')
    def test_inactive_session_is_reopened_and_command_is_retried(self, session_cls):
        http = session_cls.return_value
        http.post.side_effect = [
            self.response(
                {'session_id': 'session-1', 'task_id': 'task-open-1', 'status': 'queued'}
            ),
            self.response({'error': 'browser session is not active'}, status=400),
            self.response(
                {'session_id': 'session-2', 'task_id': 'task-open-2', 'status': 'queued'}
            ),
            self.response({'task_id': 'task-find', 'status': 'queued'}, status=202),
        ]
        http.get.side_effect = [
            self.response({'status': 'succeeded', 'result': None}),
            self.response({'status': 'succeeded', 'result': None}),
            self.response({'status': 'succeeded', 'result': {'element_id': 'element-2'}}),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )
        element = driver.find_element('css selector', '.title')

        self.assertEqual(element.element_id, 'element-2')
        self.assertEqual(driver.session_id, 'session-2')
        self.assertEqual(http.post.call_count, 4)

    @patch('app.remote_browser.requests.Session')
    def test_element_reference_is_not_retried_after_session_recovery(self, session_cls):
        http = session_cls.return_value
        http.post.side_effect = [
            self.response(
                {'session_id': 'session-1', 'task_id': 'task-open-1', 'status': 'queued'}
            ),
            self.response({'error': 'browser session is not active'}, status=400),
            self.response(
                {'session_id': 'session-2', 'task_id': 'task-open-2', 'status': 'queued'}
            ),
        ]
        http.get.side_effect = [
            self.response({'status': 'succeeded', 'result': None}),
            self.response({'status': 'succeeded', 'result': None}),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )

        with self.assertRaises(StaleElementReferenceException):
            driver._submit('element_text', {'element_id': 'old-element'})

    @patch('app.remote_browser.requests.Session')
    def test_replaced_session_is_reopened_and_command_is_retried(self, session_cls):
        http = session_cls.return_value
        http.post.side_effect = [
            self.response(
                {'session_id': 'session-1', 'task_id': 'task-open-1', 'status': 'queued'}
            ),
            self.response({'task_id': 'task-navigate-1', 'status': 'queued'}, status=202),
            self.response(
                {'session_id': 'session-2', 'task_id': 'task-open-2', 'status': 'queued'}
            ),
            self.response({'task_id': 'task-navigate-2', 'status': 'queued'}, status=202),
        ]
        http.get.side_effect = [
            self.response({'status': 'succeeded', 'result': None}),
            self.response(
                {
                    'status': 'failed',
                    'error': {
                        'type': 'browser_gateway.SessionReplaced',
                        'message': 'The browser session was replaced by a newer session.',
                    },
                }
            ),
            self.response({'status': 'succeeded', 'result': None}),
            self.response({'status': 'succeeded', 'result': None}),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )
        driver.get('https://kinopub.example/history')

        self.assertEqual(driver.session_id, 'session-2')
        self.assertEqual(http.post.call_count, 4)

    @patch('app.remote_browser.requests.Session')
    def test_replaced_open_is_retried_during_driver_creation(self, session_cls):
        http = session_cls.return_value
        http.post.side_effect = [
            self.response(
                {'session_id': 'session-1', 'task_id': 'task-open-1', 'status': 'queued'}
            ),
            self.response(
                {'session_id': 'session-2', 'task_id': 'task-open-2', 'status': 'queued'}
            ),
        ]
        http.get.side_effect = [
            self.response(
                {
                    'status': 'failed',
                    'error': {
                        'type': 'browser_gateway.SessionReplaced',
                        'message': 'The browser session was replaced by a newer session.',
                    },
                }
            ),
            self.response({'status': 'succeeded', 'result': None}),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )

        self.assertEqual(driver.session_id, 'session-2')
        self.assertEqual(http.post.call_count, 2)

    @patch('app.remote_browser.time.sleep')
    @patch('app.remote_browser.requests.Session')
    def test_transient_browser_startup_error_is_retried(self, session_cls, sleep):
        http = session_cls.return_value
        http.post.side_effect = [
            self.response(
                {
                    'session_id': 'session-1',
                    'task_id': 'task-open-1',
                    'status': 'queued',
                }
            ),
            self.response(
                {
                    'session_id': 'session-2',
                    'task_id': 'task-open-2',
                    'status': 'queued',
                }
            ),
        ]
        http.get.side_effect = [
            self.response(
                {
                    'status': 'failed',
                    'error': {
                        'type': 'selenium.common.exceptions.WebDriverException',
                        'message': 'session not created: unable to connect to renderer',
                    },
                }
            ),
            self.response({'status': 'succeeded', 'result': None}),
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )

        self.assertEqual(driver.session_id, 'session-2')
        self.assertEqual(http.post.call_count, 2)
        self.assertTrue(sleep.called)

    @patch('app.remote_browser.time.sleep')
    @patch('app.remote_browser.requests.Session')
    def test_gateway_timeout_while_starting_is_retried(self, session_cls, sleep):
        http = session_cls.return_value
        http.post.side_effect = [
            requests.ReadTimeout('gateway read timeout'),
            self.response(
                {'session_id': 'session-2', 'task_id': 'task-open-2', 'status': 'queued'}
            ),
        ]
        http.get.return_value = self.response({'status': 'succeeded', 'result': None})

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )

        self.assertEqual(driver.session_id, 'session-2')
        self.assertEqual(http.post.call_count, 2)
        self.assertTrue(sleep.called)
