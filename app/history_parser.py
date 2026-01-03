import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import undetected_chromedriver as uc
from django.conf import settings
from django.db.models import Max, Q
from django.utils import timezone
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from app.gdrive_backup import BackupManager
from app.models import Code, Country, Genre, Person, Show, ShowDuration, ViewHistory
from app.signals import view_history_created
from kinopub_parser import celery_app
from shared.constants import (
    DATE_FORMAT,
    MONTHS_MAP,
    SERIES_TYPES,
    SHOW_STATUS_MAPPING,
    SHOW_TYPE_MAPPING,
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


def is_fatal_selenium_error(e):
    """Определяет, является ли ошибка критической для сессии драйвера."""
    err_str = str(e).lower()
    return (
        'driver unresponsive' in err_str
        or 'connection refused' in err_str
        or 'max retries exceeded' in err_str
        or 'invalid session' in err_str
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


def update_show_details(driver, show_id):
    target_path = f'item/view/{show_id}'

    if target_path not in driver.current_url:
        base_url = settings.SITE_URL

        # Пытаемся сохранить текущий домен сессии (для поддержки зеркал/AUX)
        if driver.current_url and driver.current_url.startswith('http'):
            parsed = urlparse(driver.current_url)
            if parsed.netloc:
                base_url = f'{parsed.scheme}://{parsed.netloc}/'

        try:
            driver.get(f'{base_url}{target_path}')
            time.sleep(2)
        except Exception as e:
            logging.error(f'Error navigating to show page {show_id}: {e}')
            return

    try:
        show = Show.objects.get(id=show_id)
        three_months_ago = timezone.now() - timedelta(days=90)
        if show.year is not None and show.updated_at >= three_months_ago:
            return

        logging.info(f'Fetching extended details for show id={show_id}')

        wait = WebDriverWait(driver, 10)
        info_table = wait.until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, 'table.table-striped')
            )
        )

        def get_row_data(text_label):
            try:
                row = info_table.find_element(By.XPATH, f".//tr[td[contains(., '{text_label}')]]")
                return row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)')
            except NoSuchElementException:
                return None

        year_data = get_row_data('Год выхода')
        if year_data:
            show.year = _extract_int_from_string(year_data.text)
            try:
                link = year_data.find_element(By.TAG_NAME, 'a')
                href = link.get_attribute('href')
                types_pattern = '|'.join(SHOW_TYPE_MAPPING.keys())
                type_match = re.search(f'/({types_pattern})', href)
                if type_match:
                    type_key = type_match.group(1)
                    show.type = SHOW_TYPE_MAPPING.get(type_key, type_key.capitalize())
            except NoSuchElementException:
                logging.error(f'Could not find type link for show id={show_id}')

        status_data = get_row_data('Статус')
        if status_data:
            raw_status = status_data.text.strip()
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
                    show.kinopoisk_votes = _extract_int_from_string(votes_element.text)
            except (NoSuchElementException, ValueError):
                pass
            try:
                imdb_link = rating_data.find_element(By.CSS_SELECTOR, "a[href*='imdb.com']")
                show.imdb_url = imdb_link.get_attribute('href')
                show.imdb_rating = float(imdb_link.text)
                votes_element = imdb_link.find_element(By.XPATH, './following-sibling::small')
                show.imdb_votes = _extract_int_from_string(votes_element.text)
            except (NoSuchElementException, ValueError):
                pass

        show.save()

        for label, model, relation in [
            ('Страна', Country, show.countries),
            ('Жанр', Genre, show.genres),
            ('Создатель', Person, show.directors),
            ('Режиссёр', Person, show.directors),
            ('В ролях', Person, show.actors),
        ]:
            elements_data = get_row_data(label)
            if elements_data:
                elements = elements_data.find_elements(By.TAG_NAME, 'a')
                for link_element in elements:
                    name = link_element.text.strip()
                    if name:
                        obj, _ = model.objects.update_or_create(name=name)
                        relation.add(obj)

        show.save()

    except (NoSuchElementException, TimeoutException, Show.DoesNotExist) as e:
        logging.error(
            f'Could not fetch extended details for show id={show_id}. Info table may be missing.',
            exc_info=e,
        )
    except Exception as e:
        logging.error(f'An error occurred while updating show details for id={show_id}: {e}')
        raise


