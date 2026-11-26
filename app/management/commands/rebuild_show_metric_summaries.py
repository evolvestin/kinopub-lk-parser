from django.core.management.base import BaseCommand, CommandError

from app.services.show_metric_summary import rebuild_show_metric_summaries
from app.tasks import _redis_lock
from shared.constants import RedisLock


class Command(BaseCommand):
    help = 'Build and mark ready the incrementally maintained global show metric summaries.'

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

                    def report_progress(upper_id, max_id, batches):
                        self.stdout.write(
                            f'Processed Show IDs through {upper_id}/{max_id} '
                            f'({batches} batches)'
                        )

                    batches = rebuild_show_metric_summaries(
                        batch_size=batch_size,
                        progress_callback=report_progress,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Show metric summaries are ready after {batches} batches.'
            )
        )
