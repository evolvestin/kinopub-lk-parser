import calendar
import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import (
    Avg,
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
from django.db.models.functions import (
    Coalesce,
    ExtractMonth,
    ExtractWeekDay,
    ExtractYear,
    TruncMonth,
)
from django.utils import timezone

from app.models import ShowDuration, UserRating, ViewHistory, ViewUserGroup
from shared.formatters import format_duration
from shared.media import get_poster_url

logger = logging.getLogger(__name__)


def _get_yearly_summary(base_qs, dur_qs, year=None):
    counts = base_qs.aggregate(
        total_views=Count('id'),
        total_episodes=Count('id', filter=Q(season_number__gt=0)),
        total_movies=Count('id', filter=Q(season_number=0) | Q(season_number__isnull=True)),
        unique_shows=Count('show_id', distinct=True),
        unique_series=Count('show_id', distinct=True, filter=Q(season_number__gt=0)),
        unique_movies=Count(
            'show_id', distinct=True, filter=Q(season_number=0) | Q(season_number__isnull=True)
        ),
        first_view=Min('view_date'),
        last_view=Max('view_date'),
        active_days=Count('view_date', distinct=True),
    )

    durs = dur_qs.aggregate(
        total_seconds=Sum('final_duration'),
        series_seconds=Sum('final_duration', filter=Q(season_number__gt=0)),
        movies_seconds=Sum('final_duration', filter=Q(season_number=0) | Q(season_number__isnull=True))
    )

    total_seconds = durs['total_seconds'] or 0
    total_minutes = total_seconds // 60

    if year:
        try:
            total_days_in_period = 366 if calendar.isleap(int(year)) else 365
            if int(year) == timezone.now().year:
                total_days_in_period = timezone.now().timetuple().tm_yday
        except (ValueError, TypeError):
            total_days_in_period = 1
    else:
        if counts['first_view'] and counts['last_view']:
            total_days_in_period = (counts['last_view'] - counts['first_view']).days + 1
        else:
            total_days_in_period = 1

    active_days = counts['active_days'] or 0
    activity_percent = round((active_days / total_days_in_period) * 100, 1)
    daily_avg = round(total_minutes / total_days_in_period, 1)

    monthly_stats = (
        base_qs.annotate(m=TruncMonth('view_date'))
        .values('m')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
        .first()
    )

    peak_month_data = None
    if monthly_stats and monthly_stats['m']:
        peak_month_date = monthly_stats['m']
        peak_dur = dur_qs.filter(
            view_date__year=peak_month_date.year,
            view_date__month=peak_month_date.month,
        ).aggregate(mins=Sum('final_duration') / 60)

        peak_month_data = {
            'month': peak_month_date.strftime('%Y-%m-%d'),
            'month_name': peak_month_date.strftime('%B'),
            'views_count': monthly_stats['cnt'],
            'total_minutes': int(peak_dur['mins'] or 0),
        }

    return {
        'total_seconds_watched': total_seconds,
        'total_minutes_watched': total_minutes,
        'duration_display': format_duration(total_seconds),
        'series_duration': format_duration(durs['series_seconds'] or 0),
        'movies_duration': format_duration(durs['movies_seconds'] or 0),
        'continuous_days': round(total_seconds / 86400, 1),
        'total_views': counts['total_views'] or 0,
        'total_episodes': counts['total_episodes'] or 0,
        'total_movies': counts['total_movies'] or 0,
        'unique_shows': counts['unique_shows'] or 0,
        'unique_series': counts['unique_series'] or 0,
        'unique_movies': counts['unique_movies'] or 0,
        'activity_percent': activity_percent,
        'daily_average_min': daily_avg,
        'period_label': str(year) if year else 'Все время',
        'first_view_date': counts['first_view'].strftime('%Y-%m-%d')
        if counts['first_view']
        else None,
        'last_view_date': counts['last_view'].strftime('%Y-%m-%d') if counts['last_view'] else None,
        'most_active_month': peak_month_data,
    }


def _get_favorites(base_qs, dur_qs):
    # Используем первичный ключ жанра для корректной группировки
    genres_qs = (
        base_qs.values(tid=F('show__genres__id'), name=F('show__genres__name'))
        .filter(tid__isnull=False)
        .annotate(count=Count('id', distinct=True))
        .order_by('-count')
    )
    total_mentions = sum(g['count'] for g in genres_qs)

    genres = []
    # Предварительно считаем суммы минут по жанрам отдельно, чтобы избежать JOIN-коллизий
    # Группируем dur_qs, который уже содержит уникальные записи ViewHistory
    genre_mins_map = {}
    genre_durations = dur_qs.values('show__genres__name').annotate(m=Sum('final_duration'))
    for gd in genre_durations:
        if gd['show__genres__name']:
            genre_mins_map[gd['show__genres__name']] = int((gd['m'] or 0) / 60)

    for g in genres_qs[:20]: # Увеличиваем лимит до 20 для полноты картины
        name = g['name']
        show_ids = list(
            base_qs.filter(show__genres__id=g['tid']).values_list('show_id', flat=True).distinct()
        )
        genres.append(
            {
                'name': name,
                'count': g['count'],
                'minutes': genre_mins_map.get(name, 0),
                'percentage': round((g['count'] / total_mentions * 100), 1) if total_mentions else 0,
                'show_ids': show_ids,
            }
        )

    def get_person_top(field, limit=5):
        qs = (
            base_qs.values(tid=F(f'show__{field}__id'), name=F(f'show__{field}__name'))
            .filter(tid__isnull=False)
            .annotate(views=Count('id', distinct=True), shows_count=Count('show_id', distinct=True))
            .order_by('-views')[:limit]
        )
        result = []
        for p in qs:
            show_ids = list(
                base_qs.filter(**{f'show__{field}__id': p['tid']})
                .values_list('show_id', flat=True)
                .distinct()
            )
            
            show_titles = list(
                base_qs.filter(**{f'show__{field}__id': p['tid']})
                .order_by('show__original_title')
                .values_list('show__original_title', flat=True)
                .distinct()
            )
            
            result.append(
                {
                    'name': p['name'],
                    'shows': p['shows_count'],
                    'views': p['views'],
                    'count': p['views'],
                    'show_ids': show_ids,
                    'sub': ', '.join(show_titles)
                }
            )
        return result

    countries_qs = (
        base_qs.values(
            tid=F('show__countries__id'),
            name=F('show__countries__name'),
            emoji=F('show__countries__emoji_flag'),
        )
        .filter(tid__isnull=False)
        .annotate(count=Count('id', distinct=True))
        .order_by('-count')[:5]
    )

    countries = []
    for c in countries_qs:
        show_ids = list(
            base_qs.filter(show__countries__id=c['tid'])
            .values_list('show_id', flat=True)
            .distinct()
        )
        countries.append(
            {
                'name': c['name'],
                'emoji': c['emoji'] or '',
                'count': c['count'],
                'show_ids': show_ids,
            }
        )

    return {
        'genres': genres,
        'actors': get_person_top('actors'),
        'countries': countries,
    }


def _get_binge_records(base_qs):
    binge_qs = (
        base_qs.filter(season_number__gt=0)
        .values('show_id', 'show__title', 'show__original_title', 'view_date')
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

        title = b['show__title'] or b['show__original_title'] or f'Show {b["show_id"]}'

        result.append(
            {
                'show_title': title,
                'show_id': b['show_id'],
                'date': b['view_date'].strftime('%Y-%m-%d'),
                'episodes_count': cnt,
                'count': cnt,
                'tier': tier,
                'poster_url': get_poster_url(b['show_id']),
            }
        )
    return result


def _get_heatmap(dur_qs, year, all_years):
    if not all_years:
        return []

    years_to_process = [int(year)] if year else [int(y) for y in all_years if y]
    result = []

    data = {
        d['view_date']: d['mins']
        for d in dur_qs.values('view_date').annotate(mins=Sum('final_duration') / 60)
        if d['view_date']
    }

    for y in sorted(years_to_process, reverse=True):
        start = date(y, 1, 1)
        end = date(y, 12, 31)
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
        result.append({'year': y, 'data': res})

    return result


def _get_monthly_chart(base_qs, dur_qs):
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

    monthly_counts = (
        base_qs.annotate(m_num=ExtractMonth('view_date'))
        .values('m_num')
        .annotate(
            views=Count('id'),
            episodes=Count('id', filter=Q(season_number__gt=0)),
            movies=Count('id', filter=Q(season_number=0)),
        )
    )
    count_map = {mc['m_num']: mc for mc in monthly_counts if mc['m_num']}

    monthly_hours = (
        dur_qs.annotate(m_num=ExtractMonth('view_date'))
        .values('m_num')
        .annotate(hours=Sum('final_duration') / 3600)
    )
    hours_map = {mh['m_num']: mh['hours'] for mh in monthly_hours if mh['m_num']}

    labels = []
    views_data = []
    hours_data = []
    episodes_data = []
    movies_data = []

    for i in range(1, 13):
        labels.append(month_names[i])
        entry = count_map.get(i, {})
        views_data.append(entry.get('views', 0))
        hours_data.append(round(float(hours_map.get(i, 0) or 0), 1))
        episodes_data.append(entry.get('episodes', 0))
        movies_data.append(entry.get('movies', 0))

    return {
        'labels': labels,
        'views': views_data,
        'hours': hours_data,
        'episodes': episodes_data,
        'movies': movies_data,
    }


def _get_weekday_chart(base_qs):
    wd_stats = (
        base_qs.annotate(wd=ExtractWeekDay('view_date')).values('wd').annotate(cnt=Count('id'))
    )

    day_map = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    data = [0] * 7
    for s in wd_stats:
        if s['wd'] is not None:
            idx = day_map.get(s['wd'], 0)
            data[idx] = s['cnt']

    return {'labels': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], 'data': data}


def generate_user_stats(user, year=None):
    cache_key = f'user_stats_v3:{user.id}:{year or "all"}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    current_yr = timezone.now().year

    history_years = ViewHistory.objects.filter(users=user).annotate(
        y=ExtractYear('view_date')
    ).values_list('y', flat=True).distinct()

    rating_years = UserRating.objects.filter(user=user).annotate(
        y=ExtractYear('updated_at')
    ).values_list('y', flat=True).distinct()

    all_years = sorted(list(set(history_years) | set(rating_years)), reverse=True)

    is_redundant = len(all_years) == 1 and all_years[0] == current_yr
    if is_redundant:
        all_years = []

    ratings_qs = UserRating.objects.filter(user=user)
    if year:
        ratings_qs = ratings_qs.filter(updated_at__year=year)

    total_ratings = ratings_qs.count()
    avg_rating = ratings_qs.aggregate(avg=Avg('rating'))['avg'] or 0.0

    dist_data = {str(i): 0 for i in range(1, 11)}
    for r in ratings_qs.values('rating').annotate(cnt=Count('id')):
        bucket = str(int(r['rating'])) if r['rating'] >= 1 else '1'
        dist_data[bucket] += r['cnt']

    dist_list = [dist_data[str(i)] for i in range(1, 11)]

    ratings_history = []
    for r in ratings_qs.select_related('show').order_by('-updated_at'):
        ratings_history.append({
            'show_id': r.show_id,
            'title': r.show.title,
            'original_title': r.show.original_title,
            'year': r.show.year,
            'season': r.season_number,
            'episode': r.episode_number,
            'rating': r.rating,
            'date': r.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'poster_url': get_poster_url(r.show_id)
        })

    history_ids = ViewHistory.objects.filter(users=user, is_checked=True)
    if year:
        history_ids = history_ids.filter(view_date__year=year)

    base_qs = ViewHistory.objects.filter(
        id__in=Subquery(history_ids.values('id'))
    ).select_related('show').prefetch_related('users')

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

    dur_qs = base_qs.annotate(
        duration=Case(
            When(season_number=0, then=Subquery(movie_dur.values('duration_seconds')[:1])),
            default=Subquery(episode_dur.values('duration_seconds')[:1]),
        )
    ).annotate(final_duration=Coalesce('duration', 0))

    summary = _get_yearly_summary(base_qs, dur_qs, year)

    if is_redundant and str(year) == str(current_yr):
        summary['period_label'] = 'Все время'
    
    user_role = str(user.role).lower() if user.role else 'guest'

    if summary['total_views'] == 0:
        result = {
            'meta': {
                'id': user.id,
                'name': user.name or user.username,
                'year': year,
                'years': all_years,
                'role': user_role,
                'photo_url': user.photo_url
            },
            'summary': summary,
            'heatmap': [],
            'genres': [],
            'actors': [],
            'countries': [],
            'binges': [],
            'monthly_chart': {'labels': [], 'views': [], 'hours': [], 'episodes': [], 'movies': []},
            'weekday_chart': {'labels': [], 'data': []},
            'history_movies': [],
            'history_episodes': [],
            'ratings': {
                'total': total_ratings,
                'avg': round(avg_rating, 1),
                'distribution': dist_list,
                'history': ratings_history
            }
        }
        cache.set(cache_key, result, timeout=86400)
        return result

    favs = _get_favorites(base_qs, dur_qs)
    binge = _get_binge_records(base_qs)

    user_movie_rating = UserRating.objects.filter(
        user=user, show_id=OuterRef('show_id'), season_number__isnull=True
    ).values('rating')[:1]

    movies_history = []
    for h in base_qs.filter(season_number=0).annotate(user_rating=Subquery(user_movie_rating)).order_by('-view_date', '-id'):
        movies_history.append({
            'show_id': h.show_id,
            'show__title': h.show.title,
            'show__original_title': h.show.original_title,
            'show__year': h.show.year,
            'view_date': h.view_date.strftime('%Y-%m-%d'),
            'user_rating': h.user_rating,
            'poster_url': get_poster_url(h.show_id),
            'user_ids': list(h.users.values_list('id', flat=True)),
            'user_names': [u.name or u.username or str(u.telegram_id) for u in h.users.all()],
            'user_photos': [u.photo_url for u in h.users.all()]
        })

    user_ep_rating = UserRating.objects.filter(
        user=user, show_id=OuterRef('show_id'),
        season_number=OuterRef('season_number'),
        episode_number=OuterRef('episode_number')
    ).values('rating')[:1]

    user_show_rating = UserRating.objects.filter(
        user=user, show_id=OuterRef('show_id'), season_number__isnull=True
    ).values('rating')[:1]

    episodes_history = []
    for h in base_qs.filter(season_number__gt=0).annotate(user_rating=Subquery(user_ep_rating), user_show_rating=Subquery(user_show_rating)).order_by('-view_date', '-id'):
        episodes_history.append({
            'show_id': h.show_id,
            'show__title': h.show.title,
            'show__original_title': h.show.original_title,
            'show__year': h.show.year,
            'season_number': h.season_number,
            'episode_number': h.episode_number,
            'view_date': h.view_date.strftime('%Y-%m-%d'),
            'user_rating': h.user_rating,
            'user_show_rating': h.user_show_rating,
            'poster_url': get_poster_url(h.show_id),
            'user_ids': list(h.users.values_list('id', flat=True)),
            'user_names': [u.name or u.username or str(u.telegram_id) for u in h.users.all()],
            'user_photos': [u.photo_url for u in h.users.all()]
        })

    result = {
        'meta': {
            'id': user.id,
            'name': user.name or user.username,
            'year': year,
            'years': all_years,
            'role': user_role,
            'photo_url': user.photo_url
        },
        'summary': summary,
        'heatmap': _get_heatmap(dur_qs, year, all_years),
        'genres': favs['genres'],
        'actors': favs['actors'],
        'countries': favs['countries'],
        'binges': binge,
        'monthly_chart': _get_monthly_chart(base_qs, dur_qs),
        'weekday_chart': _get_weekday_chart(base_qs),
        'history_movies': movies_history,
        'history_episodes': episodes_history,
        'ratings': {
            'total': total_ratings,
            'avg': round(avg_rating, 1),
            'distribution': dist_list,
            'history': ratings_history
        }
    }
    cache.set(cache_key, result, timeout=86400)
    return result


def generate_group_stats(user, year=None):
    cache_key = f'group_stats_v4:{user.id}:{year or "all"}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    groups = ViewUserGroup.objects.filter(users=user)
    if not groups.exists():
        return None

    group = groups.first()
    group_users = list(group.users.all())

    history_filter = Q(users__in=group_users, is_checked=True)
    if year:
        history_filter &= Q(view_date__year=year)

    history_ids = ViewHistory.objects.filter(history_filter).values('id').distinct()
    
    base_qs = ViewHistory.objects.filter(id__in=Subquery(history_ids)).select_related('show').prefetch_related('users')

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
    dur_qs = base_qs.annotate(
        duration=Case(
            When(season_number=0, then=Subquery(movie_dur.values('duration_seconds')[:1])),
            default=Subquery(episode_dur.values('duration_seconds')[:1]),
        )
    ).annotate(final_duration=Coalesce('duration', 0))

    counts = base_qs.aggregate(
        total_views=Count('id'),
        total_episodes=Count('id', filter=Q(season_number__gt=0)),
        total_movies=Count('id', filter=Q(season_number=0) | Q(season_number__isnull=True)),
        unique_shows=Count('show_id', distinct=True),
        active_days=Count('view_date', distinct=True),
    )
    durs = dur_qs.aggregate(total_seconds=Sum('final_duration'))

    total_seconds = durs['total_seconds'] or 0
    total_minutes = total_seconds // 60

    favs = _get_favorites(base_qs, dur_qs)

    members = []
    for u in group_users:
        u_history_filter = Q(users=u, is_checked=True)
        if year:
            u_history_filter &= Q(view_date__year=year)
        
        u_views = ViewHistory.objects.filter(u_history_filter).count()
        members.append({
            'id': u.id,
            'name': u.name or u.username or str(u.telegram_id),
            'views': u_views,
            'photo_url': u.photo_url
        })
    members.sort(key=lambda x: x['views'], reverse=True)

    history_movies = []
    history_episodes = []

    for h in base_qs.order_by('-view_date', '-id'):
        entry = {
            'show_id': h.show_id,
            'show__title': h.show.title,
            'show__original_title': h.show.original_title,
            'show__year': h.show.year,
            'view_date': h.view_date.strftime('%Y-%m-%d'),
            'poster_url': get_poster_url(h.show_id),
            'user_ids': list(h.users.values_list('id', flat=True)),
            'user_names': [u.name or u.username or str(u.telegram_id) for u in h.users.all()],
            'user_photos': [u.photo_url for u in h.users.all()]
        }
        if h.season_number > 0:
            entry.update({
                'season_number': h.season_number,
                'episode_number': h.episode_number,
            })
            history_episodes.append(entry)
        else:
            history_movies.append(entry)

    result = {
        'group_name': group.name,
        'members_count': len(group_users),
        'members': members,
        'total_views': counts['total_views'],
        'total_episodes': counts['total_episodes'],
        'total_movies': counts['total_movies'],
        'unique_shows': counts['unique_shows'],
        'total_minutes_watched': total_minutes,
        'duration_display': format_duration(total_seconds),
        'active_days': counts['active_days'],
        'genres': favs['genres'],
        'history_movies': history_movies,
        'history_episodes': history_episodes,
    }

    cache.set(cache_key, result, timeout=86400)
    return result