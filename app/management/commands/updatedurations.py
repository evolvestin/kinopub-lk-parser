import logging
import re
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
            self.stdout.write('Series mode detected. Limit ignored. Fetching series...')

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

            for show in Show.objects.filter(type='Series'):
                already_updated = LogEntry.objects.filter(
                    message__contains=f'Finished processing durations for show ID {show.id}.',
                    created_at__gte=anchor_date,
                ).exists()

                has_errors = LogEntry.objects.filter(
                    message__contains=f'show id{show.id}',
                    level='ERROR',
                    created_at__gte=anchor_date,
                ).exists()

                if not already_updated or has_errors:
                    show_ids_to_update.append(show.id)

        else:
            if limit <= 0:
                raise CommandError('Limit must be a positive integer.')

            msg = f'Searching for up to {limit} shows with missing duration information'
            if show_type:
                msg += f' (type: {show_type})'
            self.stdout.write(f'{msg}...')

            # 1. Находим шоу с ошибками (без отсечки по дате, глобально)
            error_ids = set()
            error_logs = LogEntry.objects.filter(level='ERROR', message__contains='show id')
            for log in error_logs:
                match = re.search(r'show id(\d+)', log.message)
                if match:
                    error_ids.add(int(match.group(1)))

            base_qs = Show.objects.all()
            if show_type:
                base_qs = base_qs.filter(type=show_type)

            # Приоритет отдаем тем, кто с ошибками
            priority_ids = list(
                base_qs.filter(id__in=error_ids).values_list('id', flat=True)[:limit]
            )

            # Добираем рандомными, у которых нет длительности
            remaining_limit = limit - len(priority_ids)
            random_ids = []
            if remaining_limit > 0:
                random_ids = list(
                    base_qs.filter(showduration__isnull=True)
                    .exclude(id__in=priority_ids)
                    .order_by('?')
                    .values_list('id', flat=True)
                    .distinct()[:remaining_limit]
                )

            show_ids_to_update = priority_ids + random_ids

        if not show_ids_to_update:
            self.stdout.write(
                self.style.SUCCESS('No shows found matching criteria. Nothing to do.')
            )
            return

        self.stdout.write(f'Found {len(show_ids_to_update)} shows to update.')

        driver = None
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

                    # Удаляем логи ошибок после успешной обработки
                    LogEntry.objects.filter(
                        message__contains=f'show ID {show_id}', level='ERROR'
                    ).delete()

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
