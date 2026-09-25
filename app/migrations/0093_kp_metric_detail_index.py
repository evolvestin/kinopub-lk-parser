from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [('app', '0092_repair_zero_kp_rating_flags')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_kp_detail_available" ON "app_show" ("type", "id") '
                        'WHERE "kinopoisk_url" IS NOT NULL '
                        'AND "kinopoisk_url" <> \'\' '
                        'AND "kinopoisk_rating_available";'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_kp_detail_available";'
                    ),
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_kp_detail_available',
                        condition=(
                            Q(kinopoisk_url__isnull=False)
                            & ~Q(kinopoisk_url='')
                            & Q(kinopoisk_rating_available=True)
                        ),
                    ),
                )
            ],
        )
    ]
