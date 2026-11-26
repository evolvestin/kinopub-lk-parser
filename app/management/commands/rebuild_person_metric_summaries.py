from django.core.management.base import BaseCommand, CommandError

from app.services.person_metric_summary import rebuild_person_metric_summaries
from app.tasks import _redis_lock
from shared.constants import RedisLock


class Command(BaseCommand):
    help = 'Build the compact person/crew metric summary from the canonical ShowCrew index.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=50000)

    def handle(self, *args, **options):
        batch_size = max(1000, options['batch_size'])
        with _redis_lock(RedisLock.METRICS_SNAPSHOT, timeout=7200) as snapshot_acquired:
            if not snapshot_acquired:
                raise CommandError('A metrics snapshot is active; retry after it completes.')
            with _redis_lock(RedisLock.CATALOG_WRITES, timeout=7200) as catalog_acquired:
                if not catalog_acquired:
                    raise CommandError('Catalog writes are active; retry after they complete.')
                with _redis_lock(
                    RedisLock.EXTERNAL_RATING_WRITES,
                    timeout=7200,
                ) as ratings_acquired:
                    if not ratings_acquired:
                        raise CommandError('External rating writes are active; retry later.')

                    def report_progress(upper_id, max_id, ranges):
                        self.stdout.write(
                            f'Processed ShowCrew IDs through {upper_id}/{max_id} '
                            f'({ranges} batches)'
                        )

                    ranges = rebuild_person_metric_summaries(
                        batch_size=batch_size,
                        progress_callback=report_progress,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Person metric summaries are ready after {ranges} batches.'
            )
        )
