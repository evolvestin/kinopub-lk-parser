from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Backfill and index ShowCrew.canonical_person_id in resumable batches.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=50000)
        parser.add_argument('--start-id', type=int, default=0)
        parser.add_argument(
            '--fast',
            action='store_true',
            help='Disable synchronous WAL flushes during the rebuild.',
        )
        parser.add_argument('--no-indexes', action='store_true')

    def handle(self, *args, **options):
        batch_size = max(1000, options['batch_size'])
        with connection.cursor() as cursor:
            if options['fast']:
                cursor.execute('SET synchronous_commit TO off')
            cursor.execute('SELECT COALESCE(MAX(id), 0) FROM app_showcrew')
            max_id = cursor.fetchone()[0]

        last_id = max(0, options['start_id'])
        processed = 0
        while last_id < max_id:
            upper_id = min(last_id + batch_size, max_id)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_showcrew AS sc
                       SET canonical_person_id = COALESCE(p.master_person_id, p.id)
                      FROM app_person AS p
                     WHERE sc.id > %s
                       AND sc.id <= %s
                       AND p.id = sc.person_id
                       AND sc.canonical_person_id IS DISTINCT FROM COALESCE(p.master_person_id, p.id)
                    """,
                    [last_id, upper_id],
                )
                processed += cursor.rowcount
            self.stdout.write(f'up to id {upper_id}/{max_id}, updated {processed}')
            last_id = upper_id

        if not options['no_indexes']:
            with connection.cursor() as cursor:
                cursor.execute(
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    'idx_crew_prof_canonical ON app_showcrew (profession, canonical_person_id)'
                )
                cursor.execute(
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    'idx_crew_enprof_canonical ON app_showcrew (en_profession, canonical_person_id)'
                )
                cursor.execute(
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    'idx_crew_show_canonical ON app_showcrew (show_id, canonical_person_id)'
                )

        self.stdout.write(self.style.SUCCESS(f'Completed. Updated rows: {processed}'))
