"""Incrementally maintained, compact inputs for global person metrics."""

from django.db import connection, transaction
from django.utils import timezone

from app.models import (
    PersonMetricAggregate,
    PersonMetricSummary,
    PersonMetricSummaryDirty,
    PersonMetricSummaryState,
    PersonKpWaitingSummary,
    PersonPhotoMetricDirty,
    PersonPhotoMetricState,
    ShowCrew,
)
from shared.constants import RAW_TO_NORMALIZED_EN, RAW_TO_NORMALIZED_RU, PROFESSION_TRANS_MAP

SUMMARY_TABLE = PersonMetricSummary._meta.db_table
DIRTY_TABLE = PersonMetricSummaryDirty._meta.db_table
STATE_TABLE = PersonMetricSummaryState._meta.db_table
WAITING_TABLE = PersonKpWaitingSummary._meta.db_table
PHOTO_DIRTY_TABLE = PersonPhotoMetricDirty._meta.db_table
PHOTO_STATE_TABLE = PersonPhotoMetricState._meta.db_table
AGGREGATE_TABLE = PersonMetricAggregate._meta.db_table
CREW_TABLE = ShowCrew._meta.db_table


def person_metric_summary_ready():
    return PersonMetricSummaryState.objects.filter(id=1, ready=True).exists()


def _case_expression(column, mapping):
    if not mapping:
        return 'NULL', []
    pairs = ' '.join('WHEN %s THEN %s' for _ in mapping)
    params = [value for raw, normalized in mapping.items() for value in (raw, normalized)]
    return f'CASE {column} {pairs} END', params


def _normalized_role_expression(primary_column, primary_mapping, fallback_column, fallback_mapping):
    primary_case, primary_case_params = _case_expression(primary_column, primary_mapping)
    fallback_case, fallback_case_params = _case_expression(fallback_column, fallback_mapping)
    sql = f'''CASE
        WHEN {primary_column} = ANY(%s) THEN {primary_case}
        WHEN {fallback_column} = ANY(%s) THEN {fallback_case}
    END'''
    params = [
        list(primary_mapping),
        *primary_case_params,
        list(fallback_mapping),
        *fallback_case_params,
    ]
    return sql, params


def _role_expressions():
    en_to_ru = {en: ru for ru, en in PROFESSION_TRANS_MAP.items()}
    ru_to_en_raw = {
        raw: PROFESSION_TRANS_MAP[normalized]
        for raw, normalized in RAW_TO_NORMALIZED_RU.items()
        if normalized in PROFESSION_TRANS_MAP
    }
    en_to_ru_raw = {
        raw: en_to_ru[normalized]
        for raw, normalized in RAW_TO_NORMALIZED_EN.items()
        if normalized in en_to_ru
    }
    ru_expression, ru_params = _normalized_role_expression(
        'sc.profession', RAW_TO_NORMALIZED_RU, 'sc.en_profession', en_to_ru_raw
    )
    en_expression, en_params = _normalized_role_expression(
        'sc.en_profession', RAW_TO_NORMALIZED_EN, 'sc.profession', ru_to_en_raw
    )
    return ru_expression, ru_params, en_expression, en_params


