from datetime import date
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from app.models import Show, UserStatsAggregate, ViewHistory, ViewUser, ViewUserGroup
from app.services.stats_calculator import (
    generate_user_stats,
    load_user_stats_aggregate_periods,
    mark_user_stats_aggregates_dirty,
)


class UserStatsAggregateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = ViewUser.objects.create(telegram_id=987654321, name='Stats user')

    def test_clean_aggregate_is_returned_without_running_aggregate_queries(self):
        payload = {'summary': {'total_views': 17}, 'history_movies': []}
        UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_PERSONAL,
            year=2026,
            aggregates={'summary': payload['summary']},
            details={'history_movies': [], 'ratings_history': []},
            ready=True,
        )

        with (
            patch('app.services.stats_calculator._get_yearly_summary') as calculate,
            self.assertNumQueries(1),
        ):
            result = generate_user_stats(self.user, year=2026)

        self.assertEqual(result, payload)
        calculate.assert_not_called()

    def test_dirty_aggregate_is_served_and_refresh_is_queued_once(self):
        payload = {'summary': {'total_views': 17}, 'history_movies': []}
        UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_PERSONAL,
            year=2026,
            aggregates={'summary': payload['summary']},
            details={'history_movies': [], 'ratings_history': []},
            ready=True,
            dirty=True,
            dirty_version=1,
        )

        with patch('celery.current_app.send_task') as send_task:
            first = generate_user_stats(self.user, year=2026)
            second = generate_user_stats(self.user, year=2026)

        self.assertEqual(first, payload)
        self.assertEqual(second, payload)
        send_task.assert_called_once()

    def test_invalidation_marks_period_and_all_time_aggregates_dirty(self):
        current_year = UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_PERSONAL,
            year=2026,
            aggregates={'year': 2026},
            ready=True,
        )
        all_time = UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_PERSONAL,
            year=None,
            aggregates={'year': None},
            ready=True,
        )
        old_year = UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_PERSONAL,
            year=2025,
            aggregates={'year': 2025},
            ready=True,
        )

        mark_user_stats_aggregates_dirty(self.user.id, 2026)

        current_year.refresh_from_db()
        all_time.refresh_from_db()
        old_year.refresh_from_db()
        self.assertTrue(current_year.dirty)
        self.assertTrue(all_time.dirty)
        self.assertFalse(old_year.dirty)

    def test_group_membership_change_marks_group_payload_stale(self):
        aggregate = UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_GROUP,
            year=None,
            aggregates={'group_name': 'Old group'},
            ready=True,
        )
        group = ViewUserGroup.objects.create(name='Stats group')

        group.users.add(self.user)

        aggregate.refresh_from_db()
        self.assertTrue(aggregate.dirty)

    def test_moving_viewing_to_another_year_invalidates_both_years(self):
        show = Show.objects.create(title='Stats show', original_title='Stats show', type='movie')
        history = ViewHistory.objects.create(show=show, view_date=date(2025, 12, 31))
        history.users.add(self.user)

        with patch('app.signals.mark_user_stats_aggregates_dirty') as invalidate:
            history.view_date = date(2026, 1, 1)
            history.save(update_fields=['view_date'])

        invalidated = {
            call.args[1]
            for call in invalidate.call_args_list
            if call.args[0] == self.user.id
        }
        self.assertEqual(invalidated, {2025, 2026})

    def test_all_ready_periods_are_read_in_one_query(self):
        for year in (2024, 2025):
            UserStatsAggregate.objects.create(
                user=self.user,
                scope=UserStatsAggregate.SCOPE_PERSONAL,
                year=year,
                aggregates={'summary': {'total_views': year}},
                details={'history_movies': []},
                ready=True,
            )

        with self.assertNumQueries(1):
            result, pending = load_user_stats_aggregate_periods(self.user, ['2024', '2025'])

        self.assertEqual(pending, [])
        self.assertEqual(set(result), {'2024', '2025'})
        self.assertEqual(result['2024']['summary']['total_views'], 2024)

    def test_missing_periods_are_queued_instead_of_calculated_in_request(self):
        with patch('celery.current_app.send_task') as send_task:
            result, pending = load_user_stats_aggregate_periods(self.user, [2024, 2025])

        self.assertEqual(result, {})
        self.assertEqual(pending, ['2024', '2025'])
        self.assertEqual(send_task.call_count, 2)

    def test_bulk_periods_return_ready_rows_while_other_periods_build(self):
        UserStatsAggregate.objects.create(
            user=self.user,
            scope=UserStatsAggregate.SCOPE_PERSONAL,
            year=2024,
            aggregates={'summary': {'total_views': 12}},
            details={'history_movies': []},
            ready=True,
        )

        with patch('celery.current_app.send_task'):
            result, pending = load_user_stats_aggregate_periods(self.user, [2024, 2025])

        self.assertEqual(pending, ['2025'])
        self.assertEqual(result['2024']['summary']['total_views'], 12)
