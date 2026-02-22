import calendar
import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    When,
)
from django.db.models.functions import Coalesce, ExtractWeekDay, ExtractYear, TruncMonth
from django.utils import timezone

from app.models import ShowDuration, ViewHistory, ViewUserGroup

logger = logging.getLogger(__name__)


def _get_annotated_history(user, year=None):
    qs = ViewHistory.objects.filter(users=user, is_checked=True).select_related('show')
    if year:
        qs = qs.filter(view_date__year=year)

    episode_dur = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number=OuterRef('season_number'),
        episode_number=OuterRef('episode_number'),
    )
    movie_dur = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number__isnull=True,
        episode_number__isnull=True,
    )

    return qs.annotate(
        duration=Case(
            When(season_number=0, then=Subquery(movie_dur.values('duration_seconds')[:1])),
            default=Subquery(episode_dur.values('duration_seconds')[:1]),
        )
    ).annotate(final_duration=Coalesce('duration', 0))


def _get_yearly_summary(qs, year=None):
    agg = qs.aggregate(
        total_seconds=Sum('final_duration'),
        total_views=Count('id'),
        total_episodes=Count('id', filter=Q(season_number__gt=0)),
        total_movies=Count('id', filter=Q(season_number=0)),
        unique_shows=Count('show_id', distinct=True),
        unique_series=Count('show_id', distinct=True, filter=Q(show__type='Series')),
        first_view=Min('view_date'),
        last_view=Max('view_date'),
        active_days=Count('view_date', distinct=True),
    )

    total_seconds = agg['total_seconds'] or 0
    total_minutes = total_seconds // 60
    days, rem = divmod(total_seconds, 86400)
    hours, minutes = divmod(rem // 60, 60)

    # Расчет активности
    if year:
        total_days_in_period = 366 if calendar.isleap(int(year)) else 365
        if int(year) == timezone.now().year:
            total_days_in_period = timezone.now().timetuple().tm_yday
    else:
        if agg['first_view'] and agg['last_view']:
            total_days_in_period = (agg['last_view'] - agg['first_view']).days + 1
        else:
            total_days_in_period = 1

    activity_percent = round((agg['active_days'] / total_days_in_period) * 100, 1)
    daily_avg = round(total_minutes / total_days_in_period, 1)

    # Peak Month
    monthly_stats = (
        qs.annotate(m=TruncMonth('view_date'))
        .values('m')
        .annotate(cnt=Count('id'), mins=Sum('final_duration') / 60)
        .order_by('-cnt')
        .first()
    )

    peak_month_data = None
    if monthly_stats:
        peak_month_data = {
            'month': monthly_stats['m'].strftime('%Y-%m-%d'),
            'month_name': monthly_stats['m'].strftime('%B'),
            'views_count': monthly_stats['cnt'],
            'total_minutes': int(monthly_stats['mins'] or 0),
        }

    return {
        'total_seconds_watched': total_seconds,
        'total_minutes_watched': total_minutes,
        'duration_display': f'{days}д {hours}ч {minutes}м',
        'continuous_days': round(total_seconds / 86400, 1),
        'total_views': agg['total_views'],
        'total_episodes': agg['total_episodes'],
        'total_movies': agg['total_movies'],
        'unique_shows': agg['unique_shows'],
        'unique_series': agg['unique_series'],
        'activity_percent': activity_percent,
        'daily_average_min': daily_avg,
        'period_label': str(year) if year else 'Все время',
        'first_view_date': agg['first_view'].strftime('%Y-%m-%d') if agg['first_view'] else None,
        'last_view_date': agg['last_view'].strftime('%Y-%m-%d') if agg['last_view'] else None,
        'most_active_month': peak_month_data,
    }


def _get_favorites(qs):
    # Genres
    genres_qs = (
        qs.values(name=F('show__genres__name'))
        .filter(name__isnull=False)
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    total_mentions = sum(g['count'] for g in genres_qs)
    genres = [
        {
            'name': g['name'],
            'count': g['count'],
            'minutes': 0,
            'percentage': round((g['count'] / total_mentions * 100), 1),
        }
        for g in genres_qs[:10]
    ]

    # Добавляем минуты к жанрам (для фронтенда)
    genre_mins = qs.values(name=F('show__genres__name')).annotate(m=Sum('final_duration') / 60)
    mins_map = {gm['name']: int(gm['m'] or 0) for gm in genre_mins}
    for g in genres:
        g['minutes'] = mins_map.get(g['name'], 0)

    # Actors & Directors
    def get_person_top(field, limit=5):
        return [
            {'name': p['name'], 'shows': p['shows'], 'views': p['views'], 'count': p['views']}
            for p in qs.values(name=F(f'show__{field}__name'))
            .filter(name__isnull=False)
            .annotate(views=Count('id'), shows=Count('show_id', distinct=True))
            .order_by('-views')[:limit]
        ]

    # Countries
    countries_qs = (
        qs.values(name=F('show__countries__name'), emoji=F('show__countries__emoji_flag'))
        .filter(name__isnull=False)
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    countries = [
        {'name': c['name'], 'emoji': c['emoji'] or '', 'count': c['count']}
        for c in countries_qs[:5]
    ]

    return {
        'genres': genres,
        'actors': get_person_top('actors'),
        'countries': countries,
    }


def _get_binge_records(qs):
    binge_qs = (
        qs.filter(season_number__gt=0)
        .values('show_id', 'show__title', 'view_date')
        .annotate(episodes_count=Count('id'))
        .filter(episodes_count__gte=3)
        .order_by('-episodes_count')[:5]
    )

    result = []
    for b in binge_qs:
        cnt = b['episodes_count']
        tier = 'engaged'
        if cnt >= 8:
            tier = 'marathon'
        elif cnt >= 5:
            tier = 'binge'

        result.append(
            {
                'show_title': b['show__title'],
                'show_id': b['show_id'],
                'date': b['view_date'].strftime('%Y-%m-%d'),
                'episodes_count': cnt,
                'count': cnt,  # alias for UI
                'tier': tier,
            }
        )
    return result


def _get_heatmap(qs, year):
    if not year:
        return []
    data = {
        d['view_date']: d['mins']
        for d in qs.values('view_date').annotate(mins=Sum('final_duration') / 60)
    }
    start = date(int(year), 1, 1)
    end = date(int(year), 12, 31)
    res = []
    curr = start
    while curr <= end:
        m = data.get(curr, 0)
        val = 0
        if m > 0:
            if m < 45:
                val = 1
            elif m < 90:
                val = 2
            elif m < 180:
                val = 3
            else:
                val = 4
        res.append(val)
        curr += timedelta(days=1)
    return res


def _get_monthly_chart(qs, year):
    """Get monthly breakdown for charts: views count and hours per month."""
    month_names = [
        '',
        'Янв',
        'Фев',
        'Мар',
        'Апр',
        'Май',
        'Июн',
        'Июл',
        'Авг',
        'Сен',
        'Окт',
        'Ноя',
        'Дек',
    ]
    monthly = (
        qs.annotate(m=TruncMonth('view_date'))
        .values('m')
        .annotate(
            views=Count('id'),
            hours=Sum('final_duration') / 3600,
            episodes=Count('id', filter=Q(season_number__gt=0)),
            movies=Count('id', filter=Q(season_number=0)),
        )
        .order_by('m')
    )

    # Build full 12-month array
    labels = []
    views_data = []
    hours_data = []
    episodes_data = []
    movies_data = []

    month_map = {}
    for m in monthly:
        month_map[m['m'].month] = m

    for i in range(1, 13):
        labels.append(month_names[i])
        entry = month_map.get(i, {})
        views_data.append(entry.get('views', 0))
        hours_data.append(round(float(entry.get('hours', 0) or 0), 1))
        episodes_data.append(entry.get('episodes', 0))
        movies_data.append(entry.get('movies', 0))

    return {
        'labels': labels,
        'views': views_data,
        'hours': hours_data,
        'episodes': episodes_data,
        'movies': movies_data,
    }


def _get_weekday_chart(qs):
    """Get views by day of week for chart."""
    wd_stats = qs.annotate(wd=ExtractWeekDay('view_date')).values('wd').annotate(cnt=Count('id'))

    # Django ExtractWeekDay: 1=Sunday, 2=Monday, ..., 7=Saturday
    day_map = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    data = [0] * 7
    for s in wd_stats:
        idx = day_map.get(s['wd'], 0)
        data[idx] = s['cnt']

    return {'labels': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], 'data': data}


def generate_user_stats(user, year=None):
    cache_key = f'user_stats:{user.id}:{year or "all"}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    qs = _get_annotated_history(user, year)
    summary = _get_yearly_summary(qs, year)

    all_years = list(
        ViewHistory.objects.filter(users=user)
        .annotate(y=ExtractYear('view_date'))
        .values_list('y', flat=True)
        .distinct()
        .order_by('-y')
    )

    if summary['total_views'] == 0:
        empty_result = {
            'meta': {
                'id': user.id,
                'name': user.name or user.username,
                'year': year,
                'years': all_years,
            },
            'summary': summary,
            'heatmap': [],
            'genres': [],
            'actors': [],
            'countries': [],
            'binges': [],
            'monthly_chart': {'labels': [], 'views': [], 'hours': [], 'episodes': [], 'movies': []},
            'weekday_chart': {'labels': [], 'data': []},
        }
        return empty_result

    favs = _get_favorites(qs)
    binge = _get_binge_records(qs)

    result = {
        'meta': {
            'id': user.id,
            'name': user.name or user.username,
            'year': year,
            'years': all_years,
        },
        'summary': summary,
        'heatmap': _get_heatmap(qs, year),
        'genres': favs['genres'],
        'actors': favs['actors'],
        'countries': favs['countries'],
        'binges': binge,
        'monthly_chart': _get_monthly_chart(qs, year),
        'weekday_chart': _get_weekday_chart(qs),
    }

    cache.set(cache_key, result, timeout=86400)
    return result


def generate_group_stats(user, year=None):
    """Generate stats for the user's group, comparing with user's personal stats."""
    groups = ViewUserGroup.objects.filter(users=user)
    if not groups.exists():
        return None

    group = groups.first()
    group_users = list(group.users.all())

    if len(group_users) <= 1:
        return None

    # Get group-wide queryset (all views by any group member)
    qs = (
        ViewHistory.objects.filter(users__in=group_users, is_checked=True)
        .distinct()
        .select_related('show')
    )

    if year:
        qs = qs.filter(view_date__year=year)

    episode_dur = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number=OuterRef('season_number'),
        episode_number=OuterRef('episode_number'),
    )
    movie_dur = ShowDuration.objects.filter(
        show_id=OuterRef('show_id'),
        season_number__isnull=True,
        episode_number__isnull=True,
    )
    qs = qs.annotate(
        duration=Case(
            When(season_number=0, then=Subquery(movie_dur.values('duration_seconds')[:1])),
            default=Subquery(episode_dur.values('duration_seconds')[:1]),
        )
    ).annotate(final_duration=Coalesce('duration', 0))

    agg = qs.aggregate(
        total_views=Count('id'),
        total_seconds=Sum('final_duration'),
        total_episodes=Count('id', filter=Q(season_number__gt=0)),
        total_movies=Count('id', filter=Q(season_number=0)),
        unique_shows=Count('show_id', distinct=True),
        active_days=Count('view_date', distinct=True),
    )

    total_seconds = agg['total_seconds'] or 0
    days, rem = divmod(total_seconds, 86400)
    hours, minutes = divmod(rem // 60, 60)

    # Genres for group
    genres_qs = (
        qs.values(name=F('show__genres__name'))
        .filter(name__isnull=False)
        .annotate(count=Count('id'), mins=Sum('final_duration') / 60)
        .order_by('-count')[:5]
    )
    genres = [
        {'name': g['name'], 'count': g['count'], 'minutes': int(g['mins'] or 0)} for g in genres_qs
    ]

    # Members breakdown
    members = []
    for u in group_users:
        u_views = qs.filter(users=u).count()
        members.append(
            {
                'name': u.name or u.username or str(u.telegram_id),
                'views': u_views,
            }
        )
    members.sort(key=lambda x: x['views'], reverse=True)

    return {
        'group_name': group.name,
        'members_count': len(group_users),
        'members': members,
        'total_views': agg['total_views'],
        'total_episodes': agg['total_episodes'],
        'total_movies': agg['total_movies'],
        'unique_shows': agg['unique_shows'],
        'duration_display': f'{days}д {hours}ч {minutes}м',
        'active_days': agg['active_days'],
        'genres': genres,
    }
