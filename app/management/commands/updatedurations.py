import logging
import time

from django.core.management.base import BaseCommand

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    process_show_durations,
)
from app.models import Show


class Command(BaseCommand):
    help = 'Fetches and updates durations for shows that are missing duration data.'

    def add_arguments(self, parser):
        parser.add_argument(
            'limit', type=int, help='The maximum number of shows to process in one run.'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        if limit <= 0:
            self.stdout.write(self.style.ERROR('Limit must be a positive integer.'))
            return

        self.stdout.write(f'Searching for up to {limit} shows with missing duration information...')

        show_ids_to_update = list(
            Show.objects.filter(showduration__isnull=True)
            .order_by('?')
            .values_list('id', flat=True)
            .distinct()[:limit]
        )

        if not show_ids_to_update:
            self.stdout.write(
                self.style.SUCCESS('No shows with missing durations found. Nothing to do.')
            )
            return

        self.stdout.write(f'Found {len(show_ids_to_update)} shows to update.')

        driver = None
        updated_count = 0
        try:
            driver = initialize_driver_session(session_type='main')

            if driver is None:
                self.stderr.write(
                    self.style.ERROR(
                        'Could not initialize Selenium driver (main account). Aborting.'
                    )
                )
                return

            for i, show_id in enumerate(show_ids_to_update):
                logging.info(
                    f'Processing show {i + 1}/{len(show_ids_to_update)} (ID: {show_id})...'
                )
                try:
                    # Проверяем, жив ли драйвер, так как process_show_durations "глотает" ошибки соединения
                    try:
                        _ = driver.current_url
                    except Exception as e:
                        raise Exception(f"Driver unresponsive: {e}")

                    show = Show.objects.get(id=show_id)
                    process_show_durations(driver, show)

                    logging.info(f'Finished processing durations for show ID {show_id}.')
                    updated_count += 1
                except Show.DoesNotExist:
                    logging.warning(f'Show ID {show_id} not found in DB during processing.')
                except Exception as e:
                    # Если драйвер упал или соединение разорвано — прерываем цикл
                    err_str = str(e).lower()
                    if 'driver unresponsive' in err_str or 'connection refused' in err_str or 'max retries exceeded' in err_str:
                        logging.error('Selenium driver is dead. Aborting task loop.')
                        break
                    
                    logging.error(f'Failed to update durations for show ID {show_id}: {e}')
                    continue
                time.sleep(60)

            if updated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Finished processing durations for {updated_count} shows.')
                )
                BackupManager().schedule_backup()
            else:
                self.stdout.write(self.style.SUCCESS('Finished processing. No durations added.'))

        except Exception as e:
            logging.error(
                'A critical error occurred during the duration update process: %s',
                e,
                exc_info=True,
            )
            self.stderr.write(self.style.ERROR('A critical error occurred. Check the logs.'))
        finally:
            close_driver(driver)
