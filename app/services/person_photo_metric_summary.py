"""Incremental avatar counters and duplicate-photo groups for global metrics."""

import logging
import time

from django.db import connection, transaction
from django.utils import timezone

from app.models import (
    Person,
    PersonKpWaitingSummary,
    PersonMetricSummary,
    PersonPhotoGroup,
    PersonPhotoGroupDirty,
    PersonPhotoMetricDirty,
    PersonPhotoMetricState,
    PersonPhotoMetricSummary,
)

SUMMARY_TABLE = PersonPhotoMetricSummary._meta.db_table
DIRTY_TABLE = PersonPhotoMetricDirty._meta.db_table
GROUP_TABLE = PersonPhotoGroup._meta.db_table
GROUP_DIRTY_TABLE = PersonPhotoGroupDirty._meta.db_table
STATE_TABLE = PersonPhotoMetricState._meta.db_table
WAITING_TABLE = PersonKpWaitingSummary._meta.db_table
PERSON_TABLE = Person._meta.db_table
PERSON_METRIC_SUMMARY_TABLE = PersonMetricSummary._meta.db_table

AVATAR_FIELDS = (
    'has_tmdb_photo',
    'kp_only',
    'tmdb_none',
    'no_kp',
    'tmdb_wait',
    'all_none',
    'kp_wait',
    'all_none_wait',
)


def person_photo_metric_summary_ready():
    return PersonPhotoMetricState.objects.filter(id=1, ready=True).exists()


def _adjust_avatar_totals(person_ids, multiplier, cursor):
    if not person_ids:
        return
    cursor.execute(
        f'''
        SELECT
            COUNT(*) FILTER (WHERE has_tmdb_photo),
            COUNT(*) FILTER (WHERE has_kp_photo AND NOT has_tmdb_photo),
            COUNT(*) FILTER (WHERE photo_fetched AND NOT has_tmdb_photo),
            COUNT(*) FILTER (WHERE NOT has_kp_photo),
            COUNT(*) FILTER (WHERE NOT (photo_fetched OR has_tmdb_photo)),
            COUNT(*) FILTER (WHERE photo_fetched AND NOT has_tmdb_photo AND NOT has_kp_photo),
            COUNT(*) FILTER (WHERE kp_waiting AND NOT has_kp_photo),
            COUNT(*) FILTER (
                WHERE kp_waiting AND photo_fetched
                  AND NOT has_tmdb_photo AND NOT has_kp_photo
            )
        FROM {SUMMARY_TABLE}
        WHERE person_id = ANY(%s)
        ''',
        [person_ids],
    )
    values = cursor.fetchone()
    assignments = ', '.join(
        f'{field} = GREATEST(0, {field} + %s)' for field in AVATAR_FIELDS
    )
    cursor.execute(
        f'UPDATE {STATE_TABLE} SET {assignments} WHERE id = 1',
        [multiplier * value for value in values],
    )


def refresh_dirty_person_photo_metrics(batch_size=5000, force=False):
    if not force and not person_photo_metric_summary_ready():
        return 0

    started_at = time.monotonic()
    processed = 0
    while True:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f'''
                    DELETE FROM {DIRTY_TABLE}
                    WHERE person_id IN (
                        SELECT person_id FROM {DIRTY_TABLE}
                        ORDER BY person_id LIMIT %s
                    )
                    RETURNING person_id
                    ''',
                    [batch_size],
                )
                person_ids = [row[0] for row in cursor.fetchall()]
                if not person_ids:
                    break

                _adjust_avatar_totals(person_ids, -1, cursor)
                cursor.execute(
                    f'DELETE FROM {SUMMARY_TABLE} WHERE person_id = ANY(%s)',
                    [person_ids],
                )
                cursor.execute(
                    f'''
                    INSERT INTO {SUMMARY_TABLE}
                        (person_id, has_tmdb_photo, has_kp_photo, photo_fetched, kp_waiting)
                    SELECT
                        p.id,
                        (p.tmdb_photo_url IS NOT NULL AND p.tmdb_photo_url <> ''),
                        (p.kp_photo_url IS NOT NULL AND p.kp_photo_url <> ''),
                        p.is_photo_fetched,
                        EXISTS (
                            SELECT 1 FROM {WAITING_TABLE} waiting
                            WHERE waiting.person_id = p.id
                        )
                    FROM {PERSON_TABLE} p
                    WHERE p.id = ANY(%s)
                    ON CONFLICT (person_id) DO UPDATE SET
                        has_tmdb_photo = EXCLUDED.has_tmdb_photo,
                        has_kp_photo = EXCLUDED.has_kp_photo,
                        photo_fetched = EXCLUDED.photo_fetched,
                        kp_waiting = EXCLUDED.kp_waiting
                    ''',
                    [person_ids],
                )
                _adjust_avatar_totals(person_ids, 1, cursor)
                processed += len(person_ids)
    logging.info(
        'Metrics dirty refresh kind=person_photo rows=%s seconds=%.3f.',
        processed,
        time.monotonic() - started_at,
    )
    return processed


