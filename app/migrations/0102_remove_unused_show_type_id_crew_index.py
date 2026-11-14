from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0101_show_type_id_crew_metric_index'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='DROP INDEX CONCURRENTLY IF EXISTS "idx_show_type_id_with_crew";',
                    reverse_sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_type_id_with_crew" ON "app_show" ("type", "id") '
                        'WHERE "type" IS NOT NULL AND "type" <> \'\';'
                    ),
                )
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='show',
                    name='idx_show_type_id_with_crew',
                ),
            ],
        )
    ]
