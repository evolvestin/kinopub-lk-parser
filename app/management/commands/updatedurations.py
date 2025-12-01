import logging
import time

from django.core.management.base import BaseCommand, CommandError

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
            raise CommandError('Limit must be a positive integer.')

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

        driver = initialize_driver_session(session_type='main')
        updated_count = 0

        try:
            for i, show_id in enumerate(show_ids_to_update):
                if driver is None:
                    logging.info('Restarting Selenium driver session...')
                    driver = initialize_driver_session(session_type='main')
                    if driver is None:
                        # Если драйвер не удалось поднять - это критическая ошибка
                        raise CommandError('Could not restart Selenium driver. Aborting.')

                logging.info(
                    f'Processing show {i + 1}/{len(show_ids_to_update)} (ID: {show_id})...'
                )
                try:
                    try:
                        _ = driver.current_url
                    except Exception as e:
                        raise Exception(f'Driver unresponsive: {e}')

                    show = Show.objects.get(id=show_id)
                    process_show_durations(driver, show)

                    logging.info(f'Finished processing durations for show ID {show_id}.')
                    updated_count += 1
                except Show.DoesNotExist:
                    logging.warning(f'Show ID {show_id} not found in DB during processing.')
                except Exception as e:
                    err_str = str(e).lower()
                    if (
                        'driver unresponsive' in err_str
                        or 'connection refused' in err_str
                        or 'max retries exceeded' in err_str
                    ):
                        logging.error('Selenium driver is dead. Restarting session...')
                        close_driver(driver)
                        driver = None
                        continue

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

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Process interrupted by user.'))
            # Не вызываем CommandError здесь, если хотим статус STOPPED (нужна поддержка в tasks.py),
            # но по умолчанию tasks.py ловит это отдельно.

        except CommandError:
            # Если мы сами вызвали CommandError выше, пробрасываем его дальше
            raise

        except Exception as e:
            # Любая другая непредвиденная ошибка должна помечать таск как FAILURE
            logging.error(
                'A critical error occurred during the duration update process: %s',
                e,
                exc_info=True,
            )
            raise CommandError(f'A critical error occurred: {e}')

        finally:
            close_driver(driver)
