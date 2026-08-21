from collections import defaultdict
from datetime import timedelta
from hashlib import sha1

from django.core.cache import cache
from django.db import connection
from django.db.models import Case, CharField, Count, Exists, F, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce
from django.db.utils import ProgrammingError
from django.utils import timezone

from app.models import (
    Country,
    ExternalRating,
    Genre,
    Person,
    Show,
    ShowCrew,
    ShowDuration,
    SiteMetric,
)
from app.utils import get_proxied_image_url
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
    SHOW_TYPE_MAPPING,
)

DUPLICATE_PHOTO_CACHE_VERSION_KEY = 'metrics:duplicate_photo_urls:cache_version'
DUPLICATE_PHOTO_CACHE_TIMEOUT = 86400
PERSON_DETAIL_CACHE_VERSION_KEY = 'metrics:person_detail:cache_version'
PERSON_DETAIL_CACHE_TIMEOUT = 86400
UNRELEASED_IMDB_STATUSES = ('Filming', 'Post Production', 'Pre Production')
PERSON_DETAIL_WARM_KEYS = {
    'total_persons_by_show_type',
    'persons_avatar_stats',
    'professions_stats',
    'en_professions_stats',
    'unused_persons',
}


def _format_type(t):
    if not t:
        return 'Неизвестно'
    mapped = SHOW_TYPE_MAPPING.get(t, t)
    return SHOW_TYPE_DISPLAY_RU.get(mapped, mapped)


def _aggregate_by_display_type(stats_qs, type_field='type', count_field='total'):
    merged = defaultdict(int)
    for item in stats_qs:
        raw_type = item.get(type_field)
        display_name = _format_type(raw_type)
        merged[display_name] += item.get(count_field, 0)
    return [
        {'name': k, 'value': v} for k, v in sorted(merged.items(), key=lambda x: x[1], reverse=True)
    ]


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


def _format_type(t):
    if not t:
        return 'Неизвестно'
    return SHOW_TYPE_DISPLAY_RU.get(t, t)


def calculate_has_kp_metric():
    stats = (
        Show.objects.filter(kinopoisk_rating__isnull=False)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def calculate_has_imdb_metric():
    stats = (
        Show.objects.filter(imdb_rating__isnull=False)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def calculate_total_shows_metric():
    stats = Show.objects.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_total_shows_list(show_type: str):
    return Show.objects.filter(type=show_type).values('id', 'title', 'original_title')


def _exclude_unreleased_imdb_titles(queryset):
    current_year = timezone.localdate().year
    return queryset.exclude(
        Q(status__in=UNRELEASED_IMDB_STATUSES)
        | Q(status__iexact='announced')
        | Q(year__gt=current_year)
    )


def calculate_missing_imdb_metric():
    qs = Show.objects.filter(imdb_url__isnull=False, imdb_rating__isnull=True).exclude(imdb_url='')
    qs = _exclude_unreleased_imdb_titles(qs).filter(imdb_rating_available=True)
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_missing_imdb_list(show_type: str):
    qs = (
        Show.objects.filter(type=show_type, imdb_url__isnull=False)
        .exclude(imdb_url='')
        .filter(imdb_rating__isnull=True)
    )
    return (
        _exclude_unreleased_imdb_titles(qs)
        .filter(imdb_rating_available=True)
        .values('id', 'title', 'original_title')
    )


def calculate_imdb_unrated_metric():
    qs = Show.objects.filter(
        imdb_url__isnull=False,
        imdb_rating__isnull=True,
        imdb_rating_available=False,
    ).exclude(imdb_url='')
    qs = _exclude_unreleased_imdb_titles(qs)
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_imdb_unrated_list(show_type: str):
    qs = Show.objects.filter(
        type=show_type,
        imdb_url__isnull=False,
        imdb_rating__isnull=True,
        imdb_rating_available=False,
    ).exclude(imdb_url='')
    return _exclude_unreleased_imdb_titles(qs).values('id', 'title', 'original_title')


def get_has_rating_list(show_type: str, source: str):
    if source == 'imdb':
        return Show.objects.filter(type=show_type, imdb_rating__isnull=False).values(
            'id', 'title', 'original_title'
        )

    rating_exists = ExternalRating.objects.filter(
        show_id=OuterRef('pk'), **{f'{source}__isnull': False}
    )
    return (
        Show.objects.filter(type=show_type)
        .filter(Exists(rating_exists))
        .values('id', 'title', 'original_title')
    )


def calculate_missing_kp_metric():
    qs = Show.objects.filter(
        kinopoisk_url__gt='',
        kinopoisk_rating__isnull=True,
        kinopoisk_rating_available=True,
    ).exclude(kinopoisk_url__endswith='/film/0')
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def calculate_kp_unrated_metric():
    """Titles checked by Poiskkino where KinoPoisk has no published rating."""
    qs = Show.objects.filter(
        kinopoisk_url__gt='',
        kinopoisk_rating__isnull=True,
        kinopoisk_rating_available=False,
        poiskkino_updated_at__isnull=False,
    ).exclude(kinopoisk_url__endswith='/film/0')
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def calculate_missing_imdb_id_metric():
    qs = Show.objects.filter(kinopub_id__isnull=False).filter(
        Q(imdb_id__isnull=True) | Q(imdb_id='')
    )
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_missing_imdb_id_list(show_type: str):
    return (
        Show.objects.filter(type=show_type, kinopub_id__isnull=False)
        .filter(Q(imdb_id__isnull=True) | Q(imdb_id=''))
        .values('id', 'kinopub_id', 'title', 'original_title')
    )


def calculate_tmdb_only_shows_metric():
    qs = Show.objects.filter(tmdb_id__isnull=False, kinopub_id__isnull=True)
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_tmdb_only_shows_list(show_type: str):
    return Show.objects.filter(
        type=show_type, tmdb_id__isnull=False, kinopub_id__isnull=True
    ).values('id', 'tmdb_id', 'title', 'original_title')


def calculate_missing_tmdb_id_metric():
    qs = Show.objects.filter(kinopub_id__isnull=False, tmdb_id__isnull=True)
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_missing_tmdb_id_list(show_type: str):
    return Show.objects.filter(
        type=show_type, kinopub_id__isnull=False, tmdb_id__isnull=True
    ).values('id', 'kinopub_id', 'title', 'original_title')


def calculate_tmdb_no_kp_metric():
    qs = Show.objects.filter(tmdb_id__isnull=False).filter(
        Q(kinopoisk_url__isnull=True) | Q(kinopoisk_url='')
    )
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_tmdb_no_kp_list(show_type: str):
    return (
        Show.objects.filter(type=show_type, tmdb_id__isnull=False)
        .filter(Q(kinopoisk_url__isnull=True) | Q(kinopoisk_url=''))
        .values('id', 'tmdb_id', 'title', 'original_title')
    )


def calculate_tmdb_missing_status_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, type__in=SERIES_TYPES)
        .filter(Q(status__isnull=True) | Q(status=''))
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_tmdb_missing_status_list(show_type: str):
    return (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, type=show_type)
        .filter(Q(status__isnull=True) | Q(status=''))
        .values('id', 'title', 'original_title')
    )


