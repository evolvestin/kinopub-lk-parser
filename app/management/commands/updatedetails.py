import logging
import time

from django.core.management.base import BaseCommand
from django.conf import settings

from app.history_parser import initialize_driver_session, update_show_details
from app.models import Show


class Command(BaseCommand):
    help = 'Fetches and updates details (year, ratings, etc.) for shows that are missing this information.'

    def add_arguments(self, parser):
        parser.add_argument(
            'limit',
            type=int,
            help='The maximum number of shows to process in one run.'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        if limit <= 0:
            self.stdout.write(self.style.ERROR('Limit must be a positive integer.'))
            return

        self.stdout.write(f'Searching for up to {limit} shows with missing year information...')

        show_ids_to_update = list(Show.objects.filter(year__isnull=True).values_list('id', flat=True)[:limit])

        if not show_ids_to_update:
            self.stdout.write(self.style.SUCCESS('No shows with missing year found. Nothing to do.'))
            return

        self.stdout.write(f'Found {len(show_ids_to_update)} shows to update.')

        driver = None
        try:
            driver = initialize_driver_session()

            for i, show_id in enumerate(show_ids_to_update):
                logging.info(f'Processing show {i + 1}/{len(show_ids_to_update)} (ID: {show_id})...')
                try:
                    show_url = f"{settings.SITE_URL}item/view/{show_id}"
                    driver.get(show_url)
                    time.sleep(1)

                    update_show_details(driver, show_id)

                    logging.info(f'Successfully updated details for show ID {show_id}.')
                    time.sleep(2)
                except Exception as e:
                    logging.error(f'Failed to update show ID {show_id}: {e}')
                    continue

            self.stdout.write(self.style.SUCCESS('Finished updating show details.'))

        except Exception as e:
            logging.error('A critical error occurred during the update process: %s', e, exc_info=True)
            self.stderr.write(self.style.ERROR('A critical error occurred. Check the logs.'))
        finally:
            if driver:
                logging.info('Closing Selenium driver.')
                driver.quit()
                driver.quit = lambda: None
