from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0109_personphotogroup_idx_personphotogroup_page'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_tmdb_dupe_source_v2" ON "app_person" '
                        '("tmdb_photo_url", "id") '
                        'WHERE "master_person_id" IS NULL '
                        'AND "tmdb_photo_url" IS NOT NULL AND "tmdb_photo_url" <> \'\';'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS '
                        '"idx_person_tmdb_dupe_source_v2";'
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_kp_dupe_source_v2" ON "app_person" '
                        '("kp_photo_url", "id") '
                        'WHERE "master_person_id" IS NULL '
                        'AND "kp_photo_url" IS NOT NULL AND "kp_photo_url" <> \'\';'
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS '
                        '"idx_person_kp_dupe_source_v2";'
                    ),
                ),
                migrations.RunSQL(
                    sql='DROP INDEX CONCURRENTLY IF EXISTS "idx_person_tmdb_dupe_source";',
                    reverse_sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_tmdb_dupe_source" ON "app_person" ("tmdb_photo_url") '
                        'WHERE "master_person_id" IS NULL '
                        'AND "tmdb_photo_url" IS NOT NULL AND "tmdb_photo_url" <> \'\';'
                    ),
                ),
                migrations.RunSQL(
                    sql='DROP INDEX CONCURRENTLY IF EXISTS "idx_person_kp_dupe_source";',
                    reverse_sql=(
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                        '"idx_person_kp_dupe_source" ON "app_person" ("kp_photo_url") '
                        'WHERE "master_person_id" IS NULL '
                        'AND "kp_photo_url" IS NOT NULL AND "kp_photo_url" <> \'\';'
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='person',
                    name='idx_person_tmdb_dupe_source',
                ),
                migrations.RemoveIndex(
                    model_name='person',
                    name='idx_person_kp_dupe_source',
                ),
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['tmdb_photo_url', 'id'],
                        name='idx_person_tmdb_dupe_source_v2',
                        condition=Q(master_person__isnull=True)
                        & Q(tmdb_photo_url__isnull=False)
                        & ~Q(tmdb_photo_url=''),
                    ),
                ),
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['kp_photo_url', 'id'],
                        name='idx_person_kp_dupe_source_v2',
                        condition=Q(master_person__isnull=True)
                        & Q(kp_photo_url__isnull=False)
                        & ~Q(kp_photo_url=''),
                    ),
                ),
            ],
        ),
    ]