def generate_global_metrics_snapshot(profession_stats=None) -> dict:
    if profession_stats is None:
        profession_stats = _calculate_profession_stats()
    professions_stats, en_professions_stats = profession_stats
    duplicate_photo_stats = calculate_duplicate_photo_urls_metric()
    warm_duplicate_photo_urls_cache()
    return {
        'missing_kp': calculate_missing_kp_metric(),
        'kp_unrated': calculate_kp_unrated_metric(),
        'missing_imdb': calculate_missing_imdb_metric(),
        'imdb_unrated': calculate_imdb_unrated_metric(),
        'missing_imdb_id': calculate_missing_imdb_id_metric(),
        'tmdb_only_shows': calculate_tmdb_only_shows_metric(),
        'missing_tmdb_id': calculate_missing_tmdb_id_metric(),
        'tmdb_no_kp': calculate_tmdb_no_kp_metric(),
        'has_kp': calculate_has_kp_metric(),
        'has_imdb': calculate_has_imdb_metric(),
        'total_shows': calculate_total_shows_metric(),
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
        'professions_stats': professions_stats,
        'en_professions_stats': en_professions_stats,
        'duplicate_photo_urls': duplicate_photo_stats,
        'unused_persons': calculate_unused_persons_metric(),
        'tmdb_missing_year': calculate_tmdb_missing_year_metric(),
        'tmdb_missing_status': calculate_tmdb_missing_status_metric(),
        'tmdb_missing_plot': calculate_tmdb_missing_plot_metric(),
        'tmdb_missing_durations': calculate_tmdb_missing_durations_metric(),
        'tmdb_no_genres': calculate_tmdb_no_genres_metric(),
        'tmdb_no_countries': calculate_tmdb_no_countries_metric(),
    }


