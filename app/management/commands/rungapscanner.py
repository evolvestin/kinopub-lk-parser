import logging
import re
import time

from django.conf import settings
from django.db.models import Max
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    is_fatal_selenium_error,
    open_url_safe,
    process_show_durations,
    update_show_details,
)
from app.management.base import LoggableBaseCommand
from app.models import LogEntry, Show


class Command(LoggableBaseCommand):
    help = 'Scans gaps between the last checked ID and current Max ID, updates missing shows.'

    def handle(self, *args, **options):
        bounds = Show.objects.aggregate(max_id=Max('id'))
        end_id = bounds.get('max_id')

        if not end_id:
            logging.warning('GapScanner: Database is empty, nothing to scan.')
            return

        last_log = (
            LogEntry.objects.filter(
                message__contains='Gap scanner finished successfully up to ID',
            )
            .order_by('-created_at')
            .first()
        )

        start_id = 1
        if last_log:
            match = re.search(r'up to ID (\d+)', last_log.message)
            if match:
                start_id = int(match.group(1))

        if start_id >= end_id:
            logging.info(f'GapScanner: All IDs up to {end_id} are already checked.')
            return

        existing_ids = set(
            Show.objects.filter(id__gte=start_id, id__lte=end_id).values_list('id', flat=True)
        )
        missing_ids = sorted(list(set(range(start_id, end_id + 1)) - existing_ids))
        total_missing = len(missing_ids)

        if not missing_ids:
            logging.info(f'GapScanner: No gaps found. Syncing marker to ID {end_id}.')
            logging.info(f'Gap scanner finished successfully up to ID {end_id}')
            return

        logging.info(
            f'GapScanner: Found {total_missing} gaps to check in range {start_id}-{end_id}'
        )

        driver = None
        processed_count = 0
        found_count = 0
        current_id = start_id

        try:
            for idx, show_id in enumerate(missing_ids, start=1):
                current_id = show_id

                if idx % 50 == 0 or idx == 1:
                    logging.info(
                        f'GapScanner Progress: Checked {idx}/{total_missing}'
                        f' (Current ID: {show_id})'
                    )

                if driver is None:
                    driver = initialize_driver_session(session_type='aux')
                    if not driver:
                        logging.error('GapScanner: Failed to initialize Selenium driver.')
                        return

                target_url = f'{settings.SITE_AUX_URL}item/view/{show_id}'
                max_attempts = 3
                attempt = 0
                success = False

                while attempt < max_attempts and not success:
                    attempt += 1
                    try:
                        time.sleep(settings.FULL_SCAN_PAGE_DELAY_SECONDS)
                        driver = open_url_safe(driver, target_url, session_type='aux')

                        page_title = driver.title
                        if 'Not Found' in page_title or '404' in page_title:
                            success = True
                            continue

                        is_valid_show = False
                        content_title = f'ID {show_id}'
                        try:
                            title_el = driver.find_element(By.TAG_NAME, 'h3')
                            title_text = title_el.text.strip().split('\n')[0]
                            if title_text and title_text != 'Авторизация':
                                is_valid_show = True
                                content_title = title_text
                        except NoSuchElementException:
                            if 'window.PLAYER_ITEM_ID' in driver.page_source:
                                is_valid_show = True

                        if is_valid_show:
                            logging.info(f'GapScanner: FOUND [{show_id}] - {content_title}')
                            update_show_details(driver, show_id, force=True, session_type='aux')
                            try:
                                show = Show.objects.get(id=show_id)
                                process_show_durations(driver, show, session_type='aux')
                            except Show.DoesNotExist:
                                pass
                            processed_count += 1
                            found_count += 1

                        success = True

                    except Exception as e:
                        if is_fatal_selenium_error(e):
                            logging.warning(
                                f'GapScanner: Driver crash on ID {show_id}, restarting...'
                            )
                            close_driver(driver)
                            driver = initialize_driver_session(session_type='aux')
                            if not driver:
                                return

                        if attempt >= max_attempts:
                            logging.error(
                                f'GapScanner: Failed ID {show_id} after {max_attempts} attempts.'
                            )
                            raise e
                        else:
                            time.sleep(5)

            logging.info(f'Gap scanner finished successfully up to ID {end_id}')
            logging.info(
                f'GapScanner: Finished. Total checked: {total_missing}, New found: {found_count}'
            )

        except (Exception, KeyboardInterrupt) as e:
            logging.error(f'GapScanner: Interrupted at ID {current_id}. Error: {str(e)[:200]}')
            logging.warning(
                f'Gap scanner finished successfully up to ID {current_id} (interrupted)'
            )
            raise e

        finally:
            if processed_count > 0:
                BackupManager().schedule_backup()
            close_driver(driver)
