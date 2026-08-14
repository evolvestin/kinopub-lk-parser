import logging
import time
from urllib.parse import urljoin

import requests
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)


class RemoteBrowserError(WebDriverException):
    pass


logger = logging.getLogger(__name__)


class RemoteBrowserDriver:
    """Small Selenium-compatible facade backed by AssetHub's queued browser API."""

    def __init__(self, api_url, token, profile_key, initial_url, timeout=900):
        self.api_url = api_url.rstrip('/') + '/'
        self.token = token
        self.profile_key = profile_key
        self.timeout = timeout
        self.http = requests.Session()
        self.session_id = None
        self._closed = False
        self._last_url = initial_url
        self._start_session(initial_url)

    def _headers(self):
        return {'X-AssetHub-Browser-Token': self.token}

    def _raise_http(self, response):
        if response.status_code >= 400:
            try:
                message = response.json().get('error', response.text)
            except ValueError:
                message = response.text
            raise RemoteBrowserError(f'AssetHub browser API HTTP {response.status_code}: {message}')

    def _start_session(self, initial_url):
        response = self.http.post(
            urljoin(self.api_url, 'api/v1/browser/sessions/'),
            headers=self._headers(),
            json={'profile_key': self.profile_key, 'initial_url': initial_url},
            timeout=30,
        )
        self._raise_http(response)
        data = response.json()
        self.session_id = data['session_id']
        self._wait(data['task_id'])

    def _reopen_session(self):
        self._closed = False
        self._start_session(self._last_url)

    @staticmethod
    def _is_inactive_response(response):
        if response.status_code != 400:
            return False
        try:
            return response.json().get('error') == 'browser session is not active'
        except ValueError:
            return False

    def _submit(self, command, payload=None, recover=True):
        if self._closed or not self.session_id:
            raise InvalidSessionIdException('remote browser session is closed')
        response = self.http.post(
            urljoin(self.api_url, f'api/v1/browser/sessions/{self.session_id}/tasks/'),
            headers=self._headers(),
            json={'command': command, 'payload': payload or {}},
            timeout=30,
        )
        if recover and command != 'close' and self._is_inactive_response(response):
            logger.warning(
                'AssetHub browser session %s is inactive; reopening profile %s',
                self.session_id,
                self.profile_key,
            )
            self._reopen_session()
            response = self.http.post(
                urljoin(self.api_url, f'api/v1/browser/sessions/{self.session_id}/tasks/'),
                headers=self._headers(),
                json={'command': command, 'payload': payload or {}},
                timeout=30,
            )
        self._raise_http(response)
        return self._wait(response.json()['task_id'])

    def _wait(self, task_id):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = self.http.get(
                urljoin(self.api_url, f'api/v1/browser/tasks/{task_id}/'),
                headers=self._headers(),
                timeout=30,
            )
            self._raise_http(response)
            data = response.json()
            if data['status'] == 'succeeded':
                return data.get('result')
            if data['status'] == 'failed':
                self._raise_remote_task(data)
            time.sleep(0.2)
        raise TimeoutException(f'AssetHub browser task {task_id} timed out')

    @staticmethod
    def _raise_remote_task(data):
        message = data.get('error', {}).get('message', 'remote browser task failed')
        error_type = data.get('error', {}).get('type', '')
        if error_type.endswith('NoSuchElementException'):
            raise NoSuchElementException(message)
        if error_type.endswith('StaleElementReferenceException'):
            raise StaleElementReferenceException(message)
        if error_type.endswith('TimeoutException'):
            raise TimeoutException(message)
        if error_type.endswith('InvalidSessionIdException'):
            raise InvalidSessionIdException(message)
        raise RemoteBrowserError(message)

    @property
    def current_url(self):
        return self._submit('get_current_url')

    @property
    def title(self):
        return self._submit('get_title')

    @property
    def page_source(self):
        return self._submit('get_page_source')

    def get(self, url):
        result = self._submit('navigate', {'url': url})
        self._last_url = url
        return result

    def refresh(self):
        return self._submit('navigate', {'url': self.current_url})

    def find_element(self, by, value):
        result = self._submit('find_element', {'by': by, 'value': value})
        return RemoteWebElement(self, result['element_id'])

    def find_elements(self, by, value):
        return [
            RemoteWebElement(self, item['element_id'])
            for item in self._submit('find_elements', {'by': by, 'value': value})
        ]

    def execute_script(self, script, *args):
        return self._submit(
            'execute_script',
            {'script': script, 'args': [self._encode(item) for item in args]},
        )

    def execute_cdp_cmd(self, command, params):
        return self._submit('execute_cdp_cmd', {'command': command, 'params': params})

    def get_cookies(self):
        return self._submit('get_cookies')

    def add_cookie(self, cookie):
        return self._submit('add_cookie', {'cookie': cookie})

    def delete_all_cookies(self):
        return self._submit('delete_all_cookies')

    def persist_cookies(self):
        return self._submit('persist_cookies')

    def set_page_load_timeout(self, seconds):
        return self._submit('set_page_load_timeout', {'seconds': seconds})

    def quit(self):
        if self._closed:
            return
        try:
            self._submit('close', recover=False)
        finally:
            self._closed = True
            self.http.close()

    @staticmethod
    def _encode(value):
        if isinstance(value, RemoteWebElement):
            return {'__element_id__': value.element_id}
        if isinstance(value, list):
            return [RemoteBrowserDriver._encode(item) for item in value]
        if isinstance(value, dict):
            return {key: RemoteBrowserDriver._encode(item) for key, item in value.items()}
        return value


class RemoteWebElement:
    def __init__(self, driver, element_id):
        self.driver = driver
        self.element_id = element_id

    @property
    def text(self):
        return self.driver._submit('element_text', {'element_id': self.element_id})

    def get_attribute(self, name):
        return self.driver._submit(
            'element_attribute', {'element_id': self.element_id, 'name': name}
        )

    def find_element(self, by, value):
        result = self.driver._submit(
            'element_find_element',
            {'element_id': self.element_id, 'by': by, 'value': value},
        )
        return RemoteWebElement(self.driver, result['element_id'])

    def find_elements(self, by, value):
        return [
            RemoteWebElement(self.driver, item['element_id'])
            for item in self.driver._submit(
                'element_find_elements',
                {'element_id': self.element_id, 'by': by, 'value': value},
            )
        ]

    def click(self):
        return self.driver._submit('element_click', {'element_id': self.element_id})

    def clear(self):
        return self.driver._submit('element_clear', {'element_id': self.element_id})

    def send_keys(self, *keys):
        return self.driver._submit(
            'element_send_keys',
            {'element_id': self.element_id, 'keys': [str(key) for key in keys]},
        )

    def is_displayed(self):
        return self.driver._submit('element_is_displayed', {'element_id': self.element_id})

    def is_enabled(self):
        return self.driver._submit('element_is_enabled', {'element_id': self.element_id})
