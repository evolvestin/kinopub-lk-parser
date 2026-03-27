import logging
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from app.management.base import LoggableBaseCommand
from app.models import Country, ExternalRating, Genre, Show
from app.services.poiskkino_client import PoiskkinoClient
from app.tasks import get_kp_mapping


class Command(LoggableBaseCommand):
    help = 'Syncs ratings, genres, and countries with Poiskkino API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10000,
            help='Limit for fetching missing show ratings.',
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        client = PoiskkinoClient()
        now = timezone.now()
        today = now.date()
        yesterday = today - timedelta(days=1)

        logging.info('Fetching daily rating updates from Poiskkino...')
        kp_mapping = get_kp_mapping()
        if not kp_mapping:
            logging.warning('No Kinopoisk mappings found. Skipping.')
            return

        data = client.fetch_updated_ratings(yesterday, today)
        logging.info(f'Fetched {len(data)} daily updates.')

        missing_show_ids = set(
            Show.objects.filter(ext_rating__isnull=True).values_list('id', flat=True)[:limit]
        )
        missing_kp_ids = [kp for kp, sid in kp_mapping.items() if sid in missing_show_ids]

        if missing_kp_ids:
            logging.info(f'Fetching {len(missing_kp_ids)} missing records by IDs...')
            catchup_data = client.fetch_ratings_by_ids(missing_kp_ids)
            data.extend(catchup_data)

        if not data:
            logging.info('No data to process.')
            return

        data_map = {}
        for item in data:
            kp_id = item.get('id')
            if kp_id and kp_id in kp_mapping:
                data_map[kp_mapping[kp_id]] = item

        show_ids = list(data_map.keys())
        existing_shows = Show.objects.filter(id__in=show_ids).in_bulk(field_name='id')

        all_genre_names = {g['name'] for item in data_map.values() for g in item.get('genres', [])}
        all_country_names = {
            c['name'] for item in data_map.values() for c in item.get('countries', [])
        }

        existing_genres = {g.name: g for g in Genre.objects.filter(name__in=all_genre_names)}
        existing_countries = {c.name: c for c in Country.objects.filter(name__in=all_country_names)}

        new_genres = [Genre(name=name) for name in all_genre_names if name not in existing_genres]
        if new_genres:
            created_genres = Genre.objects.bulk_create(new_genres)
            existing_genres.update({g.name: g for g in created_genres})

        new_countries = [
            Country(name=name) for name in all_country_names if name not in existing_countries
        ]
        if new_countries:
            created_countries = Country.objects.bulk_create(new_countries)
            existing_countries.update({c.name: c for c in created_countries})

        shows_to_update = []
        ext_ratings_to_update = []
        show_genres_map = defaultdict(list)
        show_countries_map = defaultdict(list)

        for show_id, item in data_map.items():
            show = existing_shows.get(show_id)
            if not show:
                continue

            r_data = item.get('rating') or {}
            v_data = item.get('votes') or {}

            show.kinopoisk_rating = r_data.get('kp')
            show.kinopoisk_votes = v_data.get('kp')
            show.imdb_rating = r_data.get('imdb')
            show.imdb_votes = v_data.get('imdb')
            show.year = item.get('year')
            show.plot = item.get('description')
            show.status = item.get('status')
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

            for genre_data in item.get('genres', []):
                if genre := existing_genres.get(genre_data['name']):
                    show_genres_map[show_id].append(genre.id)

            for country_data in item.get('countries', []):
                if country := existing_countries.get(country_data['name']):
                    show_countries_map[show_id].append(country.id)

        if shows_to_update:
            Show.objects.bulk_update(
                shows_to_update,
                [
                    'kinopoisk_rating',
                    'kinopoisk_votes',
                    'imdb_rating',
                    'imdb_votes',
                    'year',
                    'plot',
                    'status',
                ],
            )

            Show.genres.through.objects.filter(show_id__in=show_ids).delete()
            Show.countries.through.objects.filter(show_id__in=show_ids).delete()

            Show.genres.through.objects.bulk_create(
                [
                    Show.genres.through(show_id=show_id, genre_id=genre_id)
                    for show_id, genre_ids in show_genres_map.items()
                    for genre_id in genre_ids
                ],
                ignore_conflicts=True,
            )

            Show.countries.through.objects.bulk_create(
                [
                    Show.countries.through(show_id=show_id, country_id=country_id)
                    for show_id, country_ids in show_countries_map.items()
                    for country_id in country_ids
                ],
                ignore_conflicts=True,
            )

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

        logging.info(f'Successfully synchronized {len(shows_to_update)} shows.')
