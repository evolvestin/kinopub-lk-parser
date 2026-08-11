from django.core.management.base import BaseCommand
from django.db import connection, transaction

from app.models import Person
from app.services.metrics import invalidate_duplicate_photo_urls_cache


class Command(BaseCommand):
    help = (
        'Merge canonical Person rows where one has a TMDB ID, the other does not, '
        'normalized names match, and both occur in the same show.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--min-common-shows', type=int, default=1)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        min_common_shows = max(1, options['min_common_shows'])
        limit = max(0, options['limit'])
        candidates = self._find_candidates(min_common_shows)
        if limit:
            candidates = candidates[:limit]

        mode = 'APPLY' if options['apply'] else 'DRY-RUN'
        self.stdout.write(f'TMDB aliases: candidates={len(candidates)} mode={mode}')
        for candidate in candidates:
            self.stdout.write(
                '  '
                f'master={candidate["master_id"]} alias={candidate["alias_id"]} '
                f'common_shows={candidate["common_shows"]} '
                f'master_name={candidate["master_name"]!r} '
                f'alias_name={candidate["alias_name"]!r} '
                f'tmdb_id={candidate["tmdb_id"]}'
            )

        if not options['apply'] or not candidates:
            return

        merged = self._apply_candidates(candidates)
        invalidate_duplicate_photo_urls_cache()
        self.stdout.write(self.style.SUCCESS(f'TMDB aliases merged: {merged}'))

    def _find_candidates(self, min_common_shows):
        sql = """
            WITH candidate_pairs AS (
                SELECT
                    master.id AS master_id,
                    alias.id AS alias_id,
                    count(DISTINCT alias_crew.show_id) AS common_shows,
                    master.name AS master_name,
                    alias.name AS alias_name,
                    master.tmdb_id AS tmdb_id
                FROM app_person master
                JOIN app_person alias
                  ON alias.master_person_id IS NULL
                 AND alias.tmdb_id IS NULL
                 AND lower(trim(replace(replace(replace(replace(alias.name, 'ё', 'е'), 'Ё', 'Е'), 'э', 'е'), 'Э', 'Е')))
                     = lower(trim(replace(replace(replace(replace(master.name, 'ё', 'е'), 'Ё', 'Е'), 'э', 'е'), 'Э', 'Е')))
                 AND lower(trim(coalesce(alias.en_name, '')))
                     = lower(trim(coalesce(master.en_name, '')))
                JOIN app_showcrew alias_crew ON alias_crew.person_id = alias.id
                JOIN app_showcrew master_crew
                  ON master_crew.person_id = master.id
                 AND master_crew.show_id = alias_crew.show_id
                WHERE master.master_person_id IS NULL
                  AND master.tmdb_id IS NOT NULL
                GROUP BY master.id, alias.id, master.name, alias.name, master.tmdb_id
                HAVING count(DISTINCT alias_crew.show_id) >= %s
            ), unique_aliases AS (
                SELECT alias_id
                FROM candidate_pairs
                GROUP BY alias_id
                HAVING count(*) = 1
            )
            SELECT candidate_pairs.*
            FROM candidate_pairs
            JOIN unique_aliases USING (alias_id)
            ORDER BY master_id, alias_id
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [min_common_shows])
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def _apply_candidates(self, candidates):
        merged = 0
        affected_ids = set()
        with transaction.atomic():
            for candidate in candidates:
                master_id = candidate['master_id']
                alias_id = candidate['alias_id']
                locked = (
                    Person.objects.select_for_update()
                    .filter(id__in=[master_id, alias_id], master_person__isnull=True)
                    .in_bulk()
                )
                master = locked.get(master_id)
                alias = locked.get(alias_id)
                if master is None or alias is None:
                    self.stderr.write(
                        self.style.WARNING(f'Skipped changed candidate {master_id} <- {alias_id}')
                    )
                    continue
                if not master.tmdb_id or alias.tmdb_id:
                    continue
                alias.master_person = master
                alias.save(update_fields=['master_person'])
                affected_ids.add(alias_id)
                merged += 1

            if affected_ids:
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
