import json
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from app.services.stats_calculator import generate_global_stats
from shared.constants import DATETIME_FORMAT


def dashboard_callback(context):
    global_stats = generate_global_stats()
    context['global_stats_json'] = json.dumps(global_stats)
    return context


def get_scheduled_tasks_info():
    """Возвращает список запланированных задач с учетом реального времени последнего запуска."""
    scheduled_tasks = []
    now = timezone.now()

    if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
        for name, config in settings.CELERY_BEAT_SCHEDULE.items():
            schedule_obj = config.get('schedule')
            task_path = config.get('task')

            # Получаем реальное время из Redis (записанное сигналом task_prerun)
            last_run_time = cache.get(f'last_run_{task_path}')
            next_run_dt = now

            try:
                if isinstance(schedule_obj, (int, float, timedelta)):
                    if isinstance(schedule_obj, timedelta):
                        interval = schedule_obj.total_seconds()
                    else:
                        interval = float(schedule_obj)

                    if last_run_time:
                        # Считаем строго от последнего реального запуска
                        next_run_dt = last_run_time + timedelta(seconds=interval)

                        # Если сервер был выключен или была задержка, нагоняем интервалы
                        if next_run_dt <= now:
                            delta = (now - next_run_dt).total_seconds()
                            intervals_passed = int(delta // interval) + 1
                            next_run_dt += timedelta(seconds=interval * intervals_passed)
                    else:
                        # Если данных о запуске нет (первый старт), выравниваем по сетке времени
                        next_run_dt = now + timedelta(
                            seconds=interval - (now.timestamp() % interval)
                        )
                        if next_run_dt <= now:
                            next_run_dt += timedelta(seconds=interval)

                    next_run_dt = next_run_dt.replace(microsecond=0)

                elif hasattr(schedule_obj, 'is_due'):
                    is_due, next_seconds = schedule_obj.is_due(now)
                    next_run_dt = now + timedelta(seconds=next_seconds)
                    # Корректировка округления для crontab
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
