import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from selenium.webdriver.common.by import By

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    get_movie_duration_and_save,
    get_season_durations_and_save,
    initialize_driver_session,
    update_show_details,
)
from app.models import Show


class Command(BaseCommand):
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
            self.stdout.write(self.style.ERROR('Limit must be a positive integer.'))
            return

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
        try:
            driver = initialize_driver_session(session_type='aux')

            if driver is None:
                self.stderr.write(
                    self.style.ERROR('Could not initialize Selenium driver. Aborting.')
                )
                return

            base_url = settings.SITE_AUX_URL

            for i, show_id in enumerate(show_ids_to_update):
                logging.info(
                    f'Processing show {i + 1}/{len(show_ids_to_update)} (ID: {show_id})...'
                )
                try:
                    show_url = f'{base_url}item/view/{show_id}'
                    driver.get(show_url)
                    time.sleep(1)

                    update_show_details(driver, show_id)

                    logging.info(f'Successfully updated details for show ID {show_id}.')
                    updated_count += 1
                except Exception as e:
                    logging.error(f'Failed to update show ID {show_id}: {e}')
                    continue

            if updated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Finished updating {updated_count} show details.')
                )
                BackupManager().schedule_backup()
            else:
                self.stdout.write(self.style.SUCCESS('Finished updating show details.'))

        except Exception as e:
            logging.error(
                'A critical error occurred during the update process: %s',
                e,
                exc_info=True,
            )
            self.stderr.write(self.style.ERROR('A critical error occurred. Check the logs.'))
        finally:
            close_driver(driver)
