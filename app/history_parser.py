import json
import logging
import re
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Max, Q
from django.utils import timezone
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from app.gdrive_backup import BackupManager
from app.models import (
    Code,
    Country,
    Genre,
    Person,
    Show,
    ShowCrew,
    ShowDuration,
    ViewHistory,
)
from app.remote_browser import RemoteBrowserDriver, RemoteBrowserError
from app.services.person_matching import find_person_for_kinopub
from app.services.show_duration import upsert_show_duration
from app.signals import view_history_created
from app.utils import enqueue_show_update, normalize_country_name
from shared.constants import (
    DATE_FORMAT,
    MONTHS_MAP,
    SERIES_TYPES,
    SHOW_STATUS_MAPPING,
    SHOW_TYPE_MAPPING,
    ParserSessionType,
    ShowType,
)
from shared.formatters import format_se


def is_cloudflare_page(driver):
    """Проверяет, является ли текущая страница заглушкой Cloudflare."""
    try:
        title = driver.title
        page_source = driver.page_source
        return (
            'Один момент' in title
            or 'Just a moment' in title
            or 'challenges.cloudflare.com' in page_source
            or '/cdn-cgi/challenge-platform/' in page_source
        )
    except Exception:
        return False


def is_empty_browser_page(driver):
    """Detect the tiny empty document returned by a failed remote navigation."""
    try:
        source = re.sub(r'\s+', '', driver.page_source or '').lower()
    except Exception:
        return False
    return source.startswith('<html') and '<body></body>' in source and len(source) <= 128


def navigate_with_empty_page_recovery(driver, url):
    """Retry one navigation when Chromium returns an empty document."""
    driver.get(url)
    if not is_empty_browser_page(driver):
        return driver

    logging.warning('AssetHub returned an empty document for %s. Reloading page once.', url)
    try:
        driver.refresh()
    except Exception as exc:
        logging.warning('Reload failed for empty document %s: %s', url, exc)
    if not is_empty_browser_page(driver):
        return driver

    logging.warning('Page reload did not recover %s. Restarting browser once.', url)
    driver.restart()
    time.sleep(1)
    driver.get(url)
    if is_empty_browser_page(driver):
        raise RemoteBrowserError(f'AssetHub returned an empty document for {url}')
    return driver


def is_fatal_selenium_error(e):
    """Определяет, является ли ошибка критической для сессии драйвера."""
    err_str = str(e).lower()
    return (
        'driver unresponsive' in err_str
        or 'connection refused' in err_str
        or 'max retries exceeded' in err_str
        or 'invalid session' in err_str
        or 'session was replaced by a newer session' in err_str
        or 'browser session is not available in this worker' in err_str
        or 'remote end closed connection' in err_str
        or 'remotedisconnected' in err_str
        or 'protocolerror' in err_str
        or 'err_name_not_resolved' in err_str
    )


def is_recovery_stale_element_error(e):
    """Возвращает True, если WebElement устарел из-за восстановления браузера."""
    return (
        isinstance(e, StaleElementReferenceException)
        or 'browser element reference was invalidated by session recovery' in str(e).lower()
    )


def close_driver(driver):
    if driver:
        logging.info('Closing Selenium driver.')
        try:
            driver.quit()
        except Exception:
            pass

    def do_nothing():
        pass

    if driver:
        driver.quit = do_nothing


def _extract_int_from_string(text):
    if not text:
        return None
    digits = ''.join(c for c in text if c.isdigit())
    if not digits:
        return None
    return int(digits)