def _insert_summary_sql(where_clause, upsert=False):
    ru_expression, ru_params, en_expression, en_params = _role_expressions()
    conflict_sql = ''
    if upsert:
        conflict_sql = f'''
            ON CONFLICT (canonical_person_id) DO UPDATE SET
                show_types = ARRAY(
                    SELECT DISTINCT value
                    FROM UNNEST({SUMMARY_TABLE}.show_types || EXCLUDED.show_types) AS item(value)
                    ORDER BY value
                ),
                ru_roles = ARRAY(
                    SELECT DISTINCT value
                    FROM UNNEST({SUMMARY_TABLE}.ru_roles || EXCLUDED.ru_roles) AS item(value)
                    ORDER BY value
                ),
                en_roles = ARRAY(
                    SELECT DISTINCT value
                    FROM UNNEST({SUMMARY_TABLE}.en_roles || EXCLUDED.en_roles) AS item(value)
                    ORDER BY value
                ),
                kp_waiting_person_ids = ARRAY(
                    SELECT DISTINCT value
                    FROM UNNEST(
                        {SUMMARY_TABLE}.kp_waiting_person_ids || EXCLUDED.kp_waiting_person_ids
                    ) AS item(value)
                    ORDER BY value
                )
        '''
    sql = f'''
        INSERT INTO {SUMMARY_TABLE}
            (canonical_person_id, show_types, ru_roles, en_roles, kp_waiting_person_ids)
        SELECT
            source.canonical_person_id,
            COALESCE(
                ARRAY_AGG(DISTINCT source.show_type)
                    FILTER (WHERE source.show_type IS NOT NULL AND source.show_type <> ''),
                ARRAY[]::text[]
            ),
            COALESCE(
                ARRAY_AGG(DISTINCT source.ru_role) FILTER (WHERE source.ru_role IS NOT NULL),
                ARRAY[]::text[]
            ),
            COALESCE(
                ARRAY_AGG(DISTINCT source.en_role) FILTER (WHERE source.en_role IS NOT NULL),
                ARRAY[]::text[]
            ),
            COALESCE(
                ARRAY_AGG(DISTINCT source.person_id)
                    FILTER (WHERE source.kp_waiting),
                ARRAY[]::bigint[]
            )
        FROM (
            SELECT
                sc.canonical_person_id,
                sc.person_id,
                s.type::text AS show_type,
                {ru_expression} AS ru_role,
                {en_expression} AS en_role,
                (
                    s.kinopoisk_url IS NOT NULL
                    AND s.kinopoisk_url <> ''
                    AND RIGHT(s.kinopoisk_url, 7) <> '/film/0'
                    AND NOT EXISTS (
                        SELECT 1 FROM app_externalrating AS er WHERE er.show_id = s.id
                    )
                ) AS kp_waiting
            FROM {CREW_TABLE} AS sc
            JOIN app_show AS s ON s.id = sc.show_id
            WHERE {where_clause}
        ) AS source
        GROUP BY source.canonical_person_id
        {conflict_sql}
    '''
    return sql, [*ru_params, *en_params]


def refresh_dirty_person_metric_summaries(batch_size=5000, force=False):
    """Rebuild only canonical people touched since the last summary refresh."""
    if not force and not person_metric_summary_ready():
        return 0

    processed = 0
    while True:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f'''
                    DELETE FROM {DIRTY_TABLE}
                    WHERE canonical_person_id IN (
                        SELECT canonical_person_id
                        FROM {DIRTY_TABLE}
                        ORDER BY canonical_person_id
                        LIMIT %s
                    )
                    RETURNING canonical_person_id
                    ''',
                    [batch_size],
                )
                dirty_ids = [row[0] for row in cursor.fetchall()]
                if not dirty_ids:
                    break

                cursor.execute(
                    '''
                    SELECT canonical_person_id
                    FROM unnest(%s::bigint[]) AS dirty(canonical_person_id)
                    UNION
                    SELECT DISTINCT COALESCE(master_person_id, id)
                    FROM app_person
                    WHERE id = ANY(%s)
                    ''',
                    [dirty_ids, dirty_ids],
                )
                canonical_ids = list({row[0] for row in cursor.fetchall()})
                if canonical_ids:
                    cursor.execute(
                        f'''
                        SELECT DISTINCT UNNEST(kp_waiting_person_ids)
                        FROM {SUMMARY_TABLE}
                        WHERE canonical_person_id = ANY(%s)
                          AND cardinality(kp_waiting_person_ids) > 0
                        ''',
                        [canonical_ids],
                    )
                    old_waiting_ids = [row[0] for row in cursor.fetchall()]
                    if old_waiting_ids:
                        cursor.execute(
                            f'DELETE FROM {WAITING_TABLE} WHERE person_id = ANY(%s)',
                            [old_waiting_ids],
                        )
                        cursor.execute(
                            f'''
                            INSERT INTO {PHOTO_DIRTY_TABLE} (person_id)
                            SELECT UNNEST(%s::bigint[])
                            ON CONFLICT DO NOTHING
                            ''',
                            [old_waiting_ids],
                        )
                    _adjust_person_metric_rollups(canonical_ids, -1, cursor)
                    cursor.execute(
                        f'DELETE FROM {SUMMARY_TABLE} WHERE canonical_person_id = ANY(%s)',
                        [canonical_ids],
                    )
                    sql, params = _insert_summary_sql(
                        'sc.canonical_person_id = ANY(%s)', upsert=True
                    )
                    cursor.execute(sql, [*params, canonical_ids])
                    cursor.execute(
                        f'''
                        SELECT DISTINCT UNNEST(kp_waiting_person_ids)
                        FROM {SUMMARY_TABLE}
                        WHERE canonical_person_id = ANY(%s)
                          AND cardinality(kp_waiting_person_ids) > 0
                        ''',
                        [canonical_ids],
                    )
                    new_waiting_ids = [row[0] for row in cursor.fetchall()]
                    if new_waiting_ids:
                        cursor.execute(
                            f'''
                            INSERT INTO {WAITING_TABLE} (person_id)
                            SELECT UNNEST(%s::bigint[])
                            ON CONFLICT DO NOTHING
                            ''',
                            [new_waiting_ids],
                        )
                        cursor.execute(
                            f'''
                            INSERT INTO {PHOTO_DIRTY_TABLE} (person_id)
                            SELECT UNNEST(%s::bigint[])
                            ON CONFLICT DO NOTHING
                            ''',
                            [new_waiting_ids],
                        )
                    _adjust_person_metric_rollups(canonical_ids, 1, cursor)
                processed += len(dirty_ids)
    return processed


