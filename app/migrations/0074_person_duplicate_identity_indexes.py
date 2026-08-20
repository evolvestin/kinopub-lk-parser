from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [('app', '0073_kinopoisk_rating_metric_indexes')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_tmdb_dupe_identity" '
                        'ON "app_person" ("tmdb_photo_url", "tmdb_id") '
                        'WHERE "master_person_id" IS NULL AND "tmdb_photo_url" <> \'\';'
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_kp_dupe_identity" '
                        'ON "app_person" ("kp_photo_url", "tmdb_id") '
                        'WHERE "master_person_id" IS NULL AND "kp_photo_url" <> \'\';'
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['tmdb_photo_url', 'tmdb_id'],
                        name='idx_person_tmdb_dupe_identity',
                        condition=Q(master_person__isnull=True)
                        & Q(tmdb_photo_url__isnull=False)
                        & ~Q(tmdb_photo_url=''),
                    ),
                ),
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['kp_photo_url', 'tmdb_id'],
                        name='idx_person_kp_dupe_identity',
                        condition=Q(master_person__isnull=True)
                        & Q(kp_photo_url__isnull=False)
                        & ~Q(kp_photo_url=''),
                    ),
                ),
            ],
        )
    ]
