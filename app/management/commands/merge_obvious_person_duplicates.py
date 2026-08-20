from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from app.models import Person
from app.services.metrics import invalidate_duplicate_photo_urls_cache

SOURCE_CONFIG = {
    'tmdb': {
        'source_field': 'tmdb_photo_url',
        'other_field': 'kp_photo_url',
        'group_name': 'lower(trim(name)), lower(trim(en_name))',
        'name_predicate': (
            'master.name IS NOT NULL AND alias.name IS NOT NULL '
            'AND master.en_name IS NOT NULL AND alias.en_name IS NOT NULL '
            'AND length(trim(master.en_name)) > 0 AND length(trim(alias.en_name)) > 0 '
            'AND lower(trim(master.name)) = lower(trim(alias.name)) '
            'AND lower(trim(master.en_name)) = lower(trim(alias.en_name))'
        ),
    },
    'kp': {
        'source_field': 'kp_photo_url',
        'other_field': 'tmdb_photo_url',
        'group_name': 'lower(trim(en_name))',
        'name_predicate': (
            'master.en_name IS NOT NULL AND alias.en_name IS NOT NULL '
            'AND length(trim(master.en_name)) > 0 AND length(trim(alias.en_name)) > 0 '
            'AND lower(trim(master.en_name)) = lower(trim(alias.en_name))'
        ),
    },
}


