import logging

import requests
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

    def handle(self, *args, **options):
        limit = options.get('limit')

        if options.get('force'):
            logging.info('Force flag detected. Resetting is_photo_fetched for all persons without photos.')
            Person.objects.filter(tmdb_photo_url__isnull=True, kp_photo_url__isnull=True).update(is_photo_fetched=False)

        persons = Person.objects.filter(is_photo_fetched=False).order_by('updated_at')[:limit]

        if not persons:
            logging.info('No persons need photo fetching.')
            return

        count = 0
        for person in persons:
            try:
                if fetch_person_photo_from_tmdb(person):
                    count += 1
            except DatabaseError as e:
                logging.critical(f'Fatal database error on person {person.name}: {e}')
                return
            except (requests.ConnectionError, requests.Timeout) as e:
                logging.error(f'Aborting batch: TMDB API is unreachable. Error: {e}')
                break
            except Exception as e:
                logging.error(f'Skipping {person.name} due to unexpected error: {e}')

        logging.info(f'Successfully processed {count} persons.')
