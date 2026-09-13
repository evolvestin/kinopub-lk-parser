import json
from unittest.mock import patch

from django.test import TestCase

from app.dashboard import dashboard_callback
from app.models import SiteMetric
from app.services.stats_calculator import GLOBAL_STATS_SNAPSHOT_KEY


class AdminDashboardStatsTests(TestCase):
    def test_dashboard_reads_persisted_snapshot_and_queues_refresh(self):
        stats = {'meta': {'years': [2026]}, 'summary': {'total_views': 3}}
        SiteMetric.objects.create(key=GLOBAL_STATS_SNAPSHOT_KEY, data=stats)

        with (
            patch('app.dashboard.cache.add', return_value=True),
            patch('app.tasks.refresh_global_stats_task.delay') as delay,
        ):
            context = dashboard_callback({})

        self.assertEqual(json.loads(context['global_stats_json']), stats)
        self.assertIsNotNone(context['global_stats_extracted_at'])
        self.assertTrue(context['global_stats_refresh_queued'])
        delay.assert_called_once_with()

    def test_dashboard_does_not_enqueue_again_inside_cooldown(self):
        with (
            patch('app.dashboard.cache.add', return_value=False),
            patch('app.tasks.refresh_global_stats_task.delay') as delay,
        ):
            context = dashboard_callback({})

        self.assertIsNone(json.loads(context['global_stats_json']))
        self.assertFalse(context['global_stats_refresh_queued'])
        delay.assert_not_called()
