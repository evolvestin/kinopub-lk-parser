import logging

from django.conf import settings
from redis import Redis

logger = logging.getLogger(__name__)


def enqueue_show_update(show_ids: list[int], details: bool = True, durations: bool = True):
    if not show_ids:
        return

    try:
        r = Redis.from_url(settings.CELERY_BROKER_URL)
        if details:
            r.sadd('queue:update_details', *show_ids)
        if durations:
            r.sadd('queue:update_durations', *show_ids)
    except Exception as e:
        logger.error(f'Failed to enqueue shows {show_ids} for update: {e}')
