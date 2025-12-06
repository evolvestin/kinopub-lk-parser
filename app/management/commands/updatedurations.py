import logging
import re
import time
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from app.constants import SHOW_TYPE_MAPPING
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

        # Получаем тип для БД из константы (ожидается ключ, например 'serial')
        target_db_type = SHOW_TYPE_MAPPING.get(show_type)

        # Список значений из константы, которые относятся к сериалам
        series_db_types = [
            SHOW_TYPE_MAPPING['serial'],
            SHOW_TYPE_MAPPING['docuserial'],
            SHOW_TYPE_MAPPING['tvshow'],
        ]

        is_series_mode = target_db_type in series_db_types

        if is_series_mode:
            self.stdout.write(
                f'Series mode detected ({show_type} -> {target_db_type}). Limit ignored. Fetching shows...'
            )

            # Определяем маркер лога в зависимости от типа для совместимости с runnewepisodes
            if target_db_type == SHOW_TYPE_MAPPING['serial']:
                log_marker = 'New Episodes Parser Finished'
            elif target_db_type == SHOW_TYPE_MAPPING['docuserial']:
                log_marker = 'New Episodes Parser Finished (docuserial)'
            elif target_db_type == SHOW_TYPE_MAPPING['tvshow']:
                log_marker = 'New Episodes Parser Finished (tvshow)'
            else:
                log_marker = 'New Episodes Parser Finished'

            # Ищем лог с учетом точного маркера, чтобы не зацепить (docuserial) при поиске обычных
            first_anchor_log = (
                LogEntry.objects.filter(message__contains=log_marker).order_by('created_at').first()
            )

            anchor_date = (
                first_anchor_log.created_at
                if first_anchor_log
                else datetime.min.replace(tzinfo=timezone.utc)
            )

            # ОПТИМИЗАЦИЯ: Получаем все логи разом, а не в цикле
            # 1. Собираем ID успешно обновленных шоу
            success_logs = LogEntry.objects.filter(
                message__contains='Finished processing durations for show ID',
                created_at__gte=anchor_date,
            ).values_list('message', flat=True)

            success_ids = set()
            for msg in success_logs:
                match = re.search(r'show ID (\d+)', msg)
                if match:
                    success_ids.add(int(match.group(1)))

            # 2. Собираем ID шоу с ошибками
            error_logs = LogEntry.objects.filter(
                level='ERROR',
                message__contains='show',  # Ищем шире, так как форматы могут отличаться
                created_at__gte=anchor_date,
            ).values_list('message', flat=True)

            error_ids = set()
            for msg in error_logs:
                # Ищем и 'show id123' и 'show ID 123'
                match = re.search(r'show (?:id|ID)\s*(\d+)', msg, re.IGNORECASE)
                if match:
                    error_ids.add(int(match.group(1)))

            # 3. Получаем все ID шоу конкретного типа одним запросом
            all_series_ids = Show.objects.filter(type=target_db_type).values_list('id', flat=True)

            # 4. Фильтруем в памяти (быстро)
            # Нужно обновить, если: (НЕ обновлялся успешно) ИЛИ (была ошибка)
            for show_id in all_series_ids:
                if show_id not in success_ids or show_id in error_ids:
                    show_ids_to_update.append(show_id)

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
                # Если передан тип (например 'movie'), фильтруем по нему
                if target_db_type:
                    base_qs = base_qs.filter(type=target_db_type)
                else:
                    # Если тип не найден в константах, но передан аргумент - пробуем фильтровать напрямую
                    # на случай ручного ввода, хотя это не рекомендуется
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
