from datetime import timedelta

from django.db.models import Count, F, Q
from django.db.models.functions import Lower, StrIndex
from django.utils import timezone

from app.models import Show, SiteMetric


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
        return {
            'data': entry.data,
            'timestamp': entry.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    return {
        'now': _format_entry(latest),
        'yesterday': _format_entry(yesterday),
        'week_ago': _format_entry(week_ago),
    }


def calculate_title_collision_metric():
    qs = Show.objects.filter(original_title__isnull=False).exclude(original_title='')

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
    return Show.objects.filter(
        type=show_type,
        kinopoisk_url__isnull=False,
        ext_rating__isnull=True
    ).exclude(kinopoisk_url='').values('id', 'title', 'original_title')


def get_title_collision_list(show_type: str):
    qs = Show.objects.filter(type=show_type, original_title__isnull=False).exclude(original_title='')
    return qs.annotate(
        low_title=Lower('title'),
        low_orig=Lower('original_title')
    ).annotate(
        pos=StrIndex('low_title', F('low_orig'))
    ).filter(
        pos__gt=0
    ).exclude(
        low_title=F('low_orig')
    ).values('id', 'title', 'original_title')


def calculate_missing_year_metric():
    stats = Show.objects.filter(year__isnull=True).values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_missing_year_list(show_type: str):
    return Show.objects.filter(type=show_type, year__isnull=True).values('id', 'title', 'original_title')


def calculate_missing_plot_metric():
    stats = Show.objects.filter(Q(plot__isnull=True) | Q(plot='')).values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_missing_plot_list(show_type: str):
    return Show.objects.filter(type=show_type).filter(Q(plot__isnull=True) | Q(plot='')).values('id', 'title', 'original_title')


def calculate_no_genres_metric():
    stats = Show.objects.filter(genres__isnull=True).values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_no_genres_list(show_type: str):
    return Show.objects.filter(type=show_type, genres__isnull=True).values('id', 'title', 'original_title')


def calculate_no_countries_metric():
    stats = Show.objects.filter(countries__isnull=True).values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': item['type'] or 'Unknown', 'value': item['total']} for item in stats]


def get_no_countries_list(show_type: str):
    return Show.objects.filter(type=show_type, countries__isnull=True).values('id', 'title', 'original_title')
