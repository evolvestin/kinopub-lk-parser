from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from app.services.show_merge import ShowMergeConflictError, merge_show_records


class Command(BaseCommand):
    help = (
        'Find and merge high-confidence KinoPub/TMDB show duplicates using exact type, year, '
        'title, and original title matches.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--type', choices=['Movie', 'Series', 'all'], default='all')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument(
            '--show-id', type=int, help='Merge the unique candidate containing this show.'
        )
        parser.add_argument('--canonical-id', type=int)
        parser.add_argument('--duplicate-id', type=int)
        parser.add_argument(
            '--quiet', action='store_true', help='Only print summary and conflicts.'
        )
        parser.add_argument(
            '--apply', action='store_true', help='Apply merges; otherwise read-only.'
        )

    def handle(self, *args, **options):
        explicit_ids = options['canonical_id'] or options['duplicate_id']
        if bool(options['canonical_id']) != bool(options['duplicate_id']):
            raise CommandError('--canonical-id and --duplicate-id must be supplied together')

        if explicit_ids:
            candidates = [
                {
                    'canonical_id': options['canonical_id'],
                    'duplicate_id': options['duplicate_id'],
                    'match_type': 'explicit',
                }
            ]
        elif options['show_id']:
            candidates = self._find_candidates(
                show_id=options['show_id'], show_type=options['type']
            )
            if len(candidates) != 1:
                raise CommandError(
                    f'Expected exactly one candidate for show {options["show_id"]}, '
                    f'found {len(candidates)}'
                )
        else:
            candidates = self._find_candidates(show_type=options['type'])
            if options['limit']:
                candidates = candidates[: options['limit']]

        mode = 'APPLY' if options['apply'] else 'DRY-RUN'
        self.stdout.write(f'Candidates: {len(candidates)} mode={mode}')
        if not options['apply']:
            for candidate in candidates:
                self.stdout.write(
                    f'  canonical={candidate["canonical_id"]} '
                    f'duplicate={candidate["duplicate_id"]} '
                    f'match={candidate.get("match_type", "exact")}'
                )
            return

        merged = 0
        skipped = 0
        for candidate in candidates:
            try:
                stats = merge_show_records(candidate['canonical_id'], candidate['duplicate_id'])
            except ShowMergeConflictError as exc:
                if options['canonical_id']:
                    raise CommandError(
                        f'Cannot merge {candidate["canonical_id"]} '
                        f'<- {candidate["duplicate_id"]}: {exc}'
                    ) from exc
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(
                        f'Skipped {candidate["canonical_id"]} <- {candidate["duplicate_id"]}: {exc}'
                    )
                )
                continue
            merged += 1
            if not options['quiet'] or merged % 500 == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Merged {stats.canonical_id} <- {stats.duplicate_id}; '
                        f'crew moved/dedup={stats.crew_moved}/{stats.crew_deduplicated}, '
                        'episodes moved/dedup='
                        f'{stats.durations_moved}/{stats.durations_deduplicated}, '
                        'history moved/dedup='
                        f'{stats.histories_moved}/{stats.histories_deduplicated}'
                    )
                )
        self.stdout.write(
            self.style.SUCCESS(f'Merged shows: {merged}; skipped conflicts: {skipped}')
        )

    @staticmethod
    def _find_candidates(show_type='all', show_id=None):
        type_filter = '' if show_type == 'all' else 'AND type = %s'
        params = [] if show_type == 'all' else [show_type, show_type]
        show_filter = ''
        if show_id:
            show_filter = 'AND (kp.id = %s OR tmdb.id = %s)'
            params.extend([show_id, show_id])

        sql = f"""
            WITH kp_groups AS (
                SELECT type, year, lower(trim(title)) AS title_key,
                       lower(trim(original_title)) AS original_title_key,
                       count(*) AS row_count
                FROM app_show
                WHERE kinopub_id IS NOT NULL
                  AND length(trim(title)) > 0
                  AND length(trim(original_title)) > 0
                  AND year IS NOT NULL
                  AND NOT ignore_collision
                  {type_filter}
                GROUP BY type, year, title_key, original_title_key
                HAVING count(*) = 1
            ), tmdb_groups AS (
                SELECT type, year, lower(trim(title)) AS title_key,
                       lower(trim(original_title)) AS original_title_key,
                       count(*) AS row_count
                FROM app_show
                WHERE kinopub_id IS NULL
                  AND tmdb_id IS NOT NULL
                  AND length(trim(title)) > 0
                  AND length(trim(original_title)) > 0
                  AND year IS NOT NULL
                  AND NOT ignore_collision
                  {type_filter}
                GROUP BY type, year, title_key, original_title_key
                HAVING count(*) = 1
            )
            SELECT kp.id AS canonical_id, tmdb.id AS duplicate_id,
                   'exact_title_year_type' AS match_type
            FROM app_show kp
            JOIN app_show tmdb
              ON tmdb.kinopub_id IS NULL
             AND tmdb.tmdb_id IS NOT NULL
             AND tmdb.type = kp.type
             AND tmdb.year = kp.year
             AND lower(trim(tmdb.title)) = lower(trim(kp.title))
             AND lower(trim(tmdb.original_title)) = lower(trim(kp.original_title))
            JOIN kp_groups kg
              ON kg.type = kp.type
             AND kg.year = kp.year
             AND kg.title_key = lower(trim(kp.title))
             AND kg.original_title_key = lower(trim(kp.original_title))
            JOIN tmdb_groups tg
              ON tg.type = tmdb.type
             AND tg.year = tmdb.year
             AND tg.title_key = lower(trim(tmdb.title))
             AND tg.original_title_key = lower(trim(tmdb.original_title))
            WHERE kp.kinopub_id IS NOT NULL
              AND NOT kp.ignore_collision
              AND NOT tmdb.ignore_collision
              AND NOT (kp.imdb_id IS NOT NULL AND tmdb.imdb_id IS NOT NULL)
              AND (kp.tmdb_id IS NULL OR kp.tmdb_id = tmdb.tmdb_id)
              {show_filter}
            ORDER BY kp.id, tmdb.id
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
