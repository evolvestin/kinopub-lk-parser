"""Incremental per-show facts and compact global catalog metric counts."""

import logging
import time

from django.db import connection, transaction
from django.utils import timezone

from app.models import (
    Show,
    ShowMetricAggregate,
    ShowMetricSummary,
    ShowMetricSummaryDirty,
    ShowMetricSummaryState,
)
from shared.constants import SERIES_TYPES

SUMMARY_TABLE = ShowMetricSummary._meta.db_table
DIRTY_TABLE = ShowMetricSummaryDirty._meta.db_table
AGGREGATE_TABLE = ShowMetricAggregate._meta.db_table
STATE_TABLE = ShowMetricSummaryState._meta.db_table
SHOW_TABLE = Show._meta.db_table
RATING_TABLE = 'app_externalrating'
DURATION_TABLE = 'app_showduration'
GENRE_TABLE = Show.genres.through._meta.db_table
COUNTRY_TABLE = Show.countries.through._meta.db_table


def show_metric_summary_ready():
    return ShowMetricSummaryState.objects.filter(id=1, ready=True).exists()


def _metric_case(flag, condition):
    return f"CASE WHEN {condition} THEN '{flag}' END"


def _summary_select_sql(where_clause):
    show_table = connection.ops.quote_name(SHOW_TABLE)
    rating_table = connection.ops.quote_name(RATING_TABLE)
    duration_table = connection.ops.quote_name(DURATION_TABLE)
    genre_table = connection.ops.quote_name(GENRE_TABLE)
    country_table = connection.ops.quote_name(COUNTRY_TABLE)

    kp_url = "s.kinopoisk_url IS NOT NULL AND s.kinopoisk_url <> '' " \
        "AND RIGHT(s.kinopoisk_url, 7) <> '/film/0'"
    tmdb_only = 's.kinopub_id IS NULL AND s.tmdb_id IS NOT NULL'
    no_status = "(s.status IS NULL OR s.status = '')"
    no_plot = "(s.plot IS NULL OR s.plot = '')"
    no_imdb_id = "(s.imdb_id IS NULL OR s.imdb_id = '')"
    # ExternalRating.show is one-to-one. Join it once so PostgreSQL does not
    # repeat the same full table scan for each rating flag during backfill.
    has_kp_rating = 'er.kp IS NOT NULL'
    no_kp_rating = 'er.kp IS NULL'
    duration_exists = f'EXISTS (SELECT 1 FROM {duration_table} d WHERE d.show_id = s.id)'
    genre_exists = f'EXISTS (SELECT 1 FROM {genre_table} sg WHERE sg.show_id = s.id)'
    country_exists = f'EXISTS (SELECT 1 FROM {country_table} sc WHERE sc.show_id = s.id)'
    series_filter = 's.type = ANY(%s)'
    cases = [
        _metric_case('total_shows', 'TRUE'),
        _metric_case('has_kp', has_kp_rating),
        _metric_case('has_imdb', 's.imdb_rating IS NOT NULL'),
        _metric_case('missing_kp', f'{kp_url} AND s.kinopoisk_rating_available AND {no_kp_rating}'),
        _metric_case(
            'kp_unrated',
            f'{kp_url} AND NOT s.kinopoisk_rating_available '
            f'AND s.poiskkino_updated_at IS NOT NULL AND {no_kp_rating}',
        ),
        _metric_case(
            'missing_imdb_candidate',
            "s.imdb_url IS NOT NULL AND s.imdb_url <> '' AND s.imdb_rating IS NULL "
            'AND s.imdb_rating_available',
        ),
        _metric_case(
            'imdb_unrated_candidate',
            "s.imdb_url IS NOT NULL AND s.imdb_url <> '' AND s.imdb_rating IS NULL "
            'AND NOT s.imdb_rating_available',
        ),
        _metric_case('missing_imdb_id', f's.kinopub_id IS NOT NULL AND {no_imdb_id}'),
        _metric_case('tmdb_only_shows', tmdb_only),
        _metric_case('missing_tmdb_id', 's.kinopub_id IS NOT NULL AND s.tmdb_id IS NULL'),
        _metric_case(
            'tmdb_no_kp',
            "s.tmdb_id IS NOT NULL AND (s.kinopoisk_url IS NULL OR s.kinopoisk_url = '')",
        ),
        _metric_case('missing_year', 's.kinopub_id IS NOT NULL AND s.year IS NULL'),
        _metric_case('missing_status', f's.kinopub_id IS NOT NULL AND {series_filter} AND {no_status}'),
        _metric_case('missing_plot', f's.kinopub_id IS NOT NULL AND {no_plot}'),
        _metric_case('missing_durations', f's.kinopub_id IS NOT NULL AND NOT {duration_exists}'),
        _metric_case('no_genres', f's.kinopub_id IS NOT NULL AND NOT {genre_exists}'),
        _metric_case('no_countries', f's.kinopub_id IS NOT NULL AND NOT {country_exists}'),
        _metric_case('tmdb_missing_year', f'{tmdb_only} AND s.year IS NULL'),
        _metric_case('tmdb_missing_status', f'{tmdb_only} AND {series_filter} AND {no_status}'),
        _metric_case('tmdb_missing_plot', f'{tmdb_only} AND {no_plot}'),
        _metric_case('tmdb_missing_durations', f'{tmdb_only} AND NOT {duration_exists}'),
        _metric_case('tmdb_no_genres', f'{tmdb_only} AND NOT {genre_exists}'),
        _metric_case('tmdb_no_countries', f'{tmdb_only} AND NOT {country_exists}'),
    ]
    sql = f'''
        SELECT
            s.id,
            COALESCE(s.type, ''),
            s.year,
            COALESCE(s.status, ''),
            ARRAY_REMOVE(ARRAY[{', '.join(cases)}]::text[], NULL)
        FROM {show_table} s
        LEFT JOIN {rating_table} er ON er.show_id = s.id
        WHERE {where_clause}
    '''
    return sql, [list(SERIES_TYPES), list(SERIES_TYPES)]


