from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db.models import Case, Count, OuterRef, Q, Subquery, Sum, When
from django.db.models.functions import TruncMonth
from django.utils import timezone

from shared.constants import DATETIME_FORMAT
from shared.formatters import format_duration



def dashboard_callback(context):
    ShowDuration = apps.get_model('app', 'ShowDuration')
    ViewHistory = apps.get_model('app', 'ViewHistory')

    episode_duration_query = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number=OuterRef('season_number'),
        episode_number=OuterRef('episode_number'),
    )
    movie_duration_query = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number__isnull=True,
        episode_number__isnull=True,
    )
    total_seconds_result = ViewHistory.objects.annotate(
        duration=Case(
            When(
                season_number=0,
                then=Subquery(movie_duration_query.values('duration_seconds')[:1]),
            ),
            default=Subquery(episode_duration_query.values('duration_seconds')[:1]),
        )
    ).aggregate(total_duration=Sum('duration'))

    total_seconds = total_seconds_result.get('total_duration') or 0
    duration_str = format_duration(total_seconds)

    statistics_aggregate = ViewHistory.objects.aggregate(
        total_episodes=Count('id', filter=Q(season_number__gt=0)),
        total_movies=Count('id', filter=Q(season_number=0)),
        watched_series_count=Count('show_id', distinct=True, filter=Q(show__type='Series')),
    )
    total_episodes = statistics_aggregate.get('total_episodes', 0)
    total_movies = statistics_aggregate.get('total_movies', 0)
    watched_series_count = statistics_aggregate.get('watched_series_count', 0)

    top_series_queryset = (
        ViewHistory.objects.filter(show__type='Series')
        .values('show__title')
        .annotate(episode_count=Count('id'))
        .order_by('-episode_count')[:5]
    )

    top_movies_queryset = (
        ViewHistory.objects.filter(show__type='Movie')
        .values('show__title')
        .annotate(view_count=Count('id'))
        .order_by('-view_count')[:5]
    )

    twelve_months_ago = timezone.now().date() - timedelta(days=365)
    views_per_month = (
        ViewHistory.objects.filter(view_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('view_date'))
        .values('month')
        .annotate(views_count=Count('id'))
        .order_by('month')
    )

    chart_labels = [entry['month'].strftime('%b %Y') for entry in views_per_month]
    chart_data = [entry['views_count'] for entry in views_per_month]

    context['stats'] = {
        'duration': duration_str,
        'episodes': total_episodes,
        'movies': total_movies,
        'series': watched_series_count,
    }
    context['top_series'] = list(top_series_queryset)
    context['top_movies'] = list(top_movies_queryset)
    context['chart_labels'] = chart_labels
    context['chart_data'] = chart_data

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