def _update_show_details_once(
    driver,
    kinopub_id,
    force=False,
    session_type=ParserSessionType.MAIN,
):
    target_path = f'item/view/{kinopub_id}'
    base_url = (
        settings.SITE_URL if session_type == ParserSessionType.MAIN else settings.SITE_AUX_URL
    )

    try:
        driver = open_url_safe(
            driver, f'{base_url.rstrip("/")}/{target_path}', session_type=session_type
        )
        time.sleep(2)
    except StaleElementReferenceException:
        raise
    except Exception as e:
        logging.error(f'Error navigating to show page {kinopub_id}: {e}')
        return

    current_url = driver.current_url
    if (
        'chrome-error://' in current_url
        or 'ERR_NAME_NOT_RESOLVED' in current_url
        or 'ERR_NAME_NOT_RESOLVED' in driver.page_source
    ):
        logging.error(
            f'Failed to fetch show {kinopub_id}: Network/DNS error (ERR_NAME_NOT_RESOLVED).'
        )
        return

    if '/user/login' in current_url:
        logging.error(f'Failed to fetch show {kinopub_id}: Stuck on login page.')
        return

    page_title = driver.title.strip()
    if page_title == 'Not Found (#404)':
        logging.warning(f'Show {kinopub_id} returned 404 (Not Found).')
        return

    try:
        wait = WebDriverWait(driver, 10)
        try:
            info_table = wait.until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, 'table.table-striped')
                )
            )
        except TimeoutException:
            page_text = driver.find_element(By.TAG_NAME, 'body').text
            if 'Запрошенная страница не найдена' in page_text:
                logging.warning(f'Show {kinopub_id} returned 404 content.')
                return

            logging.warning(f'Info table not found for show {kinopub_id}. Metadata update aborted.')
            return

        try:
            # KinoPub currently renders the item title as h1.iv-title-ru.
            # Keep h3/h1 fallbacks for older or alternate page layouts.
            title_elem = None
            for selector in ('h1.iv-title-ru', 'h3', 'h1'):
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    title_elem = elements[0]
                    break

            if title_elem is None:
                raise NoSuchElementException('Item title element not found')

            title_text = driver.execute_script(
                'return Array.from(arguments[0].childNodes)'
                '.filter(n => n.nodeType === Node.TEXT_NODE)'
                ".map(n => n.textContent).join('').trim();",
                title_elem,
            )
            if not title_text:
                full_title_text = title_elem.text
                try:
                    small_text = title_elem.find_element(By.TAG_NAME, 'small').text
                    title_text = full_title_text.replace(small_text, '').strip()
                except NoSuchElementException:
                    title_text = full_title_text.split('\n')[0].strip()
        except NoSuchElementException:
            title_text = ''
            title_elem = None

        forbidden_titles = {
            'Авторизация',
            'Browser',
            '404 Not Found',
            'Not Found (#404)',
            'Error',
            'Cloudflare',
            'Один момент',
            'Just a moment',
        }
        if not title_text or title_text in forbidden_titles:
            logging.error(
                f'Detected invalid header '
                f'"{title_text}" for KinoPub ID {kinopub_id}. Aborting save.'
            )
            return

        show = Show.objects.filter(kinopub_id=kinopub_id).first()
        if show:
            if not force:
                three_months_ago = timezone.now() - timedelta(days=90)
                if show.year is not None and show.updated_at >= three_months_ago:
                    return
        else:
            show = Show(
                kinopub_id=kinopub_id,
                type='Unknown',
                title=title_text,
                original_title=title_text,
            )

        logging.info(f'Fetching extended details for show kinopub_id={kinopub_id}')

        if title_text:
            show.title = title_text

        try:
            small_elem = title_elem.find_element(By.TAG_NAME, 'small')
            raw_orig = small_elem.text
        except NoSuchElementException:
            original_title_elements = driver.find_elements(By.CSS_SELECTOR, '.iv-title-orig')
            raw_orig = original_title_elements[0].text if original_title_elements else ''

        try:
            clean_orig = re.sub(
                r'\+?\s*(?:HD|4K|UHD|3D|AC3|5\.1|7\.1)\b', '', raw_orig, flags=re.IGNORECASE
            )
            clean_orig = ' '.join(clean_orig.split()).strip()
            if clean_orig:
                show.original_title = clean_orig
        except Exception:
            pass

        try:
            plot_elem = driver.find_element(By.ID, 'plot')
            p_text = plot_elem.text.strip()
            if p_text:
                show.plot = p_text
        except NoSuchElementException:
            pass

        def get_row_data(text_label):
            try:
                row = info_table.find_element(
                    By.XPATH,
                    f".//tr[td[1][descendant-or-self::*[contains(text(), '{text_label}')]]]",
                )
                return row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)')
            except NoSuchElementException:
                return None

        year_data = get_row_data('Год выхода')
        if year_data:
            y_val = _extract_int_from_string(year_data.text)
            if y_val:
                show.year = y_val
            try:
                link = year_data.find_element(By.TAG_NAME, 'a')
                href = link.get_attribute('href')
                types_pattern = '|'.join(SHOW_TYPE_MAPPING.keys())
                type_match = re.search(f'/({types_pattern})', href)
                if type_match:
                    type_key = type_match.group(1)
                    show.type = SHOW_TYPE_MAPPING.get(type_key, type_key.capitalize())
            except NoSuchElementException:
                pass

        status_data = get_row_data('Статус')
        if status_data:
            raw_status = status_data.text.strip()
            if raw_status:
                show.status = SHOW_STATUS_MAPPING.get(raw_status, raw_status)

        rating_data = get_row_data('Рейтинг')
        if rating_data:
            try:
                kinopoisk_link = rating_data.find_element(
                    By.CSS_SELECTOR, "a[href*='kinopoisk.ru']"
                )
                href = kinopoisk_link.get_attribute('href')
                if '/film/' in href and not href.endswith('/film/'):
                    show.kinopoisk_url = href
                    show.kinopoisk_rating = float(kinopoisk_link.text)
                    votes_element = kinopoisk_link.find_element(
                        By.XPATH, './following-sibling::small'
                    )
                    v_val = _extract_int_from_string(votes_element.text)
                    if v_val:
                        show.kinopoisk_votes = v_val
            except (NoSuchElementException, ValueError):
                pass
            try:
                imdb_link = rating_data.find_element(By.CSS_SELECTOR, "a[href*='imdb.com']")
                show.imdb_url = imdb_link.get_attribute('href')
            except (NoSuchElementException, ValueError):
                pass

        show_fields = [
            'title',
            'original_title',
            'plot',
            'year',
            'type',
            'status',
            'kinopoisk_url',
            'kinopoisk_rating',
            'kinopoisk_votes',
            'imdb_url',
        ]
        if show._state.adding:
            show.save()
        else:
            # IMDb ratings and votes are owned by the official dataset sync.
            # Field-scoped updates prevent a concurrent IMDb batch from being
            # overwritten by this stale Show instance.
            show.save(update_fields=[*show_fields, 'updated_at'])

        for label, model, relation in [
            ('Страна', Country, show.countries),
            ('Жанр', Genre, show.genres),
        ]:
            elements_data = get_row_data(label)
            if elements_data:
                related_objects = []
                elements = elements_data.find_elements(By.TAG_NAME, 'a')
                for el in elements:
                    name = el.get_attribute('textContent').strip()
                    if name:
                        if model is Country:
                            name = normalize_country_name(name)
                        obj, _ = model.objects.update_or_create(name=name)
                        related_objects.append(obj)
                relation.set(related_objects)

        crew_labels = ['Создатель', 'Режиссёр', 'В ролях']
        for label in crew_labels:
            elements_data = get_row_data(label)
            if elements_data:
                elements = elements_data.find_elements(By.TAG_NAME, 'a')
                for link_element in elements:
                    name = link_element.get_attribute('textContent').strip()
                    if name:
                        person = find_person_for_kinopub(name=name, show=show)
                        if not person:
                            person, _ = Person.objects.get_or_create(name=name)
                            person = person.canonical
                        ShowCrew.objects.update_or_create(
                            show=show, person=person, profession=label
                        )

    except Exception as e:
        logging.error(
            f'An error occurred while updating show details for kinopub_id={kinopub_id}: {e}'
        )
        raise


def update_show_details(
    driver,
    kinopub_id,
    force=False,
    session_type=ParserSessionType.MAIN,
):
    """Update one show, reacquiring the whole page after browser recovery.

    A gateway recovery invalidates every remote WebElement ID obtained before
    the recovery. Retrying only the failed Selenium command is therefore
    incorrect: the page and all dependent elements must be reacquired.
    """
    try:
        return _update_show_details_once(
            driver,
            kinopub_id,
            force=force,
            session_type=session_type,
        )
    except StaleElementReferenceException:
        logging.warning(
            'Browser recovered while updating show %s; reacquiring the page and retrying once.',
            kinopub_id,
        )
        return _update_show_details_once(
            driver,
            kinopub_id,
            force=force,
            session_type=session_type,
        )


