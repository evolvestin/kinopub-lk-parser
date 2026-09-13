from datetime import date
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from app.models import Country, Genre, Show, UserRating, ViewHistory, ViewUser, ViewUserGroup
from app.services.metrics import calculate_missing_country_meta_metric, get_missing_country_meta_list
from app.services.stats_calculator import generate_group_stats
from app.views import _serialize_show_details, bot_search_shows


class QueryBudgetTests(TestCase):
    """Regression tests for ORM work that used to scale with row count."""

    def setUp(self):
        cache.clear()
        self.user = ViewUser.objects.create(telegram_id=101, name='Alice')
        self.genre = Genre.objects.create(name='Drama')
        self.show = Show.objects.create(
            title='A title',
            original_title='A title',
            type='movie',
        )
        self.show.genres.add(self.genre)
        UserRating.objects.create(user=self.user, show=self.show, rating=8)

    def test_prefetched_show_helpers_use_zero_queries(self):
        show = Show.objects.prefetch_related('genres', 'ratings__user').get(pk=self.show.pk)

        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(show.display_genres, ['Drama'])
            rating, _ = show.get_internal_rating_data(current_user=self.user)

        self.assertEqual(rating, 8)
        self.assertEqual(
            len(queries),
            0,
            'display_genres/get_internal_rating_data must consume prefetched relations',
        )

    def test_group_member_views_are_aggregated_in_one_query(self):
        group = ViewUserGroup.objects.create(name='Team')
        group.users.add(self.user)
        history = ViewHistory.objects.create(
            show=self.show,
            view_date=date(2025, 1, 2),
            season_number=0,
            episode_number=0,
        )
        history.users.add(self.user)

        cache.clear()
        with CaptureQueriesContext(connection) as queries_one_member:
            stats_one_member = generate_group_stats(self.user)

        self.assertEqual(stats_one_member['members'][0]['views'], 1)

        second_user = ViewUser.objects.create(telegram_id=102, name='Bob')
        group.users.add(second_user)
        second_history = ViewHistory.objects.create(
            show=self.show,
            view_date=date(2025, 1, 3),
            season_number=0,
            episode_number=1,
        )
        second_history.users.add(second_user)

        cache.clear()
        with CaptureQueriesContext(connection) as queries_two_members:
            stats_two_members = generate_group_stats(self.user)

        member_views = {member['id']: member['views'] for member in stats_two_members['members']}
        self.assertEqual(member_views, {self.user.id: 1, second_user.id: 1})
        self.assertEqual(
            len(queries_one_member),
            len(queries_two_members),
            'adding a group member must not add a per-member COUNT query',
        )

    def test_show_serializer_query_count_is_constant_for_history_rows(self):
        def serialize_with_prefetch():
            show = (
                Show.objects.prefetch_related('genres', 'countries', 'ratings__user')
                .get(pk=self.show.pk)
            )
            with CaptureQueriesContext(connection) as queries:
                _serialize_show_details(show, self.user)
            return len(queries)

        first_history = ViewHistory.objects.create(
            show=self.show,
            view_date=date(2025, 2, 1),
            season_number=1,
            episode_number=1,
        )
        first_history.users.add(self.user)
        one_history_queries = serialize_with_prefetch()

        for episode, day in ((2, 2), (3, 3)):
            history = ViewHistory.objects.create(
                show=self.show,
                view_date=date(2025, 2, day),
                season_number=1,
                episode_number=episode,
            )
            history.users.add(self.user)

        three_history_queries = serialize_with_prefetch()
        self.assertEqual(
            one_history_queries,
            three_history_queries,
            'serializing more history rows must not add relation queries per row',
        )

    def test_country_metadata_metrics_do_not_query_once_per_alias(self):
        for canonical_name, raw_name, iso_code in (
            ('Беларусь', 'Belarus', 'BY'),
            ('Германия', 'Germany', 'DE'),
            ('Россия', 'Russia', 'RU'),
        ):
            Country.objects.create(name=canonical_name, iso_code=iso_code)
            Country.objects.create(name=raw_name)

        with CaptureQueriesContext(connection) as queries:
            metric = calculate_missing_country_meta_metric()
            missing = get_missing_country_meta_list()

        self.assertEqual(metric, [{'name': 'Страны', 'value': 0}])
        self.assertEqual(missing, [])
        self.assertEqual(
            len(queries),
            4,
            'country metadata metrics should use bounded queries for all aliases',
        )

    def test_bot_search_query_count_is_constant_for_matching_shows(self):
        request_factory = RequestFactory()

        def run_search():
            request = request_factory.get(
                '/api/bot/search',
                {'q': 'title', 'telegram_id': self.user.telegram_id},
                HTTP_X_BOT_TOKEN='test-token',
            )
            with CaptureQueriesContext(connection) as queries:
                response = bot_search_shows(request)
            self.assertEqual(response.status_code, 200)
            return len(queries)

        with patch('app.views.settings.BOT_TOKEN', 'test-token'):
            one_show_queries = run_search()
            for index in range(2):
                Show.objects.create(
                    title=f'Another title {index}',
                    original_title=f'Another title {index}',
                    type='movie',
                )
            three_show_queries = run_search()

        self.assertEqual(
            one_show_queries,
            three_show_queries,
            'bot search must batch prefetches instead of querying per matching show',
        )
