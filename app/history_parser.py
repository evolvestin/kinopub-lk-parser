import json
import logging
import os
import random
import re
import shutil
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import undetected_chromedriver as uc
from django.conf import settings
from django.db.models import Max
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from app.constants import MONTHS_MAP, SHOW_STATUS_MAPPING, SHOW_TYPE_MAPPING
from app.gdrive_backup import BackupManager
from app.models import Code, Country, Genre, Person, Show, ShowDuration, ViewHistory
from kinopub_parser import celery_app


def close_driver(driver):
    if driver:
        logging.info('Closing Selenium driver.')
        try:
            driver.quit()
        except Exception:
            pass
        driver.quit = lambda: None


def _extract_int_from_string(text):
    if not text:
        return None
    return int(''.join(c for c in text if c.isdigit()))


def update_show_details(driver, show_id):
    try:
        show = Show.objects.get(id=show_id)
        three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)
        if show.year is not None and show.updated_at >= three_months_ago:
            return

        logging.info(f'Fetching extended details for show id={show_id}')

        info_table = driver.find_element(By.CSS_SELECTOR, '.table-responsive table')

        def get_row_data(text_label):
            try:
                row = info_table.find_element(By.XPATH, f".//tr[td[strong[text()='{text_label}']]]")
                return row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)')
            except NoSuchElementException:
                return None

        year_data = get_row_data('Год выхода')
        if year_data:
            show.year = _extract_int_from_string(year_data.text)
            try:
                link = year_data.find_element(By.TAG_NAME, 'a')
                href = link.get_attribute('href')
                type_match = re.search(
                    r'/(movie|serial|concert|documovie|docuserial|tvshow|sport)', href
                )
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
                kp_link = rating_data.find_element(By.CSS_SELECTOR, "a[href*='kinopoisk.ru']")
                href = kp_link.get_attribute('href')
                if '/film/' in href and not href.endswith('/film/'):
                    show.kinopoisk_url = href
                    show.kinopoisk_rating = float(kp_link.text)
                    votes_el = kp_link.find_element(By.XPATH, './following-sibling::small')
                    show.kinopoisk_votes = _extract_int_from_string(votes_el.text)
            except (NoSuchElementException, ValueError):
                pass
            try:
                imdb_link = rating_data.find_element(By.CSS_SELECTOR, "a[href*='imdb.com']")
                show.imdb_url = imdb_link.get_attribute('href')
                show.imdb_rating = float(imdb_link.text)
                votes_el = imdb_link.find_element(By.XPATH, './following-sibling::small')
                show.imdb_votes = _extract_int_from_string(votes_el.text)
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
                for el in elements:
                    name = el.text.strip()
                    if name:
                        obj, _ = model.objects.update_or_create(name=name)
                        relation.add(obj)

        show.save()

    except (NoSuchElementException, Show.DoesNotExist) as e:
        logging.error(
            f'Could not fetch extended details for show id={show_id}. Info table may be missing.',
            exc_info=e,
        )
    except Exception as e:
        logging.error(f'An error occurred while updating show details for id={show_id}: {e}')
        raise


def setup_driver(headless=True, profile_key='main', randomize=False):
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--lang=ru-RU,ru')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
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

        driver = uc.Chrome(
            options=options,
            browser_executable_path='/usr/bin/chromium',
            user_data_dir=user_data_dir,
        )
    else:
        driver = uc.Chrome(options=options)

    driver.set_page_load_timeout(60)
    return driver


def save_cookies(driver, file_path):
    cookies = driver.get_cookies()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    logging.info('Cookies successfully saved to %s', file_path)
    if not settings.LOCAL_RUN:
        celery_app.send_task('app.tasks.backup_cookies')
        logging.info('Cookies backup scheduled via Celery.')
    else:
        logging.info('Local run detected, skipping Celery cookies backup task.')


