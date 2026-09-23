from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app.models import ExternalRating, Person, Show, ShowCrew
from app.services.metrics import (
    calculate_duplicate_photo_urls_metric,
    calculate_en_professions_stats_metric,
    calculate_has_kp_metric,
    calculate_imdb_unrated_metric,
    calculate_kp_unrated_metric,
    calculate_missing_imdb_metric,
    calculate_missing_kp_metric,
    calculate_total_persons_by_show_type_metric,
    calculate_unused_persons_metric,
    get_has_rating_list,
    get_duplicate_photo_urls_page,
    get_missing_status_list,
    get_profession_persons_list,
    get_unused_persons_list,
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

    def test_kp_rating_metric_and_details_use_the_same_authoritative_field(self):
        rated = Show.objects.create(
            title='KP rating in Show',
            original_title='KP rating in Show',
            type='Movie',
        )
        ExternalRating.objects.create(show=rated, kp=8.1)
        legacy_only = Show.objects.create(
            title='KP rating only in legacy row',
            original_title='KP rating only in legacy row',
            type='Movie',
            kinopoisk_rating=7.2,
        )

        self.assertEqual(calculate_has_kp_metric(), [{'name': 'Фильм', 'value': 1}])
        self.assertEqual(
            list(get_has_rating_list('Movie', 'kp')),
            [{'id': rated.id, 'title': rated.title, 'original_title': rated.original_title}],
        )

    def test_missing_status_metric_details_are_limited_to_series_types(self):
        series = Show.objects.create(
            title='Series without status',
            original_title='Series without status',
            type='Series',
            kinopub_id=1001,
        )
        Show.objects.create(
            title='Movie without status',
            original_title='Movie without status',
            type='Movie',
            kinopub_id=1002,
        )

        self.assertEqual(
            list(get_missing_status_list('Series')),
            [{'id': series.id, 'title': series.title, 'original_title': series.original_title}],
        )

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

    def test_duplicate_photo_details_include_kinopoisk_person_id(self):
        shared_photo = 'https://image.kinopoisk.ru/kp/shared.jpg'
        first = Person.objects.create(
            name='KP Person A', kp_photo_url=shared_photo, kinopoisk_person_id=101
        )
        second = Person.objects.create(
            name='KP Person B', kp_photo_url=shared_photo, kinopoisk_person_id=202
        )

        items, has_more = get_duplicate_photo_urls_page('KP', limit=10)

        self.assertFalse(has_more)
        self.assertEqual(len(items), 1)
        self.assertEqual(
            [(person['id'], person['kinopoisk_person_id']) for person in items[0]['persons']],
            [(first.id, 101), (second.id, 202)],
        )


class ProfessionMetricTests(TestCase):
    def test_english_roles_use_the_english_crew_field(self):
        person = Person.objects.create(name='Known actor', en_name='Known actor')
        show = Show.objects.create(title='Test movie', original_title='Test movie', type='Movie')
        ShowCrew.objects.create(
            show=show,
            person=person,
            profession='В ролях',
            en_profession='Actor',
        )

        stats = calculate_en_professions_stats_metric()
        self.assertNotIn({'name': 'Неизвестно', 'value': 1}, stats)
        self.assertEqual(get_profession_persons_list('Actor', 'en').count(), 1)


class UnusedPersonMetricTests(TestCase):
    def test_roles_attached_to_an_alias_are_counted_for_the_canonical_person(self):
        master = Person.objects.create(name='Canonical person')
        alias = Person.objects.create(name='Alias person', master_person=master)
        show = Show.objects.create(title='Show', original_title='Show', type='Movie')
        ShowCrew.objects.create(show=show, person=alias, canonical_person=master)

        self.assertEqual(calculate_unused_persons_metric(), [{'name': 'Без ролей', 'value': 0}])
        self.assertFalse(get_unused_persons_list().filter(id=master.id).exists())

    def test_unused_person_metric_uses_correlated_exists(self):
        Person.objects.create(name='Unused person')
        with CaptureQueriesContext(connection) as queries:
            metric = calculate_unused_persons_metric()

        self.assertEqual(metric, [{'name': 'Без ролей', 'value': 1}])
        count_sql = next(
            query['sql'] for query in queries if 'SELECT COUNT' in query['sql'].upper()
        )
        self.assertIn('EXISTS', count_sql.upper())
        self.assertNotIn('IN (SELECT DISTINCT', count_sql.upper())

    def test_unused_person_details_use_correlated_exists(self):
        Person.objects.create(name='Unused person')
        with CaptureQueriesContext(connection) as queries:
            list(get_unused_persons_list()[:1])

        detail_sql = next(
            query['sql']
            for query in queries
            if 'SELECT "app_person"' in query['sql']
        )
        self.assertIn('EXISTS', detail_sql.upper())
        self.assertNotIn('IN (SELECT DISTINCT', detail_sql.upper())


class TotalPersonsMetricTests(TestCase):
    def test_total_persons_uses_canonical_id_without_person_join_when_backfilled(self):
        person = Person.objects.create(name='Canonical person')
        show = Show.objects.create(
            title='Show', original_title='Show', type='Movie'
        )
        ShowCrew.objects.create(show=show, person=person, canonical_person=person)

        with CaptureQueriesContext(connection) as queries:
            metric = calculate_total_persons_by_show_type_metric()

        self.assertEqual(metric, [{'name': 'Фильм', 'value': 1}])
        aggregate_sql = next(
            query['sql']
            for query in queries
            if 'COUNT(DISTINCT' in query['sql'].upper()
        )
        self.assertNotIn('JOIN "app_person"', aggregate_sql.upper())
