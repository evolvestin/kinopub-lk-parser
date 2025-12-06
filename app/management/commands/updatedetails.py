import logging
import time

from django.conf import settings
from django.core.management.base import CommandError

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    update_show_details,
)
from app.management.base import LoggableBaseCommand
from app.models import Show


class Command(LoggableBaseCommand):
    help = 'Fetches and updates details (year, ratings, etc.) for shows that are missing this information.'

    def add_arguments(self, parser):
        parser.add_argument(
            'limit', type=int, help='The maximum number of shows to process in one run.'
        )
        parser.add_argument(
            '--type',
            type=str,
            dest='type',
            help='Filter shows by type (e.g. Series, Movie).',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        show_type = options.get('type')

        if limit <= 0:
            raise CommandError('Limit must be a positive integer.')

        msg = f'Searching for up to {limit} shows with missing year information'
        if show_type:
            msg += f' (type: {show_type})'
        self.stdout.write(f'{msg}...')

        queryset = Show.objects.filter(year__isnull=True)
        if show_type:
            queryset = queryset.filter(type=show_type)

        show_ids_to_update = list(queryset.order_by('?').values_list('id', flat=True)[:limit])

        if not show_ids_to_update:
            self.stdout.write(
                self.style.SUCCESS('No shows found matching criteria. Nothing to do.')
            )
            return

        self.stdout.write(f'Found {len(show_ids_to_update)} shows to update.')

        driver = None
        updated_count = 0
        base_url = settings.SITE_AUX_URL

        try:
            for i, show_id in enumerate(show_ids_to_update):
                if driver is None:
                    logging.info('Restarting Selenium driver session...')
                    driver = initialize_driver_session(session_type='aux')
                    if driver is None:
                        raise CommandError('Could not restart Selenium driver. Aborting.')

                logging.info(
                    f'Processing show {i + 1}/{len(show_ids_to_update)} (ID: {show_id})...'
                )
                try:
                    try:
                        _ = driver.current_url
                    except Exception as e:
                        raise Exception(f'Driver unresponsive: {e}')

                    show_url = f'{base_url}item/view/{show_id}'
                    driver.get(show_url)
                    time.sleep(1)

                    update_show_details(driver, show_id)

                    logging.info(f'Successfully updated details for show ID {show_id}.')
                    updated_count += 1
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

                    logging.error(f'Failed to update show ID {show_id}: {e}')
                    continue

            if updated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Finished updating {updated_count} show details.')
                )
                BackupManager().schedule_backup()
            else:
                self.stdout.write(self.style.SUCCESS('Finished updating show details.'))

        finally:
            close_driver(driver)