def get_global_metrics_history() -> dict:
    now = timezone.now()

    try:
        latest = SiteMetric.objects.filter(key='global_snapshot').order_by('-created_at').first()
    except ProgrammingError:
        return {}

    # Snapshots are refreshed by Celery Beat once per hour.  Do not enqueue a
    # full database-wide recalculation from a user request when the cache is
    # stale: several requests arriving together can otherwise create repeated
    # expensive metric work.

    if not latest:
        return {}

    queue_duplicate_photo_urls_warmup()
    queue_person_detail_warmup()

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


def get_missing_kp_list(show_type: str):
    return (
        Show.objects.filter(
            type=show_type,
            kinopoisk_url__gt='',
            kinopoisk_rating__isnull=True,
            kinopoisk_rating_available=True,
        )
        .exclude(kinopoisk_url__endswith='/film/0')
        .values('id', 'title', 'original_title')
    )


def get_kp_unrated_list(show_type: str):
    return (
        Show.objects.filter(
            type=show_type,
            kinopoisk_url__gt='',
            kinopoisk_rating__isnull=True,
            kinopoisk_rating_available=False,
            poiskkino_updated_at__isnull=False,
        )
        .exclude(kinopoisk_url__endswith='/film/0')
        .values('id', 'title', 'original_title')
    )


def calculate_missing_year_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=False, year__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_missing_year_list(show_type: str):
    return Show.objects.filter(kinopub_id__isnull=False, type=show_type, year__isnull=True).values(
        'id', 'title', 'original_title'
    )


def calculate_tmdb_missing_year_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, year__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_tmdb_missing_year_list(show_type: str):
    return Show.objects.filter(
        kinopub_id__isnull=True, tmdb_id__isnull=False, type=show_type, year__isnull=True
    ).values('id', 'title', 'original_title')


def calculate_missing_plot_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=False)
        .filter(Q(plot__isnull=True) | Q(plot=''))
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_missing_plot_list(show_type: str):
    return (
        Show.objects.filter(kinopub_id__isnull=False, type=show_type)
        .filter(Q(plot__isnull=True) | Q(plot=''))
        .values('id', 'title', 'original_title')
    )


def calculate_tmdb_missing_plot_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False)
        .filter(Q(plot__isnull=True) | Q(plot=''))
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_tmdb_missing_plot_list(show_type: str):
    return (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, type=show_type)
        .filter(Q(plot__isnull=True) | Q(plot=''))
        .values('id', 'title', 'original_title')
    )


def calculate_no_genres_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=False, genres__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_no_genres_list(show_type: str):
    genre_exists = Show.genres.through.objects.filter(show_id=OuterRef('pk'))
    return (
        Show.objects.filter(kinopub_id__isnull=False, type=show_type)
        .filter(~Exists(genre_exists))
        .values('id', 'title', 'original_title')
    )


def calculate_tmdb_no_genres_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, genres__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_tmdb_no_genres_list(show_type: str):
    genre_exists = Show.genres.through.objects.filter(show_id=OuterRef('pk'))
    return (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, type=show_type)
        .filter(~Exists(genre_exists))
        .values('id', 'title', 'original_title')
    )


def calculate_no_countries_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=False, countries__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_no_countries_list(show_type: str):
    country_exists = Show.countries.through.objects.filter(show_id=OuterRef('pk'))
    return (
        Show.objects.filter(kinopub_id__isnull=False, type=show_type)
        .filter(~Exists(country_exists))
        .values('id', 'title', 'original_title')
    )


def calculate_tmdb_no_countries_metric():
    stats = (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, countries__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_tmdb_no_countries_list(show_type: str):
    country_exists = Show.countries.through.objects.filter(show_id=OuterRef('pk'))
    return (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, type=show_type)
        .filter(~Exists(country_exists))
        .values('id', 'title', 'original_title')
    )


def _canonical_person_ids(crew_queryset, max_items=None):
    person_ids = (
        crew_queryset.annotate(canonical_id=_canonical_person_id_expression())
        .values('canonical_id')
        .distinct()
        .order_by('canonical_id')
    )
    return person_ids[:max_items] if max_items is not None else person_ids


def _person_values_queryset(person_ids):
    return Person.objects.filter(id__in=person_ids).values(
        'id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id'
    )


def get_total_persons_list(show_type: str, max_items=None):
    person_ids = _canonical_person_ids(
        ShowCrew.objects.filter(show__type=show_type), max_items=max_items
    )
    return _person_values_queryset(person_ids)


def get_unused_persons_list():
    return Person.objects.filter(master_person__isnull=True, showcrew__isnull=True).values(
        'id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id'
    )


