from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0089_repair_rejected_person_photo_urls'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_photo_updated" ON "app_person" '
                        '("updated_at" DESC) WHERE "is_photo_fetched";'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_person_photo_updated";'
                    ),
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['-updated_at'],
                        name='idx_person_photo_updated',
                        condition=models.Q(is_photo_fetched=True),
                    ),
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_showduration_updated" ON "app_showduration" '
                        '("updated_at" DESC);'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS "idx_showduration_updated";'
                    ),
                )
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='showduration',
                    index=models.Index(
                        fields=['-updated_at'],
                        name='idx_showduration_updated',
                    ),
                )
            ],
        ),
    ]
