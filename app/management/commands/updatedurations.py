import logging
import time
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    process_show_durations,
)
from app.models import LogEntry, Show


class Command(BaseCommand):
    help = 'Fetches and updates durations for shows that are missing duration data.'

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

        show_ids_to_update = []
        is_series_mode = show_type in ['Series', 'serial']

        if is_series_mode:
            self.stdout.write('Series mode detected. Limit ignored. Fetching unfinished series...')

            first_anchor_log = (
                LogEntry.objects.filter(message__contains='New Episodes Parser Finished')
                .order_by('created_at')
                .first()
            )

            anchor_date = (
                first_anchor_log.created_at
                if first_anchor_log
                else datetime.min.replace(tzinfo=timezone.utc)
            )

            unfinished_shows = Show.objects.filter(type='Series').exclude(status='Finished')

            for show in unfinished_shows:
                success_msg = f'Finished processing durations for show ID {show.id}.'
                already_updated = LogEntry.objects.filter(
                    message__contains=success_msg, created_at__gte=anchor_date
                ).exists()

                if not already_updated:
                    show_ids_to_update.append(show.id)

        else:
            if limit <= 0:
                raise CommandError('Limit must be a positive integer.')

            msg = f'Searching for up to {limit} shows with missing duration information'
            if show_type:
                msg += f' (type: {show_type})'
            self.stdout.write(f'{msg}...')

            queryset = Show.objects.filter(showduration__isnull=True)
            if show_type:
                queryset = queryset.filter(type=show_type)

            show_ids_to_update = list(
                queryset.order_by('?').values_list('id', flat=True).distinct()[:limit]
            )

        if not show_ids_to_update:
            self.stdout.write(
                self.style.SUCCESS('No shows found matching criteria. Nothing to do.')
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

        except CommandError:
            raise

        except Exception as e:
            logging.error(
                'A critical error occurred during the duration update process: %s',
                e,
                exc_info=True,
            )
            raise CommandError(f'A critical error occurred: {e}')

        finally:
            close_driver(driver)
