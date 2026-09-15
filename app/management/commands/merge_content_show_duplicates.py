from django.core.management.base import BaseCommand
from django.db import connection

from app.services.show_merge import ShowMergeConflictError, merge_show_records


class Command(BaseCommand):
    help = (
        'Find and merge unambiguous KinoPub/TMDB duplicates by exact type, title, '
        'original title, and plot. The year may differ.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--type', choices=['Movie', 'Series', 'all'], default='all')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument(
            '--show-id',
            type=int,
            help='Only inspect the candidate containing this local show ID.',
        )
        parser.add_argument(
            '--quiet', action='store_true', help='Only print the final summary.'
        )
        parser.add_argument(
            '--apply', action='store_true', help='Apply safe merges; otherwise read-only.'
        )

    def handle(self, *args, **options):
        candidates = self._find_candidates(
            show_type=options['type'],
            show_id=options['show_id'],
        )
        if options['limit']:
            candidates = candidates[: options['limit']]

        safe = [candidate for candidate in candidates if not candidate['conflict']]
        imdb_conflicts = sum(candidate['conflict'] == 'imdb' for candidate in candidates)
        tmdb_conflicts = sum(candidate['conflict'] == 'tmdb' for candidate in candidates)
        mode = 'APPLY' if options['apply'] else 'DRY-RUN'

        self.stdout.write(
            f'Candidates: {len(candidates)}; safe: {len(safe)}; '
            f'IMDb conflicts: {imdb_conflicts}; TMDB conflicts: {tmdb_conflicts}; '
            f'mode={mode}'
        )

        if not options['apply']:
            if not options['quiet']:
                for candidate in candidates:
                    conflict = f" conflict={candidate['conflict']}" if candidate['conflict'] else ''
                    self.stdout.write(
                        f"  canonical={candidate['canonical_id']} "
                        f"duplicate={candidate['duplicate_id']} "
                        f"years={candidate['canonical_year']}/{candidate['duplicate_year']}"
                        f'{conflict}'
                    )
            return

        merged = 0
        skipped = 0
        for candidate in safe:
            try:
                stats = merge_show_records(
                    candidate['canonical_id'],
                    candidate['duplicate_id'],
                )
            except ShowMergeConflictError as exc:
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipped {candidate['canonical_id']} <- "
                        f"{candidate['duplicate_id']}: {exc}"
                    )
                )
                continue

            merged += 1
            if not options['quiet']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Merged {stats.canonical_id} <- {stats.duplicate_id}; '
                        f'external ratings dedup={stats.external_ratings_deduplicated}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Merged shows: {merged}; skipped runtime conflicts: {skipped}; '
                f'left identity conflicts: {len(candidates) - len(safe)}'
            )
        )

    @staticmethod
    def _find_candidates(show_type='all', show_id=None):
        type_filter = '' if show_type == 'all' else 'AND type = %s'
        params = [] if show_type == 'all' else [show_type, show_type]
        show_filter = ''
        if show_id:
            show_filter = 'AND (kp.id = %s OR tmdb.id = %s)'
            params.extend([show_id, show_id])

        sql = f'''
            WITH kp_unique AS (
                SELECT type,
                       lower(trim(title)) AS title_key,
                       lower(trim(original_title)) AS original_title_key
                FROM app_show
                WHERE kinopub_id IS NOT NULL
                  AND NOT ignore_collision
                  AND NOT is_3d
                  AND length(trim(coalesce(title, ''))) > 0
                  AND length(trim(coalesce(original_title, ''))) > 0
                  AND length(trim(coalesce(plot, ''))) > 0
                  {type_filter}
                GROUP BY type, title_key, original_title_key
                HAVING count(*) = 1
            ), tmdb_unique AS (
                SELECT type,
                       lower(trim(title)) AS title_key,
                       lower(trim(original_title)) AS original_title_key
                FROM app_show
                WHERE kinopub_id IS NULL
                  AND tmdb_id IS NOT NULL
                  AND NOT ignore_collision
                  AND NOT is_3d
                  AND length(trim(coalesce(title, ''))) > 0
                  AND length(trim(coalesce(original_title, ''))) > 0
                  AND length(trim(coalesce(plot, ''))) > 0
                  {type_filter}
                GROUP BY type, title_key, original_title_key
                HAVING count(*) = 1
            )
            SELECT kp.id AS canonical_id,
                   tmdb.id AS duplicate_id,
                   kp.year AS canonical_year,
                   tmdb.year AS duplicate_year,
                   CASE
                       WHEN kp.imdb_id IS NOT NULL
                        AND tmdb.imdb_id IS NOT NULL
                        AND kp.imdb_id <> tmdb.imdb_id THEN 'imdb'
                       WHEN kp.tmdb_id IS NOT NULL
                        AND tmdb.tmdb_id IS NOT NULL
                        AND kp.tmdb_id <> tmdb.tmdb_id THEN 'tmdb'
                       ELSE NULL
                   END AS conflict
            FROM app_show kp
            JOIN app_show tmdb
              ON tmdb.kinopub_id IS NULL
             AND tmdb.tmdb_id IS NOT NULL
             AND tmdb.type = kp.type
             AND lower(trim(tmdb.title)) = lower(trim(kp.title))
             AND lower(trim(tmdb.original_title)) = lower(trim(kp.original_title))
            JOIN kp_unique
              ON kp_unique.type = kp.type
             AND kp_unique.title_key = lower(trim(kp.title))
             AND kp_unique.original_title_key = lower(trim(kp.original_title))
            JOIN tmdb_unique
              ON tmdb_unique.type = tmdb.type
             AND tmdb_unique.title_key = lower(trim(tmdb.title))
             AND tmdb_unique.original_title_key = lower(trim(tmdb.original_title))
            WHERE kp.kinopub_id IS NOT NULL
              AND length(trim(coalesce(kp.plot, ''))) > 0
              AND length(trim(coalesce(tmdb.plot, ''))) > 0
              AND lower(regexp_replace(trim(kp.plot), '\\s+', ' ', 'g'))
                  = lower(regexp_replace(trim(tmdb.plot), '\\s+', ' ', 'g'))
              {show_filter}
            ORDER BY kp.id, tmdb.id
        '''
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
