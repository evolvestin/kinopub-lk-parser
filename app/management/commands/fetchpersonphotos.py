import logging

import requests
from django.db import DatabaseError
from django.db.models import Count

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

    def handle(self, *args, **options):
        if options.get('purge_dupes'):
            logging.info('Finding duplicate TMDB photo URLs to purge...')
            duplicate_urls_qs = (
                Person.objects.exclude(tmdb_photo_url__isnull=True)
                .exclude(tmdb_photo_url='')
                .values('tmdb_photo_url')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=1)
            )

            urls_to_purge = [item['tmdb_photo_url'] for item in duplicate_urls_qs]

            if urls_to_purge:
                purged_count = Person.objects.filter(tmdb_photo_url__in=urls_to_purge).update(
                    tmdb_photo_url=None, is_photo_fetched=False
                )
                logging.info(
                    f'Successfully purged {purged_count} persons '
                    f'sharing {len(urls_to_purge)} duplicate URLs.'
                )
            else:
                logging.info('No duplicate TMDB photos found.')
            return

        limit = options.get('limit')

        if options.get('force'):
            logging.info(
                'Force flag detected. Resetting is_photo_fetched for all persons without photos.'
            )
            Person.objects.filter(tmdb_photo_url__isnull=True, kp_photo_url__isnull=True).update(
                is_photo_fetched=False
            )

        persons = Person.objects.filter(is_photo_fetched=False).order_by('updated_at')[:limit]

        if not persons:
            logging.info('No persons need photo fetching.')
            return

        count = 0
        total = len(persons)
        consecutive_errors = 0
        error_threshold = 5

        logging.info(f'Starting photo fetch for {total} persons (Batch limit: {limit}).')

        for idx, person in enumerate(persons, start=1):
            try:
                if fetch_person_photo_from_tmdb(person):
                    count += 1
                    consecutive_errors = 0

                if idx % 100 == 0:
                    logging.info(f'Progress: {idx}/{total} processed...')

            except DatabaseError as e:
                logging.critical(f'Fatal database error on person {person.name}: {e}')
                return
            except requests.RequestException as e:
                consecutive_errors += 1
                logging.warning(
                    f'TMDB request failed for '
                    f'{person.name} ({consecutive_errors}/{error_threshold}): {e}'
                )
                if consecutive_errors >= error_threshold:
                    logging.error(
                        f'Aborting batch: '
                        f'TMDB API is unreachable after {error_threshold} consecutive errors.'
                    )
                    break
                continue
            except Exception as e:
                logging.error(f'Skipping {person.name} due to unexpected error: {e}')

        logging.info(f'Successfully processed {count} persons.')
