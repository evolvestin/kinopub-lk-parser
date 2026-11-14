from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0100_viewuser_webapp_theme'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_show_type_id_with_crew" ON "app_show" ("type", "id") '
                        'WHERE "type" IS NOT NULL AND "type" <> \'\';'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_type_id_with_crew";'
                    ),
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='show',
                    index=models.Index(
                        fields=['type', 'id'],
                        name='idx_show_type_id_with_crew',
                        condition=Q(type__isnull=False) & ~Q(type=''),
                    ),
                )
            ],
        )
    ]