def _adjust_person_metric_rollups(canonical_ids, multiplier, cursor):
    """Apply a changed person's old/new arrays to compact grouped counters."""
    if not canonical_ids:
        return

    cursor.execute(
        f'''
        INSERT INTO {AGGREGATE_TABLE} (kind, language, name, value)
        SELECT kind, language, name, SUM(value)::bigint
        FROM (
            SELECT 'ru_role'::varchar AS kind, 'ru'::varchar AS language,
                   role AS name, (%s)::bigint AS value
            FROM {SUMMARY_TABLE} s
            CROSS JOIN LATERAL UNNEST(s.ru_roles) AS role
            WHERE s.canonical_person_id = ANY(%s)
            UNION ALL
            SELECT 'en_role'::varchar, 'en'::varchar, role,
                   (%s)::bigint
            FROM {SUMMARY_TABLE} s
            CROSS JOIN LATERAL UNNEST(s.en_roles) AS role
            WHERE s.canonical_person_id = ANY(%s)
            UNION ALL
            SELECT 'show_type'::varchar, ''::varchar, show_type,
                   (%s)::bigint
            FROM {SUMMARY_TABLE} s
            CROSS JOIN LATERAL UNNEST(s.show_types) AS show_type
            WHERE s.canonical_person_id = ANY(%s)
        ) deltas
        GROUP BY kind, language, name
        ON CONFLICT (kind, language, name) DO UPDATE
        SET value = {AGGREGATE_TABLE}.value + EXCLUDED.value
        ''',
        [multiplier, canonical_ids, multiplier, canonical_ids, multiplier, canonical_ids],
    )
    cursor.execute(f'DELETE FROM {AGGREGATE_TABLE} WHERE value <= 0')

    cursor.execute(
        f'''
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE cardinality(ru_roles) > 0),
            COUNT(*) FILTER (WHERE cardinality(en_roles) > 0)
        FROM {SUMMARY_TABLE}
        WHERE canonical_person_id = ANY(%s)
        ''',
        [canonical_ids],
    )
    used_count, ru_known_count, en_known_count = cursor.fetchone()
    cursor.execute(
        f'''
        UPDATE {STATE_TABLE}
        SET used_person_count = GREATEST(0, used_person_count + %s),
            ru_known_person_count = GREATEST(0, ru_known_person_count + %s),
            en_known_person_count = GREATEST(0, en_known_person_count + %s)
        WHERE id = 1
        ''',
        [multiplier * used_count, multiplier * ru_known_count, multiplier * en_known_count],
    )