def do_login(driver, login, password, cookie_path, base_url):
    login_url = f'{base_url}user/login'

    title = driver.title
    page_source = driver.page_source
    if (
        'Один момент' in title
        or 'Just a moment' in title
        or 'challenges.cloudflare.com' in page_source
    ):
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
        expiration_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.CODE_LIFETIME_MINUTES
        )

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
                'Failed to log in within the allotted time. The page might be inaccessible or changed.'
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
                with open(cookie_path, 'r', encoding='utf-8') as f:
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
        logging.error('An unexpected error occurred during session initialization: %s', e)
        close_driver(driver)
        return None


def get_movie_duration_and_save(driver, show_id):
    movie_url = f'{settings.SITE_URL}item/view/{show_id}'
    logging.info('Requesting duration for movie id%d...', show_id)
    try:
        driver.get(movie_url)
        wait = WebDriverWait(driver, 20)
        playlist_script_element = wait.until(
            expected_conditions.presence_of_element_located(
                (By.XPATH, '//script[contains(text(), "var playlist =")]')
            )
        )
        update_show_details(driver, show_id)
        script_text = playlist_script_element.get_attribute('innerHTML')
        playlist_match = re.search(r'var playlist = (\[.*?]);', script_text, re.DOTALL)

        if not playlist_match:
            logging.warning('Could not find playlist JSON for movie %s', movie_url)
            return

        playlist_data = json.loads(playlist_match.group(1))
        if playlist_data and 'duration' in playlist_data[0]:
            duration_sec = playlist_data[0]['duration']
            ShowDuration.objects.update_or_create(
                show_id=show_id,
                season_number=None,
                episode_number=None,
                defaults={'duration_seconds': duration_sec},
            )
            logging.info('Cached duration for movie id%d: %d seconds.', show_id, duration_sec)
        else:
            logging.warning('Could not find playlist JSON for movie %s', movie_url)
    except Exception as e:
        logging.error('Error getting duration for movie id%d: %s', show_id, e)


