from datetime import timedelta

from django.utils import timezone

from app.management.base import LoggableBaseCommand
from app.models import ExternalRating, Show
from app.services.poiskkino_client import PoiskkinoClient
from app.tasks import get_kp_mapping


class Command(LoggableBaseCommand):
    help = 'Manually syncs Poiskkino ratings with fine-grained control over API limits.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit the number of missing ratings to fetch. Defaults to 10.',
        )
        parser.add_argument(
            '--ids',
            type=str,
            help='Comma-separated list of specific Show IDs to sync.',
        )
        parser.add_argument(
            '--skip-daily',
            action='store_true',
            help='Skip fetching the daily updated ratings (saves API requests).',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        skip_daily = options['skip_daily']
        specific_ids = options.get('ids')

        client = PoiskkinoClient()
        now = timezone.now()
        data = []

        kp_mapping = get_kp_mapping()
        if not kp_mapping:
            self.stdout.write(self.style.ERROR('No Kinopoisk URLs found in the database.'))
            return

        if not skip_daily:
            today = now.date()
            yesterday = today - timedelta(days=1)
            self.stdout.write(f'Fetching daily updates from {yesterday} to {today}...')
            daily_data = client.fetch_updated_ratings(yesterday, today)
            data.extend(daily_data)
            self.stdout.write(self.style.SUCCESS(f'Fetched {len(daily_data)} daily updates.'))

        if specific_ids:
            show_ids_list = [int(x.strip()) for x in specific_ids.split(',') if x.strip().isdigit()]
            target_kp_ids = [kp for kp, sid in kp_mapping.items() if sid in show_ids_list]

            self.stdout.write(f'Fetching specific KP IDs: {target_kp_ids}...')
            if target_kp_ids:
                id_data = client.fetch_ratings_by_ids(target_kp_ids)
                data.extend(id_data)
                self.stdout.write(self.style.SUCCESS(f'Fetched {len(id_data)} specific records.'))
        else:
            if limit > 0:
                self.stdout.write(f'Fetching up to {limit} missing ratings...')
                missing_show_ids = set(
                    Show.objects.filter(ext_rating__isnull=True).values_list('id', flat=True)
                )

                target_kp_ids = []
                for kp, sid in kp_mapping.items():
                    if sid in missing_show_ids:
                        target_kp_ids.append(kp)
                    if len(target_kp_ids) >= limit:
                        break

                if target_kp_ids:
                    catchup_data = client.fetch_ratings_by_ids(target_kp_ids)
                    data.extend(catchup_data)
                    self.stdout.write(
                        self.style.SUCCESS(f'Fetched {len(catchup_data)} missing records.')
                    )

        if not data:
            self.stdout.write(self.style.WARNING('No data fetched from API.'))
            return

        data_map = {}
        for item in data:
            kp_id = item.get('id')
            if kp_id and kp_id in kp_mapping:
                data_map[kp_mapping[kp_id]] = item

        show_ids = list(data_map.keys())
        existing_shows = Show.objects.filter(id__in=show_ids).in_bulk(field_name='id')

        ext_ratings_to_update = []
        shows_to_update = []

        for show_id, item in data_map.items():
            show = existing_shows.get(show_id)
            if not show:
                continue

            r_data = item.get('rating') or {}
            v_data = item.get('votes') or {}

            if specific_ids:
                self.stdout.write(
                    self.style.WARNING(
                        f'Raw rating data from API for KP ID {item.get("id")}: {r_data}'
                    )
                )

            show.kinopoisk_rating = r_data.get('kp')
            show.kinopoisk_votes = v_data.get('kp')
            show.imdb_rating = r_data.get('imdb')
            show.imdb_votes = v_data.get('imdb')
            shows_to_update.append(show)

            ext_ratings_to_update.append(
                ExternalRating(
                    show_id=show_id,
                    kp=r_data.get('kp'),
                    imdb=r_data.get('imdb'),
                    tmdb=r_data.get('tmdb'),
                    film_critics=r_data.get('filmCritics'),
                    russian_film_critics=r_data.get('russianFilmCritics'),
                    await_rating=r_data.get('await'),
                    updated_at=now,
                )
            )

        if shows_to_update:
            Show.objects.bulk_update(
                shows_to_update,
                ['kinopoisk_rating', 'kinopoisk_votes', 'imdb_rating', 'imdb_votes'],
            )
            self.stdout.write(f'Updated main Show models: {len(shows_to_update)}')

        if ext_ratings_to_update:
            ExternalRating.objects.bulk_create(
                ext_ratings_to_update,
                update_conflicts=True,
                unique_fields=['show_id'],
                update_fields=[
                    'kp',
                    'imdb',
                    'tmdb',
                    'film_critics',
                    'russian_film_critics',
                    'await_rating',
                    'updated_at',
                ],
            )
            self.stdout.write(f'Upserted ExternalRating models: {len(ext_ratings_to_update)}')

        self.stdout.write(self.style.SUCCESS('Database synchronization complete.'))
