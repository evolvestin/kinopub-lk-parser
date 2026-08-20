from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from app.models import Person
from app.services.metrics import invalidate_duplicate_photo_urls_cache


class Command(BaseCommand):
    help = (
        'Merge high-confidence KP aliases: exactly two canonical rows with the same KP photo, '
        'same normalized English name, no TMDB IDs, no conflicting TMDB photos, and shared titles.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--min-common-shows', type=int, default=2)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        candidates = self._find_candidates(max(1, options['min_common_shows']))
        if options['limit']:
            candidates = candidates[: max(0, options['limit'])]
        self.stdout.write(
            f'KP verified aliases: candidates={len(candidates)} '
            f'mode={"APPLY" if options["apply"] else "DRY-RUN"}'
        )
        for candidate in candidates:
            self.stdout.write(
                f'  {candidate["master_id"]} <- {candidate["alias_id"]}: '
                f'{candidate["en_name"]!r}, common_shows={candidate["common_shows"]}'
            )
        if not options['apply'] or not candidates:
            return

        with transaction.atomic():
            for candidate in candidates:
                master_id, alias_id = candidate['master_id'], candidate['alias_id']
                people = (
                    Person.objects.select_for_update()
                    .filter(id__in=[master_id, alias_id], master_person__isnull=True)
                    .in_bulk()
                )
                master, alias = people.get(master_id), people.get(alias_id)
                if not master or not alias:
                    raise CommandError(f'Candidate changed: {master_id} <- {alias_id}')
                if master.tmdb_id or alias.tmdb_id or master.kp_photo_url != alias.kp_photo_url:
                    raise CommandError(f'Identity evidence changed: {master_id} <- {alias_id}')
                alias.master_person_id = master_id
                alias.save(update_fields=['master_person'])
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE app_showcrew AS sc
                           SET canonical_person_id = %s
                         WHERE sc.person_id = %s
                        """,
                        [master_id, alias_id],
                    )
        invalidate_duplicate_photo_urls_cache()
        self.stdout.write(self.style.SUCCESS(f'Merged {len(candidates)} verified KP aliases.'))

    def _find_candidates(self, min_common_shows):
        sql = """
            WITH photo_pairs AS (
                SELECT
                    min(id) AS master_id,
                    max(id) AS alias_id,
                    min(kp_photo_url) AS kp_photo_url
                FROM app_person
                WHERE master_person_id IS NULL AND kp_photo_url > ''
                GROUP BY kp_photo_url
                HAVING count(*) = 2
                   AND count(tmdb_id) = 0
                   AND count(DISTINCT tmdb_photo_url) FILTER (
                       WHERE tmdb_photo_url > ''
                   ) <= 1
            )
            SELECT
                pp.master_id,
                pp.alias_id,
                master.en_name,
                count(DISTINCT master_crew.show_id) AS common_shows
            FROM photo_pairs pp
            JOIN app_person master ON master.id = pp.master_id
            JOIN app_person alias ON alias.id = pp.alias_id
            JOIN app_showcrew master_crew ON master_crew.person_id = master.id
            JOIN app_showcrew alias_crew
              ON alias_crew.person_id = alias.id
             AND alias_crew.show_id = master_crew.show_id
            WHERE master.master_person_id IS NULL
              AND alias.master_person_id IS NULL
              AND master.en_name IS NOT NULL AND trim(master.en_name) <> ''
              AND lower(trim(master.en_name)) = lower(trim(alias.en_name))
            GROUP BY pp.master_id, pp.alias_id, master.en_name
            HAVING count(DISTINCT master_crew.show_id) >= %s
            ORDER BY pp.master_id, pp.alias_id
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [min_common_shows])
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