def get_chrome_major_version():
    for executable in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']:
        path = shutil.which(executable)
        if path:
            try:
                output = subprocess.check_output([path, '--version'], text=True)
                match = re.search(r'(\d+)\.', output)
                if match:
                    return int(match.group(1))
            except Exception:
                continue
    logging.warning('Could not detect Chrome version automatically')
    return None


def setup_driver(headless=True, profile_key=ParserSessionType.MAIN, randomize=False):
    profile_name = (
        'kinopub-aux' if str(profile_key) == str(ParserSessionType.AUX) else 'kinopub-main'
    )
    initial_url = settings.SITE_AUX_URL if profile_name.endswith('-aux') else settings.SITE_URL
    return RemoteBrowserDriver(
        api_url=settings.BROWSER_GATEWAY_URL,
        token=settings.BROWSER_GATEWAY_TOKEN,
        profile_key=profile_name,
        initial_url=initial_url,
        timeout=settings.BROWSER_GATEWAY_TASK_TIMEOUT_SECONDS,
    )

    # Kept below temporarily as a source reference for the browser settings that
    # were moved to AssetHub. It is unreachable: Kinopub never starts Chromium.
    """
    if headless:
        try:
            subprocess.run(
                ['legacy_process_cleanup'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ['legacy_process_cleanup'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        except Exception:
            pass

    options = legacy_chrome_options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-host=127.0.0.1')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--no-zygote')
    options.add_argument('--disable-async-dns')
    options.add_argument('--js-flags=--max-old-space-size=256')
    options.add_argument('--disk-cache-size=1')
    options.add_argument('--media-cache-size=1')

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--lang=ru-RU,ru')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (X11; Linux x86_64)'
        ' AppleWebKit/537.36 (KHTML, like Gecko)'
        ' Chrome/131.0.0.0 Safari/537.36'
    )

    options.add_argument('--autoplay-policy=user-gesture-required')
    options.add_argument('--mute-audio')
    options.add_argument(
        '--disable-features=PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies'
    )

    if randomize:
        width = random.randint(1024, 1920)
        height = random.randint(768, 1080)
        options.add_argument(f'--window-size={width},{height}')
    else:
        options.add_argument('--window-size=1920,1080')

    options.page_load_strategy = 'eager'
    options.add_experimental_option(
        'prefs',
        {
            'profile.managed_default_content_settings.images': 2,
            'intl.accept_languages': 'ru-RU,ru,en-US,en',
        },
    )

    user_data_dir = os.path.join(tempfile.gettempdir(), f'legacy_browser_data_{profile_key}')
    if os.path.exists(user_data_dir):
        for _ in range(3):
            try:
                shutil.rmtree(user_data_dir, ignore_errors=True)
                if not os.path.exists(user_data_dir):
                    break
                time.sleep(1)
            except Exception:
                pass

    source_legacy_driver = None
    if os.path.exists('/home/app/bin/legacy-driver'):
        source_legacy_driver = '/home/app/bin/legacy-driver'
    elif os.path.exists('/usr/bin/legacy-driver'):
        source_legacy_driver = '/usr/bin/legacy-driver'

    driver_executable_path = None
    if source_legacy_driver:
        unique_driver_path = os.path.join(tempfile.gettempdir(), f'legacy_driver_{profile_key}')
        try:
            if os.path.exists(unique_driver_path):
                os.remove(unique_driver_path)
            shutil.copy(source_legacy_driver, unique_driver_path)
            os.chmod(unique_driver_path, 0o755)
            driver_executable_path = unique_driver_path
        except Exception as e:
            logging.error(f'Failed to copy legacy driver for {profile_key}: {e}')
            driver_executable_path = source_legacy_driver

    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')

    browser_executable_path = '/usr/bin/chromium'
    if not os.path.exists(browser_executable_path):
        browser_executable_path = None

    chrome_version = get_chrome_major_version()

    driver = legacy_chrome(
        options=options,
        browser_executable_path=browser_executable_path,
        driver_executable_path=driver_executable_path,
        user_data_dir=user_data_dir,
        version_main=chrome_version,
    )

    # Блокировка загрузки медиа-файлов на сетевом уровне
    driver.execute_cdp_cmd('Network.enable', {})
    driver.execute_cdp_cmd(
        'Network.setBlockedURLs',
        {
            'urls': [
                '*.mp4',
                '*.m3u8',
                '*.ts',
                '*.webm',
                '*.mp3',
                '*.aac',
                '*.png',
                '*.jpg',
                '*.jpeg',
                '*.gif',
                '*.svg',
                '*.woff',
                '*.woff2',
            ]
        },
    )

    driver.set_page_load_timeout(60)
    return driver
    """


def save_cookies(driver, file_path):
    if hasattr(driver, 'persist_cookies'):
        driver.persist_cookies()
        return
    raise RuntimeError('local cookie persistence is disabled; use AssetHub browser gateway')


LOGIN_INPUT_SELECTORS = (
    (By.ID, 'login-form-login'),
    (By.CSS_SELECTOR, 'form#login-form input[name="login-form[login]"]'),
)
PASSWORD_INPUT_SELECTORS = (
    (By.ID, 'login-form-password'),
    (By.CSS_SELECTOR, 'form#login-form input[name="login-form[password]"]'),
)
CODE_INPUT_SELECTORS = (
    (By.ID, 'login-form-formcode'),
    (By.CSS_SELECTOR, 'form#login-form input[name="login-form[formcode]"]'),
    (By.CSS_SELECTOR, 'form#login-form input[id*="formcode"]'),
    (By.CSS_SELECTOR, 'form#login-form input[name*="code"]'),
)
SUBMIT_SELECTORS = (
    (By.CSS_SELECTOR, '#login-form button[type="submit"]'),
    (By.CSS_SELECTOR, 'form#login-form input[type="submit"]'),
)
RESEND_CODE_SELECTORS = (
    (By.ID, 'resend-code'),
    (By.CSS_SELECTOR, '#login-form button[name="login-form[resend]"]'),
)


def _is_login_url(current_url, login_url):
    """Compare login paths without being fooled by query strings or slashes."""
    try:
        return urlparse(current_url).path.rstrip('/') == urlparse(login_url).path.rstrip('/')
    except (TypeError, ValueError):
        return login_url.rstrip('/') in str(current_url).rstrip('/')


