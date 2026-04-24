import logging
import time

from django.conf import settings

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    get_total_pages,
    initialize_driver_session,
    open_url_safe,
    parse_new_episodes_list,
)
from app.management.base import LoggableBaseCommand
from app.models import Show, ShowDuration
from app.utils import enqueue_show_update
from shared.constants import SHOW_TYPE_MAPPING, SHOW_TYPES_TRACKED_VIA_NEW_EPISODES


class Command(LoggableBaseCommand):
    help = 'Parses new episodes from /media/new-serial-episodes daily.'

    def handle(self, *args, **options):
        logging.info('--- Starting New Episodes Parser (Main Account) ---')

        driver = initialize_driver_session(headless=True, session_type='main')
        if not driver:
            logging.error('Failed to initialize driver. Aborting.')
            return

        total_processed_count = 0

        try:
            for url_type in SHOW_TYPES_TRACKED_VIA_NEW_EPISODES:
                show_type = SHOW_TYPE_MAPPING[url_type]

                logging.info(f'--- Processing category: {show_type} (type={url_type}) ---')
                base_url = f'{settings.SITE_URL}media/new-serial-episodes?type={url_type}'

                driver = open_url_safe(driver, base_url, session_type='main')
                total_pages = get_total_pages(driver)
                logging.info(f'Found {total_pages} pages of new episodes for {show_type}.')

                stop_parsing = False

                for page in range(1, total_pages + 1):
                    if stop_parsing:
                        break

                    page_url = f'{base_url}&page={page}'
                    logging.info(f'Processing {show_type} page {page}/{total_pages}...')

                    if driver.current_url != page_url:
                        driver = open_url_safe(driver, page_url, headless=True, session_type='main')
                        time.sleep(2)

                    items = parse_new_episodes_list(driver)
                    if not items:
                        logging.warning(f'No items found on page {page}.')
                        continue

                    new_items_on_page = 0

                    for item in items:
                        show_id = item['show_id']
                        season = item['season']
                        episode = item['episode']

                        show_qs = Show.objects.filter(id=show_id)
                        show_exists = show_qs.exists()
                        show_has_details = show_exists and show_qs.first().year is not None

                        duration_exists = ShowDuration.objects.filter(
                            show_id=show_id, season_number=season, episode_number=episode
                        ).exists()

                        if show_has_details and duration_exists:
                            continue

                        logging.info(f'Processing update for: {item["title"]} (ID: {show_id})')

                        show, created = Show.objects.get_or_create(
                            id=show_id,
                            defaults={
                                'title': item['title'],
                                'original_title': item['original_title'],
                                'type': show_type,
                            },
                        )

                        if not created and show.type != show_type:
                            show.type = show_type
                            show.save(update_fields=['type'])

                        if not show_has_details or not duration_exists:
                            enqueue_show_update(
                                [show_id],
                                details=not show_has_details,
                                durations=not duration_exists,
                            )
                            new_items_on_page += 1
                            total_processed_count += 1

                    if new_items_on_page == 0:
                        logging.info(
                            f'Page {page} contains only existing items. '
                            f'Stopping scan for {show_type}.'
                        )
                        stop_parsing = True

                logging.info(f'--- New Episodes Parser Finished ({url_type}) ---')

            if total_processed_count > 0:
                logging.info(
                    f'Added {total_processed_count} tasks to update queue. Scheduling backup.'
                )
                BackupManager().schedule_backup()
            else:
                logging.info('No new data found across all categories.')

        finally:
            close_driver(driver)
            logging.info('--- New Episodes Parser Session Finished ---')