def _insert_summary(cursor, where_clause, where_params):
    sql, params = _summary_select_sql(where_clause)
    cursor.execute(
        f'''
        INSERT INTO {SUMMARY_TABLE} (show_id, show_type, show_year, status, metrics)
        {sql}
        ON CONFLICT (show_id) DO UPDATE SET
            show_type = EXCLUDED.show_type,
            show_year = EXCLUDED.show_year,
            status = EXCLUDED.status,
            metrics = EXCLUDED.metrics
        ''',
        [*params, *where_params],
    )


def _adjust_aggregate(show_ids, multiplier, cursor):
    if not show_ids:
        return
    cursor.execute(
        f'''
        INSERT INTO {AGGREGATE_TABLE}
            (metric_key, show_type, show_year, status, value)
        SELECT metric_key, show_type, show_year, status, SUM(delta)::bigint
        FROM (
            SELECT UNNEST(metrics) AS metric_key,
                   show_type, show_year, status, (%s)::bigint AS delta
            FROM {SUMMARY_TABLE}
            WHERE show_id = ANY(%s)
        ) changes
        GROUP BY metric_key, show_type, show_year, status
        ON CONFLICT (metric_key, show_type, show_year, status) DO UPDATE
        SET value = {AGGREGATE_TABLE}.value + EXCLUDED.value
        ''',
        [multiplier, show_ids],
    )
    cursor.execute(f'DELETE FROM {AGGREGATE_TABLE} WHERE value <= 0')


def refresh_dirty_show_metric_summaries(batch_size=20000):
    if not show_metric_summary_ready():
        return 0

    started_at = time.monotonic()
    processed = 0
    while True:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f'''
                    DELETE FROM {DIRTY_TABLE}
                    WHERE show_id IN (
                        SELECT show_id FROM {DIRTY_TABLE}
                        ORDER BY show_id LIMIT %s
                    )
                    RETURNING show_id
                    ''',
                    [batch_size],
                )
                show_ids = [row[0] for row in cursor.fetchall()]
                if not show_ids:
                    break
                _adjust_aggregate(show_ids, -1, cursor)
                cursor.execute(
                    f'DELETE FROM {SUMMARY_TABLE} WHERE show_id = ANY(%s)',
                    [show_ids],
                )
                _insert_summary(cursor, 's.id = ANY(%s)', [show_ids])
                _adjust_aggregate(show_ids, 1, cursor)
                processed += len(show_ids)
    logging.info(
        'Metrics dirty refresh kind=show rows=%s seconds=%.3f.',
        processed,
        time.monotonic() - started_at,
    )
    return processed


def _rebuild_show_metric_aggregate():
    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE TABLE {AGGREGATE_TABLE}')
        cursor.execute(
            f'''
            INSERT INTO {AGGREGATE_TABLE}
                (metric_key, show_type, show_year, status, value)
            SELECT metric_key, show_type, show_year, status, COUNT(*)::bigint
            FROM (
                SELECT UNNEST(metrics) AS metric_key, show_type, show_year, status
                FROM {SUMMARY_TABLE}
            ) grouped
            GROUP BY metric_key, show_type, show_year, status
            '''
        )


def rebuild_show_metric_summaries(batch_size=50000, progress_callback=None):
    state, _ = ShowMetricSummaryState.objects.get_or_create(id=1)
    state.ready = False
    state.rebuilt_at = None
    state.save(update_fields=['ready', 'rebuilt_at'])

    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE TABLE {SUMMARY_TABLE}, {DIRTY_TABLE}, {AGGREGATE_TABLE}')
        cursor.execute(f'SELECT MIN(id), MAX(id) FROM {SHOW_TABLE}')
        min_id, max_id = cursor.fetchone()

    batches = 0
    lower_id = (min_id or 0) - 1
    while min_id is not None and lower_id < max_id:
        with connection.cursor() as cursor:
            cursor.execute("SET statement_timeout = '10min'")
            cursor.execute("SET work_mem = '256MB'")
            cursor.execute(
                f'SELECT id FROM {SHOW_TABLE} WHERE id > %s ORDER BY id LIMIT 1 OFFSET %s',
                [lower_id, batch_size - 1],
            )
            boundary = cursor.fetchone()
        upper_id = boundary[0] if boundary else max_id
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '10min'")
                cursor.execute("SET LOCAL work_mem = '256MB'")
                cursor.execute('SET LOCAL jit = off')
                _insert_summary(cursor, 's.id > %s AND s.id <= %s', [lower_id, upper_id])
        batches += 1
        if progress_callback:
            progress_callback(upper_id, max_id, batches)
        lower_id = upper_id

    refresh_dirty_show_metric_summaries()
    _rebuild_show_metric_aggregate()
    state.ready = True
    state.rebuilt_at = timezone.now()
    state.save(update_fields=['ready', 'rebuilt_at'])
    return batches


def get_show_metric_aggregate_data():
    if not show_metric_summary_ready():
        return None
    refresh_dirty_show_metric_summaries()
    return list(
        ShowMetricAggregate.objects.values_list(
            'metric_key', 'show_type', 'show_year', 'status', 'value'
        )
    )