def _find_first_element(driver, selectors, visible=False):
    for by, selector in selectors:
        try:
            elements = driver.find_elements(by, selector)
            for element in elements:
                if not visible or element.is_displayed():
                    return element
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return None


def _login_error_text(driver):
    """Return a short, non-sensitive validation error from the login page."""
    texts = []
    for by, selector in (
        (By.CSS_SELECTOR, '#login-form .help-block'),
        (By.CSS_SELECTOR, '#login-form .alert-danger'),
        (By.CSS_SELECTOR, '#login-form .error-summary'),
    ):
        try:
            for element in driver.find_elements(by, selector):
                value = ' '.join(element.text.split())
                if value and value not in texts:
                    texts.append(value)
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return ' | '.join(texts)[:500]


def _login_diagnostics(driver):
    """Collect safe diagnostics; never include input values or page HTML."""
    try:
        current_url = driver.current_url
    except Exception as exc:
        current_url = f'<unavailable: {type(exc).__name__}>'
    try:
        title = driver.title
    except Exception as exc:
        title = f'<unavailable: {type(exc).__name__}>'
    error_text = _login_error_text(driver)
    diagnostics = f'url={current_url!r}, title={title!r}'
    if error_text:
        diagnostics += f', form_error={error_text!r}'
    return diagnostics


def _submit_two_factor_code(driver, code_input, submit_btn, code):
    """Submit 2FA through the form, with a browser-input fallback.

    Some Chromium/remote-driver combinations report a successful click while
    the page's JS-backed input has not received the value.  The direct form
    submission keeps the server-side CSRF/session fields and avoids relying on
    the submit button's click handler.
    """
    normalized_code = str(code).strip()
    code_input.clear()
    code_input.send_keys(normalized_code)

    try:
        entered_value = code_input.get_attribute('value')
    except Exception:
        entered_value = None

    if entered_value != normalized_code:
        try:
            driver.execute_script(
                """
                const input = arguments[0];
                const value = arguments[1];
                input.value = value;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
                """,
                code_input,
                normalized_code,
            )
        except Exception:
            logging.debug('Could not synchronize the 2FA input value through JavaScript.')

    try:
        driver.execute_script(
            """
            const input = arguments[0];
            const button = arguments[1];
            if (!input.form) throw new Error('2FA input has no form');
            if (input.form.requestSubmit) {
                input.form.requestSubmit(button);
            } else {
                input.form.submit();
            }
            """,
            code_input,
            submit_btn,
        )
    except Exception:
        # Keep compatibility with a local Selenium driver or an older gateway
        # that cannot marshal WebElement arguments into execute_script.
        submit_btn.click()


def _click_resend_code_if_available(driver):
    """Ask Kinopub for one fresh code after a rejected code."""
    # The button is rendered by Kinopub's JS and the remote AssetHub worker
    # can return an element reference whose click does not reach the page's
    # event handler.  Prefer a fresh DOM lookup and keep a JS fallback.
    resend_btn = _find_first_element(driver, RESEND_CODE_SELECTORS, visible=False)
    if resend_btn is None:
        return False
    try:
        result = driver.execute_script(
            """
            const button = document.querySelector('#resend-code') ||
                document.querySelector('#login-form button[name="login-form[resend]"]');
            if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true' ||
                button.offsetParent === null) {
                return false;
            }
            button.click();
            return true;
            """
        )
        if result is True:
            return True

        # Compatibility fallback for an older gateway that cannot execute
        # JavaScript on the current page.
        if resend_btn.is_displayed() and resend_btn.is_enabled():
            resend_btn.click()
            return True
        return False
    except (NoSuchElementException, StaleElementReferenceException):
        return False
    except Exception as exc:
        logging.debug('Could not click Kinopub 2FA resend button: %s', exc)
        return False


def _wait_for_login_state(driver, login_url, timeout=20):
    """Wait for success, a 2FA form, or a server-side form validation error."""
    def state(_driver):
        try:
            current_url = _driver.current_url
            if not _is_login_url(current_url, login_url):
                return 'authenticated'
            if _find_first_element(_driver, CODE_INPUT_SELECTORS, visible=True):
                return '2fa'
            if _login_error_text(_driver):
                return 'rejected'
        except (NoSuchElementException, StaleElementReferenceException):
            return False
        return False

    try:
        return WebDriverWait(driver, timeout, poll_frequency=1).until(state)
    except TimeoutException:
        return 'timeout'


