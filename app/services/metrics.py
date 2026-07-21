from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.db.models.functions import Coalesce, Lower, StrIndex
from django.db.utils import ProgrammingError
from django.utils import timezone

from app.models import (
    Country,
    Genre,
    LogEntry,
    Person,
    Show,
    ShowCrew,
    SiteMetric,
    TelegramLog,
    ViewUser,
)
from kinopub_parser import celery_app
from shared.constants import (
    GENRES_MAPPING,
    PROFESSION_TRANS_MAP,
    PROFESSIONS_MAPPING_EN,
    PROFESSIONS_MAPPING_RU,
    RAW_TO_NORMALIZED_COUNTRY,
    RAW_TO_NORMALIZED_EN,
    RAW_TO_NORMALIZED_GENRE,
    RAW_TO_NORMALIZED_RU,
    SERIES_TYPES,
    SHOW_TYPE_DISPLAY_RU,
)


def calculate_missing_country_meta_metric():
    raw_missing = Country.objects.filter(Q(iso_code__isnull=True) | Q(iso_code=''))
    count = 0
    for c in raw_missing:
        norm_name = RAW_TO_NORMALIZED_COUNTRY.get(c.name, c.name)
        if norm_name != c.name:
            if (
                Country.objects.filter(name=norm_name)
                .exclude(Q(iso_code__isnull=True) | Q(iso_code=''))
                .exists()
            ):
                continue
        count += 1
    return [{'name': 'Страны', 'value': count}]


def get_missing_country_meta_list():
    raw_missing = Country.objects.filter(Q(iso_code__isnull=True) | Q(iso_code=''))
    valid_missing = []
    for c in raw_missing:
        norm_name = RAW_TO_NORMALIZED_COUNTRY.get(c.name, c.name)
        if norm_name != c.name:
            if (
                Country.objects.filter(name=norm_name)
                .exclude(Q(iso_code__isnull=True) | Q(iso_code=''))
                .exists()
            ):
                continue
        valid_missing.append({'id': c.id, 'name': c.name})
    return valid_missing