def get_chrome_major_version():
    """Определяет мажорную версию установленного Chromium."""
    try:
        executable = '/usr/bin/chromium'
        if not os.path.exists(executable):
            executable = 'chromium'

        output = subprocess.check_output([executable, '--version'], text=True)
        match = re.search(r'(\d+)\.', output)
        if match:
            return int(match.group(1))
    except Exception as e:
        logging.warning(f'Could not detect Chrome version automatically: {e}')

    return None


def setup_driver(headless=True, profile_key='main', randomize=False):
    if headless:
        try:
            subprocess.run(
                ['pkill', '-f', 'chromium'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ['pkill', '-f', 'chromedriver'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        except Exception:
            pass

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

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

    real_version = get_chrome_major_version()
    logging.info(f'Detected Chrome version: {real_version}')

    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')

        user_data_dir = os.path.join('/data', f'uc_browser_data_{profile_key}')
        if os.path.exists(user_data_dir):
            try:
                shutil.rmtree(user_data_dir)
                logging.info(f'Cleaned up existing user data directory: {user_data_dir}')
            except Exception as e:
                logging.warning(f'Could not clean user data directory: {e}')

        driver_executable_path = None
        if os.path.exists('/home/app/bin/chromedriver'):
            driver_executable_path = '/home/app/bin/chromedriver'
        elif os.path.exists('/usr/bin/chromedriver'):
            driver_executable_path = '/usr/bin/chromedriver'

        driver = uc.Chrome(
            options=options,
            browser_executable_path='/usr/bin/chromium',
            driver_executable_path=driver_executable_path,
            user_data_dir=user_data_dir,
            version_main=real_version,
        )
    else:
        driver = uc.Chrome(options=options, version_main=real_version)

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


def save_cookies(driver, file_path):
    try:
        cookies = driver.get_cookies()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logging.info('Cookies successfully saved to %s', file_path)
        if not settings.LOCAL_RUN:
            celery_app.send_task('app.tasks.backup_cookies')
            logging.info('Cookies backup scheduled via Celery.')
        else:
            logging.info('Local run detected, skipping Celery cookies backup task.')
    except Exception as e:
        logging.error(f'Failed to save cookies to {file_path}: {e}')


def do_login(driver, login, password, cookie_path, base_url):
    login_url = f'{base_url}user/login'

    if is_cloudflare_page(driver):
        logging.warning('Обнаружена защита Cloudflare на странице входа.')

    try:
        wait = WebDriverWait(driver, 30)
        login_input = wait.until(
            expected_conditions.presence_of_element_located((By.ID, 'login-form-login'))
        )
        password_input = wait.until(
            expected_conditions.presence_of_element_located((By.ID, 'login-form-password'))
        )
        submit_btn = wait.until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '#login-form button[type="submit"]')
            )
        )

        login_input.clear()
        login_input.send_keys(login)
        password_input.clear()
        password_input.send_keys(password)
        time.sleep(1)
        submit_btn.click()

        code_input = WebDriverWait(driver, 15).until(
            expected_conditions.presence_of_element_located((By.ID, 'login-form-formcode'))
        )
        logging.info('2FA code is required. Waiting for code from email processor...')

        timeout = 120
        start_time = time.time()
        used_code_ids = set()
        expiration_threshold = timezone.now() - timedelta(minutes=settings.CODE_LIFETIME_MINUTES)

        while time.time() - start_time < timeout:
            if login_url not in driver.current_url:
                break

            code_obj = (
                Code.objects.filter(received_at__gte=expiration_threshold)
                .order_by('-received_at')
                .first()
            )
            if code_obj and code_obj.id not in used_code_ids:
                code_id, code = code_obj.id, code_obj.code
                logging.info('Found 2FA code %s in database. Attempting to use it.', code)
                try:
                    code_input.clear()
                    code_input.send_keys(code)
                    used_code_ids.add(code_id)
                    time.sleep(1)
                    driver.find_element(
                        By.CSS_SELECTOR, '#login-form button[type="submit"]'
                    ).click()
                    time.sleep(3)

                    if login_url not in driver.current_url:
                        logging.info('Code %s was accepted.', code)
                        break
                    else:
                        logging.warning('Code %s was not accepted. Waiting for a new one.', code)
                except Exception as e:
                    logging.warning('Could not use code %s. It might be stale. Error: %s', code, e)
            time.sleep(2)

        if login_url in driver.current_url:
            raise TimeoutException('Timeout expired while waiting for 2FA code.')

        logging.info('Authorization successful.')
        save_cookies(driver, cookie_path)
        return True

    except TimeoutException:
        if 'Один момент' in driver.title or 'Just a moment' in driver.title:
            logging.error('Не удалось пройти проверку Cloudflare.')
        else:
            logging.error(
                'Failed to log in within the allotted time.'
                ' The page might be inaccessible or changed.'
            )
        return False
    except Exception as e:
        logging.error(f'An unexpected error occurred during login: {e}')
        return False


