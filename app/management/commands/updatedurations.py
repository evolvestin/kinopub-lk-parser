import logging
import re
import time
from datetime import datetime

from django.core.management.base import CommandError
from django.db.models import Q

from app.gdrive_backup import BackupManager
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    is_fatal_selenium_error,
    process_show_durations,
)
from app.management.base import LoggableBaseCommand
from app.models import LogEntry, Show
from shared.constants import SERIES_TYPES, SHOW_TYPE_MAPPING, SHOW_TYPES_TRACKED_VIA_NEW_EPISODES


class Command(LoggableBaseCommand):
    help = 'Fetches and updates durations for shows that are missing duration data.'

    def add_arguments(self, parser):
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
            help='Specific Show ID to update (bypasses logic).',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        input_type = options.get('type')
        specific_id = options.get('id')

        show_ids_to_update = []

        if specific_id:
            logging.info(f'Forcing duration update for specific Show ID: {specific_id}...')
            if Show.objects.filter(id=specific_id).exists():
                show_ids_to_update = [specific_id]
            else:
                logging.error(f'Show ID {specific_id} not found.')
                return
        else:
            # --- Existing logic for batch selection ---
            target_show_type = None
            url_type = None

            if input_type:
                for key, val in SHOW_TYPE_MAPPING.items():
                    if input_type.lower() in (key.lower(), val.lower()):
                        url_type = key
                        target_show_type = val
                        break

                if not target_show_type:
                    target_show_type = input_type

            if url_type in SHOW_TYPES_TRACKED_VIA_NEW_EPISODES:
                logging.info(
                    f'Series mode detected ({target_show_type}). '
                    f'Limit ignored. Fetching shows based on logs...'
                )

                # Для краткости: в режиме --id мы пропускаем этот блок поиска.
                # Если вы хотите сохранить полную логику, она остается в ветке else.
                # Здесь предполагается, что оригинальный код поиска ID остается внутри `else`.

                # В данном блоке я упрощаю вывод для соблюдения лимита токенов,
                # подразумевая что старая логика остается в блоке `else`, если она не меняется.
                # Но так как я должен выдать полный рабочий блок функции, я скопирую логику поиска.

                first_anchor_log = (
                    LogEntry.objects.filter(
                        message__contains=f'New Episodes Parser Finished ({url_type})'
                    )
                    .order_by('created_at')
                    .first()
                )

                anchor_date = first_anchor_log.created_at if first_anchor_log else datetime.min

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

                all_series_ids = Show.objects.filter(type=target_show_type).values_list(
                    'id', flat=True
                )

                for show_id in all_series_ids:
                    if show_id not in success_ids or show_id in error_ids:
                        show_ids_to_update.append(show_id)

            else:
                if limit <= 0:
                    raise CommandError('Limit must be a positive integer.')

                msg = f'Searching for up to {limit} shows with missing duration information'
                if input_type:
                    msg += f' (type: {target_show_type})'
                logging.info(f'{msg}...')

                error_ids = set()
                error_logs = LogEntry.objects.filter(level='ERROR', message__contains='show id')
                for log in error_logs:
                    match = re.search(r'show id(\d+)', log.message)
                    if match:
                        error_ids.add(int(match.group(1)))

                base_qs = Show.objects.all()
                if target_show_type:
                    base_qs = base_qs.filter(type=target_show_type)
                else:
                    base_qs = base_qs.exclude(type__in=SERIES_TYPES)

                priority_ids = list(
                    base_qs.filter(id__in=error_ids).values_list('id', flat=True)[:limit]
                )

                remaining_limit = limit - len(priority_ids)
                random_ids = []
                if remaining_limit > 0:
                    random_ids = list(
                        base_qs.filter(showduration__isnull=True)
                        .exclude(id__in=priority_ids)
                        .order_by('-created_at')
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
                        raise Exception(f'Driver unresponsive: {e}') from e

                    show = Show.objects.get(id=show_id)
                    process_show_durations(driver, show)

                    logging.info(f'Finished processing durations for show ID {show_id}.')

                    # Очищаем ошибки только если это не ручной запуск
                    if not specific_id:
                        LogEntry.objects.filter(
                            Q(message__icontains=f'show id {show_id}')
                            | Q(message__icontains=f'show id{show_id}'),
                            level='ERROR',
                        ).delete()

                    updated_count += 1
                except Show.DoesNotExist:
                    logging.warning(f'Show ID {show_id} not found in DB during processing.')
                except Exception as e:
                    if is_fatal_selenium_error(e):
                        logging.error('Selenium driver is dead. Restarting session...')
                        close_driver(driver)
                        driver = None
                        continue

                    logging.error(f'Failed to update durations for show ID {show_id}: {e}')
                    continue

                if not specific_id:
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
