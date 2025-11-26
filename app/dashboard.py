from datetime import timedelta

from django.db.models import Case, Count, OuterRef, Q, Subquery, Sum, When
from django.db.models.functions import TruncMonth
from django.utils import timezone

from app.models import ShowDuration, ViewHistory


def dashboard_callback(request, context):
    episode_duration_q = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number=OuterRef('season_number'),
        episode_number=OuterRef('episode_number'),
    )
    movie_duration_q = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number__isnull=True,
        episode_number__isnull=True,
    )
    total_seconds_res = ViewHistory.objects.annotate(
        duration=Case(
            When(
                season_number=0,
                then=Subquery(movie_duration_q.values('duration_seconds')[:1]),
            ),
            default=Subquery(episode_duration_q.values('duration_seconds')[:1]),
        )
    ).aggregate(total_duration=Sum('duration'))

    total_seconds = total_seconds_res.get('total_duration') or 0
    total_minutes, _ = divmod(total_seconds, 60)
    total_hours, rem_minutes = divmod(total_minutes, 60)
    total_days, rem_hours = divmod(total_hours, 24)
    duration_str = f'{total_days} д. {rem_hours} ч. {rem_minutes} м.'

    stats_agg = ViewHistory.objects.aggregate(
        total_episodes=Count('id', filter=Q(season_number__gt=0)),
        total_movies=Count('id', filter=Q(season_number=0)),
        watched_series_count=Count('show_id', distinct=True, filter=Q(show__type='Series')),
    )
    total_episodes = stats_agg.get('total_episodes', 0)
    total_movies = stats_agg.get('total_movies', 0)
    watched_series_count = stats_agg.get('watched_series_count', 0)

    top_series_qs = (
        ViewHistory.objects.filter(show__type='Series')
        .values('show__title')
        .annotate(episode_count=Count('id'))
        .order_by('-episode_count')[:5]
    )

    top_movies_qs = (
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
        .annotate(c=Count('id'))
        .order_by('month')
    )

    chart_labels = [d['month'].strftime('%b %Y') for d in views_per_month]
    chart_data = [d['c'] for d in views_per_month]

    context['stats'] = {
        'duration': duration_str,
        'episodes': total_episodes,
        'movies': total_movies,
        'series': watched_series_count,
    }
    context['top_series'] = list(top_series_qs)
    context['top_movies'] = list(top_movies_qs)
    context['chart_labels'] = chart_labels
    context['chart_data'] = chart_data

    return context
