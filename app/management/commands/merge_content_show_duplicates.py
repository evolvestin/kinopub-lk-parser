from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from app.models import Show
from app.services.show_merge import ShowMergeConflictError, merge_show_records


class Command(BaseCommand):
    help = (
        'Find and merge unambiguous KinoPub/TMDB duplicates by exact type, title, '
        'original title, and plot. The year may differ.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--type', choices=['Movie', 'Series', 'all'], default='all')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--canonical-id', type=int)
        parser.add_argument('--duplicate-id', type=int)
        parser.add_argument(
            '--preferred-imdb-id',
            help='Verified IMDb ID to keep when applying an explicit pair.',
        )
        parser.add_argument(
            '--preferred-tmdb-id',
            type=int,
            help='Verified TMDB ID to keep when applying an explicit pair.',
        )
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
        explicit_ids = options['canonical_id'] is not None or options['duplicate_id'] is not None
        if options['canonical_id'] is None and options['duplicate_id'] is not None:
            raise CommandError('--canonical-id and --duplicate-id must be supplied together')
        if options['canonical_id'] is not None and options['duplicate_id'] is None:
            raise CommandError('--canonical-id and --duplicate-id must be supplied together')
        if (options['preferred_imdb_id'] or options['preferred_tmdb_id']) and not explicit_ids:
            raise CommandError('Preferred identity IDs require --canonical-id and --duplicate-id')

        if explicit_ids:
            self._handle_explicit_pair(options)
            return

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

    def _handle_explicit_pair(self, options):
        canonical_id = options['canonical_id']
        duplicate_id = options['duplicate_id']
        if not options['apply']:
            canonical, duplicate = Show.objects.filter(
                id__in=[canonical_id, duplicate_id]
            ).order_by('id')
            self.stdout.write(
                f'Explicit pair: canonical={canonical.id} duplicate={duplicate.id} '
                f'canonical_imdb={canonical.imdb_id} duplicate_imdb={duplicate.imdb_id} '
                f'canonical_tmdb={canonical.tmdb_id} duplicate_tmdb={duplicate.tmdb_id} '
                'mode=DRY-RUN'
            )
            return

        try:
            with transaction.atomic():
                if options['preferred_tmdb_id']:
                    shows = {
                        show.id: show
                        for show in Show.objects.select_for_update().filter(
                            id__in=[canonical_id, duplicate_id]
                        )
                    }
                    if set(shows) != {canonical_id, duplicate_id}:
                        raise CommandError('Both explicit show IDs must exist')
                    if options['preferred_tmdb_id'] not in {
                        shows[canonical_id].tmdb_id,
                        shows[duplicate_id].tmdb_id,
                    }:
                        raise CommandError('--preferred-tmdb-id is not present on either show')
                    for show in shows.values():
                        if show.tmdb_id not in (None, options['preferred_tmdb_id']):
                            Show.objects.filter(pk=show.id, tmdb_id=show.tmdb_id).update(tmdb_id=None)

                stats = merge_show_records(
                    canonical_id,
                    duplicate_id,
                    preferred_imdb_id=options['preferred_imdb_id'],
                )
        except ShowMergeConflictError as exc:
            raise CommandError(f'Cannot merge {canonical_id} <- {duplicate_id}: {exc}') from exc

        self.stdout.write(
            self.style.SUCCESS(
                f'Merged {stats.canonical_id} <- {stats.duplicate_id}; '
                f'external ratings dedup={stats.external_ratings_deduplicated}'
            )
        )

    @staticmethod
    def _find_candidates(show_type='all', show_id=None):
        type_filter = '' if show_type == 'all' else 'AND type = %s'
        params = [] if show_type == 'all' else [show_type]
        show_filter = ''
        if show_id:
            show_filter = 'AND (kp.id = %s OR tmdb.id = %s)'
            params.extend([show_id, show_id])

        sql = f'''
            WITH source_rows AS MATERIALIZED (
                SELECT id, kinopub_id, tmdb_id, imdb_id, type, year,
                       lower(trim(title)) AS title_key,
                       lower(trim(original_title)) AS original_title_key,
                       md5(lower(regexp_replace(trim(plot), '\\s+', ' ', 'g'))) AS plot_key
                FROM app_show
                WHERE NOT ignore_collision
                  AND NOT is_3d
                  AND length(trim(coalesce(title, ''))) > 0
                  AND length(trim(coalesce(original_title, ''))) > 0
                  AND length(trim(coalesce(plot, ''))) > 0
                  {type_filter}
            ), kp_unique AS (
                SELECT type, title_key, original_title_key
                FROM source_rows
                WHERE kinopub_id IS NOT NULL
                GROUP BY type, title_key, original_title_key
                HAVING count(*) = 1
            ), tmdb_unique AS (
                SELECT type, title_key, original_title_key
                FROM source_rows
                WHERE kinopub_id IS NULL AND tmdb_id IS NOT NULL
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
            FROM source_rows kp
            JOIN source_rows tmdb
              ON tmdb.kinopub_id IS NULL
             AND tmdb.tmdb_id IS NOT NULL
             AND tmdb.type = kp.type
             AND tmdb.title_key = kp.title_key
             AND tmdb.original_title_key = kp.original_title_key
             AND tmdb.plot_key = kp.plot_key
            JOIN kp_unique
              ON kp_unique.type = kp.type
             AND kp_unique.title_key = kp.title_key
             AND kp_unique.original_title_key = kp.original_title_key
            JOIN tmdb_unique
              ON tmdb_unique.type = tmdb.type
             AND tmdb_unique.title_key = tmdb.title_key
             AND tmdb_unique.original_title_key = tmdb.original_title_key
            WHERE kp.kinopub_id IS NOT NULL
              {show_filter}
            ORDER BY kp.id, tmdb.id
        '''
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