def do_login(driver, login, password, cookie_path, base_url):
    login_url = f'{base_url.rstrip("/")}/user/login'

    if is_cloudflare_page(driver):
        logging.warning('Обнаружена защита Cloudflare на странице входа.')

    try:
        wait = WebDriverWait(driver, 30, poll_frequency=1)
        login_input = wait.until(lambda d: _find_first_element(d, LOGIN_INPUT_SELECTORS))
        password_input = wait.until(lambda d: _find_first_element(d, PASSWORD_INPUT_SELECTORS))
        submit_btn = wait.until(
            lambda d: next(
                (
                    element
                    for element in (
                        _find_first_element(d, (selector,), visible=True)
                        for selector in SUBMIT_SELECTORS
                    )
                    if element and element.is_enabled()
                ),
                None,
            )
        )

        login_input.clear()
        login_input.send_keys(login)
        password_input.clear()
        password_input.send_keys(password)
        time.sleep(1)
        login_attempt_started_at = timezone.now()
        submit_btn.click()

        state = _wait_for_login_state(driver, login_url)
        if state == 'authenticated':
            logging.info('Authorization successful.')
            save_cookies(driver, cookie_path)
            return True

        if state == '2fa':
            logging.info('2FA code is required. Waiting for code from email processor...')

            timeout = 180
            start_time = time.time()
            used_code_ids = set()
            resend_attempts = 0
            max_resend_attempts = 1
            next_resend_at = start_time + 55
            resend_requested = False
            resend_wait_logged = False
            expiration_threshold = timezone.now() - timedelta(
                minutes=settings.CODE_LIFETIME_MINUTES
            )
            code_wait_threshold = max(expiration_threshold, login_attempt_started_at)

            while time.time() - start_time < timeout:
                if not _is_login_url(driver.current_url, login_url):
                    break

                if resend_requested and resend_attempts < max_resend_attempts:
                    if time.time() >= next_resend_at:
                        if _click_resend_code_if_available(driver):
                            resend_attempts += 1
                            resend_requested = False
                            resend_wait_logged = False
                            logging.info(
                                'Requested a fresh Kinopub 2FA code after rejection.'
                            )
                        else:
                            # Kinopub keeps the button disabled for a short
                            # cooldown. Retry the button independently of the
                            # next email arriving so a rejected code cannot
                            # leave the session waiting forever.
                            next_resend_at = time.time() + 5
                            if not resend_wait_logged:
                                logging.info(
                                    'Kinopub 2FA resend button is not ready yet; retrying.'
                                )
                                resend_wait_logged = True

                code_obj = (
                    Code.objects.filter(
                        # ``received_at`` is the mail's Date header and can
                        # lag behind insertion when the listener reconnects.
                        # ``created_at`` prevents a delayed old message from
                        # being selected for this login attempt.
                        created_at__gte=login_attempt_started_at,
                        received_at__gte=code_wait_threshold,
                    )
                    .order_by('-received_at')
                    .first()
                )
                if code_obj and code_obj.id not in used_code_ids:
                    code_id, code = code_obj.id, code_obj.code
                    logging.info('Found 2FA code %s in database. Attempting to use it.', code)
                    try:
                        used_code_ids.add(code_id)
                        code_input = _find_first_element(driver, CODE_INPUT_SELECTORS, visible=True)
                        if code_input is None:
                            logging.warning(
                                '2FA form disappeared before code %s could be submitted.', code
                            )
                            resend_requested = resend_attempts < max_resend_attempts
                            try:
                                driver.refresh()
                                _wait_for_login_state(driver, login_url, timeout=10)
                            except Exception as refresh_error:
                                logging.warning(
                                    'Could not restore the 2FA form after refresh: %s',
                                    refresh_error,
                                )
                            continue
                        submit_btn = _find_first_element(driver, SUBMIT_SELECTORS, visible=True)
                        if submit_btn is None:
                            logging.warning('2FA submit button is no longer available.')
                            continue
                        _submit_two_factor_code(driver, code_input, submit_btn, code)
                        state = _wait_for_login_state(driver, login_url, timeout=15)

                        if state == 'authenticated':
                            logging.info('Code %s was accepted.', code)
                            break
                        else:
                            error_text = _login_error_text(driver)
                            logging.warning(
                                'Code %s was not accepted%s. Waiting for a new one.',
                                code,
                                f' ({error_text})' if error_text else '',
                            )
                            if resend_attempts < max_resend_attempts:
                                resend_requested = True
                    except Exception as e:
                        logging.warning(
                            'Could not use code %s. It might be stale. Error: %s', code, e
                        )
                time.sleep(2)

        if _is_login_url(driver.current_url, login_url):
            raise TimeoutException(
                'Login did not leave the login page. ' + _login_diagnostics(driver)
            )

        logging.info('Authorization successful.')
        save_cookies(driver, cookie_path)
        return True

    except TimeoutException as exc:
        try:
            title = driver.title
        except Exception:
            title = ''
        if 'Один момент' in title or 'Just a moment' in title:
            logging.error('Не удалось пройти проверку Cloudflare.')
        else:
            logging.error(
                'Login timed out or was rejected: %s. Diagnostics: %s',
                exc,
                _login_diagnostics(driver),
            )
        return False
    except Exception as e:
        logging.error(
            'Unexpected login error: %s. Diagnostics: %s',
            e,
            _login_diagnostics(driver),
            exc_info=True,
        )
        return False


def initialize_driver_session(headless=True, session_type=ParserSessionType.MAIN):
    logging.info(f'Initializing Selenium driver session (Type: {session_type})...')

    if session_type == ParserSessionType.AUX:
        target_url = settings.SITE_AUX_URL
        login = settings.KINOPUB_AUX_LOGIN
        password = settings.KINOPUB_AUX_PASSWORD
        randomize = True
    else:
        target_url = settings.SITE_URL
        login = settings.KINOPUB_LOGIN
        password = settings.KINOPUB_PASSWORD
        randomize = False

    if not settings.BROWSER_GATEWAY_URL or not settings.BROWSER_GATEWAY_TOKEN:
        raise RuntimeError(
            'BROWSER_GATEWAY_URL and BROWSER_GATEWAY_TOKEN are required; '
            'local Chromium is no longer supported'
        )

    driver = None
    try:
        driver = setup_driver(headless=headless, profile_key=session_type, randomize=randomize)
        navigate_with_empty_page_recovery(driver, target_url)
        try:
            WebDriverWait(driver, 5).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[href*='/user/logout']")
                )
            )
            logging.info('Session is valid.')
            return driver
        except TimeoutException:
            logging.warning('Session is invalid or expired. Attempting to log in...')
            navigate_with_empty_page_recovery(driver, f'{target_url}user/login')
            if do_login(driver, login, password, None, target_url):
                return driver
            else:
                logging.error('Login process failed. Unable to establish a session.')
                close_driver(driver)
                return None
    except Exception as e:
        logging.error(
            'An unexpected error occurred during session initialization: %s', e, exc_info=True
        )
        close_driver(driver)
        return None


def _extract_js_data(driver, var_name, regex_pattern):
    try:
        data = driver.execute_script(f'return window.{var_name};')
        if data:
            return data
    except Exception:
        pass

    scripts = driver.find_elements(By.TAG_NAME, 'script')
    for script in scripts:
        try:
            content = script.get_attribute('innerHTML')
            if not content:
                continue
            match = re.search(regex_pattern, content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except (Exception, json.JSONDecodeError):
            continue
    return None


def _fetch_playlist_data(driver, url, session_type='main'):
    logging.info(f'Requesting playlist data from {url}...')
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver = open_url_safe(driver, url, session_type=session_type)
            time.sleep(3)

            data = _extract_js_data(
                driver, 'PLAYER_PLAYLIST', r'window\.PLAYER_PLAYLIST\s*=\s*(\[.*?\]);'
            )

            if data:
                return data

            if attempt < max_retries - 1:
                logging.warning(f'Playlist variable not found on {url}. Retrying...')
                time.sleep(5)
                continue
            logging.warning(f'Could not find PLAYER_PLAYLIST for {url}')
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f'Retry {attempt + 1} for playlist {url} due to: {e}')
                time.sleep(5)
                continue
            logging.error(
                f'Error getting playlist data from {url} after {max_retries} attempts: {e}'
            )
    return None


