from django.core.management.base import BaseCommand, CommandError

from app.services.person_photo_metric_summary import rebuild_person_photo_metric_summaries
from app.services.person_metric_summary import person_metric_summary_ready
from app.tasks import _redis_lock
from shared.constants import RedisLock


class Command(BaseCommand):
    help = 'Build incremental avatar counters and duplicate-photo groups.'

    def handle(self, *args, **options):
        if not person_metric_summary_ready():
            raise CommandError('Person metric summaries must be ready first.')

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

                    rows = rebuild_person_photo_metric_summaries()

        self.stdout.write(
            self.style.SUCCESS(
                f'Person photo metric summaries are ready for {rows:,} people.'
            )
        )