def get_persons_avatar_list(source_type: str):
    has_tmdb = Q(tmdb_photo_url__isnull=False) & ~Q(tmdb_photo_url='')
    has_kp = Q(kp_photo_url__isnull=False) & ~Q(kp_photo_url='')
    tmdb_done = Q(is_photo_fetched=True)
    waiting_shows = (
        Show.objects.filter(kinopoisk_url__isnull=False, ext_rating__isnull=True)
        .exclude(kinopoisk_url='')
        .exclude(kinopoisk_url__endswith='/film/0')
    )
    kp_wait_filter = Q(id__in=ShowCrew.objects.filter(show__in=waiting_shows).values('person_id'))

    filters = {
        'has_tmdb': Q(has_tmdb),
        'kp': Q(has_kp) & ~Q(has_tmdb),
        'tmdb_none': Q(tmdb_done) & ~Q(has_tmdb),
        'kp_none': ~Q(has_kp) & ~Q(kp_wait_filter),
        'tmdb_wait': ~Q(tmdb_done | has_tmdb),
        'kp_wait': Q(kp_wait_filter) & ~Q(has_kp),
        'all_none': Q(tmdb_done) & ~Q(has_tmdb | has_kp) & ~Q(kp_wait_filter),
    }
    return Person.objects.filter(filters.get(source_type, Q(pk__in=[]))).values(
        'id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id'
    )


def get_profession_persons_list(normalized: str, language: str, max_items=None):
    if language == 'ru':
        primary_mapping = RAW_TO_NORMALIZED_RU
        en_to_ru = {en: ru for ru, en in PROFESSION_TRANS_MAP.items()}
        fallback_mapping = {
            raw: en_to_ru[value] for raw, value in RAW_TO_NORMALIZED_EN.items() if value in en_to_ru
        }
    else:
        primary_mapping = RAW_TO_NORMALIZED_EN
        ru_to_en = {ru: en for ru, en in PROFESSION_TRANS_MAP.items()}
        fallback_mapping = {
            raw: ru_to_en[value] for raw, value in RAW_TO_NORMALIZED_RU.items() if value in ru_to_en
        }

    unknown = '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e'
    if normalized == unknown:
        if language == 'ru':
            known_filter = Q(showcrew__profession__in=primary_mapping) | Q(
                showcrew__en_profession__in=fallback_mapping
            )
        else:
            known_filter = Q(showcrew__profession__in=primary_mapping) | Q(
                showcrew__en_profession__in=fallback_mapping
            )
        return (
            Person.objects.filter(master_person__isnull=True)
            .exclude(known_filter)
            .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id')
        )

    role_case = Case(
        *[When(profession=raw, then=Value(value)) for raw, value in primary_mapping.items()],
        *[When(en_profession=raw, then=Value(value)) for raw, value in fallback_mapping.items()],
        output_field=CharField(),
    )
    primary_known = Q(profession__in=primary_mapping)
    target_primary = Q(
        profession__in=[raw for raw, value in primary_mapping.items() if value == normalized]
    )
    target_fallback = Q(
        en_profession__in=[raw for raw, value in fallback_mapping.items() if value == normalized]
    )
    role_filter = target_primary | (~primary_known & target_fallback)
    person_ids = _canonical_person_ids(
        ShowCrew.objects.filter(role_filter).annotate(normalized_role=role_case),
        max_items=max_items,
    )
    return _person_values_queryset(person_ids)


def calculate_total_persons_by_show_type_metric():
    canonical_id = _canonical_person_id_expression()
    with connection.cursor() as cursor:
        cursor.execute('SET enable_sort TO off')
    try:
        stats = (
            ShowCrew.objects.filter(show__type__isnull=False)
            .exclude(show__type='')
            .annotate(canonical_id=canonical_id)
            .values('show__type')
            .annotate(total=Count('canonical_id', distinct=True))
            .order_by('-total')
        )
        return _aggregate_by_display_type(stats, type_field='show__type', count_field='total')
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SET enable_sort TO on')


def _canonical_person_id_expression():
    if ShowCrew.objects.filter(canonical_person__isnull=True).exists():
        return Coalesce('canonical_person_id', 'person__master_person_id', 'person_id')
    return F('canonical_person_id')