def get_movie_duration_and_save(driver, show, session_type='main'):
    if isinstance(show, int):
        show = Show.objects.get(id=show)

    if not show.kinopub_id:
        logging.warning(f'Show ID {show.id} has no kinopub_id. Skipping duration fetch.')
        return

    base_url = settings.SITE_URL if session_type == 'main' else settings.SITE_AUX_URL
    movie_url = f'{base_url.rstrip("/")}/item/play/{show.kinopub_id}/s0e1'
    playlist_data = _fetch_playlist_data(driver, movie_url, session_type=session_type)

    if playlist_data:
        duration_sec = None
        for item in playlist_data:
            if item.get('duration'):
                duration_sec = item['duration']
                break

        if duration_sec:
            upsert_show_duration(
                show=show,
                season_number=None,
                episode_number=None,
                duration_seconds=duration_sec,
                is_estimated=False,
            )
            logging.info('Cached duration for movie id%d: %d seconds.', show.id, duration_sec)
        else:
            logging.warning('Playlist data found but duration is missing for %s', movie_url)
    else:
        logging.warning('Could not fetch playlist data for movie %s', movie_url)


def get_season_durations_and_save(driver, show, season, session_type='main'):
    if isinstance(show, int):
        show = Show.objects.get(id=show)

    if not show.kinopub_id:
        logging.warning(f'Show ID {show.id} has no kinopub_id. Skipping season duration fetch.')
        return

    base_url = settings.SITE_URL if session_type == 'main' else settings.SITE_AUX_URL
    episode_url = f'{base_url.rstrip("/")}/item/play/{show.kinopub_id}/s{season}e1'
    playlist_data = _fetch_playlist_data(driver, episode_url, session_type=session_type)

    if not playlist_data:
        return

    updated_count = 0
    for item in playlist_data:
        item_season = item.get('season')
        item_episode = item.get('episode')
        duration_sec = item.get('duration')

        if item_season == season and item_episode is not None and duration_sec is not None:
            upsert_show_duration(
                show=show,
                season_number=item_season,
                episode_number=item_episode,
                duration_seconds=duration_sec,
                is_estimated=False,
            )
            updated_count += 1

    if updated_count > 0:
        logging.info(
            'Cached/updated %d episode durations for show id%d, season %d.',
            updated_count,
            show.id,
            season,
        )
    else:
        logging.warning('No episodes found in playlist for show id%d season %d', show.id, season)


def parse_and_save_history(driver, mode, latest_db_date=None, session_type='main'):
    wait = WebDriverWait(driver, 20)
    wait.until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '.item-list')))

    stop_parsing = False
    latest_date_in_db = None
    if latest_db_date:
        latest_date_in_db = datetime.strptime(latest_db_date, DATE_FORMAT).date()

    views_on_page = []
    item_blocks = driver.find_elements(By.CSS_SELECTOR, '.item-list .col-md-3')
    for block in reversed(item_blocks):
        try:
            date_header = block.find_element(By.XPATH, 'preceding-sibling::h4[1]')
            year = date_header.find_element(By.TAG_NAME, 'small').text.strip()
            match = re.match(r'(\d{1,2})\s+([А-Яа-яA-Za-z]+)', date_header.text)
            formatted_date = f'{year}-{MONTHS_MAP[match.group(2)]}-{match.group(1).zfill(2)}'
            current_date_from_site = datetime.strptime(formatted_date, DATE_FORMAT).date()

            if latest_date_in_db and current_date_from_site < latest_date_in_db:
                if not stop_parsing:
                    logging.info(
                        (
                            'Found a date (%s) older than the latest in DB (%s).'
                            ' Will stop after this page.'
                        ),
                        current_date_from_site,
                        latest_date_in_db,
                    )
                stop_parsing = True

            link_element = block.find_element(By.CSS_SELECTOR, '.item-title a')
            title = link_element.text.strip()
            href = link_element.get_attribute('href')
            kinopub_id = int(re.search(r'/item/view/(\d+)', href).group(1))

            try:
                original_title = block.find_element(By.CSS_SELECTOR, '.item-author a').text.strip()
            except NoSuchElementException:
                original_title = title
            if not original_title:
                original_title = title

            season, episode = 0, 0
            item_type = (
                SHOW_TYPE_MAPPING[ShowType.MOVIE]
                if mode == 'movies'
                else SHOW_TYPE_MAPPING[ShowType.SERIES]
            )

            if mode == 'episodes':
                try:
                    season_episode_text = block.find_element(
                        By.CSS_SELECTOR, '.topleft-2x .label-success'
                    ).text.strip()
                    season_episode_match = re.search(
                        r'Сезон (\d+)\. Эпизод (\d+)', season_episode_text
                    )
                    if season_episode_match:
                        season = int(season_episode_match.group(1))
                        episode = int(season_episode_match.group(2))
                        if season == 0:
                            continue
                except NoSuchElementException:
                    item_type = SHOW_TYPE_MAPPING[ShowType.MOVIE]

            views_on_page.append(
                {
                    'kinopub_id': kinopub_id,
                    'title': title,
                    'original_title': original_title,
                    'view_date': current_date_from_site,
                    'season': season,
                    'episode': episode,
                    'type': item_type,
                }
            )
        except Exception as e:
            logging.error('Error parsing a view block: %s', e)

    kinopub_ids_on_page = list({item['kinopub_id'] for item in views_on_page})
    existing_shows = {
        s.kinopub_id: s for s in Show.objects.filter(kinopub_id__in=kinopub_ids_on_page)
    }

    shows_to_create = []
    for item in views_on_page:
        kinopub_id = item['kinopub_id']
        if kinopub_id not in existing_shows:
            shows_to_create.append(
                Show(
                    kinopub_id=kinopub_id,
                    title=item['title'],
                    original_title=item['original_title'],
                    type=item['type'],
                )
            )
            existing_shows[kinopub_id] = None

    if shows_to_create:
        Show.objects.bulk_create(shows_to_create, ignore_conflicts=True)

    db_shows = {s.kinopub_id: s.id for s in Show.objects.filter(kinopub_id__in=kinopub_ids_on_page)}

    for item in views_on_page:
        item['show_id'] = db_shows[item['kinopub_id']]

    unique_show_ids = list({item['show_id'] for item in views_on_page})
    enqueue_show_update(unique_show_ids, details=True, durations=False, ratings=True)

    q_objects = Q()
    for item in views_on_page:
        q_objects |= Q(
            show_id=item['show_id'],
            view_date=item['view_date'],
            season_number=item['season'],
            episode_number=item['episode'],
        )

    existing_set = set()
    if q_objects:
        existing_set = set(
            ViewHistory.objects.filter(q_objects).values_list(
                'show_id', 'view_date', 'season_number', 'episode_number'
            )
        )

    new_views_to_create = []
    for item in views_on_page:
        key = (item['show_id'], item['view_date'], item['season'], item['episode'])
        if key not in existing_set:
            new_views_to_create.append(
                ViewHistory(
                    show_id=item['show_id'],
                    view_date=item['view_date'],
                    season_number=item['season'],
                    episode_number=item['episode'],
                    source=ViewHistory.SOURCE_KINOPUB,
                )
            )
            existing_set.add(key)

    created_views = []
    if new_views_to_create:
        created_views = ViewHistory.objects.bulk_create(new_views_to_create)

    views_added = len(created_views)

    for view in created_views:
        view_history_created.send(sender=ViewHistory, instance=view)

    three_months_ago = timezone.now() - timedelta(days=90)
    existing_durations_qs = ShowDuration.objects.filter(
        show_id__in=[item['show_id'] for item in views_on_page]
    )
    duration_map = {
        (d.show.id, d.season_number, d.episode_number): d.updated_at for d in existing_durations_qs
    }

    seasons_to_fetch = defaultdict(list)
    unique_movie_ids_to_fetch = set()
    for item in views_on_page:
        show_id, season, episode = item['show_id'], item['season'], item['episode']
        is_movie = item['type'] == SHOW_TYPE_MAPPING[ShowType.MOVIE]

        key = (show_id, None, None) if is_movie else (show_id, season, episode)
        updated_at = duration_map.get(key)

        if not updated_at or updated_at < three_months_ago:
            if updated_at:
                logging.info(
                    f'Duration for show id={show_id} ({format_se(season, episode)}) is stale.'
                    f' Re-fetching.'
                )
            if is_movie:
                unique_movie_ids_to_fetch.add(show_id)
            else:
                seasons_to_fetch[(show_id, season)].append(item)

    if unique_movie_ids_to_fetch:
        logging.info(
            'Need to fetch duration data for %d movie(s).',
            len(unique_movie_ids_to_fetch),
        )
        for show_id in unique_movie_ids_to_fetch:
            get_movie_duration_and_save(driver, show_id, session_type=session_type)

    if seasons_to_fetch:
        logging.info('Need to fetch duration data for %d season(s).', len(seasons_to_fetch))
        for (show_id, season), _ in seasons_to_fetch.items():
            get_season_durations_and_save(driver, show_id, season, session_type=session_type)

    return views_added, stop_parsing


