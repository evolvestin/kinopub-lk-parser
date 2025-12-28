import logging
import time

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    is_fatal_selenium_error,
    update_show_details,
)
from app.management.base import LoggableBaseCommand
from app.models import Show


class Command(LoggableBaseCommand):
    help = (
        'Fetches and updates details (year, ratings, etc.)'
        ' for shows that are missing this information.'
    )

    def add_arguments(self, parser):
        # Делаем limit опциональным, так как при --id он не нужен,
        # но для обратной совместимости оставляем nargs='?' и дефолт.
        parser.add_argument(
            'limit',
            type=int,
            nargs='?',
            default=10,
            help='The maximum number of shows to process in one run.',
        )
        parser.add_argument(
            '--type',
            type=str,
            dest='type',
            help='Filter shows by type (e.g. Series, Movie).',
        )
        parser.add_argument(
            '--id',
            type=int,
            dest='id',
            help='Specific Show ID to update (bypasses missing year check).',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        show_type = options.get('type')
        specific_id = options.get('id')

        show_ids_to_update = []

        if specific_id:
            self.stdout.write(f'Forcing update for specific Show ID: {specific_id}...')
            # Проверяем существование, но не проверяем year__isnull
            if Show.objects.filter(id=specific_id).exists():
                show_ids_to_update = [specific_id]
            else:
                self.stdout.write(self.style.ERROR(f'Show ID {specific_id} not found.'))
                return
        else:
            if limit <= 0:
                raise CommandError('Limit must be a positive integer.')

            msg = f'Searching for up to {limit} shows with missing year information'
            if show_type:
                msg += f' (type: {show_type})'
            self.stdout.write(f'{msg}...')

            queryset = Show.objects.filter(year__isnull=True)
            if show_type:
                queryset = queryset.filter(type=show_type)

            show_ids_to_update = list(
                queryset.order_by('-created_at').values_list('id', flat=True)[:limit]
            )

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
                        raise Exception(f'Driver unresponsive: {e}') from e

                    show_url = f'{base_url}item/view/{show_id}'
                    driver.get(show_url)
                    time.sleep(8)

                    # Если это принудительное обновление, очищаем год перед обновлением,
                    # чтобы update_show_details точно отработала
                    if specific_id:
                        Show.objects.filter(id=show_id).update(year=None, updated_at=timezone.now())

                    update_show_details(driver, show_id)

                    logging.info(f'Successfully updated details for show ID {show_id}.')
                    updated_count += 1
                except Exception as e:
                    if is_fatal_selenium_error(e):
                        logging.error('Selenium driver is dead. Restarting session...')
                        close_driver(driver)
                        driver = None
                        continue

                    logging.error(f'Failed to update show ID {show_id}: {e}')
                    continue

            if updated_count > 0:
                logging.info(f'Finished updating {updated_count} show details.')
                BackupManager().schedule_backup()
            else:
                logging.info('Finished updating show details. 0 updated.')
        finally:
            close_driver(driver)