def calculate_persons_avatar_stats_metric():
    has_tmdb = Q(tmdb_photo_url__isnull=False) & ~Q(tmdb_photo_url='')
    has_kp = Q(kp_photo_url__isnull=False) & ~Q(kp_photo_url='')
    tmdb_done = Q(is_photo_fetched=True)

    waiting_shows = (
        Show.objects.filter(
            kinopoisk_url__isnull=False,
            ext_rating__isnull=True,
        )
        .exclude(kinopoisk_url='')
        .exclude(kinopoisk_url__endswith='/film/0')
    )
    kp_waiting_ids = ShowCrew.objects.filter(show__in=waiting_shows).values('person_id')
    kp_wait_filter = Q(id__in=kp_waiting_ids)

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
            'value': Person.objects.exclude(has_kp).exclude(kp_wait_filter).count(),
        },
        {'name': 'В ожидании TMDB', 'value': Person.objects.exclude(tmdb_done | has_tmdb).count()},
        {
            'name': 'В ожидании KP',
            'value': Person.objects.filter(kp_wait_filter).exclude(has_kp).count(),
        },
        {
            'name': 'Не найдено вообще',
            'value': Person.objects.filter(tmdb_done)
            .exclude(has_tmdb | has_kp)
            .exclude(kp_wait_filter)
            .count(),
        },
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def _get_crew_profession_tuples():
    return list(
        ShowCrew.objects.exclude(profession__isnull=True, en_profession__isnull=True)
        .values('profession', 'en_profession')
        .annotate(master_id=Coalesce('person__master_person_id', 'person__id'))
        .values('profession', 'en_profession', 'master_id')
        .distinct()
    )


def _get_alias_map():
    return dict(
        Person.objects.filter(master_person__isnull=False).values_list('id', 'master_person_id')
    )


def _calculate_profession_stats_db():
    canonical_id = Coalesce('person__master_person_id', 'person_id')
    total_masters = Person.objects.filter(master_person__isnull=True).count()

    def calculate(mapping, raw_to_normalized, fallback_mapping):
        whens = []
        known_filter = Q()
        for normalized, raw_values in mapping.items():
            whens.append(When(profession__in=raw_values, then=Value(normalized)))
            known_filter |= Q(profession__in=raw_values)
            fallback_values = fallback_mapping.get(normalized, [])
            if fallback_values:
                whens.append(When(en_profession__in=fallback_values, then=Value(normalized)))
                known_filter |= Q(en_profession__in=fallback_values)

        role_case = Case(*whens, output_field=CharField())
        stats = (
            ShowCrew.objects.filter(known_filter)
            .annotate(normalized=role_case, canonical_id=canonical_id)
            .values('normalized')
            .annotate(value=Count('canonical_id', distinct=True))
            .order_by('-value')
        )
        result = [
            {'name': row['normalized'], 'value': row['value']} for row in stats if row['normalized']
        ]
        known_count = (
            ShowCrew.objects.filter(known_filter)
            .annotate(canonical_id=canonical_id)
            .values('canonical_id')
            .distinct()
            .count()
        )
        unknown_count = max(0, total_masters - known_count)
        if unknown_count:
            result.append(
                {
                    'name': '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e',
                    'value': unknown_count,
                }
            )
        return result

    ru_to_en = PROFESSION_TRANS_MAP
    ru_result = calculate(
        PROFESSIONS_MAPPING_RU,
        RAW_TO_NORMALIZED_RU,
        {ru: PROFESSIONS_MAPPING_EN.get(en, []) for ru, en in ru_to_en.items()},
    )
    en_result = calculate(
        PROFESSIONS_MAPPING_EN,
        RAW_TO_NORMALIZED_EN,
        {en: PROFESSIONS_MAPPING_RU.get(ru, []) for ru, en in ru_to_en.items()},
    )
    return ru_result, en_result


def _calculate_profession_stats_indexed():
    """Use role indexes while keeping all person IDs inside the database."""
    canonical_id = Coalesce('person__master_person_id', 'person_id')
    total_masters = Person.objects.filter(master_person__isnull=True).count()
    ru_to_en = PROFESSION_TRANS_MAP

    def calculate(mapping, fallback_mapping):
        result = []
        known_filter = Q()
        for normalized, raw_values in mapping.items():
            fallback_values = fallback_mapping.get(normalized, [])
            role_filter = Q(profession__in=raw_values)
            known_filter |= role_filter
            if fallback_values:
                role_filter |= Q(en_profession__in=fallback_values)
                known_filter |= Q(en_profession__in=fallback_values)
            value = (
                ShowCrew.objects.filter(role_filter)
                .annotate(canonical_id=canonical_id)
                .values('canonical_id')
                .distinct()
                .count()
            )
            if value:
                result.append({'name': normalized, 'value': value})

        known_count = (
            ShowCrew.objects.filter(known_filter)
            .annotate(canonical_id=canonical_id)
            .values('canonical_id')
            .distinct()
            .count()
        )
        unknown_count = max(0, total_masters - known_count)
        if unknown_count:
            result.append(
                {
                    'name': '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e',
                    'value': unknown_count,
                }
            )
        return sorted(result, key=lambda x: x['value'], reverse=True)

    ru_fallback = {ru: PROFESSIONS_MAPPING_EN.get(en, []) for ru, en in ru_to_en.items()}
    en_fallback = {en: PROFESSIONS_MAPPING_RU.get(ru, []) for ru, en in ru_to_en.items()}
    return calculate(PROFESSIONS_MAPPING_RU, ru_fallback), calculate(
        PROFESSIONS_MAPPING_EN, en_fallback
    )


