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
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

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
_AUTH_LOCK_TIMEOUT_SECONDS = 360
_CODE_ARRIVAL_GRACE_SECONDS = 15


def _profile_lock(profile_key: str) -> threading.RLock:
    with _SESSION_LOCKS_GUARD:
        return _SESSION_LOCKS.setdefault(profile_key, threading.RLock())


@contextmanager
def _distributed_profile_lock(profile_key: str):
    """Serialize login attempts across Celery processes and containers."""
    local_lock = _profile_lock(profile_key)
    local_lock.acquire()
    cache_key = f'kinopub:http-auth-lock:{profile_key}'
    cache_lock_acquired = False
    try:
        deadline = time.monotonic() + _AUTH_LOCK_TIMEOUT_SECONDS
        while True:
            try:
                cache_lock_acquired = cache.add(
                    cache_key,
                    'locked',
                    timeout=_AUTH_LOCK_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                # A cache outage must not make the parser unusable. The local
                # lock still protects threads inside this process.
                logger.warning('Could not acquire distributed KinoPub auth lock: %s', exc)
                break

            if cache_lock_acquired:
                break
            if time.monotonic() >= deadline:
                raise TimeoutException(
                    f'Timed out waiting for KinoPub authentication lock ({profile_key})'
                )
            logger.info('Another %s worker is authenticating KinoPub; waiting for its session.', profile_key)
            time.sleep(1)

        yield
    finally:
        if cache_lock_acquired:
            try:
                cache.delete(cache_key)
            except Exception as exc:
                logger.warning('Could not release distributed KinoPub auth lock: %s', exc)
        local_lock.release()


def _is_authentication_failure(exc: Exception | str) -> bool:
    """Return True for failures where browser fallback would request another OTP."""
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            'waiting for kinopub http 2fa code',
            'authentication lock',
            'kinopub 2fa',
            'kinopub login',
            'login form',
            'login was rejected',
        )
    )


