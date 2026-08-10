from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0064_metric_detail_imdb_index'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='DROP INDEX CONCURRENTLY IF EXISTS "idx_show_tmdb_only";',
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[migrations.RemoveIndex(model_name='show', name='idx_show_tmdb_only')],
        )
    ]