def _calculate_profession_stats():
    """Aggregate canonical people in PostgreSQL instead of streaming every crew row to Python."""
    return _calculate_profession_stats_canonical()


def _calculate_profession_stats_canonical():
    ru_to_en = PROFESSION_TRANS_MAP
    canonical_id = _canonical_person_id_expression()

    def calculate(primary_raw_to_normalized, fallback_raw_to_normalized):
        whens = [
            When(profession=raw, then=Value(normalized))
            for raw, normalized in primary_raw_to_normalized.items()
        ]
        whens.extend(
            When(en_profession=raw, then=Value(normalized))
            for raw, normalized in fallback_raw_to_normalized.items()
        )
        known_filter = Q(profession__in=primary_raw_to_normalized) | Q(
            en_profession__in=fallback_raw_to_normalized
        )

        role_case = Case(*whens, output_field=CharField())
        result = [
            {'name': row['normalized'], 'value': row['value']}
            for row in (
                ShowCrew.objects.filter(known_filter)
                .annotate(normalized=role_case, canonical_id=canonical_id)
                .values('normalized')
                .annotate(value=Count('canonical_id', distinct=True))
                .order_by('-value')
            )
            if row['normalized']
        ]
        unknown_count = (
            Person.objects.filter(master_person__isnull=True)
            .exclude(showcrew__profession__in=primary_raw_to_normalized)
            .exclude(showcrew__en_profession__in=fallback_raw_to_normalized)
            .count()
        )
        if unknown_count:
            result.append(
                {
                    'name': '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e',
                    'value': unknown_count,
                }
            )
        return result

    en_to_ru = {en: ru for ru, en in ru_to_en.items()}
    ru_to_en_raw = {
        raw: ru_to_en[normalized]
        for raw, normalized in RAW_TO_NORMALIZED_RU.items()
        if normalized in ru_to_en
    }
    en_to_ru_raw = {
        raw: en_to_ru[normalized]
        for raw, normalized in RAW_TO_NORMALIZED_EN.items()
        if normalized in en_to_ru
    }
    with connection.cursor() as cursor:
        cursor.execute('SET enable_sort TO off')
    try:
        return calculate(RAW_TO_NORMALIZED_RU, en_to_ru_raw), calculate(
            RAW_TO_NORMALIZED_EN, ru_to_en_raw
        )
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SET enable_sort TO on')


def calculate_professions_stats_metric():
    return _calculate_profession_stats()[0]
    alias_map = _get_alias_map()
    result = []
    all_known_masters = set()

    for norm_ru, raw_ru_list in PROFESSIONS_MAPPING_RU.items():
        norm_en = PROFESSION_TRANS_MAP.get(norm_ru)
        raw_en_list = PROFESSIONS_MAPPING_EN.get(norm_en, []) if norm_en else []

        q_filter = Q(profession__in=raw_ru_list)
        if raw_en_list:
            q_filter |= Q(en_profession__in=raw_en_list)

        person_ids = set(ShowCrew.objects.filter(q_filter).values_list('person_id', flat=True))
        if person_ids:
            master_ids = {alias_map.get(pid, pid) for pid in person_ids}
            all_known_masters.update(master_ids)
            cnt = len(master_ids)
            if cnt > 0:
                result.append({'name': norm_ru, 'value': cnt})

    total_master_persons = Person.objects.filter(master_person__isnull=True).count()
    unknown_count = max(0, total_master_persons - len(all_known_masters))

    if unknown_count > 0:
        result.append({'name': 'Неизвестно', 'value': unknown_count})

    return sorted(result, key=lambda x: x['value'], reverse=True)


def calculate_missing_status_metric():
    qs = Show.objects.filter(kinopub_id__isnull=False, type__in=SERIES_TYPES).filter(
        Q(status__isnull=True) | Q(status='')
    )
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def get_missing_status_list(show_type: str):
    return (
        Show.objects.filter(kinopub_id__isnull=False, type=show_type)
        .filter(Q(status__isnull=True) | Q(status=''))
        .values('id', 'title', 'original_title')
    )


