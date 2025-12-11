import logging
import re
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from app.constants import SHOW_TYPE_MAPPING
from app.gdrive_backup import BackupManager
from app.history_parser import close_driver, get_total_pages, initialize_driver_session
from app.management.base import LoggableBaseCommand
from app.models import LogEntry, Show


def parse_and_save_catalog_page(driver, mode):
    shows_on_page = []
    item_blocks = driver.find_elements(By.CSS_SELECTOR, "#items > div[class*='col-']")
    logging.debug('Found %d item blocks on page.', len(item_blocks))

    for block in item_blocks:
        try:
            link_element = block.find_element(By.CSS_SELECTOR, '.item-poster a')
            href = link_element.get_attribute('href')
            match = re.search(r'/item/view/(\d+)', href)
            if not match:
                continue
            show_id = int(match.group(1))

            title = block.find_element(By.CSS_SELECTOR, '.item-title a').text.strip()
            try:
                original_title = block.find_element(By.CSS_SELECTOR, '.item-author a').text.strip()
            except NoSuchElementException:
                original_title = title
            if not original_title:
                original_title = title

            show_data = {
                'id': show_id,
                'title': title,
                'original_title': original_title,
                'type': SHOW_TYPE_MAPPING.get(mode, mode.capitalize()),
                'kinopoisk_url': None,
                'kinopoisk_rating': None,
                'imdb_url': None,
                'imdb_rating': None,
            }

            try:
                rating_container = block.find_element(By.CSS_SELECTOR, '.bottomcenter-2x')

                try:
                    kp_link = rating_container.find_element(
                        By.CSS_SELECTOR, "a[href*='kinopoisk.ru']"
                    )
                    href = kp_link.get_attribute('href')
                    if '/film/' in href and not href.endswith('/film/'):
                        show_data['kinopoisk_url'] = href
                        rating_text = kp_link.text.strip()
                        if rating_text:
                            show_data['kinopoisk_rating'] = float(rating_text)
                except (NoSuchElementException, ValueError):
                    pass

                try:
                    imdb_link = rating_container.find_element(
                        By.CSS_SELECTOR, "a[href*='imdb.com']"
                    )
                    href = imdb_link.get_attribute('href')
                    if '/title/tt' in href:
                        show_data['imdb_url'] = href
                        rating_text = imdb_link.text.strip()
                        if rating_text:
                            show_data['imdb_rating'] = float(rating_text)
                except (NoSuchElementException, ValueError):
                    pass

            except NoSuchElementException:
                logging.debug(f'Rating container not found for show id={show_id}')

            shows_on_page.append(show_data)
        except Exception as e:
            logging.error('Error parsing a show block: %s', e)

    if not shows_on_page:
        return 0

    page_ids = [item['id'] for item in shows_on_page]
    existing_ids = set(Show.objects.filter(id__in=page_ids).values_list('id', flat=True))
    new_count = len(page_ids) - len(existing_ids)

    shows_to_upsert = [Show(**data) for data in shows_on_page]

    update_fields = [
        'title',
        'original_title',
        'type',
        'kinopoisk_url',
        'kinopoisk_rating',
        'imdb_url',
        'imdb_rating',
    ]

    Show.objects.bulk_create(
        shows_to_upsert,
        update_conflicts=True,
        unique_fields=['id'],
        update_fields=update_fields,
    )

    return new_count