def initialize_driver_session(headless=True, session_type='main'):
    logging.info(f'Initializing Selenium driver session (Type: {session_type})...')

    if session_type == 'aux':
        target_url = settings.SITE_AUX_URL
        login = settings.KINOPUB_AUX_LOGIN
        password = settings.KINOPUB_AUX_PASSWORD
        cookie_path = settings.COOKIES_FILE_PATH_AUX
        randomize = True
    else:
        target_url = settings.SITE_URL
        login = settings.KINOPUB_LOGIN
        password = settings.KINOPUB_PASSWORD
        cookie_path = settings.COOKIES_FILE_PATH_MAIN
        randomize = False

    driver = setup_driver(headless=headless, profile_key=session_type, randomize=randomize)

    try:
        driver.get(target_url)
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, encoding='utf-8') as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    if 'expiry' in cookie and cookie['expiry']:
                        cookie['expiry'] = int(cookie['expiry'])
                    driver.add_cookie(cookie)
                logging.info('Cookies loaded. Refreshing page to validate session...')
                driver.get(target_url)
                time.sleep(2)
            except Exception as e:
                logging.warning(
                    'Failed to load cookies: %s. Clearing all and proceeding to login.',
                    e,
                )
                driver.delete_all_cookies()

        try:
            WebDriverWait(driver, 5).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[href*='/user/logout']")
                )
            )
            logging.info('Session is valid.')
            return driver
        except TimeoutException:
            if os.path.exists(cookie_path):
                logging.warning(
                    'Loaded cookies did not result in a valid session. Deleting cookie file.'
                )
                try:
                    os.remove(cookie_path)
                except OSError as e:
                    logging.error(f'Failed to delete stale cookie file: {e}')
            logging.warning('Session is invalid or expired. Attempting to log in...')
            driver.get(f'{target_url}user/login')
            if do_login(driver, login, password, cookie_path, target_url):
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


