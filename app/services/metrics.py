import json
from collections import defaultdict
from contextlib import contextmanager
from datetime import timedelta
from hashlib import sha1

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.db.utils import ProgrammingError
from django.utils import timezone

from app.models import (
    Country,
    Genre,
    LogEntry,
    Person,
    PersonPhotoGroup,
    Show,
    ShowCrew,
    ShowDuration,
    SiteMetric,
    TelegramLog,
    ViewHistory,
    ViewUser,
)
from app.services.person_metric_summary import (
    get_person_metric_summary_data,
    person_metric_summary_ready,
)
from app.services.person_photo_metric_summary import (
    get_person_photo_metric_summary_data,
    person_photo_metric_summary_ready,
    refresh_dirty_person_photo_groups,
)
from app.services.show_metric_summary import get_show_metric_aggregate_data
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
DUPLICATE_PHOTO_MEMBER_PAGE_SIZE = 50
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
SYSTEM_STATUS_SNAPSHOT_KEY = '_system_status'
HEAVY_METRIC_AGGREGATE_WORK_MEM = '256MB'
HEAVY_METRIC_AGGREGATE_TIMEOUT_MS = 600_000


@contextmanager
def metrics_statement_timeout():
    """Bound each PostgreSQL statement issued by a metrics calculation."""
    timeout_ms = settings.METRICS_STATEMENT_TIMEOUT_MS
    with connection.cursor() as cursor:
        cursor.execute('SHOW statement_timeout')
        previous_timeout = cursor.fetchone()[0]
        cursor.execute('SET statement_timeout = %s', [timeout_ms])

    interrupted = False
    try:
        yield
    except BaseException:
        # A Celery soft timeout can arrive while psycopg is waiting for a
        # result. The connection then still has a command in flight; trying to
        # restore statement_timeout on it masks the original timeout with
        # "another command is already in progress".
        interrupted = True
        connection.close()
        raise
    finally:
        if not interrupted:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SET statement_timeout = %s', [previous_timeout])
            except Exception:
                # A timed-out statement can leave the connection unusable.
                # Closing it makes Django open a clean connection next time.
                connection.close()


