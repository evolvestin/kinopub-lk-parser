import logging
import re
import time
from datetime import datetime

from django.core.management.base import CommandError
from django.db.models import Q
from django.utils import timezone

from app.constants import SHOW_TYPE_MAPPING
from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    process_show_durations,
)
from app.management.base import LoggableBaseCommand
from app.models import LogEntry, Show


class Command(LoggableBaseCommand):
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

        # Универсальное получение типа для БД
        target_db_type = SHOW_TYPE_MAPPING.get(show_type)
        if not target_db_type and show_type in SHOW_TYPE_MAPPING.values():
            target_db_type = show_type

        series_db_types = [
            SHOW_TYPE_MAPPING['serial'],
            SHOW_TYPE_MAPPING['docuserial'],
            SHOW_TYPE_MAPPING['tvshow'],
        ]

        is_series_mode = target_db_type in series_db_types

        if is_series_mode:
            logging.info(
                f'Series mode detected ({show_type} -> {target_db_type}). Limit ignored. Fetching shows...'
            )

            if target_db_type == SHOW_TYPE_MAPPING['serial']:
                log_marker = 'New Episodes Parser Finished'
            elif target_db_type == SHOW_TYPE_MAPPING['docuserial']:
                log_marker = 'New Episodes Parser Finished (docuserial)'
            elif target_db_type == SHOW_TYPE_MAPPING['tvshow']:
                log_marker = 'New Episodes Parser Finished (tvshow)'
            else:
                log_marker = 'New Episodes Parser Finished'

            first_anchor_log = (
                LogEntry.objects.filter(message__contains=log_marker).order_by('created_at').first()
            )

            anchor_date = (
                first_anchor_log.created_at
                if first_anchor_log
                else datetime.min.replace(tzinfo=timezone.utc)
            )

            success_logs = LogEntry.objects.filter(
                message__contains='Finished processing durations for show ID',
                created_at__gte=anchor_date,
            ).values_list('message', flat=True)

            success_ids = set()
            for msg in success_logs:
                match = re.search(r'show ID (\d+)', msg)
                if match:
                    success_ids.add(int(match.group(1)))

            error_logs = LogEntry.objects.filter(
                level='ERROR',
                message__contains='show',
                created_at__gte=anchor_date,
            ).values_list('message', flat=True)

            error_ids = set()
            for msg in error_logs:
                match = re.search(r'show (?:id|ID)\s*(\d+)', msg, re.IGNORECASE)
                if match:
                    error_ids.add(int(match.group(1)))

            all_series_ids = Show.objects.filter(type=target_db_type).values_list('id', flat=True)

            for show_id in all_series_ids:
                if show_id not in success_ids or show_id in error_ids:
                    show_ids_to_update.append(show_id)

        else:
            if limit <= 0:
                raise CommandError('Limit must be a positive integer.')

            msg = f'Searching for up to {limit} shows with missing duration information'
            if show_type:
                msg += f' (type: {show_type})'
            logging.info(f'{msg}...')

            error_ids = set()
            error_logs = LogEntry.objects.filter(level='ERROR', message__contains='show id')
            for log in error_logs:
                match = re.search(r'show id(\d+)', log.message)
                if match:
                    error_ids.add(int(match.group(1)))

            base_qs = Show.objects.all()
            if show_type:
                if target_db_type:
                    base_qs = base_qs.filter(type=target_db_type)
                else:
                    base_qs = base_qs.filter(type=show_type)

            priority_ids = list(
                base_qs.filter(id__in=error_ids).values_list('id', flat=True)[:limit]
            )

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
            logging.info('No shows found matching criteria. Nothing to do.')
            return

        logging.info(f'Found {len(show_ids_to_update)} shows to update.')

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

                    LogEntry.objects.filter(
                        Q(message__icontains=f'show id {show_id}')
                        | Q(message__icontains=f'show id{show_id}'),
                        level='ERROR',
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

                time.sleep(15)

            if updated_count > 0:
                logging.info(f'Finished processing durations for {updated_count} shows.')
                BackupManager().schedule_backup()
            else:
                logging.info('Finished processing. No durations added.')

        except KeyboardInterrupt:
            logging.warning('Process interrupted by user.')
        finally:
            close_driver(driver)
