from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0086_classify_legacy_3d_title_suffixes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_crew_canonical_person" '
                        'ON "app_showcrew" ("canonical_person_id");'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_crew_canonical_person";'
                    ),
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='showcrew',
                    index=models.Index(
                        fields=['canonical_person'],
                        name='idx_crew_canonical_person',
                    ),
                )
            ],
        )
    ]
