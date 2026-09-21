from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from app.management.commands.syncimdbdata import Command as ImdbCommand
from app.management.commands.syncpoiskkinoratings import Command
from app.models import ExternalRating, Person, Show, ShowCrew, ShowPoster
from app.services.poiskkino_client import PoiskkinoFetchResult
from shared.formatters import format_country_display_names


class PoiskkinoSyncHelperTests(SimpleTestCase):
    def test_object_list_treats_null_and_invalid_values_as_empty(self):
        self.assertEqual(Command._object_list({'genres': None}, 'genres'), [])
        self.assertEqual(Command._object_list({'genres': {'name': 'Drama'}}, 'genres'), [])
        self.assertEqual(
            Command._object_list({'genres': [{'name': 'Drama'}, None]}, 'genres'),
            [{'name': 'Drama'}],
        )

    def test_person_id_is_coerced_without_api_lookup(self):
        self.assertEqual(Command._coerce_person_id(123), 123)
        self.assertEqual(Command._coerce_person_id('123'), 123)
        self.assertIsNone(Command._coerce_person_id(None))
        self.assertIsNone(Command._coerce_person_id('not-an-id'))
        self.assertIsNone(Command._coerce_person_id(0))

    def test_deadlock_is_detected_by_postgres_sqlstate_or_message(self):
        sqlstate_error = OperationalError('database operation failed')
        cause = OperationalError('postgres deadlock')
        cause.sqlstate = '40P01'
        sqlstate_error.__cause__ = cause

        self.assertTrue(Command._is_deadlock(sqlstate_error))
        self.assertTrue(Command._is_deadlock(OperationalError('deadlock detected')))
        self.assertFalse(Command._is_deadlock(OperationalError('connection lost')))

    def test_deadlocked_write_is_retried(self):
        attempts = 0

        def operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise OperationalError('deadlock detected')
            return 'saved'

        with patch('app.management.commands.syncpoiskkinoratings.time.sleep') as sleep:
            self.assertEqual(Command._with_deadlock_retry(operation, 'test write'), 'saved')

        self.assertEqual(attempts, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_showcrew_professions_are_unbounded_text_fields(self):
        self.assertEqual(ShowCrew._meta.get_field('profession').get_internal_type(), 'TextField')
        self.assertEqual(ShowCrew._meta.get_field('en_profession').get_internal_type(), 'TextField')

    def test_country_display_names_deduplicate_source_aliases(self):
        countries = [
            type('Country', (), {'name': 'США', 'emoji_flag': '🇺🇸'})(),
            type('Country', (), {'name': 'United States of America', 'emoji_flag': None})(),
            type('Country', (), {'name': 'Италия', 'emoji_flag': '🇮🇹'})(),
            type('Country', (), {'name': 'Italy', 'emoji_flag': None})(),
        ]

        self.assertEqual(
            format_country_display_names(
                countries,
                {country.name: country.emoji_flag for country in countries},
            ),
            ['🇮🇹 Италия', '🇺🇸 США'],
        )


class ImdbRatingTimestampTests(TestCase):
    def test_imdb_rating_sync_records_its_own_timestamp(self):
        show = Show.objects.create(
            title='IMDb timestamp test',
            original_title='IMDb timestamp test',
            type='Movie',
            imdb_id='tt12345678',
        )

        result = ImdbCommand._save_rating_batch([('tt12345678', 8.4, 1234)], {})

        show.refresh_from_db()
        self.assertEqual(result['updated'], 1)
        self.assertEqual(show.imdb_rating, 8.4)
        self.assertIsNotNone(show.imdb_rating_updated_at)


class PoiskkinoRefreshSelectionTests(TestCase):
    def test_batch_does_not_write_stale_status_when_source_omits_it(self):
        show = Show.objects.create(
            title='Status preservation test',
            original_title='Status preservation test',
            type='Series',
            status='Finished',
        )

        with patch.object(Show.objects, 'bulk_update', wraps=Show.objects.bulk_update) as bulk_update:
            Command()._process_batch(
                [{'id': 900001, 'rating': {'kp': 8.2}}],
                {900001: show.id},
                timezone.now(),
            )

        show.refresh_from_db()
        self.assertEqual(show.status, 'Finished')
        self.assertTrue(bulk_update.called)
        self.assertNotIn('status', bulk_update.call_args_list[0].args[1])

    def test_checked_kp_ids_update_their_mapped_shows(self):
        rated_show = Show.objects.create(
            title='Rated show',
            original_title='Rated show',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/900001/',
        )
        unrated_show = Show.objects.create(
            title='Unrated show',
            original_title='Unrated show',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/900002/',
        )
        kp_mapping = {
            900001: rated_show.id,
            900002: unrated_show.id,
        }
        result = PoiskkinoFetchResult(
            data=[
                {'id': 900001, 'rating': {'kp': 8.2}},
                {'id': 900002, 'rating': {}},
            ],
            checked_values=[900001, 900002],
            completed=True,
            requests_made=1,
        )

        with (
            patch(
                'app.management.commands.syncpoiskkinoratings.get_kp_mapping',
                return_value=kp_mapping,
            ),
            patch(
                'app.management.commands.syncpoiskkinoratings.PoiskkinoClient'
            ) as client_class,
        ):
            client_class.return_value.fetch_ratings_by_ids.return_value = result
            Command().handle(limit=2)

        rated_show.refresh_from_db()
        unrated_show.refresh_from_db()
        self.assertIsNotNone(rated_show.poiskkino_updated_at)
        self.assertIsNotNone(unrated_show.poiskkino_updated_at)
        self.assertTrue(rated_show.kinopoisk_rating_available)
        self.assertFalse(unrated_show.kinopoisk_rating_available)
        self.assertEqual(ExternalRating.objects.get(show=rated_show).kp, 8.2)
        self.assertIsNone(ExternalRating.objects.get(show=unrated_show).kp)


class PoiskkinoPosterConflictTests(TestCase):
    def test_conflicting_poster_does_not_abort_sync_write(self):
        existing_show = Show.objects.create(
            title='Existing show',
            original_title='Existing show',
            type='Movie',
        )
        incoming_show = Show.objects.create(
            title='Incoming show',
            original_title='Incoming show',
            type='Movie',
        )
        existing_poster = ShowPoster.objects.create(
            show=existing_show,
            source=ShowPoster.SOURCE_KINOPOISK,
            variant='main',
            external_id=6695,
            url='https://example.test/existing.jpg',
        )

        now = timezone.now()
        Command._save_posters(
            [
                ShowPoster(
                    show=incoming_show,
                    source=ShowPoster.SOURCE_KINOPOISK,
                    variant='main',
                    external_id=6695,
                    url='https://example.test/incoming.jpg',
                )
            ],
            now,
        )

        existing_poster.refresh_from_db()
        self.assertEqual(existing_poster.show_id, existing_show.id)
        self.assertEqual(existing_poster.url, 'https://example.test/existing.jpg')
        self.assertFalse(
            ShowPoster.objects.filter(
                show=incoming_show, source=ShowPoster.SOURCE_KINOPOISK
            ).exists()
        )

    def test_existing_poster_for_same_show_is_updated(self):
        show = Show.objects.create(
            title='Poster update show',
            original_title='Poster update show',
            type='Movie',
        )
        poster = ShowPoster.objects.create(
            show=show,
            source=ShowPoster.SOURCE_KINOPOISK,
            variant='main',
            external_id=123,
            url='https://example.test/old.jpg',
        )

        Command._save_posters(
            [
                ShowPoster(
                    show=show,
                    source=ShowPoster.SOURCE_KINOPOISK,
                    variant='main',
                    external_id=456,
                    url='https://example.test/new.jpg',
                )
            ],
            timezone.now(),
        )

        poster.refresh_from_db()
        self.assertEqual(poster.external_id, 456)
        self.assertEqual(poster.url, 'https://example.test/new.jpg')


class PoiskkinoPersonMatchingTests(TestCase):
    def test_one_kp_id_with_name_variants_creates_one_person(self):
        show = Show.objects.create(
            title='KP person matching test',
            original_title='KP person matching test',
            type='Movie',
        )

        Command()._process_batch(
            [
                {
                    'id': 900001,
                    'persons': [
                        {'id': 700001, 'name': 'Иван Иванов', 'profession': 'Актёр'},
                        {'id': 700001, 'name': 'Иванов Иван', 'profession': 'Режиссёр'},
                    ],
                }
            ],
            {900001: show.id},
            timezone.now(),
        )

        self.assertEqual(
            Person.objects.filter(kinopoisk_person_id=700001).count(),
            1,
        )
        self.assertEqual(
            ShowCrew.objects.filter(show=show).values('person_id').distinct().count(),
            1,
        )

    def test_existing_kp_id_wins_over_a_new_source_name(self):
        show = Show.objects.create(
            title='Existing KP person test',
            original_title='Existing KP person test',
            type='Movie',
        )
        person = Person.objects.create(name='Старое имя', kinopoisk_person_id=700002)

        Command()._process_batch(
            [
                {
                    'id': 900002,
                    'persons': [
                        {'id': 700002, 'name': 'Новое имя', 'profession': 'Актёр'},
                    ],
                }
            ],
            {900002: show.id},
            timezone.now(),
        )

        self.assertEqual(Person.objects.filter(kinopoisk_person_id=700002).count(), 1)
        self.assertTrue(ShowCrew.objects.filter(show=show, person=person).exists())
