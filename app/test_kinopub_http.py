import json
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from app import history_parser, kinopub_http
from app.kinopub_http import KinopubHttpDriver


class KinopubHttpDriverTests(SimpleTestCase):
    def _driver_for_html(self, html):
        driver = object.__new__(KinopubHttpDriver)
        driver._soup = BeautifulSoup(html, 'html.parser')
        driver._last_url = 'https://kino.watch/'
        return driver

    def test_history_markup_supports_existing_selenium_selectors(self):
        driver = self._driver_for_html(
            '<div class="item-list"><h4>2 сентября <small>2026</small></h4>'
            '<div class="col-md-3"><div class="item-title"><a href="/item/view/7/X">X</a></div>'
            '<div class="item-author"><a>Original X</a></div>'
            '<span class="label-success">Сезон 1. Эпизод 2</span></div></div>'
        )

        blocks = driver.find_elements(By.CSS_SELECTOR, '.item-list .col-md-3')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].find_element(By.XPATH, 'preceding-sibling::h4[1]').text, '2 сентября 2026')
        self.assertEqual(blocks[0].find_element(By.CSS_SELECTOR, '.item-title a').get_attribute('href'), '/item/view/7/X')
        self.assertEqual(blocks[0].find_element(By.CSS_SELECTOR, '.label-success').text, 'Сезон 1. Эпизод 2')

    def test_catalog_script_is_parsed_without_javascript(self):
        driver = self._driver_for_html(
            '<div id="items"><div class="col-md-3">'
            '<div class="item-poster"><a href="/item/view/12/X"></a></div>'
            '<div class="item-title"><a>Title</a></div>'
            '<div class="item-author"><a>Original</a></div></div></div>'
        )
        result = driver.execute_script(
            'const blocks = document.querySelectorAll("#items > div[class*=\'col-\']");'
            'const linkElement = block.querySelector(\'.item-poster a\');'
        )
        self.assertEqual(result[0]['href'], '/item/view/12/X')
        self.assertEqual(result[0]['title'], 'Title')

    def test_window_json_is_read_from_server_rendered_script(self):
        driver = self._driver_for_html(
            '<script>window.PLAYER_PLAYLIST = [{"season": 1, "episode": 2, "duration": 123}];</script>'
        )
        self.assertEqual(
            driver.execute_script('return window.PLAYER_PLAYLIST;'),
            [{'season': 1, 'episode': 2, 'duration': 123}],
        )

    @override_settings(KINOPUB_HTTP_SESSION_DIR='/tmp/kinopub-http-test')
    def test_cookies_are_persisted_as_json(self):
        with TemporaryDirectory() as directory, patch(
            'app.kinopub_http.settings.KINOPUB_HTTP_SESSION_DIR', directory
        ):
            first = KinopubHttpDriver('https://kino.watch/', 'login', 'password', 'main')
            first.http.cookies.set('PHPSESSID', 'session-value', domain='kino.watch', path='/')
            first.persist_cookies()

            second = KinopubHttpDriver('https://kino.watch/', 'login', 'password', 'main')
            self.assertEqual(second.http.cookies.get('PHPSESSID'), 'session-value')
            payload = json.loads(second.session_file.read_text(encoding='utf-8'))
            self.assertEqual(payload['base_url'], 'https://kino.watch/')
            self.assertEqual(payload['cookies'][0]['name'], 'PHPSESSID')

    @patch('app.kinopub_http.curl_requests.Session')
    def test_session_uses_chrome_impersonation(self, session_class):
        KinopubHttpDriver('https://kino.watch/', 'login', 'password', 'main')
        session_class.assert_called_once_with(
            impersonate='chrome',
            default_headers=True,
        )

    def test_missing_element_keeps_selenium_exception_contract(self):
        driver = self._driver_for_html('<html></html>')
        with self.assertRaises(NoSuchElementException):
            driver.find_element(By.ID, 'missing')

    @override_settings(KINOPUB_HTTP_LOGIN_TIMEOUT_SECONDS=3, CODE_LIFETIME_MINUTES=15)
    @patch('app.kinopub_http.time.sleep')
    def test_http_login_uses_post_redirect_url_for_password_and_code(self, _sleep):
        driver = self._driver_for_html(
            '<form id="login-form" method="post" action="/user/login">'
            '<input name="login-form[login]">'
            '<input name="login-form[password]">'
            '<input name="login-form[formcode]">'
            '<button type="submit">Войти</button></form>'
        )
        driver.base_url = 'http://kinopub.test/'
        driver.login = 'login'
        driver.password = 'password'
        driver._last_url = 'https://kinopub.test/user/login'
        driver._has_logout_marker = lambda: driver._authenticated
        driver._authenticated = False
        driver._save_cookies = lambda: None
        requests = []

        code = type('CodeStub', (), {
            'id': 7,
            'code': '123456',
            'received_at': timezone.now() - timedelta(seconds=10),
        })()

        def request(url, method='GET', data=None, referer=None):
            requests.append((url, method, referer, dict(data or {})))
            if method == 'GET':
                driver._last_url = 'https://kinopub.test/user/login'
                driver._soup = BeautifulSoup(
                    '<form id="login-form" method="post" action="/user/login">'
                    '<input name="login-form[login]">'
                    '<input name="login-form[password]">'
                    '<input name="login-form[formcode]">'
                    '<button type="submit">Войти</button></form>',
                    'html.parser',
                )
            elif data and data.get('login-form[formcode]') == '123456':
                driver._authenticated = True
                driver._soup = BeautifulSoup(
                    '<a href="/user/logout">Выйти</a>', 'html.parser'
                )
            return type('ResponseStub', (), {'status_code': 200})()

        driver._request = request
        with patch('app.models.Code.objects.filter') as filter_codes:
            filter_codes.return_value.exclude.return_value.order_by.return_value.first.side_effect = [
                code,
                None,
            ]
            self.assertTrue(driver.ensure_authenticated())

        post_requests = [item for item in requests if item[1] == 'POST']
        self.assertEqual(len(post_requests), 2)
        self.assertEqual(
            [item[2] for item in post_requests],
            ['https://kinopub.test/user/login', 'https://kinopub.test/user/login'],
        )
        self.assertEqual(post_requests[1][3]['login-form[login]'], 'login')
        self.assertEqual(post_requests[1][3]['login-form[password]'], 'password')

    @override_settings(KINOPUB_BROWSER_FALLBACK_ENABLED=True)
    @patch('app.history_parser.notify_browser_fallback_once')
    @patch('app.history_parser.close_driver')
    @patch('app.history_parser._initialize_browser_session')
    @patch('app.history_parser.navigate_with_empty_page_recovery')
    def test_cloudflare_switches_http_transport_to_asset_hub(
        self,
        navigate,
        initialize_browser,
        close_driver,
        notify_fallback,
    ):
        http_driver = self._driver_for_html(
            '<title>Just a moment...</title><body>challenge-platform</body>'
        )
        http_driver.profile_key = 'main'
        navigate.side_effect = lambda driver, url: driver
        fallback_driver = type('FallbackDriver', (), {})()
        fallback_driver.page_source = '<html><body>history</body></html>'
        fallback_driver.current_url = 'https://kino.watch/history'
        fallback_driver.get = lambda url: setattr(fallback_driver, 'current_url', url)
        initialize_browser.return_value = fallback_driver

        result = history_parser.open_url_safe(
            http_driver,
            'https://kino.watch/history',
            session_type='main',
        )

        self.assertIs(result, fallback_driver)
        notify_fallback.assert_called_once()
        initialize_browser.assert_called_once_with(headless=True, session_type='main')
        close_driver.assert_called_once_with(http_driver)

    @override_settings(KINOPUB_BROWSER_FALLBACK_NOTIFY_TTL=60, DEV_CHANNEL_ID='dev-channel')
    @patch('app.telegram_bot.TelegramSender')
    @patch('app.kinopub_http.cache.add', side_effect=RuntimeError('Redis unavailable'))
    def test_fallback_notification_is_rate_limited_without_redis(
        self,
        _cache_add,
        sender_class,
    ):
        kinopub_http._LOCAL_FALLBACK_NOTICE_UNTIL.clear()

        kinopub_http.notify_browser_fallback_once('main', 'first failure')
        kinopub_http.notify_browser_fallback_once('main', 'second failure')

        sender_class.return_value.send_dev_log.assert_called_once()
