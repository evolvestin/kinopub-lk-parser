import json
import logging

from django.core.cache import cache
from django.utils import timezone

from app.models import SiteMetric
from app.services.stats_calculator import (
    GLOBAL_STATS_REFRESH_COOLDOWN_KEY,
    GLOBAL_STATS_SNAPSHOT_KEY,
)


def queue_global_stats_refresh():
    """Queue at most one dashboard refresh during the one-hour cooldown."""
    try:
        if not cache.add(GLOBAL_STATS_REFRESH_COOLDOWN_KEY, True, timeout=3600):
            return False

        # Import lazily: app.tasks imports a number of application services,
        # while this module is loaded during admin-site initialization.
        from app.tasks import refresh_global_stats_task

        refresh_global_stats_task.delay()
        return True
    except Exception:
        # A broker outage must not leave the cooldown blocking the next visit.
        try:
            cache.delete(GLOBAL_STATS_REFRESH_COOLDOWN_KEY)
        except Exception:
            logging.exception('Failed to clear global stats refresh cooldown')
        logging.exception('Failed to queue global stats refresh')
        return False


def get_global_stats_snapshot():
    return (
        SiteMetric.objects.filter(key=GLOBAL_STATS_SNAPSHOT_KEY)
        .order_by('-updated_at')
        .first()
    )


def dashboard_callback(context):
    snapshot = get_global_stats_snapshot()
    context['global_stats_json'] = json.dumps(snapshot.data if snapshot else None)
    context['global_stats_extracted_at'] = (
        timezone.localtime(snapshot.updated_at).strftime('%d.%m.%Y %H:%M:%S')
        if snapshot
        else None
    )
    context['global_stats_refresh_queued'] = queue_global_stats_refresh()
    return context