class Command(BaseCommand):
    help = (
        'Merge only high-confidence Person duplicates: same photo source, one TMDB ID, '
        'matching names, no conflicting second photo source, and shared filmography.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            choices=['tmdb', 'kp', 'all'],
            default='all',
            help='Photo source to inspect; all runs TMDB first and KP second.',
        )
        parser.add_argument(
            '--min-common-shows',
            type=int,
            default=2,
            help='Minimum number of shared shows required for every alias (default: 2).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximum number of aliases to merge; 0 means no limit.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply aliases. Without this flag the command is read-only.',
        )

    def handle(self, *args, **options):
        min_common_shows = max(1, options['min_common_shows'])
        limit = max(0, options['limit'])
        sources = ['tmdb', 'kp'] if options['source'] == 'all' else [options['source']]

        total = 0
        for source in sources:
            candidates = self._find_candidates(source, min_common_shows)
            if limit:
                candidates = candidates[: max(0, limit - total)]

            self.stdout.write(
                f'{source.upper()}: candidates={len(candidates)} '
                f'mode={"APPLY" if options["apply"] else "DRY-RUN"}'
            )
            for candidate in candidates:
                self.stdout.write(
                    '  '
                    f'master={candidate["master_id"]} alias={candidate["alias_id"]} '
                    f'common_shows={candidate["common_shows"]} '
                    f'master_name={candidate["master_name"]!r} '
                    f'alias_name={candidate["alias_name"]!r} '
                    f'tmdb_ids=({candidate["master_tmdb_id"]},{candidate["alias_tmdb_id"]})'
                )

            if options['apply'] and candidates:
                merged = self._apply_candidates(candidates)
                total += merged
                self.stdout.write(self.style.SUCCESS(f'{source.upper()}: merged={merged}'))
            else:
                total += len(candidates)

        if options['apply']:
            invalidate_duplicate_photo_urls_cache()
            self._verify_canonical_crew()
            self.stdout.write(self.style.SUCCESS(f'Total aliases merged: {total}'))
        else:
            self.stdout.write(f'Total aliases eligible: {total}')

    def _find_candidates(self, source, min_common_shows):
        config = SOURCE_CONFIG[source]
        source_field = config['source_field']
        other_field = config['other_field']
        group_name = config['group_name']
        name_predicate = config['name_predicate']

        sql = f"""
            WITH candidate_groups AS (
                SELECT
                    {source_field},
                    {group_name},
                    min(id) FILTER (WHERE tmdb_id IS NOT NULL) AS master_id
                FROM app_person
                WHERE master_person_id IS NULL
                  AND length({source_field}) > 0
                GROUP BY {source_field}, {group_name}
                HAVING count(*) = 2
                   AND count(tmdb_id) = 1
                   AND count(DISTINCT {other_field}) FILTER (
                       WHERE length({other_field}) > 0
                   ) <= 1
            ), valid_groups AS (
                SELECT g.*
                FROM candidate_groups g
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM app_person alias
                    JOIN app_person master ON master.id = g.master_id
                    WHERE alias.master_person_id IS NULL
                      AND alias.id <> g.master_id
                      AND alias.{source_field} = g.{source_field}
                      AND {
            'lower(trim(alias.name)) = lower(trim(master.name))'
            if source == 'tmdb'
            else 'lower(trim(alias.en_name)) = lower(trim(master.en_name))'
        }
                      AND NOT EXISTS (
                          SELECT 1
                          FROM app_showcrew alias_crew
                          JOIN app_showcrew master_crew
                            ON master_crew.show_id = alias_crew.show_id
                           AND master_crew.person_id = g.master_id
                          WHERE alias_crew.person_id = alias.id
                      )
                )
            )
            SELECT
                g.master_id,
                alias.id AS alias_id,
                count(DISTINCT alias_crew.show_id) AS common_shows,
                master.name AS master_name,
                alias.name AS alias_name,
                master.tmdb_id AS master_tmdb_id,
                alias.tmdb_id AS alias_tmdb_id
            FROM valid_groups g
            JOIN app_person master ON master.id = g.master_id
            JOIN app_person alias
              ON alias.master_person_id IS NULL
             AND alias.id <> master.id
             AND alias.{source_field} = g.{source_field}
            JOIN app_showcrew alias_crew ON alias_crew.person_id = alias.id
            JOIN app_showcrew master_crew
              ON master_crew.person_id = master.id
             AND master_crew.show_id = alias_crew.show_id
            WHERE master.master_person_id IS NULL
              AND alias.master_person_id IS NULL
              AND {name_predicate}
            GROUP BY g.master_id, alias.id, master.name, alias.name,
                     master.tmdb_id, alias.tmdb_id
            HAVING count(DISTINCT alias_crew.show_id) >= %s
            ORDER BY g.master_id, alias.id
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, [min_common_shows])
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def _apply_candidates(self, candidates):
        merged = 0
        with transaction.atomic():
            affected_ids = set()
            for candidate in candidates:
                master_id = candidate['master_id']
                alias_id = candidate['alias_id']
                locked = list(
                    Person.objects.select_for_update()
                    .filter(id__in=[master_id, alias_id])
                    .values_list('id', 'master_person_id', 'tmdb_id')
                )
                rows = {row[0]: row for row in locked}
                if set(rows) != {master_id, alias_id}:
                    raise CommandError(f'Candidate disappeared: {master_id} <- {alias_id}')
                if rows[master_id][1] is not None or rows[alias_id][1] is not None:
                    raise CommandError(
                        f'Candidate is no longer canonical: {master_id} <- {alias_id}'
                    )
                if rows[master_id][2] is None or rows[alias_id][2] is not None:
                    raise CommandError(f'TMDB identity changed: {master_id} <- {alias_id}')

                updated = Person.objects.filter(id=alias_id, master_person__isnull=True).update(
                    master_person_id=master_id
                )
                if updated != 1:
                    raise CommandError(f'Alias update failed: {master_id} <- {alias_id}')
                merged += updated

                # Keep the alias graph flat. A canonical person may already
                # have aliases from an earlier merge; leaving those rows
                # pointing at alias_id would make canonical resolution depend
                # on traversal depth.
                frontier = [alias_id]
                descendants = []
                while frontier:
                    child_ids = list(
                        Person.objects.select_for_update()
                        .filter(master_person_id__in=frontier)
                        .exclude(id=master_id)
                        .values_list('id', flat=True)
                    )
                    if not child_ids:
                        break
                    Person.objects.filter(id__in=child_ids).update(master_person_id=master_id)
                    descendants.extend(child_ids)
                    frontier = child_ids
                affected_ids.update([master_id, alias_id, *descendants])

            # Recompute the denormalized canonical FK explicitly. This is
            # idempotent and protects the operation if the migration trigger
            # is absent or stale on a restored production copy.
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_showcrew AS sc
                       SET canonical_person_id = COALESCE(p.master_person_id, p.id)
                      FROM app_person AS p
                     WHERE p.id = sc.person_id
                       AND sc.person_id = ANY(%s)
                    """,
                    [list(affected_ids)],
                )
        return merged

    def _verify_canonical_crew(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM app_showcrew sc
                JOIN app_person p ON p.id = sc.person_id
                WHERE sc.canonical_person_id IS DISTINCT FROM COALESCE(p.master_person_id, p.id)
                """
            )
            stale = cursor.fetchone()[0]
        if stale:
            raise CommandError(f'ShowCrew canonical_person is stale for {stale} rows')
