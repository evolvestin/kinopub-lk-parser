from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [('app', '0072_kinopoisk_rating_available')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_missing_kp_rating" ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL AND "kinopoisk_url" <> \'\' '
                        'AND "kinopoisk_rating" IS NULL '
                        'AND "kinopoisk_rating_available";'
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_kp_unrated" ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL AND "kinopoisk_url" <> \'\' '
                        'AND "kinopoisk_rating" IS NULL '
                        'AND NOT "kinopoisk_rating_available" '
                        'AND "poiskkino_updated_at" IS NOT NULL;'
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_missing_kp_rating',
                        condition=Q(kinopoisk_url__isnull=False)
                        & ~Q(kinopoisk_url='')
                        & Q(kinopoisk_rating__isnull=True)
                        & Q(kinopoisk_rating_available=True),
                    ),
                ),
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_kp_unrated',
                        condition=Q(kinopoisk_url__isnull=False)
                        & ~Q(kinopoisk_url='')
                        & Q(kinopoisk_rating__isnull=True)
                        & Q(kinopoisk_rating_available=False)
                        & Q(poiskkino_updated_at__isnull=False),
                    ),
                ),
            ],
        )
    ]