def get_latest_view_date_orm(mode: str):
    if mode == 'episodes':
        qs = ViewHistory.objects.filter(season_number__gt=0)
    elif mode == 'movies':
        qs = ViewHistory.objects.filter(season_number=0)
    else:
        logging.error("Unknown mode '%s' for getting latest view date.", mode)
        return None

    result = qs.aggregate(max_date=Max('view_date'))
    if result and result['max_date']:
        max_date_str = result['max_date'].strftime(DATE_FORMAT)
        logging.info("Latest view date for '%s' in DB: %s", mode, max_date_str)
        return max_date_str
    else:
        logging.info("No view history found for mode '%s'. A full scan will be performed.", mode)
        return None


def open_url_safe(driver, url, headless=True, session_type=ParserSessionType.MAIN):
    navigate_with_empty_page_recovery(driver, url)
    try:
        if is_cloudflare_page(driver):
            logging.warning(f'Обнаружена защита Cloudflare на {url}. Перезапуск сессии...')
            driver.restart()
            time.sleep(10)

            navigate_with_empty_page_recovery(driver, url)
            if is_cloudflare_page(driver):
                close_driver(driver)
                raise Exception('Защита Cloudflare срабатывает повторно после перезапуска.')
            return driver

        if '/user/login' in driver.current_url and '/user/login' not in url:
            logging.warning('Сессия истекла (редирект на логин). Попытка повторной авторизации...')

            login = (
                settings.KINOPUB_LOGIN
                if session_type == ParserSessionType.MAIN
                else settings.KINOPUB_AUX_LOGIN
            )
            password = (
                settings.KINOPUB_PASSWORD
                if session_type == ParserSessionType.MAIN
                else settings.KINOPUB_AUX_PASSWORD
            )
            base_url = (
                settings.SITE_URL
                if session_type == ParserSessionType.MAIN
                else settings.SITE_AUX_URL
            )

            if do_login(driver, login, password, None, base_url):
                logging.info('Авторизация восстановлена. Переход к целевому URL.')
                navigate_with_empty_page_recovery(driver, url)
            else:
                raise Exception('Не удалось восстановить сессию через do_login.')

    except Exception as e:
        logging.error(f'Ошибка при проверке состояния страницы: {e}')
        raise
    return driver


