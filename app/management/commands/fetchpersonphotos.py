import csv
import logging

import requests
from celery.exceptions import SoftTimeLimitExceeded
from django import db
from django.core.management.base import CommandError
from django.db import DatabaseError

from app.management.base import LoggableBaseCommand
from app.models import Person
from app.services.person_service import fetch_person_photo_from_tmdb


class Command(LoggableBaseCommand):
    help = 'Fetches missing person photos from TMDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=50, help='Limit number of persons to process'
        )
        parser.add_argument(
            '--force', action='store_true', help='Reset is_photo_fetched flag and retry everyone'
        )
        parser.add_argument(
            '--purge-dupes',
            action='store_true',
            help='Remove TMDB photos that belong to multiple different persons',
        )
        parser.add_argument(
            '--ids-file',
            help='CSV file with an id column; restrict refetching to those Person IDs.',
        )

    def handle(self, *args, **options):
        if options.get('purge_dupes'):
            raise CommandError(
                'Disabled because it clears verified and aliased rows. '
                'Use reset_unverified_duplicate_photos instead.'
            )

        limit = options.get('limit')
        target_ids = None
        if options.get('ids_file'):
            if options.get('force'):
                raise ValueError('--ids-file cannot be combined with --force')
            target_ids = []
            with open(options['ids_file'], newline='', encoding='utf-8') as stream:
                reader = csv.DictReader(stream)
                if 'id' not in (reader.fieldnames or []):
                    raise ValueError('--ids-file must contain an id column')
                for row in reader:
                    try:
                        target_ids.append(int(row['id']))
                    except (TypeError, ValueError):
                        raise ValueError(f'Invalid Person id in --ids-file: {row.get("id")}')
            target_ids = sorted(set(target_ids))
            logging.info('Restricting photo fetch to %d Person IDs from CSV.', len(target_ids))

        if options.get('force'):
            logging.info('Force flag detected. Resetting is_photo_fetched for missing photos.')
            Person.objects.filter(tmdb_photo_url__isnull=True, kp_photo_url__isnull=True).update(
                is_photo_fetched=False
            )

        processed_count = 0
        consecutive_errors = 0
        error_threshold = 5
        batch_size = 100

        # WARNING: Track failed IDs to avoid infinite loops over transient network or API failures
        # in the same session
        failed_ids = []

        logging.info(f'Starting photo fetch. Target limit: {limit}')

        try:
            while processed_count < limit:
                current_batch_limit = min(batch_size, limit - processed_count)

                batch_qs = Person.objects.filter(is_photo_fetched=False)
                if target_ids is not None:
                    batch_qs = batch_qs.filter(id__in=target_ids)
                batch = list(
                    batch_qs.exclude(id__in=failed_ids)
                    .order_by('id')[:current_batch_limit]
                )

                if not batch:
                    break

                for person in batch:
                    try:
                        if fetch_person_photo_from_tmdb(person):
                            processed_count += 1
                            consecutive_errors = 0
                        else:
                            processed_count += 1

                    except SoftTimeLimitExceeded:
                        raise
                    except DatabaseError as e:
                        logging.critical(f'Fatal database error on person {person.name}: {e}')
                        return
                    except requests.RequestException as e:
                        consecutive_errors += 1
                        failed_ids.append(person.id)
                        logging.warning(
                            f'TMDB request failed for {person.name} '
                            f'({consecutive_errors}/{error_threshold}): {e}'
                        )
                        if consecutive_errors >= error_threshold:
                            logging.error('Aborting: TMDB API is unreachable.')
                            return
                    except Exception as e:
                        failed_ids.append(person.id)
                        logging.error(f'Skipping {person.name} due to unexpected error: {e}')

                    if processed_count % 50 == 0:
                        logging.info(f'Progress: {processed_count} processed...')

                # WARNING: db.reset_queries() is required here to prevent memory leaks
                db.reset_queries()

        except SoftTimeLimitExceeded:
            # WARNING: Celery SoftTimeLimitExceeded is caught here
            # to allow the long-running loop to terminate cleanly,
            # preserving database integrity before the hard limit kills the process
            logging.warning('Soft time limit reached. Exiting gracefully to save progress.')

        logging.info(f'Successfully processed {processed_count} persons.')