def rebuild_person_metric_summaries(batch_size=50000, progress_callback=None):
    """One-time indexed backfill; subsequent writes are handled incrementally."""
    state, _ = PersonMetricSummaryState.objects.get_or_create(id=1)
    state.ready = False
    state.rebuilt_at = None
    state.save(update_fields=['ready', 'rebuilt_at'])
    PersonPhotoMetricState.objects.filter(id=1).update(ready=False, rebuilt_at=None)

    with connection.cursor() as cursor:
        cursor.execute(
            f'TRUNCATE TABLE {SUMMARY_TABLE}, {DIRTY_TABLE}, {AGGREGATE_TABLE}'
        )
        cursor.execute(f'SELECT MIN(id), MAX(id) FROM {CREW_TABLE}')
        min_id, max_id = cursor.fetchone()
        cursor.execute(
            'SELECT EXISTS (SELECT 1 FROM app_showcrew WHERE canonical_person_id IS NULL)'
        )
        has_unbackfilled_rows = cursor.fetchone()[0]

    if has_unbackfilled_rows:
        raise RuntimeError(
            'Cannot build person metric summaries while ShowCrew canonical_person_id is NULL. '
            'Run backfillcanonicalperson first.'
        )

    processed_ranges = 0
    if min_id is not None and max_id is not None:
        lower_id = min_id - 1
        while lower_id < max_id:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'''
                    SELECT id
                    FROM {CREW_TABLE}
                    WHERE id > %s
                    ORDER BY id
                    LIMIT 1 OFFSET %s
                    ''',
                    [lower_id, batch_size - 1],
                )
                boundary = cursor.fetchone()
            upper_id = boundary[0] if boundary else max_id
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '10min'")
                    sql, params = _insert_summary_sql(
                        'sc.id > %s AND sc.id <= %s',
                        upsert=True,
                    )
                    cursor.execute(sql, [*params, lower_id, upper_id])
            processed_ranges += 1
            if progress_callback:
                progress_callback(upper_id, max_id, processed_ranges)
            lower_id = upper_id

    refresh_dirty_person_metric_summaries(force=True)
    _rebuild_person_metric_rollups()
    state.ready = True
    state.rebuilt_at = timezone.now()
    state.save(update_fields=['ready', 'rebuilt_at'])
    return processed_ranges


def _rebuild_person_metric_rollups():
    """Build the tiny snapshot-facing rollups once after the summary backfill."""
    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE TABLE {WAITING_TABLE}')
        cursor.execute(
            f'''
            INSERT INTO {WAITING_TABLE} (person_id)
            SELECT DISTINCT UNNEST(kp_waiting_person_ids)
            FROM {SUMMARY_TABLE}
            WHERE cardinality(kp_waiting_person_ids) > 0
            ON CONFLICT DO NOTHING
            '''
        )
        cursor.execute(f'TRUNCATE TABLE {AGGREGATE_TABLE}')
        cursor.execute(
            f'''
            INSERT INTO {AGGREGATE_TABLE} (kind, language, name, value)
            SELECT kind, language, name, COUNT(*)::bigint
            FROM (
                SELECT 'ru_role'::varchar AS kind, 'ru'::varchar AS language,
                       role AS name, s.canonical_person_id
                FROM {SUMMARY_TABLE} s
                CROSS JOIN LATERAL UNNEST(s.ru_roles) AS role
                UNION ALL
                SELECT 'en_role'::varchar, 'en'::varchar, role, s.canonical_person_id
                FROM {SUMMARY_TABLE} s
                CROSS JOIN LATERAL UNNEST(s.en_roles) AS role
                UNION ALL
                SELECT 'show_type'::varchar, ''::varchar, show_type, s.canonical_person_id
                FROM {SUMMARY_TABLE} s
                CROSS JOIN LATERAL UNNEST(s.show_types) AS show_type
            ) rows
            GROUP BY kind, language, name
            '''
        )
        cursor.execute(
            f'''
            UPDATE {STATE_TABLE} AS state
            SET root_person_count = (
                    SELECT COUNT(*) FROM app_person WHERE master_person_id IS NULL
                ),
                used_person_count = (SELECT COUNT(*) FROM {SUMMARY_TABLE}),
                ru_known_person_count = (
                    SELECT COUNT(*) FROM {SUMMARY_TABLE} WHERE cardinality(ru_roles) > 0
                ),
                en_known_person_count = (
                    SELECT COUNT(*) FROM {SUMMARY_TABLE} WHERE cardinality(en_roles) > 0
                )
            WHERE state.id = 1
            '''
        )


def get_person_metric_summary_data():
    """Return compact role and show-type counts for one global snapshot."""
    if not person_metric_summary_ready():
        raise RuntimeError('Person metric summaries have not been backfilled yet.')

    refresh_dirty_person_metric_summaries()

    aggregates = list(
        PersonMetricAggregate.objects.order_by('kind', 'language', '-value').values_list(
            'kind', 'language', 'name', 'value'
        )
    )
    state = PersonMetricSummaryState.objects.get(id=1)
    role_rows = [
        (language, name, value)
        for kind, language, name, value in aggregates
        if kind in ('ru_role', 'en_role')
    ]
    show_type_rows = [
        (name, value)
        for kind, _language, name, value in aggregates
        if kind == 'show_type'
    ]
    return {
        'role_rows': role_rows,
        'ru_known_count': state.ru_known_person_count,
        'en_known_count': state.en_known_person_count,
        'used_person_count': state.used_person_count,
        'root_person_count': state.root_person_count,
        'show_type_rows': show_type_rows,
    }
