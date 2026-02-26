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
            return

        last_log = (
            LogEntry.objects.filter(
                module='rungapscanner',
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
            return

        existing_ids = set(
            Show.objects.filter(id__gte=start_id, id__lte=end_id).values_list('id', flat=True)
        )
        missing_ids = sorted(list(set(range(start_id, end_id + 1)) - existing_ids))

        if not missing_ids:
            LogEntry.objects.create(
                level='INFO',
                module='rungapscanner',
                message=f'Gap scanner finished successfully up to ID {end_id}',
            )
            return

        driver = None
        processed_count = 0

        try:
            for _, show_id in enumerate(missing_ids, start=1):
                if driver is None:
                    driver = initialize_driver_session(session_type='aux')
                    if not driver:
                        return

                target_url = f'{settings.SITE_AUX_URL}item/view/{show_id}'
                max_attempts = 3
                attempt = 0
                success = False

                while attempt < max_attempts and not success:
                    attempt += 1
                    try:
                        time.sleep(settings.FULL_SCAN_PAGE_DELAY_SECONDS)
                        driver.get(target_url)

                        page_title = driver.title
                        if 'Not Found' in page_title or '404' in page_title:
                            success = True
                            continue

                        is_valid_show = False
                        try:
                            title_el = driver.find_element(By.TAG_NAME, 'h3')
                            if title_el.text.strip().split('\n')[0]:
                                is_valid_show = True
                        except NoSuchElementException:
                            if 'window.PLAYER_ITEM_ID' in driver.page_source:
                                is_valid_show = True

                        if is_valid_show:
                            update_show_details(driver, show_id, force=True)
                            try:
                                show = Show.objects.get(id=show_id)
                                process_show_durations(driver, show)
                            except Show.DoesNotExist:
                                pass
                            processed_count += 1

                        success = True

                    except Exception as e:
                        if is_fatal_selenium_error(e):
                            close_driver(driver)
                            driver = initialize_driver_session(session_type='aux')
                            if not driver:
                                return

                        if attempt >= max_attempts:
                            pass
                        else:
                            time.sleep(5)

            if processed_count > 0:
                BackupManager().schedule_backup()

            LogEntry.objects.create(
                level='INFO',
                module='rungapscanner',
                message=f'Gap scanner finished successfully up to ID {end_id}',
            )

        finally:
            close_driver(driver)
