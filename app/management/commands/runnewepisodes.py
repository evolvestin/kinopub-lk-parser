import logging
import time

from django.conf import settings
from shared.formatters import format_se

from app.constants import SHOW_TYPE_MAPPING, SHOW_TYPES_TRACKED_VIA_NEW_EPISODES
from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    get_season_durations_and_save,
    get_total_pages,
    initialize_driver_session,
    open_url_safe,
    parse_new_episodes_list,
    process_show_durations,
    update_show_details,
)
from app.management.base import LoggableBaseCommand
from app.models import Show, ShowDuration


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

                driver.get(base_url)
                total_pages = get_total_pages(driver)
                logging.info(f'Found {total_pages} pages of new episodes for {show_type}.')

                stop_parsing = False
                category_processed_count = 0

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
                            logging.info(
                                f'Data exists for {item["title"]} {format_se(season, episode)}.'
                                f' Stopping scan for {show_type}.'
                            )
                            stop_parsing = True
                            break

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

                        delay_needed = False

                        if not show_has_details:
                            logging.info(
                                f'Show {show_id} missing details/year. Performing full update...'
                            )
                            try:
                                show_page_url = f'{settings.SITE_URL}item/view/{show_id}'
                                driver.get(show_page_url)
                                update_show_details(driver, show_id)
                                process_show_durations(driver, show)
                                delay_needed = True
                            except Exception as e:
                                logging.error(f'Failed full update for show {show_id}: {e}')

                        elif not duration_exists:
                            logging.info(
                                f'Missing duration for {show_id} {format_se(season, episode)}.'
                                f' Fetching season...'
                            )
                            try:
                                get_season_durations_and_save(driver, show_id, season)
                                delay_needed = True
                            except Exception as e:
                                logging.error(f'Failed duration update for {show_id}: {e}')

                        category_processed_count += 1
                        total_processed_count += 1

                        if delay_needed:
                            logging.info('Waiting 60s before next request...')
                            time.sleep(60)

                logging.info(f'--- New Episodes Parser Finished ({url_type}) ---')

            if total_processed_count > 0:
                logging.info(
                    f'Updated {total_processed_count} shows/episodes total. Scheduling backup.'
                )
                BackupManager().schedule_backup()
            else:
                logging.info('No new data found across all categories.')

        finally:
            close_driver(driver)
            logging.info('--- New Episodes Parser Session Finished ---')