import logging

from django.db import DatabaseError
from django.db.models import Q

from app.management.base import LoggableBaseCommand
from app.models import Person
from app.services.person_service import fetch_person_photo_from_tmdb


class Command(LoggableBaseCommand):
    help = 'Fetches missing person photos from TMDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=50, help='Limit number of persons to process'
        )

    def handle(self, *args, **options):
        limit = options.get('limit')

        persons = Person.objects.filter(
            Q(is_photo_fetched=False) | Q(photo_url__isnull=True) | Q(photo_url='')
        ).order_by('updated_at')[:limit]

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
            except Exception as e:
                logging.error(f'Unexpected error on {person.name}: {e}')

        logging.info(f'Successfully processed {count} persons.')