def _fetch_playlist_data(driver, url):
    logging.info(f'Requesting playlist data from {url}...')
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(
            expected_conditions.presence_of_element_located(
                (By.XPATH, '//script[contains(text(), "window.PLAYER_PLAYLIST")]')
            )
        )
        script_element = driver.find_element(
            By.XPATH, '//script[contains(text(), "window.PLAYER_PLAYLIST")]'
        )
        script_text = script_element.get_attribute('innerHTML')
        match = re.search(r'window\.PLAYER_PLAYLIST\s*=\s*(\[.*?\]);', script_text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        logging.warning(f'Could not find PLAYER_PLAYLIST JSON for {url}')
    except Exception as e:
        logging.error(f'Error getting playlist data from {url}: {e}')
    return None


def get_movie_duration_and_save(driver, show_id):
    movie_url = f'{settings.SITE_URL}item/play/{show_id}/s0e1'
    playlist_data = _fetch_playlist_data(driver, movie_url)

    if playlist_data and 'duration' in playlist_data[0]:
        duration_sec = playlist_data[0]['duration']
        ShowDuration.objects.update_or_create(
            show_id=show_id,
            season_number=None,
            episode_number=None,
            defaults={'duration_seconds': duration_sec},
        )
        logging.info('Cached duration for movie id%d: %d seconds.', show_id, duration_sec)
    elif playlist_data:
        logging.warning('Playlist data empty or missing duration for movie %s', movie_url)


def get_season_durations_and_save(driver, show_id, season):
    episode_url = f'{settings.SITE_URL}item/play/{show_id}/s{season}e1'
    playlist_data = _fetch_playlist_data(driver, episode_url)

    if not playlist_data:
        return

    updated_count = 0
    for item in playlist_data:
        item_season = item.get('season')
        item_episode = item.get('episode')
        duration_sec = item.get('duration')

        if item_season == season and item_episode is not None and duration_sec is not None:
            ShowDuration.objects.update_or_create(
                show_id=show_id,
                season_number=item_season,
                episode_number=item_episode,
                defaults={'duration_seconds': duration_sec},
            )
            updated_count += 1

    if updated_count > 0:
        logging.info(
            'Cached/updated %d episode durations for show id%d, season %d.',
            updated_count,
            show_id,
            season,
        )
    else:
        logging.warning('No episodes found in playlist for show id%d season %d', show_id, season)


def parse_and_save_history(driver, mode, latest_db_date=None):
    wait = WebDriverWait(driver, 20)
    wait.until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '.item-list')))

    stop_parsing = False
    latest_date_in_db = None
    if latest_db_date:
        latest_date_in_db = datetime.strptime(latest_db_date, DATE_FORMAT).date()

    views_on_page = []
    item_blocks = driver.find_elements(By.CSS_SELECTOR, '.item-list .col-md-3')
    for block in item_blocks:
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
            show_id = int(re.search(r'/item/view/(\d+)', href).group(1))

            try:
                original_title = block.find_element(By.CSS_SELECTOR, '.item-author a').text.strip()
            except NoSuchElementException:
                original_title = title
            if not original_title:
                original_title = title

            season, episode = 0, 0
            item_type = 'Movie' if mode == 'movies' else 'Series'

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
                    item_type = 'Movie'

            views_on_page.append(
                {
                    'show_id': show_id,
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

    shows_to_create = [
        Show(
            id=item['show_id'],
            title=item['title'],
            original_title=item['original_title'],
            type=item['type'],
        )
        for item in views_on_page
    ]
    Show.objects.bulk_create(shows_to_create, ignore_conflicts=True)

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
        is_movie = item['type'] == 'Movie'

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
            get_movie_duration_and_save(driver, show_id)

    if seasons_to_fetch:
        logging.info('Need to fetch duration data for %d season(s).', len(seasons_to_fetch))
        for (show_id, season), _ in seasons_to_fetch.items():
            get_season_durations_and_save(driver, show_id, season)

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


def open_url_safe(driver, url, headless=True, session_type='main'):
    driver.get(url)
    try:
        if is_cloudflare_page(driver):
            logging.warning(f'Обнаружена защита Cloudflare на {url}. Перезапуск сессии...')
            close_driver(driver)
            time.sleep(10)

            new_driver = initialize_driver_session(headless=headless, session_type=session_type)
            if not new_driver:
                raise Exception('Не удалось перезапустить драйвер после обнаружения защиты.')

            new_driver.get(url)

            if is_cloudflare_page(new_driver):
                close_driver(new_driver)
                raise Exception('Защита Cloudflare срабатывает повторно после перезапуска.')

            return new_driver
    except Exception as e:
        logging.error(f'Ошибка при проверке Cloudflare: {e}')
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
            logging.error('Failed to initialize or use provided driver. Aborting parser run.')
            return

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
    finally:
        close_driver(driver)


def process_show_durations(driver, show):
    """
    Determines if the show is a movie or series and fetches durations accordingly.
    For series, it parses the available seasons from window.PLAYER_SEASONS on the player page.
    """
    if show.type not in SERIES_TYPES:
        get_movie_duration_and_save(driver, show.id)
    else:
        try:
            player_url = f'{settings.SITE_URL}item/play/{show.id}/s1e1'
            logging.info(f'Navigating to player to fetch seasons list: {player_url}')
            driver.get(player_url)

            wait = WebDriverWait(driver, 20)
            wait.until(
                expected_conditions.presence_of_element_located(
                    (By.XPATH, '//script[contains(text(), "window.PLAYER_SEASONS")]')
                )
            )

            script_element = driver.find_element(
                By.XPATH, '//script[contains(text(), "window.PLAYER_SEASONS")]'
            )
            script_text = script_element.get_attribute('innerHTML')

            match = re.search(r'window\.PLAYER_SEASONS\s*=\s*(\[.*?\]);', script_text, re.DOTALL)

            seasons = set()
            if match:
                seasons_data = json.loads(match.group(1))
                for item in seasons_data:
                    if 'season' in item:
                        seasons.add(int(item['season']))
            else:
                logging.warning(
                    f'Could not regex PLAYER_SEASONS for show {show.id}. Defaulting to season 1.'
                )
                seasons.add(1)

            logging.info(f'Found seasons {sorted(list(seasons))} for show {show.id}')

            for season in sorted(list(seasons)):
                get_season_durations_and_save(driver, show.id, season)

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
