from datetime import timedelta

from django.db.models import Count, F, Q
from django.db.models.functions import Lower, StrIndex
from django.utils import timezone

from app.models import Country, Person, Show, ShowCrew, SiteMetric
from shared.constants import SERIES_TYPES


def calculate_missing_country_meta_metric():
    count = Country.objects.filter(Q(iso_code__isnull=True) | Q(iso_code='')).count()
    return [{'name': 'Страны', 'value': count}]


def get_missing_country_meta_list():
    return Country.objects.filter(Q(iso_code__isnull=True) | Q(iso_code='')).values('id', 'name')


def calculate_total_countries_with_shows_metric():
    count = Country.objects.filter(show__isnull=False).distinct().count()
    return [{'name': 'Страны', 'value': count}]


def get_total_countries_with_shows_list():
    return (
        Country.objects.filter(show__isnull=False)
        .distinct()
        .annotate(num_shows=Count('show'))
        .order_by('-num_shows')
        .values('id', 'name', 'iso_code', 'emoji_flag')
    )


def calculate_has_kp_metric():
    stats = (
        Show.objects.filter(ext_rating__kp__isnull=False)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_has_kp_list(show_type: str):
    return Show.objects.filter(type=show_type, ext_rating__kp__isnull=False).values(
        'id', 'title', 'original_title'
    )


def calculate_has_imdb_metric():
    stats = (
        Show.objects.filter(ext_rating__imdb__isnull=False)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_has_imdb_list(show_type: str):
    return Show.objects.filter(type=show_type, ext_rating__imdb__isnull=False).values(
        'id', 'title', 'original_title'
    )


def calculate_total_shows_metric():
    stats = Show.objects.values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_total_shows_list(show_type: str):
    return Show.objects.filter(type=show_type).values('id', 'title', 'original_title')


def calculate_missing_imdb_metric():
    qs = Show.objects.filter(imdb_url__isnull=False, ext_rating__isnull=True).exclude(imdb_url='')

    stats = qs.values('type').annotate(total_missing=Count('id')).order_by('-total_missing')

    data = [{'name': item['type'] or 'Unknown', 'value': item['total_missing']} for item in stats]
    return data


def get_missing_imdb_list(show_type: str):
    return (
        Show.objects.filter(type=show_type, imdb_url__isnull=False, ext_rating__isnull=True)
        .exclude(imdb_url='')
        .values('id', 'title', 'original_title')
    )


def calculate_missing_kp_metric():
    qs = Show.objects.filter(kinopoisk_url__isnull=False, ext_rating__isnull=True).exclude(
        kinopoisk_url=''
    )

    stats = qs.values('type').annotate(total_missing=Count('id')).order_by('-total_missing')

    data = [{'name': item['type'] or 'Unknown', 'value': item['total_missing']} for item in stats]
    return data


def get_or_update_metric(key: str, calc_func) -> dict:
    now = timezone.now()

    latest = SiteMetric.objects.filter(key=key).order_by('-created_at').first()

    if not latest or (now - latest.created_at).total_seconds() > 300:
        new_data = calc_func()
        latest = SiteMetric.objects.create(key=key, data=new_data)

    yesterday_cutoff = now - timedelta(days=1)
    yesterday = (
        SiteMetric.objects.filter(key=key, created_at__lte=yesterday_cutoff)
        .order_by('-created_at')
        .first()
    )

    week_cutoff = now - timedelta(days=7)
    week_ago = (
        SiteMetric.objects.filter(key=key, created_at__lte=week_cutoff)
        .order_by('-created_at')
        .first()
    )

    def _format_entry(entry):
        if not entry:
            return {'data': [], 'timestamp': None}
        return {'data': entry.data, 'timestamp': entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}

    return {
        'now': _format_entry(latest),
        'yesterday': _format_entry(yesterday),
        'week_ago': _format_entry(week_ago),
    }


def calculate_title_collision_metric():
    qs = Show.objects.filter(
        original_title__isnull=False,
        ignore_collision=False
    ).exclude(original_title='')

    stats = (
        qs.annotate(low_title=Lower('title'), low_orig=Lower('original_title'))
        .annotate(pos=StrIndex('low_title', F('low_orig')))
        .values('type')
        .annotate(
            total=Count('id'),
            contains_orig=Count('id', filter=Q(pos__gt=0) & ~Q(low_title=F('low_orig'))),
            unique_titles=Count('id', filter=Q(pos=0)),
        )
        .order_by('-total')
    )

    data = [
        {
            'type': item['type'] or 'Unknown',
            'total': item['total'],
            'collisions': item['contains_orig'],
            'unique': item['unique_titles'],
        }
        for item in stats
    ]
    return data


def get_missing_kp_list(show_type: str):
    return (
        Show.objects.filter(type=show_type, kinopoisk_url__isnull=False, ext_rating__isnull=True)
        .exclude(kinopoisk_url='')
        .values('id', 'title', 'original_title')
    )


def get_title_collision_list(show_type: str):
    qs = Show.objects.filter(
        type=show_type,
        original_title__isnull=False,
        ignore_collision=False
    ).exclude(
        original_title=''
    )
    return (
        qs.annotate(low_title=Lower('title'), low_orig=Lower('original_title'))
        .annotate(pos=StrIndex('low_title', F('low_orig')))
        .filter(pos__gt=0)
        .exclude(low_title=F('low_orig'))
        .values('id', 'title', 'original_title')
    )


def calculate_missing_year_metric():
    stats = (
        Show.objects.filter(year__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_missing_year_list(show_type: str):
    return Show.objects.filter(type=show_type, year__isnull=True).values(
        'id', 'title', 'original_title'
    )


def calculate_missing_plot_metric():
    stats = (
        Show.objects.filter(Q(plot__isnull=True) | Q(plot=''))
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_missing_plot_list(show_type: str):
    return (
        Show.objects.filter(type=show_type)
        .filter(Q(plot__isnull=True) | Q(plot=''))
        .values('id', 'title', 'original_title')
    )


def calculate_no_genres_metric():
    stats = (
        Show.objects.filter(genres__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_no_genres_list(show_type: str):
    return Show.objects.filter(type=show_type, genres__isnull=True).values(
        'id', 'title', 'original_title'
    )


def calculate_no_countries_metric():
    stats = (
        Show.objects.filter(countries__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_no_countries_list(show_type: str):
    return Show.objects.filter(type=show_type, countries__isnull=True).values(
        'id', 'title', 'original_title'
    )


def calculate_total_persons_by_show_type_metric():
    stats = (
        ShowCrew.objects.values('show__type')
        .annotate(total=Count('person', distinct=True))
        .order_by('-total')
    )
    return [{'name': item['show__type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_total_persons_by_show_type_list(show_type: str):
    return (
        Person.objects.filter(showcrew__show__type=show_type)
        .distinct()
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')
    )


def calculate_persons_avatar_stats_metric():
    has_tmdb = Q(tmdb_photo_url__isnull=False) & ~Q(tmdb_photo_url='')
    has_kp = Q(kp_photo_url__isnull=False) & ~Q(kp_photo_url='')
    tmdb_done = Q(is_photo_fetched=True)
    kp_done = Q(showcrew__show__ext_rating__isnull=False)

    return [
        {'name': 'Есть фото (TMDB)', 'value': Person.objects.filter(has_tmdb).count()},
        {
            'name': 'Есть фото (KP)',
            'value': Person.objects.filter(has_kp).exclude(has_tmdb).count(),
        },
        {
            'name': 'TMDB не найдено',
            'value': Person.objects.filter(tmdb_done).exclude(has_tmdb).count(),
        },
        {
            'name': 'KP не найдено',
            'value': Person.objects.filter(kp_done).exclude(has_kp).distinct().count(),
        },
        {'name': 'В ожидании TMDB', 'value': Person.objects.exclude(tmdb_done | has_tmdb).count()},
        {
            'name': 'В ожидании KP',
            'value': Person.objects.exclude(kp_done | has_kp).distinct().count(),
        },
        {
            'name': 'Не найдено вообще',
            'value': Person.objects.filter(tmdb_done, kp_done)
            .exclude(has_tmdb | has_kp)
            .distinct()
            .count(),
        },
    ]


def get_persons_avatar_stats_list(category: str):
    has_tmdb = Q(tmdb_photo_url__isnull=False) & ~Q(tmdb_photo_url='')
    has_kp = Q(kp_photo_url__isnull=False) & ~Q(kp_photo_url='')
    tmdb_done = Q(is_photo_fetched=True)
    kp_done = Q(showcrew__show__ext_rating__isnull=False)

    qs = Person.objects.all()
    if category == 'Есть фото (TMDB)':
        qs = qs.filter(has_tmdb)
    elif category == 'Есть фото (KP)':
        qs = qs.filter(has_kp).exclude(has_tmdb)
    elif category == 'TMDB не найдено':
        qs = qs.filter(tmdb_done).exclude(has_tmdb)
    elif category == 'KP не найдено':
        qs = qs.filter(kp_done).exclude(has_kp)
    elif category == 'В ожидании TMDB':
        qs = qs.exclude(tmdb_done | has_tmdb)
    elif category == 'В ожидании KP':
        qs = qs.exclude(kp_done | has_kp)
    elif category == 'Не найдено вообще':
        qs = qs.filter(tmdb_done, kp_done).exclude(has_tmdb | has_kp)

    return qs.distinct().values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')


def calculate_professions_stats_metric():
    stats = (
        ShowCrew.objects.exclude(profession__isnull=True)
        .exclude(profession='')
        .values('profession')
        .annotate(total=Count('person', distinct=True))
        .order_by('-total')
    )
    return [{'name': item['profession'], 'value': item['total']} for item in stats]


def get_professions_stats_list(profession: str):
    return (
        Person.objects.filter(showcrew__profession=profession)
        .distinct()
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')
    )


def calculate_missing_status_metric():
    qs = Show.objects.filter(type__in=SERIES_TYPES).filter(Q(status__isnull=True) | Q(status=''))
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_missing_status_list(show_type: str):
    return (
        Show.objects.filter(type=show_type)
        .filter(Q(status__isnull=True) | Q(status=''))
        .values('id', 'title', 'original_title')
    )