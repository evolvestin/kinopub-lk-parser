import logging
import re
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    get_total_pages,
    initialize_driver_session,
    is_fatal_selenium_error,
)
from app.management.base import LoggableBaseCommand
from app.models import LogEntry, Show
from shared.constants import SHOW_TYPE_MAPPING, SHOW_TYPES_TRACKED_VIA_NEW_EPISODES


def parse_and_save_catalog_page(driver, mode):
    script = """
    const results = [];
    const blocks = document.querySelectorAll("#items > div[class*='col-']");

    blocks.forEach(block => {
        const linkElement = block.querySelector('.item-poster a');
        if (!linkElement) return;

        const titleElement = block.querySelector('.item-title a');
        const originalTitleElement = block.querySelector('.item-author a');
        const kinopoiskLink = block.querySelector(".bottomcenter-2x a[href*='kinopoisk.ru']");
        const imdbLink = block.querySelector(".bottomcenter-2x a[href*='imdb.com']");

        results.push({
            href: linkElement.getAttribute('href'),
            title: titleElement ? titleElement.textContent.trim() : '',
            original_title: originalTitleElement ? originalTitleElement.textContent.trim() : '',
            kinopoisk_url: kinopoiskLink ? kinopoiskLink.getAttribute('href') : null,
            kinopoisk_rating: kinopoiskLink ? kinopoiskLink.textContent.trim() : null,
            imdb_url: imdbLink ? imdbLink.getAttribute('href') : null,
            imdb_rating: imdbLink ? imdbLink.textContent.trim() : null
        });
    });
    return results;
    """

    try:
        items_data = driver.execute_script(script)
    except Exception as e:
        logging.error('Error executing JS parser: %s', e)
        return 0

    if not items_data:
        return 0

    shows_on_page = []

    for item in items_data:
        try:
            match = re.search(r'/item/view/(\d+)', item['href'])
            if not match:
                continue

            show_id = int(match.group(1))
            title = item['title']
            original_title = item['original_title'] if item['original_title'] else title

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

            if item['kinopoisk_url']:
                url = item['kinopoisk_url']
                if '/film/' in url and not url.endswith('/film/'):
                    show_data['kinopoisk_url'] = url
                    if item['kinopoisk_rating']:
                        try:
                            show_data['kinopoisk_rating'] = float(item['kinopoisk_rating'])
                        except ValueError:
                            pass

            if item['imdb_url']:
                url = item['imdb_url']
                if '/title/tt' in url:
                    show_data['imdb_url'] = url
                    if item['imdb_rating']:
                        try:
                            show_data['imdb_rating'] = float(item['imdb_rating'])
                        except ValueError:
                            pass

            shows_on_page.append(show_data)

        except Exception as e:
            logging.error('Error processing item data: %s', e)

    if not shows_on_page:
        return 0

    page_ids = [s['id'] for s in shows_on_page]
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


def run_full_scan_session(headless=True, target_type=None, process_all_pages=False):
    logging.info('--- Starting Full Catalog Scan Session ---')
    driver = None
    total_added = 0

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

            if not target_type and mode in SHOW_TYPES_TRACKED_VIA_NEW_EPISODES:
                logging.info(f"Skipping '{mode}' mode by default. Use --type={mode} to force scan.")
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

                page_url = f'{base_url}?page={page}&per-page=50'

                try:
                    try:
                        _ = driver.current_url
                    except Exception as e:
                        raise Exception(f'Driver unresponsive: {e}') from e

                    driver.get(page_url)
                    added_count = parse_and_save_catalog_page(driver, mode)
                    total_added += added_count

                    logging.info(
                        "Processing '%s' page %d of %d. Saved %d records.",
                        mode,
                        page,
                        total_pages,
                        added_count,
                    )

                    if added_count == 0 and not process_all_pages:
                        logging.info(
                            "No new items found on page %d. Stopping scan for mode '%s'.",
                            page,
                            mode,
                        )
                        break

                    time.sleep(settings.FULL_SCAN_PAGE_DELAY_SECONDS)
                except Exception as e:
                    if is_fatal_selenium_error(e):
                        logging.error('Selenium driver is dead. Restarting session...')
                        close_driver(driver)
                        driver = None
                        continue
                    else:
                        logging.error(f'Error processing page {page} in mode {mode}: {e}')
                        continue

            backup_manager.schedule_backup()

        logging.info(
            '--- Full catalog scan session finished successfully. Total new: %d ---', total_added
        )
        return total_added

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
        parser.add_argument(
            '--all-pages',
            action='store_true',
            dest='all_pages',
            help='Force scanning of all pages even if no new items are found.',
        )

    def handle(self, *args, **options):
        target_type = options.get('type')
        process_all_pages = options.get('all_pages', False)

        if target_type and target_type not in SHOW_TYPE_MAPPING:
            for key, val in SHOW_TYPE_MAPPING.items():
                if val == target_type:
                    target_type = key
                    break

        if target_type and target_type not in SHOW_TYPE_MAPPING:
            raise CommandError(
                f'Invalid type: {target_type}. Choices: {", ".join(SHOW_TYPE_MAPPING.keys())}'
            )
        return run_full_scan_session(target_type=target_type, process_all_pages=process_all_pages)
