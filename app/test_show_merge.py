from datetime import date
from unittest.mock import patch

from django.test import TestCase

from app.models import (
    CasinoSpin,
    Country,
    ExternalRating,
    Genre,
    MutedShowNotification,
    Person,
    Show,
    ShowCrew,
    ShowDuration,
    UserRating,
    ViewHistory,
    ViewUser,
    WishlistItem,
)
from app.services.show_merge import merge_show_records
from app.services.tmdb_client import sync_show_from_tmdb


class ShowMergeTests(TestCase):
    def test_merge_preserves_identity_and_all_show_relations(self):
        canonical = Show.objects.create(
            kinopub_id=1001,
            imdb_id='tt10000001',
            title='Укрытие',
            original_title='Silo',
            type='Series',
            year=2023,
        )
        duplicate = Show.objects.create(
            tmdb_id=125988,
            title='Укрытие',
            original_title='Silo',
            type='Series',
            year=2023,
            plot='TMDB plot',
        )

        country = Country.objects.create(name='United States')
        genre = Genre.objects.create(name='Science Fiction')
        canonical.countries.add(country)
        duplicate.genres.add(genre)

        person = Person.objects.create(name='Actor')
        ShowCrew.objects.create(show=duplicate, person=person, profession='Actor')
        ShowDuration.objects.create(
            show=duplicate,
            season_number=1,
            episode_number=1,
            duration_seconds=3600,
        )

        user = ViewUser.objects.create(telegram_id=10001, name='Test user')
        history = ViewHistory.objects.create(
            show=duplicate,
            view_date=date(2026, 8, 21),
            season_number=1,
            episode_number=1,
        )
        history.users.add(user)
        UserRating.objects.create(
            user=user,
            show=duplicate,
            season_number=1,
            episode_number=1,
            rating=9,
        )
        ExternalRating.objects.create(show=duplicate, tmdb=8.2)
        WishlistItem.objects.create(user=user, show=duplicate)
        CasinoSpin.objects.create(user=user, show=duplicate)
        MutedShowNotification.objects.create(user=user, show=duplicate)

        stats = merge_show_records(canonical.id, duplicate.id)

        self.assertFalse(Show.objects.filter(id=duplicate.id).exists())
        merged = Show.objects.get(id=canonical.id)
        self.assertEqual(merged.tmdb_id, 125988)
        self.assertEqual(merged.plot, 'TMDB plot')
        self.assertEqual(list(merged.countries.values_list('name', flat=True)), ['United States'])
        self.assertEqual(list(merged.genres.values_list('name', flat=True)), ['Science Fiction'])
        self.assertEqual(ShowCrew.objects.filter(show=merged).count(), 1)
        self.assertEqual(ShowDuration.objects.filter(show=merged).count(), 1)
        self.assertEqual(ViewHistory.objects.filter(show=merged).count(), 1)
        self.assertEqual(UserRating.objects.filter(show=merged).count(), 1)
        self.assertTrue(ExternalRating.objects.filter(show=merged, tmdb=8.2).exists())
        self.assertEqual(WishlistItem.objects.filter(show=merged).count(), 1)
        self.assertEqual(CasinoSpin.objects.filter(show=merged).count(), 1)
        self.assertEqual(MutedShowNotification.objects.filter(show=merged).count(), 1)
        self.assertEqual(stats.durations_moved, 1)
        self.assertEqual(stats.histories_moved, 1)

    def test_merge_unions_conflicting_unique_history_and_rating_rows(self):
        canonical = Show.objects.create(
            kinopub_id=1002,
            title='Title',
            original_title='Title',
            type='Series',
            year=2023,
        )
        duplicate = Show.objects.create(
            tmdb_id=1002,
            title='Title',
            original_title='Title',
            type='Series',
            year=2023,
        )
        user_a = ViewUser.objects.create(telegram_id=10002, name='A')
        user_b = ViewUser.objects.create(telegram_id=10003, name='B')

        first_history = ViewHistory.objects.create(
            show=canonical,
            view_date=date(2026, 8, 21),
            season_number=1,
            episode_number=1,
        )
        first_history.users.add(user_a)
        second_history = ViewHistory.objects.create(
            show=duplicate,
            view_date=date(2026, 8, 21),
            season_number=1,
            episode_number=1,
        )
        second_history.users.add(user_b)
        UserRating.objects.create(
            user=user_a,
            show=canonical,
            season_number=1,
            episode_number=1,
            rating=7,
        )
        UserRating.objects.create(
            user=user_a,
            show=duplicate,
            season_number=1,
            episode_number=1,
            rating=9,
        )

        stats = merge_show_records(canonical.id, duplicate.id)

        merged_history = ViewHistory.objects.get(show=canonical)
        self.assertSetEqual(
            set(merged_history.users.values_list('id', flat=True)), {user_a.id, user_b.id}
        )
        self.assertEqual(UserRating.objects.get(show=canonical).rating, 9)
        self.assertEqual(stats.histories_deduplicated, 1)
        self.assertEqual(stats.ratings_deduplicated, 1)

    @patch('app.services.tmdb_client.TMDBClient')
    def test_tmdb_sync_merges_bare_tmdb_row_when_imdb_belongs_to_kinopub(self, client_class):
        canonical = Show.objects.create(
            kinopub_id=1003,
            imdb_id='tt10000003',
            title='Укрытие',
            original_title='Silo',
            type='Series',
            year=2023,
        )
        duplicate = Show.objects.create(
            tmdb_id=125988,
            title='Silo',
            original_title='Silo',
            type='Series',
        )
        client_class.return_value.get_details.return_value = {
            'external_ids': {'imdb_id': 'tt10000003'},
            'name': 'Укрытие',
            'original_name': 'Silo',
            'first_air_date': '2023-01-01',
            'overview': 'Overview',
            'status': 'Ended',
            'genres': [],
            'production_countries': [],
            'credits': {'cast': [], 'crew': []},
        }

        merged = sync_show_from_tmdb(
            show_id=duplicate.id,
            tmdb_id=duplicate.tmdb_id,
            media_type='tv',
        )

        self.assertEqual(merged.id, canonical.id)
        self.assertFalse(Show.objects.filter(id=duplicate.id).exists())
        self.assertEqual(Show.objects.get(id=canonical.id).tmdb_id, 125988)

    @patch('app.services.tmdb_client.TMDBClient')
    def test_tmdb_sync_resolves_conflicting_tmdb_ids_when_imdb_matches(self, client_class):
        canonical = Show.objects.create(
            kinopub_id=1004,
            tmdb_id=270263,
            imdb_id='tt10000004',
            title='Canonical title',
            original_title='Canonical title',
            type='Series',
            year=2023,
        )
        duplicate = Show.objects.create(
            tmdb_id=32398,
            title='Duplicate title',
            original_title='Duplicate title',
            type='Series',
        )
        client_class.return_value.get_details.return_value = {
            'external_ids': {'imdb_id': 'tt10000004'},
            'name': 'Canonical title',
            'original_name': 'Canonical title',
            'first_air_date': '2023-01-01',
            'overview': 'Overview',
            'status': 'Ended',
            'genres': [],
            'production_countries': [],
            'credits': {'cast': [], 'crew': []},
        }

        merged = sync_show_from_tmdb(
            show_id=duplicate.id,
            tmdb_id=duplicate.tmdb_id,
            media_type='tv',
        )

        self.assertEqual(merged.id, canonical.id)
        self.assertFalse(Show.objects.filter(id=duplicate.id).exists())
        merged.refresh_from_db()
        self.assertEqual(merged.tmdb_id, 270263)
        self.assertEqual(merged.plot, 'Overview')

    @patch('app.services.tmdb_client.TMDBClient')
    def test_tmdb_sync_keeps_tmdb_confirmed_imdb_when_existing_row_is_stale(self, client_class):
        canonical = Show.objects.create(
            kinopub_id=1005,
            tmdb_id=270264,
            imdb_id='tt26930830',
            title='Stale title',
            original_title='Stale title',
            type='Series',
            year=2023,
        )
        duplicate = Show.objects.create(
            tmdb_id=32399,
            imdb_id='tt15565600',
            title='Confirmed title',
            original_title='Confirmed title',
            type='Series',
            year=2023,
        )
        client_class.return_value.get_details.return_value = {
            'external_ids': {'imdb_id': 'tt15565600'},
            'name': 'Confirmed title',
            'original_name': 'Confirmed title',
            'first_air_date': '2023-01-01',
            'overview': 'Overview',
            'status': 'Ended',
            'genres': [],
            'production_countries': [],
            'credits': {'cast': [], 'crew': []},
        }

        merged = sync_show_from_tmdb(
            show_id=canonical.id,
            tmdb_id=canonical.tmdb_id,
            media_type='tv',
        )

        self.assertEqual(merged.id, canonical.id)
        self.assertFalse(Show.objects.filter(id=duplicate.id).exists())
        merged.refresh_from_db()
        self.assertEqual(merged.imdb_id, 'tt15565600')
        self.assertEqual(merged.tmdb_id, 270264)