def _secure_url(url: str) -> str:
    """Use the TLS endpoint for credential/2FA form submissions."""
    parts = urlsplit(url)
    if parts.scheme.lower() != 'http':
        return url
    return urlunsplit(('https', parts.netloc, parts.path, parts.query, parts.fragment))


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
        self.code_wait_started_at = None

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
        if method.upper() == 'POST':
            # Native browser form submissions include Origin and an explicit
            # URL-encoded content type.  Some KinoPub edges return an empty
            # 200 response when these signals are missing.
            origin = absolute_url.split('/', 3)
            headers.update(
                {
                    'Origin': '/'.join(origin[:3]),
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
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
        return not compact or (
            compact.startswith('<html') and '<body></body>' in compact and len(compact) <= 256
        )

    def get(self, url):
        with _profile_lock(self.profile_key):
            referer = self._last_url if self._last_response is not None else None
            try:
                self._request(url, referer=referer)
            except KinopubHttpError as exc:
                if 'empty document' not in str(exc).lower():
                    raise
                # A concurrent login on the same KinoPub account can revoke
                # this session and produce an empty 200 document once. Treat
                # it as a stale page: reload the target and let the caller
                # observe the normal redirect to /user/login.
                logger.warning(
                    'KinoPub returned an empty document for %s; reloading once '
                    'before checking session expiry.',
                    url,
                )
                time.sleep(1)
                self._request(url, referer=self._last_url)
            if not self.page_source.strip():
                logger.warning(
                    'KinoPub returned an empty page for %s; reloading once '
                    'before checking session expiry.',
                    url,
                )
                time.sleep(1)
                self._request(url, referer=self._last_url)
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
        # Record the challenge before submitting credentials. KinoPub can
        # deliver the email code while the password POST is still returning;
        # recording it only after the 2FA form is parsed drops that valid code.
        login_challenge_started_at = timezone.now()
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
        submitter = form.select_one('button[type="submit"], input[type="submit"]')
        if submitter and submitter.get('name'):
            data[submitter['name']] = submitter.get('value', '')
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
        self._wait_for_code(login_url, login_challenge_started_at)
        if not self._has_logout_marker():
            raise KinopubHttpError(self._login_error() or 'KinoPub 2FA was rejected')
        self._save_cookies()
        return True

    def _wait_for_code(self, login_url, login_challenge_started_at=None):
        from app.models import Code

        deadline = time.monotonic() + settings.KINOPUB_HTTP_LOGIN_TIMEOUT_SECONDS
        login_started_at = login_challenge_started_at or timezone.now()
        # This remains the moment when the actual 2FA form became visible;
        # external smoke tooling uses it as the safe point to start polling.
        self.code_wait_started_at = timezone.now()
        used_ids = set()
        while time.monotonic() < deadline:
            expiration = timezone.now() - timedelta(minutes=settings.CODE_LIFETIME_MINUTES)
            code_not_before = max(
                expiration,
                login_started_at - timedelta(seconds=_CODE_ARRIVAL_GRACE_SECONDS),
            )
            code_obj = (
                Code.objects.filter(
                    created_at__gte=code_not_before,
                )
                .exclude(id__in=used_ids)
                .order_by('-created_at')
                .first()
            )
            if code_obj:
                form = self._soup.select_one('form#login-form')
                if not form:
                    logger.warning(
                        'KinoPub HTTP 2FA form disappeared before code submission; '
                        'refreshing the login page.'
                    )
                    self._request(_secure_url(login_url), referer=self.current_url)
                    time.sleep(1)
                    continue
                data = {
                    field.get('name'): field.get('value', '')
                    for field in form.select('input[name]')
                    if field.get('name')
                    and field.get('name')
                    not in {'login-form[login]', 'login-form[password]'}
                }
                submitter = form.select_one('button[type="submit"], input[type="submit"]')
                if submitter and submitter.get('name'):
                    data[submitter['name']] = submitter.get('value', '')
                # The 2FA response form is a separate POST and contains its
                # own CSRF token. KinoPub rejects the original login/password
                # fields when they are added to this second request; a real
                # browser submits only the fields from the visible 2FA form.
                data['login-form[formcode]'] = code_obj.code
                logger.info(
                    'KinoPub HTTP 2FA code found (id=%s, created_at=%s); submitting via %s.',
                    code_obj.id,
                    code_obj.created_at.isoformat(),
                    self.current_url,
                )
                submit_url = _secure_url(
                    urljoin(self.current_url, form.get('action', '/user/login'))
                )
                self._request(
                    submit_url,
                    method='POST',
                    data=data,
                    # Use the actual post-redirect document URL.  With an
                    # HTTP SITE_URL this is HTTPS, matching a real browser.
                    referer=self.current_url,
                )
                # Some KinoPub frontends answer the successful form POST with
                # an empty 200 document while keeping the authenticated state
                # in the PHP session. Fetch the redirect target once before
                # deciding that authentication failed.
                if not self.page_source.strip() and self.current_url:
                    logger.info(
                        'KinoPub returned an empty 2FA POST document; refreshing %s '
                        'to inspect the session state.',
                        self.current_url,
                    )
                    self._request(self.current_url, referer=self.current_url)
                if self._has_logout_marker():
                    logger.info('KinoPub HTTP 2FA code accepted (id=%s).', code_obj.id)
                    return
                error = self._login_error()
                logger.warning(
                    'KinoPub HTTP 2FA code was not accepted (id=%s). '
                    'Diagnostics: url=%r, title=%r, status=%s, body_len=%s, '
                    'code_form=%s, logout_marker=%s%s',
                    code_obj.id,
                    self.current_url,
                    self.title,
                    self._last_response.status_code if self._last_response is not None else None,
                    len(self.page_source),
                    bool(self._soup.select_one('input[name="login-form[formcode]"]')),
                    self._has_logout_marker(),
                    f', form_error={error!r}' if error else '',
                )
                # Never submit a rejected OTP a second time. KinoPub commonly
                # responds to an expired code by issuing a fresh one; retrying
                # the old value only burns time and can trigger another code.
                used_ids.add(code_obj.id)
                error_lower = error.lower()
                fresh_code_sent = any(
                    marker in error_lower
                    for marker in ('отправили новый', 'отправлен проверочный', 'sent a new')
                )
                if fresh_code_sent:
                    logger.info('KinoPub reported that a fresh 2FA code was sent; waiting for it.')
                else:
                    logger.warning(
                        'KinoPub did not confirm a fresh 2FA code; waiting for an externally '
                        'delivered code without requesting another resend.'
                    )
            time.sleep(1)
        latest_code = Code.objects.order_by('-created_at').first()
        latest_code_info = (
            f' Latest stored code id={latest_code.id}, created_at={latest_code.created_at.isoformat()}'
            if latest_code
            else ' No stored KinoPub codes were found.'
        )
        raise TimeoutException(
            'Timed out waiting for KinoPub HTTP 2FA code.' + latest_code_info
        )

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