def calculate_duplicate_photo_urls_metric():
    tmdb_dupes = _potential_duplicate_photo_groups('tmdb_photo_url').count()
    kp_dupes = _potential_duplicate_photo_groups('kp_photo_url').count()

    data = [
        {'name': 'TMDB дубликаты', 'value': tmdb_dupes},
        {'name': 'KP дубликаты', 'value': kp_dupes},
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def _potential_duplicate_photo_groups(field: str):
    """Photo groups that have not already been disproved by TMDB identity.

    A unique TMDB person ID is authoritative. Two rows with different IDs may
    legitimately share an image, so they are not duplicate people. Only a
    group containing an unresolved row remains a review candidate.
    """
    return (
        Person.objects.filter(master_person__isnull=True, **{f'{field}__gt': ''})
        .values(field)
        .annotate(cnt=Count('*'), tmdb_id_count=Count('tmdb_id'))
        .filter(cnt__gt=1, tmdb_id_count__lt=F('cnt'))
    )


def get_duplicate_photo_urls_page(source_type: str, offset: int = 0, limit: int = 50):
    """Return one page of duplicate-photo groups without materializing all groups."""
    field = 'tmdb_photo_url' if 'TMDB' in source_type else 'kp_photo_url'
    version = cache.get(DUPLICATE_PHOTO_CACHE_VERSION_KEY, 1)
    # v2 excludes groups already disproved by distinct TMDB identities.
    cache_key = f'metrics:duplicate_photo_urls:v2:{version}:{field}:{offset}:{limit}'
    cached_page = cache.get(cache_key)
    if cached_page is not None:
        return cached_page

    dupe_urls_data = _potential_duplicate_photo_groups(field).order_by('-cnt', field)

    group_rows = list(dupe_urls_data[offset : offset + limit + 1])
    has_more = len(group_rows) > limit
    group_rows = group_rows[:limit]
    if not group_rows:
        result = ([], False)
        cache.set(cache_key, result, timeout=DUPLICATE_PHOTO_CACHE_TIMEOUT)
        return result

    url_counts = {entry[field]: entry['cnt'] for entry in group_rows}
    urls = list(url_counts.keys())

    persons_qs = (
        Person.objects.filter(master_person__isnull=True)
        .filter(**{f'{field}__in': urls})
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id')
    )

    grouped_persons = defaultdict(list)
    for p in persons_qs:
        grouped_persons[p[field]].append(
            {
                'id': p['id'],
                'name': p['name'],
                'en_name': p['en_name'],
                'tmdb_photo_url': get_proxied_image_url(p['tmdb_photo_url']),
                'kp_photo_url': get_proxied_image_url(p['kp_photo_url']),
                'tmdb_id': p['tmdb_id'],
            }
        )

    results = []
    for url in urls:
        persons_list = sorted(grouped_persons[url], key=lambda x: x['id'])

        kp_status = None
        if field == 'tmdb_photo_url':
            kp_urls = {p['kp_photo_url'] for p in persons_list if p.get('kp_photo_url')}
            kp_urls.discard('')
            has_kp_count = sum(
                1 for p in persons_list if p.get('kp_photo_url') and p.get('kp_photo_url') != ''
            )
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
            has_tmdb_count = sum(
                1 for p in persons_list if p.get('tmdb_photo_url') and p.get('tmdb_photo_url') != ''
            )
            if len(tmdb_urls) == 0:
                tmdb_status = 'missing'
            elif len(tmdb_urls) == 1:
                if has_tmdb_count == len(persons_list):
                    tmdb_status = 'same'
                else:
                    tmdb_status = 'partial'
            else:
                tmdb_status = 'different'

        proxied_main_url = get_proxied_image_url(url)

        results.append(
            {
                'id': 0,
                'title': f'Группа дубликатов ({url_counts[url]})',
                'persons': persons_list,
                'tmdb_photo_url': proxied_main_url if field == 'tmdb_photo_url' else None,
                'kp_photo_url': proxied_main_url if field == 'kp_photo_url' else None,
                'kp_status': kp_status,
                'tmdb_status': tmdb_status,
                'admin_url': f'/admin/app/person/?q={url}',
            }
        )
    result = (results, has_more)
    cache.set(cache_key, result, timeout=DUPLICATE_PHOTO_CACHE_TIMEOUT)
    return result


def queue_duplicate_photo_urls_warmup():
    """Queue duplicate pages before a user opens the corresponding modal."""
    version = cache.get(DUPLICATE_PHOTO_CACHE_VERSION_KEY, 1)
    cache_keys = (
        f'metrics:duplicate_photo_urls:v2:{version}:kp_photo_url:0:50',
        f'metrics:duplicate_photo_urls:v2:{version}:tmdb_photo_url:0:50',
    )
    if any(cache.get(cache_key) is None for cache_key in cache_keys) and cache.add(
        'metrics:duplicate_photo_urls:warmup_lock', True, timeout=300
    ):
        celery_app.send_task('app.tasks.warm_duplicate_photo_urls_task', queue='metrics')


def person_detail_cache_key(key, value, offset, limit):
    version = cache.get(PERSON_DETAIL_CACHE_VERSION_KEY, 1)
    digest = sha1(f'{key}|{value}|{offset}|{limit}'.encode()).hexdigest()
    return f'metrics:person_detail:{version}:{digest}'


def queue_person_detail_warmup():
    if cache.add('metrics:person_detail:warmup_lock', True, timeout=900):
        celery_app.send_task('app.tasks.warm_person_metric_pages_task', queue='metrics')


def warm_duplicate_photo_urls_cache():
    """Populate the first modal page off the request path."""
    for source_type in ('TMDB', 'KP'):
        get_duplicate_photo_urls_page(source_type, offset=0, limit=50)


def invalidate_duplicate_photo_urls_cache():
    version = cache.get(DUPLICATE_PHOTO_CACHE_VERSION_KEY, 1)
    cache.set(DUPLICATE_PHOTO_CACHE_VERSION_KEY, int(version) + 1, timeout=None)
    cache.delete('metrics:duplicate_photo_urls:warmup_lock')


def get_duplicate_photo_urls_list(source_type: str):
    """Backward-compatible full-list helper for non-HTTP callers."""
    results = []
    offset = 0
    while True:
        page, has_more = get_duplicate_photo_urls_page(source_type, offset=offset, limit=500)
        results.extend(page)
        if not has_more:
            return results
        offset += len(page)


def calculate_en_professions_stats_metric():
    return _calculate_profession_stats()[1]

    alias_map = _get_alias_map()
    ru_to_en_map = PROFESSION_TRANS_MAP

    result = []
    all_known_masters = set()

    for norm_en, raw_en_list in PROFESSIONS_MAPPING_EN.items():
        norm_ru = next((k for k, v in ru_to_en_map.items() if v == norm_en), None)
        raw_ru_list = PROFESSIONS_MAPPING_RU.get(norm_ru, []) if norm_ru else []

        q_filter = Q(en_profession__in=raw_en_list)
        if raw_ru_list:
            q_filter |= Q(profession__in=raw_ru_list)

        person_ids = set(ShowCrew.objects.filter(q_filter).values_list('person_id', flat=True))
        if person_ids:
            master_ids = {alias_map.get(pid, pid) for pid in person_ids}
            all_known_masters.update(master_ids)
            cnt = len(master_ids)
            if cnt > 0:
                result.append({'name': norm_en, 'value': cnt})

    total_master_persons = Person.objects.filter(master_person__isnull=True).count()
    unknown_count = max(0, total_master_persons - len(all_known_masters))

    if unknown_count > 0:
        result.append({'name': 'Неизвестно', 'value': unknown_count})

    return sorted(result, key=lambda x: x['value'], reverse=True)


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
        Show.objects.filter(kinopub_id__isnull=False, showduration__isnull=True)
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_missing_durations_list(show_type: str):
    duration_exists = ShowDuration.objects.filter(show_id=OuterRef('pk'))
    return (
        Show.objects.filter(kinopub_id__isnull=False, type=show_type)
        .filter(~Exists(duration_exists))
        .values('id', 'title', 'original_title')
    )


def calculate_tmdb_missing_durations_metric():
    stats = (
        Show.objects.filter(
            kinopub_id__isnull=True, tmdb_id__isnull=False, showduration__isnull=True
        )
        .values('type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return _aggregate_by_display_type(stats)


def get_tmdb_missing_durations_list(show_type: str):
    duration_exists = ShowDuration.objects.filter(show_id=OuterRef('pk'))
    return (
        Show.objects.filter(kinopub_id__isnull=True, tmdb_id__isnull=False, type=show_type)
        .filter(~Exists(duration_exists))
        .values('id', 'title', 'original_title')
    )


def calculate_unused_persons_metric():
    return [
        {
            'name': 'Без ролей',
            'value': Person.objects.filter(
                master_person__isnull=True, showcrew__isnull=True
            ).count(),
        }
    ]

    alias_map = _get_alias_map()
    used_person_ids = set(ShowCrew.objects.values_list('person_id', flat=True))
    used_master_ids = {alias_map.get(pid, pid) for pid in used_person_ids}
    total_master_persons = Person.objects.filter(master_person__isnull=True).count()
    count = max(0, total_master_persons - len(used_master_ids))
    return [{'name': 'Без ролей', 'value': count}]
