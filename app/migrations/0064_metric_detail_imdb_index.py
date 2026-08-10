from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0063_metric_detail_indexes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_missing_imdb" ON "app_show" ("type", "id") '
                        'WHERE "imdb_url" IS NOT NULL AND "imdb_url" <> \'\';'
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_missing_imdb',
                        condition=Q(imdb_url__isnull=False) & ~Q(imdb_url=''),
                    ),
                )
            ],
        )
    ]
