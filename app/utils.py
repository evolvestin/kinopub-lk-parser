import logging
import os
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from redis import Redis
from shared.constants import DATETIME_FORMAT

logger = logging.getLogger(__name__)

def update_heartbeat():
    if getattr(settings, 'LOCAL_RUN', False):
        return
    try:
        heartbeat_file = settings.HEARTBEAT_FILE
        os.makedirs(os.path.dirname(heartbeat_file), exist_ok=True)
        with open(heartbeat_file, 'a'):
            os.utime(heartbeat_file, None)
    except Exception as e:
        logger.warning('Could not update heartbeat file %s: %s', settings.HEARTBEAT_FILE, e)


def enqueue_show_update(
    show_ids: list[int], details: bool = True, durations: bool = True, ratings: bool = False
):
    if not show_ids:
        return

    try:
        r = Redis.from_url(settings.CELERY_BROKER_URL)
        if details:
            r.sadd('queue:update_details', *show_ids)
        if durations:
            r.sadd('queue:update_durations', *show_ids)
        if ratings:
            r.sadd('queue:priority_ratings_sync', *show_ids)
    except Exception as e:
        logger.error(f'Failed to enqueue shows {show_ids} for update: {e}')


def get_scheduled_tasks_info():
    """Возвращает список запланированных задач с учетом реального времени последнего запуска."""
    scheduled_tasks = []
    now = timezone.now()

    if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
        for name, config in settings.CELERY_BEAT_SCHEDULE.items():
            schedule_obj = config.get('schedule')
            task_path = config.get('task')

            last_run_time = cache.get(f'last_run_{task_path}')
            next_run_dt = now

            try:
                if isinstance(schedule_obj, (int, float, timedelta)):
                    if isinstance(schedule_obj, timedelta):
                        interval = schedule_obj.total_seconds()
                    else:
                        interval = float(schedule_obj)

                    if last_run_time:
                        next_run_dt = last_run_time + timedelta(seconds=interval)

                        if next_run_dt <= now:
                            delta = (now - next_run_dt).total_seconds()
                            intervals_passed = int(delta // interval) + 1
                            next_run_dt += timedelta(seconds=interval * intervals_passed)
                    else:
                        next_run_dt = now + timedelta(
                            seconds=interval - (now.timestamp() % interval)
                        )
                        if next_run_dt <= now:
                            next_run_dt += timedelta(seconds=interval)

                    next_run_dt = next_run_dt.replace(microsecond=0)

                elif hasattr(schedule_obj, 'is_due'):
                    is_due, next_seconds = schedule_obj.is_due(now)
                    next_run_dt = now + timedelta(seconds=next_seconds)
                    next_run_dt = (next_run_dt + timedelta(microseconds=500000)).replace(
                        microsecond=0
                    )

            except Exception:
                pass

            seconds_left = (next_run_dt - now).total_seconds()

            scheduled_tasks.append(
                {
                    'name': name,
                    'next_run_display': next_run_dt.strftime(DATETIME_FORMAT),
                    'seconds_left': seconds_left,
                }
            )

    scheduled_tasks.sort(key=lambda x: x['seconds_left'])
    return scheduled_tasks
