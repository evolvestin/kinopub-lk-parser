import logging
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from app.gdrive_backup import BackupManager
from app.history_parser import (
    initialize_driver_session,
    close_driver,
    get_total_pages,
    parse_new_episodes_list,
    update_show_details,
    process_show_durations,
    get_season_durations_and_save,
    open_url_safe,
)
from app.models import Show, ShowDuration


class Command(BaseCommand):
    help = 'Parses new episodes from /media/new-serial-episodes daily.'

    def handle(self, *args, **options):
        logging.info('--- Starting New Episodes Parser (Main Account) ---')

        driver = initialize_driver_session(headless=True, session_type='main')
        if not driver:
            logging.error('Failed to initialize driver. Aborting.')
            return

        base_url = f'{settings.SITE_URL}media/new-serial-episodes'
        # Параметр type=serial можно добавить, если нужно, но по умолчанию страница открывает всё

        try:
            # 1. Determine total pages
            driver.get(base_url)
            total_pages = get_total_pages(driver)
            logging.info(f'Found {total_pages} pages of new episodes.')

            stop_parsing = False
            processed_count = 0

            for page in range(1, total_pages + 1):
                if stop_parsing:
                    break

                page_url = f'{base_url}?page={page}'
                logging.info(f'Processing page {page}/{total_pages}...')

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

                    # Check if Show exists and has basic data (year is a good indicator of details)
                    show_qs = Show.objects.filter(id=show_id)
                    show_exists = show_qs.exists()
                    show_has_details = show_exists and show_qs.first().year is not None

                    # Check if Duration exists for this specific episode
                    duration_exists = ShowDuration.objects.filter(
                        show_id=show_id, season_number=season, episode_number=episode
                    ).exists()

                    if show_has_details and duration_exists:
                        logging.info(
                            f'Data exists for {item["title"]} s{season}e{episode}. Stopping scan.'
                        )
                        stop_parsing = True
                        break

                    logging.info(f'Processing update for: {item["title"]} (ID: {show_id})')

                    # Prepare Show object
                    show, created = Show.objects.get_or_create(
                        id=show_id,
                        defaults={
                            'title': item['title'],
                            'original_title': item['original_title'],
                            'type': 'Series',  # Default, will be updated
                        },
                    )

                    delay_needed = False

                    # Logic 1: Series doesn't exist or no details -> Full Parse
                    if not show_has_details:
                        logging.info(
                            f'Show {show_id} missing details/year. Performing full update...'
                        )
                        try:
                            # Go to show page
                            show_page_url = f'{settings.SITE_URL}item/view/{show_id}'
                            driver.get(show_page_url)

                            # Update details (year, genres, etc)
                            update_show_details(driver, show_id)

                            # Process ALL seasons (finds tabs and parses them)
                            process_show_durations(driver, show)

                            delay_needed = True
                        except Exception as e:
                            logging.error(f'Failed full update for show {show_id}: {e}')

                    # Logic 2: Series exists, but specific episode duration is missing
                    elif not duration_exists:
                        logging.info(
                            f'Missing duration for {show_id} s{season}e{episode}. Fetching season...'
                        )
                        try:
                            get_season_durations_and_save(driver, show_id, season)
                            delay_needed = True
                        except Exception as e:
                            logging.error(f'Failed duration update for {show_id}: {e}')

                    processed_count += 1

                    if delay_needed:
                        logging.info('Waiting 60s before next request...')
                        time.sleep(60)

            if processed_count > 0:
                logging.info(f'Updated {processed_count} shows/episodes. Scheduling backup.')
                BackupManager().schedule_backup()
            else:
                logging.info('No new data found.')

        except Exception as e:
            logging.error(f'Critical error in runnewepisodes: {e}', exc_info=True)
        finally:
            close_driver(driver)
            logging.info('--- New Episodes Parser Finished ---')