def calculate_total_countries_metric():
    active_count = Country.objects.filter(show__isnull=False).distinct().count()
    unused_count = Country.objects.filter(show__isnull=True).count()
    data = [
        {'name': 'Активные', 'value': active_count},
        {'name': 'Неиспользуемые', 'value': unused_count},
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def get_active_countries_list():
    return (
        Country.objects.filter(show__isnull=False)
        .distinct()
        .annotate(num_shows=Count('show'))
        .order_by('-num_shows')
        .values('id', 'name', 'iso_code', 'emoji_flag')
    )


def get_unused_countries_list():
    return (
        Country.objects.filter(show__isnull=True)
        .order_by('name')
        .values('id', 'name', 'iso_code', 'emoji_flag')
    )


def get_total_countries_with_shows_list():
    return (
        Country.objects.filter(show__isnull=False)
        .distinct()
        .annotate(num_shows=Count('show'))
        .order_by('-num_shows')
        .values('id', 'name', 'iso_code', 'emoji_flag')
    )


def _format_type(t):
    if not t:
        return 'Неизвестно'
    return SHOW_TYPE_DISPLAY_RU.get(t, t)


def calculate_has_kp_metric():
    stats = (
        Show.objects.filter(ext_rating__kp__isnull=False)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


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
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


def get_has_imdb_list(show_type: str):
    return Show.objects.filter(type=show_type, ext_rating__imdb__isnull=False).values(
        'id', 'title', 'original_title'
    )


def calculate_total_shows_metric():
    stats = Show.objects.values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


def get_total_shows_list(show_type: str):
    return Show.objects.filter(type=show_type).values('id', 'title', 'original_title')


def calculate_missing_imdb_metric():
    qs = Show.objects.filter(imdb_url__isnull=False, ext_rating__isnull=True).exclude(imdb_url='')

    stats = qs.values('type').annotate(total_missing=Count('id')).order_by('-total_missing')

    data = [{'name': _format_type(item['type']), 'value': item['total_missing']} for item in stats]
    return data


def get_missing_imdb_list(show_type: str):
    return (
        Show.objects.filter(type=show_type, imdb_url__isnull=False, ext_rating__isnull=True)
        .exclude(imdb_url='')
        .values('id', 'title', 'original_title')
    )


def calculate_missing_kp_metric():
    qs = (
        Show.objects.filter(kinopoisk_url__isnull=False, ext_rating__isnull=True)
        .exclude(kinopoisk_url='')
        .exclude(kinopoisk_url__endswith='/film/0')
    )

    stats = qs.values('type').annotate(total_missing=Count('id')).order_by('-total_missing')

    data = [{'name': _format_type(item['type']), 'value': item['total_missing']} for item in stats]
    return data


def generate_global_metrics_snapshot() -> dict:
    return {
        'missing_kp': calculate_missing_kp_metric(),
        'missing_imdb': calculate_missing_imdb_metric(),
        'has_kp': calculate_has_kp_metric(),
        'has_imdb': calculate_has_imdb_metric(),
        'total_shows': calculate_total_shows_metric(),
        'title_collision': calculate_title_collision_metric(),
        'missing_year': calculate_missing_year_metric(),
        'missing_status': calculate_missing_status_metric(),
        'missing_plot': calculate_missing_plot_metric(),
        'missing_durations': calculate_missing_durations_metric(),
        'no_genres': calculate_no_genres_metric(),
        'total_genres': calculate_total_genres_metric(),
        'unmapped_genres': calculate_unmapped_genres_metric(),
        'no_countries': calculate_no_countries_metric(),
        'missing_country_meta': calculate_missing_country_meta_metric(),
        'total_countries': calculate_total_countries_metric(),
        'total_persons_by_show_type': calculate_total_persons_by_show_type_metric(),
        'persons_avatar_stats': calculate_persons_avatar_stats_metric(),
        'professions_stats': calculate_professions_stats_metric(),
        'en_professions_stats': calculate_en_professions_stats_metric(),
        'duplicate_photo_urls': calculate_duplicate_photo_urls_metric(),
        'unused_persons': calculate_unused_persons_metric(),
    }


def get_global_metrics_history() -> dict:
    now = timezone.now()

    try:
        latest = SiteMetric.objects.filter(key='global_snapshot').order_by('-created_at').first()
    except ProgrammingError:
        return {}

    cache_timeout = 60 if settings.DEBUG else 3600
    if not latest or (now - latest.created_at).total_seconds() > cache_timeout:
        lock_key = 'lock:queuing_global_snapshot'
        if not cache.get(lock_key):
            cache.set(lock_key, True, timeout=300)
            celery_app.send_task('app.tasks.update_site_metrics_task', queue='metrics')

    if not latest:
        return {}

    yesterday_cutoff = now - timedelta(days=1)
    yesterday = (
        SiteMetric.objects.filter(key='global_snapshot', created_at__lte=yesterday_cutoff)
        .order_by('-created_at')
        .first()
    )

    week_cutoff = now - timedelta(days=7)
    week_ago = (
        SiteMetric.objects.filter(key='global_snapshot', created_at__lte=week_cutoff)
        .order_by('-created_at')
        .first()
    )

    def _format_entry(entry, metric_key):
        if not entry or metric_key not in entry.data:
            return {'data': [], 'timestamp': None}
        return {
            'data': entry.data[metric_key],
            'timestamp': entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }

    result = {}
    for key in latest.data.keys():
        result[key] = {
            'now': _format_entry(latest, key),
            'yesterday': _format_entry(yesterday, key),
            'week_ago': _format_entry(week_ago, key),
        }

    return result


def calculate_title_collision_metric():
    qs = Show.objects.filter(original_title__isnull=False, ignore_collision=False).exclude(
        original_title=''
    )

    stats = (
        qs.annotate(low_title=Lower('title'), low_orig=Lower('original_title'))
        .annotate(pos=StrIndex('low_title', F('low_orig')))
        .values('type')
        .annotate(
            total=Count('id'),
            contains_orig=Count('id', filter=Q(pos__gt=0) & ~Q(low_title=F('low_orig'))),
            unique_titles=Count('id', filter=Q(pos=0)),
        )
        .order_by('-contains_orig')
    )

    data = [
        {
            'type': _format_type(item['type']),
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
        .exclude(kinopoisk_url__endswith='/film/0')
        .values('id', 'title', 'original_title')
    )


def get_title_collision_list(show_type: str):
    qs = Show.objects.filter(
        type=show_type, original_title__isnull=False, ignore_collision=False
    ).exclude(original_title='')
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
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


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
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


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
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


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
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


def get_no_countries_list(show_type: str):
    return Show.objects.filter(type=show_type, countries__isnull=True).values(
        'id', 'title', 'original_title'
    )


def calculate_total_persons_by_show_type_metric():
    stats = (
        ShowCrew.objects.annotate(canonical_id=Coalesce('person__master_person_id', 'person__id'))
        .values('show__type')
        .annotate(total=Count('canonical_id', distinct=True))
        .order_by('-total')
    )
    return [{'name': _format_type(item['show__type']), 'value': item['total']} for item in stats]


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

    invalid_url = Q(showcrew__show__kinopoisk_url__endswith='/film/0')
    kp_waiting = (
        Q(showcrew__show__kinopoisk_url__isnull=False)
        & ~Q(showcrew__show__kinopoisk_url='')
        & ~invalid_url
        & Q(showcrew__show__ext_rating__isnull=True)
    )

    data = [
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
            'value': Person.objects.exclude(has_kp).exclude(kp_waiting).distinct().count(),
        },
        {'name': 'В ожидании TMDB', 'value': Person.objects.exclude(tmdb_done | has_tmdb).count()},
        {
            'name': 'В ожидании KP',
            'value': Person.objects.filter(kp_waiting).exclude(has_kp).distinct().count(),
        },
        {
            'name': 'Не найдено вообще',
            'value': Person.objects.filter(tmdb_done)
            .exclude(has_tmdb | has_kp)
            .exclude(kp_waiting)
            .distinct()
            .count(),
        },
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def get_persons_avatar_stats_list(category: str):
    has_tmdb = Q(tmdb_photo_url__isnull=False) & ~Q(tmdb_photo_url='')
    has_kp = Q(kp_photo_url__isnull=False) & ~Q(kp_photo_url='')
    tmdb_done = Q(is_photo_fetched=True)

    invalid_url = Q(showcrew__show__kinopoisk_url__endswith='/film/0')
    kp_waiting = (
        Q(showcrew__show__kinopoisk_url__isnull=False)
        & ~Q(showcrew__show__kinopoisk_url='')
        & ~invalid_url
        & Q(showcrew__show__ext_rating__isnull=True)
    )

    qs = Person.objects.all()
    if category == 'Есть фото (TMDB)':
        qs = qs.filter(has_tmdb)
    elif category == 'Есть фото (KP)':
        qs = qs.filter(has_kp).exclude(has_tmdb)
    elif category == 'TMDB не найдено':
        qs = qs.filter(tmdb_done).exclude(has_tmdb)
    elif category == 'KP не найдено':
        qs = qs.exclude(has_kp).exclude(kp_waiting)
    elif category == 'В ожидании TMDB':
        qs = qs.exclude(tmdb_done | has_tmdb)
    elif category == 'В ожидании KP':
        qs = qs.filter(kp_waiting).exclude(has_kp)
    elif category == 'Не найдено вообще':
        qs = qs.filter(tmdb_done).exclude(has_tmdb | has_kp).exclude(kp_waiting)

    return qs.distinct().values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')


def calculate_professions_stats_metric():
    # Собираем всех людей, у которых есть хоть какая-то привязка к ролям
    # Считаем их по нормализованным RU ролям, используя кросс-маппинг

    # Инвертированный маппинг EN -> RU для кросс-чека
    en_to_ru_map = {v: k for k, v in PROFESSION_TRANS_MAP.items()}

    # Получаем все записи, где заполнено хотя бы одно поле
    crew_qs = (
        ShowCrew.objects.exclude(
            Q(profession__isnull=True, en_profession__isnull=True)
            | Q(profession='', en_profession='')
        )
        .annotate(canonical_id=Coalesce('person__master_person_id', 'person__id'))
        .values('profession', 'en_profession', 'canonical_id')
    )

    merged = defaultdict(set)  # {NormName: {person_ids}}

    for row in crew_qs:
        norm_ru = RAW_TO_NORMALIZED_RU.get(row['profession'])
        if not norm_ru and row['en_profession']:
            norm_en = RAW_TO_NORMALIZED_EN.get(row['en_profession'])
            norm_ru = en_to_ru_map.get(norm_en)

        if norm_ru:
            merged[norm_ru].add(row['canonical_id'])

    result = [{'name': k, 'value': len(v)} for k, v in merged.items()]

    # Неизвестно — это те, у кого вообще нет распознанных ролей
    unknown_count = (
        Person.objects.filter(master_person__isnull=True)
        .exclude(
            Q(showcrew__profession__in=RAW_TO_NORMALIZED_RU.keys())
            | Q(showcrew__en_profession__in=RAW_TO_NORMALIZED_EN.keys())
        )
        .distinct()
        .count()
    )

    if unknown_count > 0:
        result.append({'name': 'Неизвестно', 'value': unknown_count})

    return sorted(result, key=lambda x: x['value'], reverse=True)


def get_professions_stats_list(profession: str):
    search_list = PROFESSIONS_MAPPING_RU.get(profession, [profession])
    return (
        Person.objects.filter(showcrew__profession__in=search_list)
        .distinct()
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')
    )


def calculate_missing_status_metric():
    qs = Show.objects.filter(type__in=SERIES_TYPES).filter(Q(status__isnull=True) | Q(status=''))
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


def get_missing_status_list(show_type: str):
    return (
        Show.objects.filter(type=show_type)
        .filter(Q(status__isnull=True) | Q(status=''))
        .values('id', 'title', 'original_title')
    )


def calculate_duplicate_photo_urls_metric():
    tmdb_qs = (
        Person.objects.filter(master_person__isnull=True)
        .exclude(tmdb_photo_url='')
        .filter(tmdb_photo_url__isnull=False)
        .values('tmdb_photo_url')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )
    tmdb_dupes = tmdb_qs.count()

    kp_qs = (
        Person.objects.filter(master_person__isnull=True)
        .exclude(kp_photo_url='')
        .filter(kp_photo_url__isnull=False)
        .values('kp_photo_url')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )
    kp_dupes = kp_qs.count()

    data = [
        {'name': 'TMDB дубликаты', 'value': tmdb_dupes},
        {'name': 'KP дубликаты', 'value': kp_dupes},
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def get_duplicate_photo_urls_list(source_type: str):
    field = 'tmdb_photo_url' if 'TMDB' in source_type else 'kp_photo_url'

    dupe_urls_data = (
        Person.objects.filter(master_person__isnull=True)
        .exclude(**{field: ''})
        .filter(**{f'{field}__isnull': False})
        .values(field)
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
        .order_by('-cnt')
    )

    if not dupe_urls_data:
        return []

    url_counts = {entry[field]: entry['cnt'] for entry in dupe_urls_data}
    urls = list(url_counts.keys())

    persons_qs = (
        Person.objects.filter(master_person__isnull=True)
        .filter(**{f'{field}__in': urls})
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')
    )

    grouped_persons = defaultdict(list)
    for p in persons_qs:
        grouped_persons[p[field]].append(
            {
                'id': p['id'],
                'name': p['name'],
                'en_name': p['en_name'],
                'tmdb_photo_url': p['tmdb_photo_url'],
                'kp_photo_url': p['kp_photo_url'],
            }
        )

    results = []
    for url in urls:
        persons_list = sorted(grouped_persons[url], key=lambda x: x['id'])

        kp_status = None
        if field == 'tmdb_photo_url':
            kp_urls = {p['kp_photo_url'] for p in persons_list if p.get('kp_photo_url')}
            kp_urls.discard('')
            has_kp_count = sum(1 for p in persons_list if p.get('kp_photo_url') and p.get('kp_photo_url') != '')
            if len(kp_urls) == 0:
                kp_status = 'missing'
            elif len(kp_urls) == 1:
                if has_kp_count == len(persons_list):
                    kp_status = 'same'
                else:
                    kp_status = 'partial'
            else:
                kp_status = 'different'

        tmdb_status = None
        if field == 'kp_photo_url':
            tmdb_urls = {p['tmdb_photo_url'] for p in persons_list if p.get('tmdb_photo_url')}
            tmdb_urls.discard('')
            has_tmdb_count = sum(1 for p in persons_list if p.get('tmdb_photo_url') and p.get('tmdb_photo_url') != '')
            if len(tmdb_urls) == 0:
                tmdb_status = 'missing'
            elif len(tmdb_urls) == 1:
                if has_tmdb_count == len(persons_list):
                    tmdb_status = 'same'
                else:
                    tmdb_status = 'partial'
            else:
                tmdb_status = 'different'

        results.append(
            {
                'id': 0,
                'title': f'Группа дубликатов ({url_counts[url]})',
                'persons': persons_list,
                'tmdb_photo_url': url if field == 'tmdb_photo_url' else None,
                'kp_photo_url': url if field == 'kp_photo_url' else None,
                'kp_status': kp_status,
                'tmdb_status': tmdb_status,
                'admin_url': f'/admin/app/person/?q={url}',
            }
        )
    return results


def calculate_en_professions_stats_metric():
    # Аналогичная логика для английских метрик
    crew_qs = (
        ShowCrew.objects.exclude(
            Q(profession__isnull=True, en_profession__isnull=True)
            | Q(profession='', en_profession='')
        )
        .annotate(canonical_id=Coalesce('person__master_person_id', 'person__id'))
        .values('profession', 'en_profession', 'canonical_id')
    )

    merged = defaultdict(set)

    for row in crew_qs:
        norm_en = RAW_TO_NORMALIZED_EN.get(row['en_profession'])
        if not norm_en and row['profession']:
            norm_ru = RAW_TO_NORMALIZED_RU.get(row['profession'])
            norm_en = PROFESSION_TRANS_MAP.get(norm_ru)

        if norm_en:
            merged[norm_en].add(row['canonical_id'])

    result = [{'name': k, 'value': len(v)} for k, v in merged.items()]

    unknown_count = (
        Person.objects.filter(master_person__isnull=True)
        .exclude(
            Q(showcrew__profession__in=RAW_TO_NORMALIZED_RU.keys())
            | Q(showcrew__en_profession__in=RAW_TO_NORMALIZED_EN.keys())
        )
        .distinct()
        .count()
    )

    if unknown_count > 0:
        result.append({'name': 'Неизвестно', 'value': unknown_count})

    return sorted(result, key=lambda x: x['value'], reverse=True)


def get_en_professions_stats_list(en_profession: str):
    search_list = PROFESSIONS_MAPPING_EN.get(en_profession, [en_profession])
    return (
        Person.objects.filter(showcrew__en_profession__in=search_list)
        .distinct()
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')
    )


def calculate_total_genres_metric():
    known_keys = set(GENRES_MAPPING.keys())
    db_genres = set(Genre.objects.values_list('name', flat=True))

    mapped_count = len(db_genres.intersection(known_keys))
    unmapped_count = len(db_genres.difference(known_keys))

    data = [
        {'name': 'Основные жанры', 'value': mapped_count},
        {'name': 'Дубликаты', 'value': unmapped_count},
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def get_total_genres_list(category: str):
    known_keys = set(GENRES_MAPPING.keys())

    if category == 'Основные жанры':
        qs = Genre.objects.filter(name__in=known_keys).order_by('name')
    else:
        qs = Genre.objects.exclude(name__in=known_keys).order_by('name')

    results = []
    for g in qs:
        results.append(
            {
                'id': g.id,
                'name': g.name,
                'title': g.name,
                'is_genre': True,
                'admin_url': f'/admin/app/genre/{g.id}/change/',
            }
        )
    return results


def calculate_unmapped_genres_metric():
    count = Genre.objects.exclude(name__in=RAW_TO_NORMALIZED_GENRE.keys()).count()
    return [{'name': 'Не распознано', 'value': count}]


def get_unmapped_genres_list():
    qs = Genre.objects.exclude(name__in=RAW_TO_NORMALIZED_GENRE.keys()).order_by('name')
    results = []
    for g in qs:
        results.append(
            {
                'id': g.id,
                'name': g.name,
                'title': g.name,
                'is_genre': True,
                'admin_url': f'/admin/app/genre/{g.id}/change/',
            }
        )
    return results


def calculate_missing_durations_metric():
    stats = (
        Show.objects.filter(showduration__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return [{'name': _format_type(item['type']), 'value': item['total']} for item in stats]


def get_missing_durations_list(show_type: str):
    return Show.objects.filter(type=show_type, showduration__isnull=True).values(
        'id', 'title', 'original_title'
    )


def calculate_unused_persons_metric():
    count = Person.objects.filter(showcrew__isnull=True).count()
    return [{'name': 'Без ролей', 'value': count}]


def get_unused_persons_list():
    return (
        Person.objects.filter(showcrew__isnull=True)
        .order_by('-created_at')
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url')
    )


def calculate_last_tg_activity_metric():
    last_log = TelegramLog.objects.order_by('-created_at').first()
    if not last_log:
        return [{'name': 'Активность', 'value': 0}]

    timestamp = int(last_log.created_at.timestamp())
    return [{'name': 'Последнее сообщение', 'value': timestamp}]


def calculate_recent_errors_metric():
    cutoff = timezone.now() - timedelta(days=1)
    count = LogEntry.objects.filter(created_at__gte=cutoff, level__in=['ERROR', 'CRITICAL']).count()
    return [{'name': 'Ошибки (24ч)', 'value': count}]


def calculate_bot_users_health_metric():
    active = ViewUser.objects.filter(is_bot_active=True).count()
    inactive = ViewUser.objects.filter(is_bot_active=False).count()
    data = [{'name': 'Активны', 'value': active}, {'name': 'Отключены', 'value': inactive}]
    return sorted(data, key=lambda x: x['value'], reverse=True)