def _adjust_duplicate_group_totals(old_tmdb, old_kp, new_tmdb, new_kp, cursor):
    cursor.execute(
        f'''
        UPDATE {STATE_TABLE}
        SET tmdb_duplicate_groups = GREATEST(0, tmdb_duplicate_groups - %s + %s),
            kp_duplicate_groups = GREATEST(0, kp_duplicate_groups - %s + %s)
        WHERE id = 1
        ''',
        [old_tmdb, new_tmdb, old_kp, new_kp],
    )


def refresh_dirty_person_photo_groups(batch_size=2000, force=False):
    if not force and not person_photo_metric_summary_ready():
        return 0

    started_at = time.monotonic()
    processed = 0
    while True:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f'''
                    DELETE FROM {GROUP_DIRTY_TABLE}
                    WHERE (source, photo_url) IN (
                        SELECT source, photo_url FROM {GROUP_DIRTY_TABLE}
                        ORDER BY source, photo_url LIMIT %s
                    )
                    RETURNING source, photo_url
                    ''',
                    [batch_size],
                )
                dirty = cursor.fetchall()
                if not dirty:
                    break
                sources = [row[0] for row in dirty]
                urls = [row[1] for row in dirty]
                cursor.execute(
                    f'''
                    SELECT
                        COUNT(*) FILTER (WHERE groups.source = 'tmdb'),
                        COUNT(*) FILTER (WHERE groups.source = 'kp')
                    FROM {GROUP_TABLE} groups
                    JOIN UNNEST(%s::varchar[], %s::text[]) AS dirty(source, photo_url)
                      USING (source, photo_url)
                    ''',
                    [sources, urls],
                )
                old_tmdb, old_kp = cursor.fetchone()
                cursor.execute(
                    f'''
                    DELETE FROM {GROUP_TABLE} groups
                    USING UNNEST(%s::varchar[], %s::text[]) AS dirty(source, photo_url)
                    WHERE (groups.source, groups.photo_url) = (dirty.source, dirty.photo_url)
                    ''',
                    [sources, urls],
                )
                cursor.execute(
                    f'''
                    INSERT INTO {GROUP_TABLE} (source, photo_url, root_count, unresolved_count)
                    SELECT dirty.source, dirty.photo_url,
                           COUNT(p.id)::bigint,
                           COUNT(p.id) FILTER (WHERE p.tmdb_id IS NULL)::bigint
                    FROM UNNEST(%s::varchar[], %s::text[]) AS dirty(source, photo_url)
                    JOIN {PERSON_TABLE} p
                      ON p.master_person_id IS NULL
                     AND (
                         (dirty.source = 'tmdb' AND p.tmdb_photo_url = dirty.photo_url)
                         OR (dirty.source = 'kp' AND p.kp_photo_url = dirty.photo_url)
                     )
                    GROUP BY dirty.source, dirty.photo_url
                    HAVING COUNT(p.id) > 1
                       AND COUNT(p.id) FILTER (WHERE p.tmdb_id IS NULL) > 0
                    ON CONFLICT (source, photo_url) DO UPDATE SET
                        root_count = EXCLUDED.root_count,
                        unresolved_count = EXCLUDED.unresolved_count
                    RETURNING source
                    ''',
                    [sources, urls],
                )
                inserted = [row[0] for row in cursor.fetchall()]
                _adjust_duplicate_group_totals(
                    old_tmdb,
                    old_kp,
                    inserted.count('tmdb'),
                    inserted.count('kp'),
                    cursor,
                )
                processed += len(dirty)
    logging.info(
        'Metrics dirty refresh kind=person_photo_group rows=%s seconds=%.3f.',
        processed,
        time.monotonic() - started_at,
    )
    return processed


def _build_waiting_person_summary(cursor):
    cursor.execute(f'TRUNCATE TABLE {WAITING_TABLE}')
    cursor.execute(
        f'''
        INSERT INTO {WAITING_TABLE} (person_id)
        SELECT DISTINCT UNNEST(kp_waiting_person_ids)
        FROM {PERSON_METRIC_SUMMARY_TABLE}
        WHERE cardinality(kp_waiting_person_ids) > 0
        ON CONFLICT DO NOTHING
        '''
    )