@contextmanager
def _heavy_metric_query(value):
    """Give one large metric aggregate bounded memory and execution time."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SHOW work_mem')
            previous_work_mem = cursor.fetchone()[0]
            cursor.execute('SHOW statement_timeout')
            previous_statement_timeout = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('work_mem', %s, true)", [value])
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                [str(HEAVY_METRIC_AGGREGATE_TIMEOUT_MS)],
            )
            yield cursor
            cursor.execute(
                "SELECT set_config('work_mem', %s, true)",
                [previous_work_mem],
            )
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                [previous_statement_timeout],
            )


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


def _countries_with_metadata_for_aliases(countries):
    normalized_names = {
        RAW_TO_NORMALIZED_COUNTRY[country.name]
        for country in countries
        if country.name in RAW_TO_NORMALIZED_COUNTRY
    }
    if not normalized_names:
        return set()

    return set(
        Country.objects.filter(name__in=normalized_names)
        .exclude(Q(iso_code__isnull=True) | Q(iso_code=''))
        .values_list('name', flat=True)
    )


def calculate_missing_country_meta_metric():
    raw_missing = list(Country.objects.filter(Q(iso_code__isnull=True) | Q(iso_code='')))
    normalized_with_metadata = _countries_with_metadata_for_aliases(raw_missing)
    count = 0
    for c in raw_missing:
        norm_name = RAW_TO_NORMALIZED_COUNTRY.get(c.name, c.name)
        if norm_name != c.name and norm_name in normalized_with_metadata:
            continue
        count += 1
    return [{'name': 'Страны', 'value': count}]


def get_missing_country_meta_list():
    raw_missing = list(Country.objects.filter(Q(iso_code__isnull=True) | Q(iso_code='')))
    normalized_with_metadata = _countries_with_metadata_for_aliases(raw_missing)
    valid_missing = []
    for c in raw_missing:
        norm_name = RAW_TO_NORMALIZED_COUNTRY.get(c.name, c.name)
        if norm_name != c.name and norm_name in normalized_with_metadata:
            continue
        valid_missing.append({'id': c.id, 'name': c.name})
    return valid_missing


def calculate_total_countries_metric():
    show_country = Show.countries.through.objects.filter(country_id=OuterRef('pk'))
    counts = Country.objects.annotate(has_show=Exists(show_country)).aggregate(
        active=Count('id', filter=Q(has_show=True)),
        unused=Count('id', filter=Q(has_show=False)),
    )
    data = [
        {'name': 'Активные', 'value': counts['active'] or 0},
        {'name': 'Неиспользуемые', 'value': counts['unused'] or 0},
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


def calculate_has_kp_metric():
    stats = (
        Show.objects.filter(ext_rating__kp__isnull=False)
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
    if source == 'kp':
        return Show.objects.filter(type=show_type, ext_rating__kp__isnull=False).values(
            'id', 'title', 'original_title'
        )
    return Show.objects.none()


def calculate_missing_kp_metric():
    qs = Show.objects.filter(
        kinopoisk_url__isnull=False,
        ext_rating__kp__isnull=True,
        kinopoisk_rating_available=True,
    ).exclude(kinopoisk_url='').exclude(kinopoisk_url__endswith='/film/0')
    stats = qs.values('type').annotate(total=Count('id')).order_by('-total')
    return _aggregate_by_display_type(stats)


def calculate_kp_unrated_metric():
    """Titles checked by Poiskkino where KinoPoisk has no published rating."""
    qs = Show.objects.filter(
        kinopoisk_url__isnull=False,
        ext_rating__kp__isnull=True,
        kinopoisk_rating_available=False,
        poiskkino_updated_at__isnull=False,
    ).exclude(kinopoisk_url='').exclude(kinopoisk_url__endswith='/film/0')
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


def _format_snapshot_datetime(value):
    if not value:
        return 'Никогда'
    return timezone.localtime(value).strftime('%d.%m.%Y %H:%M')


def calculate_system_status_snapshot() -> dict:
    """Collect the values shown in the metrics-page status strip.

    These values belong to the same immutable snapshot as the charts. Keeping
    them here prevents a page GET from running live queries against the large
    catalog tables.
    """
    cutoff_24h = timezone.now() - timedelta(days=1)
    shows_latest = Show.objects.order_by('-created_at').values_list('created_at', flat=True).first()
    ratings_kp_latest = (
        Show.objects.filter(poiskkino_updated_at__isnull=False)
        .order_by('-poiskkino_updated_at')
        .values_list('poiskkino_updated_at', flat=True)
        .first()
    )
    ratings_imdb_latest = (
        Show.objects.filter(imdb_rating_updated_at__isnull=False)
        .order_by('-imdb_rating_updated_at')
        .values_list('imdb_rating_updated_at', flat=True)
        .first()
    )
    parser_run_latest = (
        LogEntry.objects.filter(message__contains='Parser session finished')
        .order_by('-created_at')
        .values_list('created_at', flat=True)
        .first()
    )
    errors_24h_count = LogEntry.objects.filter(
        created_at__gte=cutoff_24h,
        level__in=['ERROR', 'CRITICAL'],
    ).count()
    users = ViewUser.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_bot_active=True)),
    )

    return {
        'last_actions': {
            'history': _format_snapshot_datetime(
                ViewHistory.objects.order_by('-created_at')
                .values_list('created_at', flat=True)
                .first()
            ),
            'parser_run': _format_snapshot_datetime(parser_run_latest),
            'shows': _format_snapshot_datetime(shows_latest),
            'ratings_kp': _format_snapshot_datetime(ratings_kp_latest),
            'ratings_imdb': _format_snapshot_datetime(ratings_imdb_latest),
            'durations': _format_snapshot_datetime(
                ShowDuration.objects.order_by('-updated_at')
                .values_list('updated_at', flat=True)
                .first()
            ),
            'photos': _format_snapshot_datetime(
                Person.objects.filter(is_photo_fetched=True)
                .order_by('-updated_at')
                .values_list('updated_at', flat=True)
                .first()
            ),
            'tg': _format_snapshot_datetime(
                TelegramLog.objects.order_by('-created_at')
                .values_list('created_at', flat=True)
                .first()
            ),
        },
        'errors_24h_count': errors_24h_count,
        'bot_users_active': users['active'] or 0,
        'bot_users_total': users['total'] or 0,
    }


def generate_global_metrics_snapshot(profession_stats=None) -> dict:
    person_summary = (
        get_person_metric_summary_data() if person_metric_summary_ready() else None
    )
    person_photo_summary = (
        get_person_photo_metric_summary_data()
        if person_photo_metric_summary_ready()
        else None
    )
    show_metric_summary = get_show_metric_aggregate_data()
    if profession_stats is None:
        profession_stats = (
            _profession_stats_from_summary(person_summary)
            if person_summary is not None
            else _calculate_profession_stats()
        )
    professions_stats, en_professions_stats = profession_stats
    duplicate_photo_stats = calculate_duplicate_photo_urls_metric(
        photo_summary=person_photo_summary
    )
    # Cache warming is deliberately kept off the snapshot path.  This
    # Cache warming is deliberately kept off the snapshot path.  The
    # duplicate-photo query scans a large person table, so a slow cache fill
    # must not pin the snapshot lock or any parser/browser resource.
    return {
        SYSTEM_STATUS_SNAPSHOT_KEY: calculate_system_status_snapshot(),
        'missing_kp': _snapshot_show_metric(show_metric_summary, 'missing_kp', calculate_missing_kp_metric),
        'kp_unrated': _snapshot_show_metric(show_metric_summary, 'kp_unrated', calculate_kp_unrated_metric),
        'missing_imdb': _snapshot_show_metric(show_metric_summary, 'missing_imdb_candidate', calculate_missing_imdb_metric, exclude_unreleased=True),
        'imdb_unrated': _snapshot_show_metric(show_metric_summary, 'imdb_unrated_candidate', calculate_imdb_unrated_metric, exclude_unreleased=True),
        'missing_imdb_id': _snapshot_show_metric(show_metric_summary, 'missing_imdb_id', calculate_missing_imdb_id_metric),
        'tmdb_only_shows': _snapshot_show_metric(show_metric_summary, 'tmdb_only_shows', calculate_tmdb_only_shows_metric),
        'missing_tmdb_id': _snapshot_show_metric(show_metric_summary, 'missing_tmdb_id', calculate_missing_tmdb_id_metric),
        'tmdb_no_kp': _snapshot_show_metric(show_metric_summary, 'tmdb_no_kp', calculate_tmdb_no_kp_metric),
        'has_kp': _snapshot_show_metric(show_metric_summary, 'has_kp', calculate_has_kp_metric),
        'has_imdb': _snapshot_show_metric(show_metric_summary, 'has_imdb', calculate_has_imdb_metric),
        'total_shows': _snapshot_show_metric(show_metric_summary, 'total_shows', calculate_total_shows_metric),
        'missing_year': _snapshot_show_metric(show_metric_summary, 'missing_year', calculate_missing_year_metric),
        'missing_status': _snapshot_show_metric(show_metric_summary, 'missing_status', calculate_missing_status_metric),
        'missing_plot': _snapshot_show_metric(show_metric_summary, 'missing_plot', calculate_missing_plot_metric),
        'missing_durations': _snapshot_show_metric(show_metric_summary, 'missing_durations', calculate_missing_durations_metric),
        'no_genres': _snapshot_show_metric(
            show_metric_summary, 'no_genres', calculate_no_genres_metric
        ),
        'total_genres': calculate_total_genres_metric(),
        'unmapped_genres': calculate_unmapped_genres_metric(),
        'no_countries': _snapshot_show_metric(
            show_metric_summary, 'no_countries', calculate_no_countries_metric
        ),
        'missing_country_meta': calculate_missing_country_meta_metric(),
        'total_countries': calculate_total_countries_metric(),
        'total_persons_by_show_type': (
            _total_persons_by_show_type_from_summary(person_summary)
            if person_summary is not None
            else calculate_total_persons_by_show_type_metric()
        ),
        'persons_avatar_stats': calculate_persons_avatar_stats_metric(
            person_summary=person_summary,
            photo_summary=person_photo_summary,
        ),
        'professions_stats': professions_stats,
        'en_professions_stats': en_professions_stats,
        'duplicate_photo_urls': duplicate_photo_stats,
        'unused_persons': (
            _unused_persons_from_summary(person_summary)
            if person_summary is not None
            else calculate_unused_persons_metric()
        ),
        'tmdb_missing_year': _snapshot_show_metric(show_metric_summary, 'tmdb_missing_year', calculate_tmdb_missing_year_metric),
        'tmdb_missing_status': _snapshot_show_metric(show_metric_summary, 'tmdb_missing_status', calculate_tmdb_missing_status_metric),
        'tmdb_missing_plot': _snapshot_show_metric(show_metric_summary, 'tmdb_missing_plot', calculate_tmdb_missing_plot_metric),
        'tmdb_missing_durations': _snapshot_show_metric(show_metric_summary, 'tmdb_missing_durations', calculate_tmdb_missing_durations_metric),
        'tmdb_no_genres': _snapshot_show_metric(show_metric_summary, 'tmdb_no_genres', calculate_tmdb_no_genres_metric),
        'tmdb_no_countries': _snapshot_show_metric(show_metric_summary, 'tmdb_no_countries', calculate_tmdb_no_countries_metric),
    }


def _snapshot_show_metric(summary_rows, metric_key, fallback, exclude_unreleased=False):
    if summary_rows is None:
        return fallback()

    counts = defaultdict(int)
    current_year = timezone.localdate().year
    for key, show_type, show_year, status, value in summary_rows:
        if key != metric_key:
            continue
        if exclude_unreleased and (
            status in UNRELEASED_IMDB_STATUSES
            or status.casefold() == 'announced'
            or (show_year is not None and show_year > current_year)
        ):
            continue
        counts[show_type] += value

    return _aggregate_by_display_type(
        [
            {'type': show_type or None, 'total': count}
            for show_type, count in counts.items()
        ]
    )


def _profession_stats_from_summary(summary_data):
    stats = {'ru': [], 'en': []}
    known_counts = {
        'ru': summary_data['ru_known_count'],
        'en': summary_data['en_known_count'],
    }
    for language, role, value in summary_data['role_rows']:
        stats[language].append({'name': role, 'value': value})

    for language in ('ru', 'en'):
        stats[language].sort(key=lambda item: item['value'], reverse=True)
        unknown_count = max(0, summary_data['root_person_count'] - known_counts[language])
        if unknown_count:
            stats[language].append({'name': '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e', 'value': unknown_count})
    return stats['ru'], stats['en']


def _total_persons_by_show_type_from_summary(summary_data):
    stats = [
        {'show__type': show_type, 'total': value}
        for show_type, value in summary_data['show_type_rows']
    ]
    return _aggregate_by_display_type(stats, type_field='show__type', count_field='total')


def _unused_persons_from_summary(summary_data):
    unused_count = max(
        0,
        summary_data['root_person_count'] - summary_data['used_person_count'],
    )
    return [{'name': '\u0411\u0435\u0437 \u0440\u043e\u043b\u0435\u0439', 'value': unused_count}]


def get_global_metrics_history() -> dict:
    now = timezone.now()

    try:
        snapshots = _get_global_snapshot_periods(now)
    except ProgrammingError:
        return {}

    latest = snapshots.get('now')
    if not latest:
        return {}

    yesterday = snapshots.get('yesterday')
    week_ago = snapshots.get('week_ago')

    def _format_entry(entry, metric_key):
        data = entry.get('data', {}) if entry else {}
        if metric_key not in data:
            return {'data': [], 'timestamp': None}
        return {
            'data': data[metric_key],
            'timestamp': entry['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
        }

    result = {}
    for key in latest['data'].keys():
        result[key] = {
            'now': _format_entry(latest, key),
            'yesterday': _format_entry(yesterday, key),
            'week_ago': _format_entry(week_ago, key),
        }

    return result


def _get_global_snapshot_periods(now):
    """Load all three dashboard periods with one SQL round-trip on Postgres."""
    yesterday_cutoff = now - timedelta(days=1)
    week_cutoff = now - timedelta(days=7)

    if connection.vendor != 'postgresql':
        rows = {
            'now': SiteMetric.objects.filter(key='global_snapshot')
            .order_by('-created_at')
            .values('data', 'created_at')
            .first(),
            'yesterday': SiteMetric.objects.filter(
                key='global_snapshot', created_at__lte=yesterday_cutoff
            )
            .order_by('-created_at')
            .values('data', 'created_at')
            .first(),
            'week_ago': SiteMetric.objects.filter(
                key='global_snapshot', created_at__lte=week_cutoff
            )
            .order_by('-created_at')
            .values('data', 'created_at')
            .first(),
        }
        return rows

    table = connection.ops.quote_name(SiteMetric._meta.db_table)
    sql = f'''
        SELECT period, data, created_at
        FROM (
            (SELECT %s::text AS period, data, created_at
             FROM {table}
             WHERE key = %s
             ORDER BY created_at DESC
             LIMIT 1)
            UNION ALL
            (SELECT %s::text AS period, data, created_at
             FROM {table}
             WHERE key = %s AND created_at <= %s
             ORDER BY created_at DESC
             LIMIT 1)
            UNION ALL
            (SELECT %s::text AS period, data, created_at
             FROM {table}
             WHERE key = %s AND created_at <= %s
             ORDER BY created_at DESC
             LIMIT 1)
        ) AS selected_snapshots
    '''
    params = [
        'now', 'global_snapshot',
        'yesterday', 'global_snapshot', yesterday_cutoff,
        'week_ago', 'global_snapshot', week_cutoff,
    ]
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return {
            period: {
                'data': json.loads(data) if isinstance(data, str) else data,
                'created_at': created_at,
            }
            for period, data, created_at in cursor.fetchall()
        }


def get_missing_kp_list(show_type: str):
    return (
        Show.objects.filter(
            type=show_type,
            kinopoisk_url__gt='',
            ext_rating__kp__isnull=True,
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
            ext_rating__kp__isnull=True,
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
    if ShowCrew.objects.filter(canonical_person__isnull=True).exists():
        canonical_id = Coalesce('canonical_person_id', 'person__master_person_id', 'person_id')
        crew_rows = (
            ShowCrew.objects.filter(show__type=show_type)
            .annotate(canonical_id=canonical_id)
            .filter(canonical_id=OuterRef('pk'))
        )
    else:
        crew_rows = ShowCrew.objects.filter(
            show__type=show_type,
            canonical_person_id=OuterRef('pk'),
        )

    # Start from the ordered Person primary-key index and probe crew rows with
    # EXISTS. The old DISTINCT subquery scanned millions of crew rows to find
    # the first 51 IDs even though the detail page only needs one page.
    persons = (
        Person.objects.filter(Exists(crew_rows))
        .order_by('id')
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id')
    )
    return persons[:max_items] if max_items is not None else persons


def get_unused_persons_list():
    # Keep this as a correlated anti-join.  The previous ``id__in`` form
    # materialized a DISTINCT list of every crew member before PostgreSQL
    # could return the first page.  On the production-sized catalogue that
    # meant scanning 15M+ ShowCrew rows for every concurrent detail request.
    if ShowCrew.objects.filter(canonical_person__isnull=True).exists():
        used_persons = ShowCrew.objects.annotate(
            canonical_id=_canonical_person_id_expression()
        ).filter(canonical_id=OuterRef('pk'))
    else:
        # The canonical-person index makes this branch an indexed EXISTS
        # lookup per root person and avoids joining the full Person table.
        used_persons = ShowCrew.objects.filter(canonical_person_id=OuterRef('pk'))

    return (
        Person.objects.filter(master_person__isnull=True)
        .filter(~Exists(used_persons))
        .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id')
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
        primary_field = 'profession'
        fallback_field = 'en_profession'
    else:
        primary_mapping = RAW_TO_NORMALIZED_EN
        ru_to_en = {ru: en for ru, en in PROFESSION_TRANS_MAP.items()}
        fallback_mapping = {
            raw: ru_to_en[value] for raw, value in RAW_TO_NORMALIZED_RU.items() if value in ru_to_en
        }
        primary_field = 'en_profession'
        fallback_field = 'profession'

    unknown = '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e'
    if normalized == unknown:
        known_filter = Q(**{f'showcrew__{primary_field}__in': primary_mapping}) | Q(
            **{f'showcrew__{fallback_field}__in': fallback_mapping}
        )
        return (
            Person.objects.filter(master_person__isnull=True)
            .exclude(known_filter)
            .values('id', 'name', 'en_name', 'tmdb_photo_url', 'kp_photo_url', 'tmdb_id')
        )

    role_case = Case(
        *[
            When(**{primary_field: raw}, then=Value(value))
            for raw, value in primary_mapping.items()
        ],
        *[
            When(**{fallback_field: raw}, then=Value(value))
            for raw, value in fallback_mapping.items()
        ],
        output_field=CharField(),
    )
    primary_known = Q(**{f'{primary_field}__in': primary_mapping})
    target_primary = Q(
        **{
            f'{primary_field}__in': [
                raw for raw, value in primary_mapping.items() if value == normalized
            ]
        }
    )
    target_fallback = Q(
        **{
            f'{fallback_field}__in': [
                raw for raw, value in fallback_mapping.items() if value == normalized
            ]
        }
    )
    role_filter = target_primary | (~primary_known & target_fallback)
    person_ids = _canonical_person_ids(
        ShowCrew.objects.filter(role_filter).annotate(normalized_role=role_case),
        max_items=max_items,
    )
    return _person_values_queryset(person_ids)


def calculate_total_persons_by_show_type_metric():
    if ShowCrew.objects.filter(canonical_person__isnull=True).exists():
        # Preserve correctness for old/unbackfilled rows.  This is only a
        # compatibility path; production data is expected to use the indexed
        # canonical_person_id branch below after backfillcanonicalperson.
        stats = (
            ShowCrew.objects.filter(show__type__isnull=False)
            .exclude(show__type='')
            .annotate(canonical_id=_canonical_person_id_expression())
            .values('show__type')
            .annotate(total=Count('canonical_id', distinct=True))
            .order_by('-total')
        )
    else:
        # COUNT(DISTINCT) forced PostgreSQL to sort all 15M+ joined crew rows
        # serially. Grouping unique (type, person) pairs first allows a
        # parallel hash join/aggregate and avoids carrying duplicate credits
        # through a large serial sort.
        show_table = connection.ops.quote_name(Show._meta.db_table)
        crew_table = connection.ops.quote_name(ShowCrew._meta.db_table)
        # The 15M-row grouped aggregate sorts millions of rows per parallel
        # worker. Give the hash aggregate a larger budget to cut disk spills
        # and allow it a longer bound, scoped to this transaction only.
        with _heavy_metric_query(HEAVY_METRIC_AGGREGATE_WORK_MEM) as cursor:
            cursor.execute(
                f'''
                    SELECT unique_people.show_type, COUNT(*) AS total
                    FROM (
                        SELECT show_row.type AS show_type, crew.canonical_person_id
                        FROM {crew_table} AS crew
                        INNER JOIN {show_table} AS show_row ON crew.show_id = show_row.id
                        WHERE show_row.type IS NOT NULL AND show_row.type <> %s
                        GROUP BY show_row.type, crew.canonical_person_id
                    ) AS unique_people
                    GROUP BY unique_people.show_type
                    ORDER BY total DESC
                    ''',
                [''],
            )
            stats = [
                {'show__type': show_type, 'total': total}
                for show_type, total in cursor.fetchall()
            ]
    return _aggregate_by_display_type(stats, type_field='show__type', count_field='total')


def _canonical_person_id_expression():
    if ShowCrew.objects.filter(canonical_person__isnull=True).exists():
        return Coalesce('canonical_person_id', 'person__master_person_id', 'person_id')
    return F('canonical_person_id')


def calculate_persons_avatar_stats_metric(person_summary=None, photo_summary=None):
    has_tmdb = Q(tmdb_photo_url__isnull=False) & ~Q(tmdb_photo_url='')
    has_kp = Q(kp_photo_url__isnull=False) & ~Q(kp_photo_url='')
    tmdb_done = Q(is_photo_fetched=True)

    if photo_summary is not None:
        person_stats = {
            'has_tmdb': photo_summary['has_tmdb_photo'],
            'kp_only': photo_summary['kp_only'],
            'tmdb_none': photo_summary['tmdb_none'],
            'no_kp': photo_summary['no_kp'],
            'tmdb_wait': photo_summary['tmdb_wait'],
            'all_none': photo_summary['all_none'],
        }
        waiting_stats = {
            'kp_wait': photo_summary['kp_wait'],
            'all_none_wait': photo_summary['all_none_wait'],
        }
    else:
        person_stats = Person.objects.aggregate(
            has_tmdb=Count('id', filter=has_tmdb),
            kp_only=Count('id', filter=has_kp & ~has_tmdb),
            tmdb_none=Count('id', filter=tmdb_done & ~has_tmdb),
            no_kp=Count('id', filter=~has_kp),
            tmdb_wait=Count('id', filter=~(tmdb_done | has_tmdb)),
            all_none=Count('id', filter=tmdb_done & ~has_tmdb & ~has_kp),
        )

    if photo_summary is None:
        if person_summary is None:
            # Keep direct callers (including health diagnostics) fresh and isolated.
            kp_waiting_person_ids = (
                ShowCrew.objects.filter(
                    show__kinopoisk_url__isnull=False,
                    show__ext_rating__isnull=True,
                )
                .exclude(show__kinopoisk_url='')
                .exclude(show__kinopoisk_url__endswith='/film/0')
                .values_list('person_id', flat=True)
            )
            waiting_stats = Person.objects.filter(
                id__in=Subquery(kp_waiting_person_ids)
            ).aggregate(
                kp_wait=Count('id', filter=~has_kp),
                all_none_wait=Count('id', filter=tmdb_done & ~has_tmdb & ~has_kp),
            )
        else:
            # Keep direct callers fresh; only the global snapshot uses photo rollups.
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    WITH waiting_person_ids AS (
                        SELECT DISTINCT UNNEST(kp_waiting_person_ids) AS person_id
                        FROM app_personmetricsummary
                        WHERE cardinality(kp_waiting_person_ids) > 0
                    )
                    SELECT
                        COUNT(p.id) FILTER (
                            WHERE NOT (p.kp_photo_url IS NOT NULL AND p.kp_photo_url <> '')
                        ),
                        COUNT(p.id) FILTER (
                            WHERE p.is_photo_fetched
                              AND NOT (p.tmdb_photo_url IS NOT NULL AND p.tmdb_photo_url <> '')
                              AND NOT (p.kp_photo_url IS NOT NULL AND p.kp_photo_url <> '')
                        )
                    FROM waiting_person_ids AS waiting
                    JOIN app_person AS p ON p.id = waiting.person_id
                    '''
                )
                waiting_stats = dict(zip(('kp_wait', 'all_none_wait'), cursor.fetchone()))

    data = [
        {'name': 'Есть фото (TMDB)', 'value': person_stats['has_tmdb']},
        {'name': 'Есть фото (KP)', 'value': person_stats['kp_only']},
        {'name': 'TMDB не найдено', 'value': person_stats['tmdb_none']},
        {
            'name': 'KP не найдено',
            'value': person_stats['no_kp'] - (waiting_stats['kp_wait'] or 0),
        },
        {'name': 'В ожидании TMDB', 'value': person_stats['tmdb_wait']},
        {'name': 'В ожидании KP', 'value': waiting_stats['kp_wait'] or 0},
        {
            'name': 'Не найдено вообще',
            'value': person_stats['all_none'] - (waiting_stats['all_none_wait'] or 0),
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
    canonical_complete = not ShowCrew.objects.filter(canonical_person__isnull=True).exists()
    canonical_id = (
        F('canonical_person_id') if canonical_complete else _canonical_person_id_expression()
    )
    total_masters = Person.objects.filter(master_person__isnull=True).count()

    def calculate(
        primary_raw_to_normalized,
        fallback_raw_to_normalized,
        primary_field='profession',
        fallback_field='en_profession',
    ):
        if canonical_complete:
            if connection.vendor == 'postgresql':
                primary_values = list(primary_raw_to_normalized)
                fallback_values = list(fallback_raw_to_normalized)
                primary_column = connection.ops.quote_name(primary_field)
                fallback_column = connection.ops.quote_name(fallback_field)
                canonical_column = connection.ops.quote_name('canonical_person_id')
                crew_table = connection.ops.quote_name(ShowCrew._meta.db_table)

                def case_expression(column, mapping):
                    if not mapping:
                        return 'NULL'
                    cases = ' '.join('WHEN %s THEN %s' for _ in mapping)
                    return f'CASE {column} {cases} END'

                sql = f"""
                    WITH role_rows AS (
                        SELECT {canonical_column},
                            CASE
                                WHEN {primary_column} = ANY(%s) THEN
                                    {case_expression(primary_column, primary_raw_to_normalized)}
                                WHEN {fallback_column} = ANY(%s) THEN
                                    {case_expression(fallback_column, fallback_raw_to_normalized)}
                            END AS normalized
                        FROM {crew_table}
                        WHERE {primary_column} = ANY(%s)
                           OR {fallback_column} = ANY(%s)
                    )
                    , unique_role_people AS (
                        SELECT {canonical_column}, normalized,
                               GROUPING(normalized) AS is_total
                        FROM role_rows
                        GROUP BY GROUPING SETS (
                            (normalized, {canonical_column}),
                            ({canonical_column})
                        )
                    )
                    SELECT normalized, COUNT(*) AS value, is_total
                    FROM unique_role_people
                    GROUP BY normalized, is_total
                    ORDER BY is_total DESC, value DESC
                """
                params = [primary_values]
                params.extend(
                    value
                    for raw, normalized in primary_raw_to_normalized.items()
                    for value in (raw, normalized)
                )
                params.append(fallback_values)
                params.extend(
                    value
                    for raw, normalized in fallback_raw_to_normalized.items()
                    for value in (raw, normalized)
                )
                params.extend((primary_values, fallback_values))

                # PostgreSQL plans a multi-million-row parallel sort here;
                # scope the additional memory and timeout to this query.
                with _heavy_metric_query(HEAVY_METRIC_AGGREGATE_WORK_MEM) as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()

                result = [
                    {'name': normalized, 'value': value}
                    for normalized, value, is_total in rows
                    if not is_total and normalized
                ]
                known_count = next(
                    (value for _normalized, value, is_total in rows if is_total),
                    0,
                )
                unknown_count = max(0, total_masters - known_count)
                if unknown_count:
                    result.append({'name': 'Неизвестно', 'value': unknown_count})
                return result

            # Aggregate every normalized role in one CASE/GROUP BY query.
            # The previous implementation issued one DISTINCT count per role
            # (dozens of scans of the 15M-row ShowCrew table for each language)
            # and was the direct cause of the production soft timeout.
            all_primary_raw = list(primary_raw_to_normalized)
            primary_known = Q(**{f'{primary_field}__in': all_primary_raw})
            fallback_allowed = Q(**{f'{primary_field}__isnull': True}) | ~primary_known
            whens = [
                When(**{primary_field: raw}, then=Value(normalized))
                for raw, normalized in primary_raw_to_normalized.items()
            ]
            whens.extend(
                When(
                    Q(**{fallback_field: raw}) & fallback_allowed,
                    then=Value(normalized),
                )
                for raw, normalized in fallback_raw_to_normalized.items()
            )
            role_case = Case(*whens, output_field=CharField())
            known_filter = primary_known | Q(
                **{f'{fallback_field}__in': fallback_raw_to_normalized}
            )
            role_stats = (
                ShowCrew.objects.filter(known_filter)
                .annotate(normalized=role_case)
                .values('normalized')
                .annotate(value=Count('canonical_person_id', distinct=True))
                .order_by('-value')
            )
            result = [
                {'name': row['normalized'], 'value': row['value']}
                for row in role_stats
                if row['normalized']
            ]
            known_count = (
                ShowCrew.objects.filter(known_filter)
                .values('canonical_person_id')
                .distinct()
                .count()
            )
            unknown_count = max(0, total_masters - known_count)
            if unknown_count:
                result.append(
                    {'name': '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e', 'value': unknown_count}
                )
            return result

        whens = [
            When(**{primary_field: raw}, then=Value(normalized))
            for raw, normalized in primary_raw_to_normalized.items()
        ]
        whens.extend(
            When(**{fallback_field: raw}, then=Value(normalized))
            for raw, normalized in fallback_raw_to_normalized.items()
        )
        known_filter = Q(**{f'{primary_field}__in': primary_raw_to_normalized}) | Q(
            **{f'{fallback_field}__in': fallback_raw_to_normalized}
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
        if canonical_complete:
            # With canonical_person backfilled, derive the unknown bucket from
            # the same indexed ShowCrew population as the role aggregate.
            # The previous reverse Person join scanned the whole Person table
            # and timed out on the production catalogue.
            known_count = (
                ShowCrew.objects.filter(known_filter)
                .values('canonical_person_id')
                .distinct()
                .count()
            )
            unknown_count = max(0, total_masters - known_count)
        else:
            unknown_count = (
                Person.objects.filter(master_person__isnull=True)
                .exclude(**{f'showcrew__{primary_field}__in': primary_raw_to_normalized})
                .exclude(**{f'showcrew__{fallback_field}__in': fallback_raw_to_normalized})
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
    return calculate(RAW_TO_NORMALIZED_RU, en_to_ru_raw), calculate(
        RAW_TO_NORMALIZED_EN,
        ru_to_en_raw,
        primary_field='en_profession',
        fallback_field='profession',
    )


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
        Show.objects.filter(kinopub_id__isnull=False, type__in=SERIES_TYPES, type=show_type)
        .filter(Q(status__isnull=True) | Q(status=''))
        .values('id', 'title', 'original_title')
    )


def calculate_duplicate_photo_urls_metric(photo_summary=None):
    if photo_summary is not None:
        data = [
            {'name': 'TMDB дубликаты', 'value': photo_summary['tmdb_duplicate_groups']},
            {'name': 'KP дубликаты', 'value': photo_summary['kp_duplicate_groups']},
        ]
        return sorted(data, key=lambda x: x['value'], reverse=True)

    tmdb_dupes = _count_duplicate_photo_groups('tmdb_photo_url')
    kp_dupes = _count_duplicate_photo_groups('kp_photo_url')

    data = [
        {'name': 'TMDB дубликаты', 'value': tmdb_dupes},
        {'name': 'KP дубликаты', 'value': kp_dupes},
    ]
    return sorted(data, key=lambda x: x['value'], reverse=True)


def _count_duplicate_photo_groups(field: str):
    """Count duplicate-photo groups with an unresolved person exactly.

    A candidate group is defined by the old GROUP BY query as: at least two
    root persons share a non-empty photo URL and at least one row has no
    TMDB identity.  Starting from unresolved rows and using a correlated
    EXISTS preserves that definition while avoiding a full grouping of every
    root person by a long text URL.
    """
    other_person = Person.objects.filter(
        master_person__isnull=True,
        **{field: OuterRef(field)},
    ).exclude(
        pk=OuterRef('pk')
    ).filter(
        **{f'{field}__gt': ''}
    )
    unresolved_persons = (
        Person.objects.filter(
            master_person__isnull=True,
            tmdb_id__isnull=True,
            **{f'{field}__gt': ''},
        )
        .annotate(has_other=Exists(other_person))
        .filter(has_other=True)
        .values(field)
        .distinct()
    )
    return unresolved_persons.count()


def _potential_duplicate_photo_groups(field: str):
    """Photo groups that have not already been disproved by TMDB identity.

    A unique TMDB person ID is authoritative. Two rows with different IDs may
    legitimately share an image, so they are not duplicate people. Only a
    group containing an unresolved row remains a review candidate.
    """
    if person_photo_metric_summary_ready():
        refresh_dirty_person_photo_groups()
        source = 'tmdb' if field == 'tmdb_photo_url' else 'kp'
        return (
            PersonPhotoGroup.objects.filter(source=source)
            .annotate(
                **{
                    field: F('photo_url'),
                    'cnt': F('root_count'),
                    'tmdb_id_count': F('root_count') - F('unresolved_count'),
                }
            )
            .values(field, 'cnt', 'tmdb_id_count')
        )

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
    # v4 caps the initial member preview and lazily pages large groups.
    cache_key = f'metrics:duplicate_photo_urls:v4:{version}:{field}:{offset}:{limit}'
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
    grouped_persons = defaultdict(list)
    for row in _load_duplicate_photo_group_members(
        field,
        urls,
        after_id=None,
        limit=DUPLICATE_PHOTO_MEMBER_PAGE_SIZE + 1,
    ):
        grouped_persons[row['photo_url']].append(row['person'])

    results = []
    for url in urls:
        fetched_persons = grouped_persons[url]
        persons_has_more = len(fetched_persons) > DUPLICATE_PHOTO_MEMBER_PAGE_SIZE
        persons_list = fetched_persons[:DUPLICATE_PHOTO_MEMBER_PAGE_SIZE]
        persons_complete = not persons_has_more

        kp_status = None
        if persons_complete and field == 'tmdb_photo_url':
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
        if persons_complete and field == 'kp_photo_url':
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
                'photo_url': url,
                'persons_total': url_counts[url],
                'persons_has_more': persons_has_more,
                'persons_after_id': persons_list[-1]['id'] if persons_has_more else None,
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


def _load_duplicate_photo_group_members(field, urls, after_id, limit):
    """Fetch a bounded, ID-ordered preview for each requested photo URL."""
    if not urls or limit <= 0:
        return []

    person_table = connection.ops.quote_name(Person._meta.db_table)
    photo_column = connection.ops.quote_name(field)
    after_filter = 'AND person.id > %s' if after_id is not None else ''
    params = [urls]
    if after_id is not None:
        params.append(after_id)
    params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            SELECT requested.photo_url,
                   member.id,
                   member.name,
                   member.en_name,
                   member.tmdb_photo_url,
                   member.kp_photo_url,
                   member.tmdb_id,
                   member.kinopoisk_person_id
            FROM UNNEST(%s::text[]) WITH ORDINALITY AS requested(photo_url, ordinal)
            LEFT JOIN LATERAL (
                SELECT person.id,
                       person.name,
                       person.en_name,
                       person.tmdb_photo_url,
                       person.kp_photo_url,
                       person.tmdb_id,
                       person.kinopoisk_person_id
                FROM {person_table} AS person
                WHERE person.master_person_id IS NULL
                  AND person.{photo_column} = requested.photo_url
                  {after_filter}
                ORDER BY person.id
                LIMIT %s
            ) AS member ON TRUE
            ORDER BY requested.ordinal, member.id
            ''',
            params,
        )
        rows = cursor.fetchall()

    result = []
    for photo_url, person_id, name, en_name, tmdb_url, kp_url, tmdb_id, kp_id in rows:
        if person_id is None:
            continue
        result.append(
            {
                'photo_url': photo_url,
                'person': {
                    'id': person_id,
                    'name': name,
                    'en_name': en_name,
                    'tmdb_photo_url': get_proxied_image_url(tmdb_url),
                    'kp_photo_url': get_proxied_image_url(kp_url),
                    'tmdb_id': tmdb_id,
                    'kinopoisk_person_id': kp_id,
                },
            }
        )
    return result


def get_duplicate_photo_url_group_members(source_type, photo_url, after_id=None, limit=50):
    """Return one bounded page of members for a single duplicate-photo group."""
    source = 'tmdb' if 'TMDB' in source_type else 'kp'
    field = 'tmdb_photo_url' if source == 'tmdb' else 'kp_photo_url'
    group = PersonPhotoGroup.objects.filter(
        source=source,
        photo_url=photo_url,
        root_count__gt=1,
        unresolved_count__gt=0,
    ).values('root_count').first()
    if not group:
        return None

    rows = _load_duplicate_photo_group_members(
        field,
        [photo_url],
        after_id=after_id,
        limit=limit + 1,
    )
    people = [row['person'] for row in rows]
    has_more = len(people) > limit
    people = people[:limit]
    return {
        'items': people,
        'total': group['root_count'],
        'has_more': has_more,
        'next_after_id': people[-1]['id'] if has_more and people else None,
    }


def queue_duplicate_photo_urls_warmup():
    """Queue duplicate pages before a user opens the corresponding modal."""
    version = cache.get(DUPLICATE_PHOTO_CACHE_VERSION_KEY, 1)
    cache_keys = (
        f'metrics:duplicate_photo_urls:v3:{version}:kp_photo_url:0:50',
        f'metrics:duplicate_photo_urls:v3:{version}:tmdb_photo_url:0:50',
    )
    if any(cache.get(cache_key) is None for cache_key in cache_keys):
        queue_metric_caches_warmup()


def person_detail_cache_key(key, value, offset, limit):
    version = cache.get(PERSON_DETAIL_CACHE_VERSION_KEY, 1)
    digest = sha1(f'{key}|{value}|{offset}|{limit}'.encode()).hexdigest()
    return f'metrics:person_detail:{version}:{digest}'


def queue_person_detail_warmup():
    queue_metric_caches_warmup()


def queue_metric_caches_warmup():
    """Queue one job for all metrics caches instead of two competing jobs."""
    if cache.add('metrics:all:warmup_lock', True, timeout=900):
        celery_app.send_task('app.tasks.warm_metrics_caches_task', queue='metrics')


def warm_duplicate_photo_urls_cache():
    """Populate the first modal page off the request path."""
    for source_type in ('TMDB', 'KP'):
        get_duplicate_photo_urls_page(source_type, offset=0, limit=50)


def invalidate_duplicate_photo_urls_cache():
    version = cache.get(DUPLICATE_PHOTO_CACHE_VERSION_KEY, 1)
    cache.set(DUPLICATE_PHOTO_CACHE_VERSION_KEY, int(version) + 1, timeout=None)
    cache.delete('metrics:duplicate_photo_urls:warmup_lock')
    cache.delete('metrics:all:warmup_lock')


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
        {'name': 'Неканонические', 'value': unmapped_count},
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
    if ShowCrew.objects.filter(canonical_person__isnull=True).exists():
        # Keep compatibility with rows that have not been backfilled yet.
        used_persons = ShowCrew.objects.annotate(
            canonical_id=_canonical_person_id_expression()
        ).filter(canonical_id=OuterRef('pk'))
    else:
        # The canonical-person index supports an indexed anti-join and avoids
        # a full DISTINCT pass across all 15M+ ShowCrew rows.
        used_persons = ShowCrew.objects.filter(canonical_person_id=OuterRef('pk'))

    with metrics_statement_timeout():
        unused_count = (
            Person.objects.filter(master_person__isnull=True)
            .annotate(has_crew=Exists(used_persons))
            .filter(has_crew=False)
            .count()
        )
    return [{'name': 'Без ролей', 'value': unused_count}]
