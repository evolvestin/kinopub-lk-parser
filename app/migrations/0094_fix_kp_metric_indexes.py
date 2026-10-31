from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [('app', '0093_kp_metric_detail_index')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_missing_kp_v2" ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL AND "kinopoisk_url" <> \'\' '
                        'AND "kinopoisk_rating_available";'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_missing_kp_v2";'
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_kp_unrated_v2" ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL AND "kinopoisk_url" <> \'\' '
                        'AND NOT "kinopoisk_rating_available" '
                        'AND "poiskkino_updated_at" IS NOT NULL;'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_kp_unrated_v2";'
                    ),
                ),
                migrations.RunSQL(
                    sql='DROP INDEX CONCURRENTLY IF EXISTS "idx_show_missing_kp_rating";',
                    reverse_sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_missing_kp_rating" ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL AND "kinopoisk_url" <> \'\' '
                        'AND "kinopoisk_rating" IS NULL AND "kinopoisk_rating_available";'
                    ),
                ),
                migrations.RunSQL(
                    sql='DROP INDEX CONCURRENTLY IF EXISTS "idx_show_kp_unrated";',
                    reverse_sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_kp_unrated" '
                        'ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL AND "kinopoisk_url" <> \'\' '
                        'AND "kinopoisk_rating" IS NULL '
                        'AND NOT "kinopoisk_rating_available" '
                        'AND "poiskkino_updated_at" IS NOT NULL;'
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='show', name='idx_show_missing_kp_rating'
                ),
                migrations.RemoveIndex(model_name='show', name='idx_show_kp_unrated'),
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_missing_kp_v2',
                        condition=Q(kinopoisk_url__isnull=False)
                        & ~Q(kinopoisk_url='')
                        & Q(kinopoisk_rating_available=True),
                    ),
                ),
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_kp_unrated_v2',
                        condition=Q(kinopoisk_url__isnull=False)
                        & ~Q(kinopoisk_url='')
                        & Q(kinopoisk_rating_available=False)
                        & Q(poiskkino_updated_at__isnull=False),
                    ),
                ),
            ],
        )
    ]