def get_season_durations_and_save(driver, show_id, season):
    episode_url = f'{settings.SITE_URL}item/view/{show_id}/s{season}e1'
    logging.info('Requesting season data for s%d of show id%d...', season, show_id)
    try:
        driver.get(episode_url)
        wait = WebDriverWait(driver, 20)
        playlist_script_element = wait.until(
            expected_conditions.presence_of_element_located(
                (By.XPATH, '//script[contains(text(), "var playlist =")]')
            )
        )
        update_show_details(driver, show_id)
        script_text = playlist_script_element.get_attribute('innerHTML')
        playlist_match = re.search(r'var playlist = (\[.*?]);', script_text, re.DOTALL)

        if not playlist_match:
            logging.warning('Could not find playlist JSON for %s', episode_url)
            return

        playlist_data = json.loads(playlist_match.group(1))
        updated_count = 0
        for item in playlist_data:
            if item.get('snumber') == season:
                episode_num = item.get('vnumber')
                duration_sec = item.get('duration')
                if episode_num is not None and duration_sec is not None:
                    ShowDuration.objects.update_or_create(
                        show_id=show_id,
                        season_number=season,
                        episode_number=episode_num,
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

    except Exception as e:
        logging.error('Error getting duration for season %d of show id%d: %s', season, show_id, e)


def parse_and_save_history(driver, mode, latest_db_date=None):
    wait = WebDriverWait(driver, 20)
    wait.until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '.item-list')))

    stop_parsing = False
    latest_date_in_db = None
    if latest_db_date:
        latest_date_in_db = datetime.strptime(latest_db_date, '%Y-%m-%d').date()

    views_on_page = []
    item_blocks = driver.find_elements(By.CSS_SELECTOR, '.item-list .col-md-3')
    for block in item_blocks:
        try:
            date_header = block.find_element(By.XPATH, 'preceding-sibling::h4[1]')
            year = date_header.find_element(By.TAG_NAME, 'small').text.strip()
            match = re.match(r'(\d{1,2})\s+([А-Яа-яA-Za-z]+)', date_header.text)
            formatted_date = f'{year}-{MONTHS_MAP[match.group(2)]}-{match.group(1).zfill(2)}'
            current_date_from_site = datetime.strptime(formatted_date, '%Y-%m-%d').date()

            if latest_date_in_db and current_date_from_site < latest_date_in_db:
                if not stop_parsing:
                    logging.info(
                        'Found a date (%s) older than the latest in DB (%s). Will stop after this page.',
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
                    se_text = block.find_element(
                        By.CSS_SELECTOR, '.topleft-2x .label-success'
                    ).text.strip()
                    se_match = re.search(r'Сезон (\d+)\. Эпизод (\d+)', se_text)
                    if se_match:
                        season, episode = int(se_match.group(1)), int(se_match.group(2))
                except NoSuchElementException:
                    item_type = 'Movie'

            views_on_page.append(
                {
                    'show_id': show_id,
                    'title': title,
                    'original_title': original_title,
                    'view_date': formatted_date,
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

    views_to_create = [
        ViewHistory(
            show_id=item['show_id'],
            view_date=item['view_date'],
            season_number=item['season'],
            episode_number=item['episode'],
        )
        for item in views_on_page
    ]

    before_count = ViewHistory.objects.count()
    ViewHistory.objects.bulk_create(views_to_create, ignore_conflicts=True)
    after_count = ViewHistory.objects.count()
    views_added = after_count - before_count

    three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)
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
                    f'Duration for show id={show_id} (s:{season}, e:{episode}) is stale. Re-fetching.'
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
        max_date_str = result['max_date'].strftime('%Y-%m-%d')
        logging.info("Latest view date for '%s' in DB: %s", mode, max_date_str)
        return max_date_str
    else:
        logging.info("No view history found for mode '%s'. A full scan will be performed.", mode)
        return None


def open_url_safe(driver, url, headless=True, session_type='main'):
    driver.get(url)
    try:
        title = driver.title
        page_source = driver.page_source

        is_cloudflare = (
            'Один момент' in title
            or 'Just a moment' in title
            or '/cdn-cgi/challenge-platform/' in page_source
            or 'challenges.cloudflare.com' in page_source
        )

        if is_cloudflare:
            logging.warning(f'Обнаружена защита Cloudflare на {url}. Перезапуск сессии...')
            close_driver(driver)
            time.sleep(10)

            new_driver = initialize_driver_session(headless=headless, session_type=session_type)
            if not new_driver:
                raise Exception('Не удалось перезапустить драйвер после обнаружения защиты.')

            new_driver.get(url)

            new_title = new_driver.title
            new_source = new_driver.page_source

            if (
                'Один момент' in new_title
                or 'Just a moment' in new_title
                or '/cdn-cgi/challenge-platform/' in new_source
            ):
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
                'Failed to access history page: PRO account is required. Aborting scan for mode "%s".',
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
                '--- Parser session finished. Total new records added: %d. A database backup will be scheduled. ---',
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
    For series, it parses the available seasons from the page.
    """
    movie_types = ['Movie', 'Concert', 'Documentary Movie']

    if show.type in movie_types:
        get_movie_duration_and_save(driver, show.id)
    else:
        # Logic for Series, DocuSeries, TV Show, etc.
        try:
            # Navigate to the show page to find season links
            show_url = f'{settings.SITE_URL}item/view/{show.id}'
            driver.get(show_url)

            # Wait for basic load
            wait = WebDriverWait(driver, 10)
            wait.until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, 'h1, h3')))

            # Обновляем детали (год, жанры, статус) сразу на главной странице сериала
            update_show_details(driver, show.id)

            seasons = set()
            # New layout: Seasons are links like /item/view/ID/s1e1 inside a div
            # We look for all links containing the show ID and /s followed by a digit
            links = driver.find_elements(By.CSS_SELECTOR, f'a[href*="/item/view/{show.id}/s"]')

            for link in links:
                href = link.get_attribute('href')
                if not href:
                    continue
                # Extract season number from pattern .../s(\d+)e1
                match = re.search(r'/s(\d+)e1', href)
                if match:
                    seasons.add(int(match.group(1)))

            # Fallback: if no tabs are found, it might be a single season show
            if not seasons:
                seasons.add(1)

            logging.info(f'Found seasons {seasons} for show {show.id}')

            for season in sorted(list(seasons)):
                get_season_durations_and_save(driver, show.id, season)

        except Exception as e:
            logging.error(f'Error processing seasons for show {show.id}: {e}')
