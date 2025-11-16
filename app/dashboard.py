from datetime import timedelta
from django.db.models import Sum, Subquery, OuterRef, Case, When, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from unfold.components import Chart, Card
from unfold.widgets import List, ListItem

from app.models import ViewHistory, ShowDuration


def dashboard_callback(request, context):
    episode_duration_q = ShowDuration.objects.filter(
        show_id=OuterRef("show_id"),
        season_number=OuterRef("season_number"),
        episode_number=OuterRef("episode_number"),
    )
    movie_duration_q = ShowDuration.objects.filter(
        show_id=OuterRef("show_id"),
        season_number__isnull=True,
        episode_number__isnull=True,
    )
    total_seconds_res = (
        ViewHistory.objects.annotate(
            duration=Case(
                When(
                    season_number=0,
                    then=Subquery(movie_duration_q.values("duration_seconds")[:1]),
                ),
                default=Subquery(episode_duration_q.values("duration_seconds")[:1]),
            )
        ).aggregate(total_duration=Sum("duration"))
    )

    total_seconds = total_seconds_res.get("total_duration") or 0
    total_minutes, _ = divmod(total_seconds, 60)
    total_hours, rem_minutes = divmod(total_minutes, 60)
    total_days, rem_hours = divmod(total_hours, 24)
    duration_str = f"{total_days} д. {rem_hours} ч. {rem_minutes} м."

    total_episodes = ViewHistory.objects.filter(season_number__gt=0).count()
    total_movies = ViewHistory.objects.filter(season_number=0).count()
    watched_series_count = ViewHistory.objects.filter(show__type='Series').values('show_id').distinct().count()

    top_series_qs = ViewHistory.objects.filter(
        show__type='Series'
    ).values(
        'show__title'
    ).annotate(
        episode_count=Count('id')
    ).order_by('-episode_count')[:5]

    top_movies_qs = ViewHistory.objects.filter(
        show__type='Movie'
    ).values(
        'show__title'
    ).annotate(
        view_count=Count('id')
    ).order_by('-view_count')[:5]

    top_series_list = List(
        children=[
            ListItem(title=f"{series['show__title']} ({series['episode_count']})")
            for series in top_series_qs
        ] if top_series_qs else [ListItem(title="Недостаточно данных.")]
    )

    top_movies_list = List(
        children=[
            ListItem(title=f"{movie['show__title']} ({movie['view_count']})")
            for movie in top_movies_qs
        ] if top_movies_qs else [ListItem(title="Недостаточно данных.")]
    )

    twelve_months_ago = timezone.now().date() - timedelta(days=365)
    views_per_month = ViewHistory.objects.filter(
        view_date__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('view_date')
    ).values('month').annotate(
        c=Count('id')
    ).order_by('month')

    chart_labels = [d['month'].strftime('%b %Y') for d in views_per_month]
    chart_data = [d['c'] for d in views_per_month]

    stats_list = List(
        children=[
            ListItem(title=f"Общее время просмотра: {duration_str}"),
            ListItem(title=f"Просмотрено эпизодов: {total_episodes}"),
            ListItem(title=f"Просмотрено фильмов: {total_movies}"),
            ListItem(title=f"Просмотрено сериалов: {watched_series_count}"),
        ]
    )

    components = [
        Card(title="Статистика", children=[stats_list]),
        Card(title="Топ-5 сериалов (по эпизодам)", children=[top_series_list]),
        Card(title="Топ-5 фильмов (по просмотрам)", children=[top_movies_list]),
        Chart(
            title="Активность просмотров",
            data={
                "labels": chart_labels,
                "datasets": [
                    {
                        "label": "Просмотры по месяцам (за последний год)",
                        "data": chart_data,
                    }
                ],
            },
        )
    ]

    context.update({"dashboard_components": components})
    return context