def run_full_scan_session(headless=True, target_type=None):
    logging.info('--- Starting Full Catalog Scan Session ---')
    driver = None

    start_mode = None
    start_page = 1
    resume_window = timezone.now() - timedelta(hours=settings.FULL_SCAN_RESUME_WINDOW_HOURS)
    last_log = (
        LogEntry.objects.filter(
            module='runfullscan',
            message__contains='Processing',
            created_at__gte=resume_window,
        )
        .order_by('-created_at')
        .first()
    )

    if last_log:
        match = re.search(r"Processing '(\w+)' page (\d+)", last_log.message)
        if match:
            found_mode = match.group(1)
            found_page = int(match.group(2))

            if target_type:
                if found_mode == target_type:
                    start_mode = found_mode
                    start_page = found_page + 1
                    logging.info(
                        'Resuming scan for specific type %s from page %d.',
                        start_mode,
                        start_page,
                    )
            else:
                start_mode = found_mode
                start_page = found_page + 1
                logging.info(
                    'Resuming scan from %s, page %d based on recent logs.',
                    start_mode,
                    start_page,
                )

    try:
        driver = initialize_driver_session(headless=headless, session_type='aux')
        backup_manager = BackupManager()

        mode_found = not bool(start_mode)

        for mode in SHOW_TYPE_MAPPING:
            if target_type and mode != target_type:
                continue

            if not target_type and mode == 'serial':
                logging.info("Skipping 'serial' mode by default. Use --type=serial to force scan.")
                continue

            if not mode_found and mode == start_mode:
                mode_found = True
            if not mode_found:
                logging.info("Skipping mode '%s' to resume.", mode)
                continue

            if driver and driver.current_url:
                current_base_url = driver.current_url.rstrip('/')
                if current_base_url.endswith('/user/login'):
                    current_base_url = settings.SITE_AUX_URL.rstrip('/')
            else:
                current_base_url = settings.SITE_AUX_URL.rstrip('/')

            base_url = f'{current_base_url}/{mode}'

            if driver is None:
                driver = initialize_driver_session(headless=headless, session_type='aux')
                if not driver:
                    logging.error(f'Could not initialize driver for mode {mode}. Skipping.')
                    continue

            driver.get(base_url)
            total_pages = get_total_pages(driver)
            logging.info("Found %d pages for mode '%s'.", total_pages, mode)

            current_page = start_page if mode == start_mode else 1
            start_page = 1

            for page in range(current_page, total_pages + 1):
                if driver is None:
                    logging.info('Restarting Selenium driver...')
                    driver = initialize_driver_session(headless=headless, session_type='aux')
                    if not driver:
                        raise CommandError('Failed to restart driver. Aborting scan.')

                logging.info("Processing '%s' page %d of %d...", mode, page, total_pages)
                page_url = f'{base_url}?page={page}&per-page=50'

                try:
                    try:
                        _ = driver.current_url
                    except Exception as e:
                        raise Exception(f'Driver unresponsive: {e}') from e

                    driver.get(page_url)
                    added_count = parse_and_save_catalog_page(driver, mode)
                    logging.info('Saved %d show records from page %d.', added_count, page)
                    time.sleep(settings.FULL_SCAN_PAGE_DELAY_SECONDS)
                except Exception as e:
                    err_str = str(e).lower()
                    if (
                        'driver unresponsive' in err_str
                        or 'connection refused' in err_str
                        or 'max retries exceeded' in err_str
                        or 'invalid session' in err_str
                    ):
                        logging.error('Selenium driver is dead. Restarting session...')
                        close_driver(driver)
                        driver = None
                        continue
                    else:
                        logging.error(f'Error processing page {page} in mode {mode}: {e}')
                        continue

            backup_manager.schedule_backup()

        logging.info('--- Full catalog scan session finished successfully. ---')

    finally:
        close_driver(driver)


class Command(LoggableBaseCommand):
    help = 'Runs a full scan of the site catalog to populate the Show database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            dest='type',
            help='Filter shows by type (e.g. serial, movie).',
        )

    def handle(self, *args, **options):
        target_type = options.get('type')

        if target_type and target_type not in SHOW_TYPE_MAPPING:
            for key, val in SHOW_TYPE_MAPPING.items():
                if val == target_type:
                    target_type = key
                    break

        if target_type and target_type not in SHOW_TYPE_MAPPING:
            raise CommandError(
                f'Invalid type: {target_type}. Choices: {", ".join(SHOW_TYPE_MAPPING.keys())}'
            )
        run_full_scan_session(target_type=target_type)
