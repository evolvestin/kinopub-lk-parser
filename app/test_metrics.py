from django.test import TestCase

from app.models import Show
from app.services.metrics import calculate_imdb_unrated_metric, calculate_missing_imdb_metric


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