def _rebuild_avatar_totals(cursor):
    cursor.execute(
        f'''
        UPDATE {STATE_TABLE} state
        SET has_tmdb_photo = counts.has_tmdb_photo,
            kp_only = counts.kp_only,
            tmdb_none = counts.tmdb_none,
            no_kp = counts.no_kp,
            tmdb_wait = counts.tmdb_wait,
            all_none = counts.all_none,
            kp_wait = counts.kp_wait,
            all_none_wait = counts.all_none_wait
        FROM (
            SELECT
                COUNT(*) FILTER (WHERE has_tmdb_photo) AS has_tmdb_photo,
                COUNT(*) FILTER (WHERE has_kp_photo AND NOT has_tmdb_photo) AS kp_only,
                COUNT(*) FILTER (WHERE photo_fetched AND NOT has_tmdb_photo) AS tmdb_none,
                COUNT(*) FILTER (WHERE NOT has_kp_photo) AS no_kp,
                COUNT(*) FILTER (WHERE NOT (photo_fetched OR has_tmdb_photo)) AS tmdb_wait,
                COUNT(*) FILTER (
                    WHERE photo_fetched AND NOT has_tmdb_photo AND NOT has_kp_photo
                ) AS all_none,
                COUNT(*) FILTER (WHERE kp_waiting AND NOT has_kp_photo) AS kp_wait,
                COUNT(*) FILTER (
                    WHERE kp_waiting AND photo_fetched
                      AND NOT has_tmdb_photo AND NOT has_kp_photo
                ) AS all_none_wait
            FROM {SUMMARY_TABLE}
        ) counts
        WHERE state.id = 1
        '''
    )


def _rebuild_photo_groups(cursor):
    cursor.execute(f'TRUNCATE TABLE {GROUP_TABLE}')
    cursor.execute(
        f'''
        INSERT INTO {GROUP_TABLE} (source, photo_url, root_count, unresolved_count)
        SELECT source, photo_url, COUNT(*)::bigint,
               COUNT(*) FILTER (WHERE tmdb_id IS NULL)::bigint
        FROM (
            SELECT 'tmdb'::varchar AS source, tmdb_photo_url AS photo_url, tmdb_id
            FROM {PERSON_TABLE}
            WHERE master_person_id IS NULL AND tmdb_photo_url > ''
            UNION ALL
            SELECT 'kp'::varchar, kp_photo_url, tmdb_id
            FROM {PERSON_TABLE}
            WHERE master_person_id IS NULL AND kp_photo_url > ''
        ) photos
        GROUP BY source, photo_url
        HAVING COUNT(*) > 1 AND COUNT(*) FILTER (WHERE tmdb_id IS NULL) > 0
        '''
    )
    cursor.execute(
        f'''
        UPDATE {STATE_TABLE} state
        SET tmdb_duplicate_groups = (
                SELECT COUNT(*) FROM {GROUP_TABLE} WHERE source = 'tmdb'
            ),
            kp_duplicate_groups = (
                SELECT COUNT(*) FROM {GROUP_TABLE} WHERE source = 'kp'
            )
        WHERE state.id = 1
        '''
    )


def rebuild_person_photo_metric_summaries(progress_callback=None):
    state, _ = PersonPhotoMetricState.objects.get_or_create(id=1)
    state.ready = False
    state.rebuilt_at = None
    state.save(update_fields=['ready', 'rebuilt_at'])

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f'TRUNCATE TABLE {SUMMARY_TABLE}, {DIRTY_TABLE}, '
                f'{GROUP_TABLE}, {GROUP_DIRTY_TABLE}'
            )
            _build_waiting_person_summary(cursor)
            cursor.execute(
                f'''
                INSERT INTO {SUMMARY_TABLE}
                    (person_id, has_tmdb_photo, has_kp_photo, photo_fetched, kp_waiting)
                SELECT
                    p.id,
                    (p.tmdb_photo_url IS NOT NULL AND p.tmdb_photo_url <> ''),
                    (p.kp_photo_url IS NOT NULL AND p.kp_photo_url <> ''),
                    p.is_photo_fetched,
                    (waiting.person_id IS NOT NULL)
                FROM {PERSON_TABLE} p
                LEFT JOIN {WAITING_TABLE} waiting ON waiting.person_id = p.id
                '''
            )
            person_count = cursor.rowcount
            _rebuild_avatar_totals(cursor)
            _rebuild_photo_groups(cursor)

    refresh_dirty_person_photo_metrics(force=True)
    refresh_dirty_person_photo_groups(force=True)
    state.ready = True
    state.rebuilt_at = timezone.now()
    state.save(update_fields=['ready', 'rebuilt_at'])
    if progress_callback:
        progress_callback(person_count)

    return person_count


def get_person_photo_metric_summary_data():
    if not person_photo_metric_summary_ready():
        raise RuntimeError('Person photo metric summaries have not been backfilled yet.')
    refresh_dirty_person_photo_metrics()
    refresh_dirty_person_photo_groups()
    return PersonPhotoMetricState.objects.filter(id=1).values(
        *AVATAR_FIELDS, 'tmdb_duplicate_groups', 'kp_duplicate_groups'
    ).get()
