"""HTTP client for the server-rendered parts of KinoPub.

The parser historically used a Selenium-shaped object everywhere.  Keeping a
small compatible facade here lets all existing parsers use a persistent,
ordinary HTTP session while retaining Asset Hub as a fallback for pages that
eventually require a real browser.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup, NavigableString, Tag
from django.conf import settings
from django.core.cache import cache
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


class KinopubHttpError(WebDriverException):
    """The HTTP transport cannot provide a usable KinoPub page."""


_SESSION_LOCKS: dict[str, threading.RLock] = {}
_SESSION_LOCKS_GUARD = threading.Lock()
_LOCAL_FALLBACK_NOTICE_UNTIL: dict[str, float] = {}


def _profile_lock(profile_key: str) -> threading.RLock:
    with _SESSION_LOCKS_GUARD:
        return _SESSION_LOCKS.setdefault(profile_key, threading.RLock())


def _session_path(profile_key: str) -> Path:
    directory = Path(settings.KINOPUB_HTTP_SESSION_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{profile_key}.json'


def notify_browser_fallback_once(profile_key: str, reason: Exception | str) -> None:
    """Queue one fallback alert per profile and incident window.

    Error delivery is deliberately best-effort.  A Redis outage must never
    prevent the browser fallback from running.
    """
    key = f'kinopub:http-fallback-notified:{profile_key}'
    try:
        should_notify = cache.add(
            key,
            1,
            timeout=settings.KINOPUB_BROWSER_FALLBACK_NOTIFY_TTL,
        )
    except Exception as exc:
        logger.warning('Could not rate-limit HTTP fallback notification: %s', exc)
        now = time.monotonic()
        with _SESSION_LOCKS_GUARD:
            notice_until = _LOCAL_FALLBACK_NOTICE_UNTIL.get(profile_key, 0)
            should_notify = notice_until <= now
            if should_notify:
                _LOCAL_FALLBACK_NOTICE_UNTIL[profile_key] = (
                    now + settings.KINOPUB_BROWSER_FALLBACK_NOTIFY_TTL
                )

    if not should_notify:
        return

    message = (
        f'KinoPub HTTP transport failed for {profile_key}; '
        f'using Asset Hub browser fallback. Reason: {str(reason)[:300]}'
    )
    logger.warning(message)
    try:
        from app.telegram_bot import TelegramSender

        TelegramSender().send_dev_log('WARNING', 'kinopub_http', message)
    except Exception as exc:
        logger.warning('Could not queue HTTP fallback notification: %s', exc)


class HttpWebElement:
    def __init__(self, driver: 'KinopubHttpDriver', node: Tag | NavigableString):
        self.driver = driver
        self.node = node

    @property
    def text(self) -> str:
        if isinstance(self.node, NavigableString):
            return str(self.node).strip()
        return self.node.get_text(' ', strip=True)

    def get_attribute(self, name: str):
        if isinstance(self.node, NavigableString):
            return None
        if name == 'innerHTML':
            return ''.join(str(child) for child in self.node.children)
        if name == 'textContent':
            return self.node.get_text('', strip=False)
        if name == 'value':
            return self.node.get('value')
        value = self.node.get(name)
        if isinstance(value, list):
            return ' '.join(value)
        return value

    def find_element(self, by, value):
        return self.driver._find_in_node(self.node, by, value, first=True)

    def find_elements(self, by, value):
        return self.driver._find_in_node(self.node, by, value, first=False)

    def click(self):
        # HTTP authentication does not use DOM clicks.  This is provided for
        # compatibility with small utility paths and submits a regular form.
        if isinstance(self.node, Tag) and self.node.name in {'button', 'input'}:
            form = self.node.find_parent('form')
            if form:
                self.driver._submit_form(form, submitter=self.node)
                return
        raise WebDriverException('HTTP element cannot be clicked without a form')

    def clear(self):
        if isinstance(self.node, Tag):
            self.node['value'] = ''

    def send_keys(self, *keys):
        if isinstance(self.node, Tag):
            self.node['value'] = ''.join(str(key) for key in keys)

    def is_displayed(self):
        if not isinstance(self.node, Tag):
            return True
        style = str(self.node.get('style', '')).lower()
        classes = set(self.node.get('class', []))
        return 'display:none' not in style.replace(' ', '') and 'hidden' not in classes

    def is_enabled(self):
        return isinstance(self.node, Tag) and not self.node.has_attr('disabled')


class KinopubHttpDriver:
    """Persistent Chrome-impersonated HTTP session with a Selenium facade."""

    RETRIES = 3

    def __init__(self, base_url, login, password, profile_key, timeout=30, impersonate=None):
        self.base_url = base_url.rstrip('/') + '/'
        self.login = login
        self.password = password
        self.profile_key = str(profile_key)
        self.timeout = timeout
        self.impersonate = impersonate or settings.KINOPUB_HTTP_IMPERSONATE
        self.session_file = _session_path(self.profile_key)
        # curl_cffi supplies a current Chrome TLS/JA3 profile, HTTP/2/3 and the
        # corresponding browser headers.  Keeping the profile on the session
        # is important: changing it request-by-request would look unlike one
        # browser connection and would also lose connection reuse.
        self.http = curl_requests.Session(
            impersonate=self.impersonate,
            default_headers=True,
        )
        self.http.headers.update(
            {
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        )
        self.http.cookies.clear()
        self._load_cookies()
        self._closed = False
        self._last_response = None
        self._last_url = self.base_url
        self._soup = BeautifulSoup('', 'html.parser')

    def _load_cookies(self):
        try:
            payload = json.loads(self.session_file.read_text(encoding='utf-8'))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return
        if payload.get('base_url') != self.base_url:
            return
        for item in payload.get('cookies', []):
            try:
                self.http.cookies.set(
                    item['name'],
                    item['value'],
                    domain=item.get('domain') or None,
                    path=item.get('path') or '/',
                )
            except (KeyError, TypeError, ValueError):
                continue

    def _cookie_objects(self):
        """Return Cookie objects, not just names from curl_cffi's facade."""
        return getattr(self.http.cookies, 'jar', self.http.cookies)

    def _save_cookies(self):
        payload = {
            'base_url': self.base_url,
            'updated_at': time.time(),
            'cookies': [
                {
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                }
                for cookie in self._cookie_objects()
            ],
        }
        path = self.session_file
        temporary = path.with_suffix(f'.{os.getpid()}.tmp')
        temporary.write_text(json.dumps(payload), encoding='utf-8')
        temporary.replace(path)

    @property
    def current_url(self):
        return self._last_url

    @property
    def title(self):
        return self._soup.title.get_text(strip=True) if self._soup.title else ''

    @property
    def page_source(self):
        return str(self._soup)

    def _request(self, url, method='GET', data=None, referer=None):
        absolute_url = urljoin(self._last_url or self.base_url, url)
        headers = {}
        if referer:
            # A form submit or an internal document navigation carries these
            # values in Chrome.  The initial navigation deliberately keeps
            # curl_cffi's `Sec-Fetch-Site: none` default.
            headers.update(
                {
                    'Referer': referer,
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                }
            )
        last_error = None
        for attempt in range(1, self.RETRIES + 1):
            try:
                response = self.http.request(
                    method,
                    absolute_url,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                if response.status_code >= 500:
                    raise KinopubHttpError(f'KinoPub HTTP {response.status_code}')
                response.encoding = response.encoding or 'utf-8'
                self._last_response = response
                self._last_url = response.url
                self._soup = BeautifulSoup(response.text or '', 'html.parser')
                self._save_cookies()
                if self._is_empty_document(response.text):
                    if attempt < self.RETRIES:
                        time.sleep(attempt * 0.5)
                        continue
                    raise KinopubHttpError(f'KinoPub returned an empty document for {absolute_url}')
                return response
            except (curl_requests.exceptions.RequestException, KinopubHttpError) as exc:
                last_error = exc
                if attempt < self.RETRIES:
                    time.sleep(attempt * 0.5)
        raise KinopubHttpError(str(last_error or 'KinoPub HTTP request failed'))

    @staticmethod
    def _is_empty_document(source):
        compact = re.sub(r'\s+', '', source or '').lower()
        return compact.startswith('<html') and '<body></body>' in compact and len(compact) <= 256

    def get(self, url):
        with _profile_lock(self.profile_key):
            referer = self._last_url if self._last_response is not None else None
            self._request(url, referer=referer)
        return None

    def refresh(self):
        return self.get(self.current_url)

    def restart(self):
        # There is no browser process to restart.  Keep the authenticated
        # connection and cookies; callers use this hook to recycle Selenium
        # workers, which is unnecessary for a requests.Session.
        return self

    def keep_alive(self):
        if self._last_url:
            self._request(self._last_url)
        return True

    def quit(self):
        if not self._closed:
            self._save_cookies()
            self.http.close()
            self._closed = True

    def persist_cookies(self):
        self._save_cookies()

    def set_page_load_timeout(self, seconds):
        self.timeout = max(1, int(seconds))

    def get_cookies(self):
        return [
            {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
            }
            for cookie in self._cookie_objects()
        ]

    def add_cookie(self, cookie):
        self.http.cookies.set(
            cookie['name'],
            cookie['value'],
            domain=cookie.get('domain'),
            path=cookie.get('path', '/'),
        )
        self._save_cookies()

    def delete_all_cookies(self):
        self.http.cookies.clear()
        self._save_cookies()

    def execute_cdp_cmd(self, command, params):
        if command == 'Page.captureScreenshot':
            return {}
        return {}

    def _find_in_node(self, node, by, value, first):
        if by == By.ID:
            found = node.find_all(id=value) if hasattr(node, 'find_all') else []
        elif by == By.TAG_NAME:
            found = node.find_all(value) if hasattr(node, 'find_all') else []
        elif by == By.CSS_SELECTOR:
            found = node.select(value) if hasattr(node, 'select') else []
        elif by == By.XPATH:
            found = self._find_xpath(node, value)
        else:
            raise WebDriverException(f'Unsupported HTTP selector: {by}')
        if first:
            if not found:
                raise NoSuchElementException(value)
            return HttpWebElement(self, found[0])
        return [HttpWebElement(self, item) for item in found]

    def find_element(self, by, value):
        return self._find_in_node(self._soup, by, value, first=True)

    def find_elements(self, by, value):
        return self._find_in_node(self._soup, by, value, first=False)

    @staticmethod
    def _find_xpath(node, expression):
        if expression == 'preceding-sibling::h4[1]':
            parent = getattr(node, 'parent', None)
            if not parent:
                return []
            siblings = [child for child in parent.children if isinstance(child, Tag)]
            try:
                index = siblings.index(node)
            except ValueError:
                return []
            return [item for item in reversed(siblings[:index]) if item.name == 'h4'][:1]

        following_small = re.fullmatch(r'\./following-sibling::small', expression)
        if following_small:
            parent = getattr(node, 'parent', None)
            if not parent:
                return []
            siblings = [child for child in parent.children if isinstance(child, Tag)]
            try:
                index = siblings.index(node)
            except ValueError:
                return []
            return [item for item in siblings[index + 1 :] if item.name == 'small'][:1]

        label_match = re.fullmatch(
            r"\.//tr\[td\[1\]\[descendant-or-self::\*\[contains\(text\(\), '(.+)'\)\]\]\]",
            expression,
        )
        if label_match:
            label = label_match.group(1)
            rows = node.select('tr') if hasattr(node, 'select') else []
            return [row for row in rows if row.find('td') and label in row.find('td').get_text(' ', strip=True)][:1]

        raise WebDriverException(f'Unsupported HTTP XPath: {expression}')

    def execute_script(self, script, *args):
        script = str(script)
        if '#items > div[class*=' in script and 'item-poster' in script:
            results = []
            for block in self._soup.select('#items > div[class*="col-"]'):
                link = block.select_one('.item-poster a')
                if not link:
                    continue
                title = block.select_one('.item-title a')
                original = block.select_one('.item-author a')
                kinopoisk = block.select_one('.bottomcenter-2x a[href*="kinopoisk.ru"]')
                imdb = block.select_one('.bottomcenter-2x a[href*="imdb.com"]')
                results.append(
                    {
                        'href': link.get('href'),
                        'title': title.get_text(strip=True) if title else '',
                        'original_title': original.get_text(strip=True) if original else '',
                        'kinopoisk_url': kinopoisk.get('href') if kinopoisk else None,
                        'kinopoisk_rating': kinopoisk.get_text(strip=True) if kinopoisk else None,
                        'imdb_url': imdb.get('href') if imdb else None,
                        'imdb_rating': imdb.get_text(strip=True) if imdb else None,
                    }
                )
            return results

        if 'Array.from(arguments[0].childNodes)' in script and args:
            element = args[0]
            if isinstance(element, HttpWebElement) and isinstance(element.node, Tag):
                return ''.join(
                    str(child) for child in element.node.children if isinstance(child, NavigableString)
                ).strip()

        window_match = re.search(r'return window\.([A-Za-z_][\w]*)\s*;', script)
        if window_match:
            variable = window_match.group(1)
            for script_tag in self._soup.find_all('script'):
                content = script_tag.string or script_tag.get_text()
                match = re.search(rf'window\.{re.escape(variable)}\s*=\s*', content)
                if match:
                    try:
                        value, _ = json.JSONDecoder().raw_decode(content[match.end() :])
                        return value
                    except json.JSONDecodeError:
                        continue
            return None

        if 'const form = document.querySelector' in script:
            form = self._soup.select_one('#login-form')
            code = self._soup.select_one('#login-form input[name="login-form[formcode]"]')
            button = self._soup.select_one(
                '#login-form button[type="submit"], #login-form input[type="submit"]'
            )
            return {
                'form_present': form is not None,
                'form_method': (form.get('method', '').upper() if form else None),
                'form_action': (urljoin(self.current_url, form.get('action', '')) if form else None),
                'code_present': code is not None,
                'code_visible': bool(code and HttpWebElement(self, code).is_displayed()),
                'submit_present': button is not None,
                'submit_disabled': bool(button and button.has_attr('disabled')),
                'active_tag': None,
                'active_id': None,
            }

        if 'input.value = value' in script and args:
            element = args[0]
            value = args[1] if len(args) > 1 else ''
            if isinstance(element, HttpWebElement) and isinstance(element.node, Tag):
                element.node['value'] = str(value)
            return None

        if re.search(r'\breturn\s+true\s*;', script):
            return True
        return None

    def _submit_form(self, form, submitter=None):
        action = urljoin(self.current_url, form.get('action', self.current_url))
        data = {
            field.get('name'): field.get('value', '')
            for field in form.select('input[name]')
            if field.get('name')
        }
        if submitter and submitter.get('name'):
            data[submitter['name']] = submitter.get('value', '')
        return self._request(action, method=form.get('method', 'GET').upper(), data=data, referer=self.current_url)

    def ensure_authenticated(self):
        if self._has_logout_marker():
            return True
        requested_login_url = urljoin(self.base_url, 'user/login')
        self._request(requested_login_url, referer=self.current_url)
        # KinoPub redirects an HTTP entry point to HTTPS.  Subsequent browser
        # form submits use the URL of the document that is actually open, not
        # the pre-redirect URL supplied by configuration.  Keeping the
        # canonical URL here is important for Referer checks on the password
        # and 2FA POSTs.
        login_url = self.current_url
        form = self._soup.select_one('form#login-form')
        if not form:
            raise KinopubHttpError('KinoPub login form is missing')
        data = {
            field.get('name'): field.get('value', '')
            for field in form.select('input[name]')
            if field.get('name')
        }
        data['login-form[login]'] = self.login
        data['login-form[password]'] = self.password
        data.setdefault('login-form[rememberMe]', '0')
        self._request(
            urljoin(self.current_url, form.get('action', '/user/login')),
            method=form.get('method', 'POST').upper(),
            data=data,
            referer=self.current_url,
        )
        if self._has_logout_marker():
            self._save_cookies()
            return True
        if not self._soup.select_one('input[name="login-form[formcode]"]'):
            raise KinopubHttpError(self._login_error() or 'KinoPub login was rejected')

        logger.info(
            'KinoPub HTTP login requires 2FA. Diagnostics: url=%r, title=%r',
            self.current_url,
            self.title,
        )
        self._wait_for_code(login_url)
        if not self._has_logout_marker():
            raise KinopubHttpError(self._login_error() or 'KinoPub 2FA was rejected')
        self._save_cookies()
        return True

    def _wait_for_code(self, login_url):
        from app.models import Code

        deadline = time.monotonic() + settings.KINOPUB_HTTP_LOGIN_TIMEOUT_SECONDS
        used_ids = set()
        attempted_at = {}
        while time.monotonic() < deadline:
            expiration = timezone.now() - timedelta(minutes=settings.CODE_LIFETIME_MINUTES)
            code_obj = (
                Code.objects.filter(received_at__gte=expiration)
                .exclude(id__in=used_ids)
                .order_by('-received_at')
                .first()
            )
            if code_obj:
                # A transient failed POST must not make the only still-valid
                # code disappear from the polling loop.  The browser path
                # retries the form after a rejected/unfinished submit; do the
                # same here, at most twice per database row.
                attempts = attempted_at.get(code_obj.id, 0)
                if attempts >= 2:
                    used_ids.add(code_obj.id)
                    time.sleep(1)
                    continue
                attempted_at[code_obj.id] = attempts + 1
                form = self._soup.select_one('form#login-form')
                if not form:
                    logger.warning(
                        'KinoPub HTTP 2FA form disappeared before code submission; '
                        'refreshing the login page.'
                    )
                    self._request(login_url, referer=self.current_url)
                    time.sleep(1)
                    continue
                data = {
                    field.get('name'): field.get('value', '')
                    for field in form.select('input[name]')
                    if field.get('name')
                }
                # The 2FA response form may contain only the code input, but
                # KinoPub validates the credentials again on this POST. A
                # browser keeps the typed values in its live DOM; a server
                # rendered HTTP response does not, so send them explicitly.
                data['login-form[login]'] = self.login
                data['login-form[password]'] = self.password
                data['login-form[formcode]'] = code_obj.code
                logger.info(
                    'KinoPub HTTP 2FA code found (id=%s, received_at=%s); submitting via %s.',
                    code_obj.id,
                    code_obj.received_at.isoformat(),
                    self.current_url,
                )
                self._request(
                    urljoin(self.current_url, form.get('action', '/user/login')),
                    method='POST',
                    data=data,
                    # Use the actual post-redirect document URL.  With an
                    # HTTP SITE_URL this is HTTPS, matching a real browser.
                    referer=self.current_url,
                )
                if self._has_logout_marker():
                    logger.info('KinoPub HTTP 2FA code accepted (id=%s).', code_obj.id)
                    return
                error = self._login_error()
                logger.warning(
                    'KinoPub HTTP 2FA code was not accepted (id=%s, attempt=%s). '
                    'Diagnostics: url=%r, title=%r%s',
                    code_obj.id,
                    attempts + 1,
                    self.current_url,
                    self.title,
                    f', form_error={error!r}' if error else '',
                )
                if attempts + 1 < 2:
                    # Re-read the form after a failed navigation before the
                    # retry. This also handles servers that return the form in
                    # a fresh document with a new hidden field/token.
                    self._request(login_url, referer=self.current_url)
            time.sleep(1)
        raise TimeoutException('Timed out waiting for KinoPub HTTP 2FA code')

    def _has_logout_marker(self):
        return bool(self._soup.select_one('a[href*="/user/logout"]'))

    def _login_error(self):
        selectors = ('#login-form .help-block', '#login-form .alert-danger', 'body .alert-danger', '[role="alert"]')
        texts = []
        for selector in selectors:
            for element in self._soup.select(selector):
                value = ' '.join(element.get_text(' ', strip=True).split())
                if value and value not in texts:
                    texts.append(value)
        return ' | '.join(texts)[:500]


# Imported lazily by history_parser to keep settings import order simple.
from django.utils import timezone  # noqa: E402  (used by the login polling code)
