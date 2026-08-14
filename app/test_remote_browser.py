from unittest import TestCase
from unittest.mock import Mock, patch

from selenium.common.exceptions import NoSuchElementException

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
        ]

        driver = RemoteBrowserDriver(
            'http://assethub/', 'secret', 'kinopub-main', 'https://kinopub.example/'
        )
        element = driver.find_element('css selector', '.title')

        self.assertEqual(element.text, 'Title')
        self.assertEqual(http.post.call_count, 3)
        self.assertEqual(
            http.post.call_args_list[1].kwargs['json'],
            {
                'command': 'find_element',
                'payload': {'by': 'css selector', 'value': '.title'},
            },
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