def _run_parser_for_mode(driver, mode, headless=True, session_type='main'):
    if mode == 'episodes':
        history_url = f'{settings.SITE_URL}history/index/{settings.KINOPUB_LOGIN}/episodes'
        logging.info('Parsing mode: TV Show EPISODES')
    elif mode == 'movies':
        history_url = f'{settings.SITE_URL}history/index/{settings.KINOPUB_LOGIN}'
        logging.info('Parsing mode: MOVIES')
    else:
        logging.error("Invalid parsing mode '%s'. Aborting.", mode)
        return 0, driver

    logging.info('Navigating to history page: %s', history_url)
    driver = open_url_safe(driver, history_url, headless, session_type)

    try:
        body_text = driver.find_element(By.TAG_NAME, 'body').text
        if 'Для доступа к этой странице нужен PRO-аккаунт' in body_text:
            logging.error(
                'Failed to access history page: PRO account is required. Aborting scan for "%s".',
                mode,
            )
            return 0, driver
    except Exception:
        pass

    total_pages = get_total_pages(driver)
    logging.info("Found %d pages to parse for mode '%s'.", total_pages, mode)

    latest_db_date = get_latest_view_date_orm(mode)
    total_views_added = 0

    for page in range(1, total_pages + 1):
        try:
            page_url = f'{history_url}?page={page}&per-page=50'
            if driver.current_url != page_url:
                driver = open_url_safe(driver, page_url, headless, session_type)
                time.sleep(1)

            logging.info('Parsing page %d/%d...', page, total_pages)
            added_count, stop_parsing = parse_and_save_history(driver, mode, latest_db_date)

            if added_count > 0:
                logging.info('Added %d new view records from page %d.', added_count, page)
                total_views_added += added_count

            if stop_parsing:
                logging.info(
                    "Stopping the process for mode '%s' as existing database entries were reached.",
                    mode,
                )
                break

            if page < total_pages:
                time.sleep(2)
        except Exception as e:
            logging.error(
                "A critical error occurred while parsing page %d for mode '%s': %s",
                page,
                mode,
                e,
            )
            continue

    logging.info("--- Finished parsing for '%s'. Added %d records. ---", mode, total_views_added)
    return total_views_added, driver


def get_total_pages(driver):
    try:
        pagination = driver.find_element(By.CSS_SELECTOR, 'ul.pagination')
        last_page_link = pagination.find_element(By.CSS_SELECTOR, 'li.last a')
        href = last_page_link.get_attribute('href')
        match = re.search(r'page=(\d+)', href)
        return int(match.group(1)) if match else 1
    except NoSuchElementException:
        return 1


def run_parser_session(headless=True, driver_instance=None):
    logging.info('--- Starting Kinopub History Parser Session ---')
    driver = driver_instance
    try:
        if driver is None:
            driver = initialize_driver_session(headless=headless)

        if driver is None:
            message = 'Failed to initialize or use provided driver. Aborting parser run.'
            logging.error(message)
            raise RuntimeError(message)

        episodes_added, driver = _run_parser_for_mode(driver, 'episodes', headless=headless)
        movies_added, driver = _run_parser_for_mode(driver, 'movies', headless=headless)

        total_views_added = episodes_added + movies_added
        if total_views_added > 0:
            logging.info(
                (
                    '--- Parser session finished. '
                    'Total new records added: %d. A database backup will be scheduled. ---'
                ),
                total_views_added,
            )
            BackupManager().schedule_backup()
        else:
            logging.info('--- Parser session finished. No new records added. ---')

    except Exception as e:
        logging.error('An unexpected error occurred in the parser session: %s', e)
        raise
    finally:
        close_driver(driver)


def process_show_durations(driver, show, session_type='main'):
    if not show.kinopub_id:
        logging.warning(f'Show ID {show.id} has no kinopub_id. Skipping duration fetch.')
        return

    if show.type not in SERIES_TYPES:
        get_movie_duration_and_save(driver, show.id, session_type=session_type)
    else:
        try:
            base_url = settings.SITE_URL if session_type == 'main' else settings.SITE_AUX_URL
            player_url = f'{base_url.rstrip("/")}/item/play/{show.kinopub_id}/s1e1'
            logging.info(f'Navigating to player to fetch seasons list: {player_url}')

            driver = open_url_safe(driver, player_url, session_type=session_type)
            time.sleep(3)

            seasons_data = _extract_js_data(
                driver, 'PLAYER_SEASONS', r'window\.PLAYER_SEASONS\s*=\s*(\[.*?\]);'
            )

            seasons = set()
            if seasons_data:
                for item in seasons_data:
                    if 'season' in item:
                        seasons.add(int(item['season']))
            else:
                logging.warning(
                    f'Could not extract seasons for show {show.id}. Defaulting to season 1.'
                )
                seasons.add(1)

            logging.info(f'Found seasons {sorted(list(seasons))} for show {show.id}')

            for season in sorted(list(seasons)):
                get_season_durations_and_save(driver, show.id, season, session_type=session_type)

        except Exception as e:
            logging.error(f'Error processing seasons for show {show.id}: {e}')


def parse_new_episodes_list(driver):
    """
    Parses the /media/new-serial-episodes page table.
    Returns a list of dictionaries with basic episode info.
    """
    episodes = []
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, 'table.table tbody tr')
        logging.debug(f'Found {len(rows)} rows on new episodes page.')

        for row in rows:
            try:
                # Extract URL from onclick attribute or first link
                onclick_attribute = row.get_attribute('onclick')
                href = None

                if onclick_attribute and 'document.location' in onclick_attribute:
                    # Extract URL from: document.location = '/path/...'
                    match = re.search(r"['\"]([^'\"]+)['\"]", onclick_attribute)
                    if match:
                        href = match.group(1)

                if not href:
                    # Fallback to link inside row
                    try:
                        link_element = row.find_element(By.TAG_NAME, 'a')
                        href = link_element.get_attribute('href')
                    except NoSuchElementException:
                        continue

                # Parse ID, Season, Episode from URL: /item/view/104191/s2e3/Daddy-Issues
                # Regex must handle: /item/view/<id>/s<S>e<E>...
                url_match_result = re.search(r'/item/view/(\d+)/s(\d+)e(\d+)', href)
                if not url_match_result:
                    continue

                show_id = int(url_match_result.group(1))
                season_num = int(url_match_result.group(2))
                episode_num = int(url_match_result.group(3))

                # Parse Titles
                try:
                    title_cell = row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)')
                    title_element = title_cell.find_element(By.TAG_NAME, 'b')
                    title = title_element.text.strip()

                    full_text = title_cell.text
                    original_title = full_text.replace(title, '').strip()
                    if not original_title:
                        original_title = title
                except NoSuchElementException:
                    title = f'Show {show_id}'
                    original_title = title

                episodes.append(
                    {
                        'show_id': show_id,
                        'title': title,
                        'original_title': original_title,
                        'season': season_num,
                        'episode': episode_num,
                        'href': href,
                    }
                )

            except Exception as e:
                logging.error(f'Error parsing row in new episodes list: {e}')
                continue

    except NoSuchElementException:
        logging.warning('Table not found on new episodes page.')

    return episodes
