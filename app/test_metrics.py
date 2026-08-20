from django.test import TestCase
from django.utils import timezone

from app.models import Person, Show
from app.services.metrics import (
    calculate_duplicate_photo_urls_metric,
    calculate_imdb_unrated_metric,
    calculate_kp_unrated_metric,
    calculate_missing_imdb_metric,
    calculate_missing_kp_metric,
)


class ImdbMetricSplitTests(TestCase):
    def test_missing_rating_metrics_distinguish_sync_error_from_unrated_title(self):
        Show.objects.create(
            title='Rated by IMDb but missing locally',
            original_title='Rated by IMDb but missing locally',
            type='Movie',
            year=2020,
            status='Finished',
            imdb_id='tt10000001',
            imdb_url='https://www.imdb.com/title/tt10000001/',
            imdb_rating_available=True,
        )
        Show.objects.create(
            title='No IMDb rating published',
            original_title='No IMDb rating published',
            type='Movie',
            year=2020,
            status='Finished',
            imdb_id='tt10000002',
            imdb_url='https://www.imdb.com/title/tt10000002/',
            imdb_rating_available=False,
        )

        self.assertEqual(calculate_missing_imdb_metric(), [{'name': 'Фильм', 'value': 1}])
        self.assertEqual(calculate_imdb_unrated_metric(), [{'name': 'Фильм', 'value': 1}])

    def test_kp_metrics_distinguish_sync_error_from_unrated_title(self):
        Show.objects.create(
            title='KP rating missing locally',
            original_title='KP rating missing locally',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/10000001/',
            kinopoisk_rating_available=True,
        )
        Show.objects.create(
            title='KP rating not published',
            original_title='KP rating not published',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/10000002/',
            poiskkino_updated_at=timezone.now(),
        )

        self.assertEqual(calculate_missing_kp_metric(), [{'name': 'Фильм', 'value': 1}])
        self.assertEqual(calculate_kp_unrated_metric(), [{'name': 'Фильм', 'value': 1}])

    def test_duplicate_photo_metric_excludes_distinct_tmdb_identities(self):
        shared_photo = 'https://image.tmdb.org/t/p/w200/shared.jpg'
        Person.objects.create(name='Confirmed A', tmdb_id=10001, tmdb_photo_url=shared_photo)
        Person.objects.create(name='Confirmed B', tmdb_id=10002, tmdb_photo_url=shared_photo)
        Person.objects.create(
            name='Unresolved', tmdb_photo_url='https://image.tmdb.org/t/p/w200/x.jpg'
        )
        Person.objects.create(
            name='Confirmed C',
            tmdb_id=10003,
            tmdb_photo_url='https://image.tmdb.org/t/p/w200/x.jpg',
        )

        self.assertEqual(
            calculate_duplicate_photo_urls_metric(),
            [{'name': 'TMDB дубликаты', 'value': 1}, {'name': 'KP дубликаты', 'value': 0}],
        )
