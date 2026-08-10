from django.db import migrations, models
from django.db.models import Q

SHOW_INDEXES = [
    models.Index(
        fields=['type', 'id'], name='idx_show_kp_type_id', condition=Q(kinopub_id__isnull=False)
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_tmdb_type_id',
        condition=Q(tmdb_id__isnull=False) & Q(kinopub_id__isnull=True),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_kp_missing_plot',
        condition=Q(kinopub_id__isnull=False) & (Q(plot__isnull=True) | Q(plot='')),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_kp_missing_year',
        condition=Q(kinopub_id__isnull=False) & Q(year__isnull=True),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_kp_missing_status',
        condition=Q(kinopub_id__isnull=False) & (Q(status__isnull=True) | Q(status='')),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_kp_missing_imdb_id',
        condition=Q(kinopub_id__isnull=False) & (Q(imdb_id__isnull=True) | Q(imdb_id='')),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_tmdb_missing_year',
        condition=Q(tmdb_id__isnull=False) & Q(kinopub_id__isnull=True) & Q(year__isnull=True),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_tmdb_missing_status',
        condition=Q(tmdb_id__isnull=False)
        & Q(kinopub_id__isnull=True)
        & (Q(status__isnull=True) | Q(status='')),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_tmdb_missing_plot',
        condition=Q(tmdb_id__isnull=False)
        & Q(kinopub_id__isnull=True)
        & (Q(plot__isnull=True) | Q(plot='')),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_tmdb_only',
        condition=Q(tmdb_id__isnull=False) & Q(kinopub_id__isnull=True),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_missing_tmdb',
        condition=Q(kinopub_id__isnull=False) & Q(tmdb_id__isnull=True),
    ),
    models.Index(
        fields=['type', 'id'],
        name='idx_show_tmdb_no_kp',
        condition=Q(tmdb_id__isnull=False) & (Q(kinopoisk_url__isnull=True) | Q(kinopoisk_url='')),
    ),
]


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0062_search_upper_trigram_indexes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_kp_type_id" ON "app_show" ("type", "id") WHERE "kinopub_id" IS NOT NULL;',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_tmdb_type_id" ON "app_show" ("type", "id") WHERE "tmdb_id" IS NOT NULL AND "kinopub_id" IS NULL;',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_kp_missing_plot" ON "app_show" ("type", "id") WHERE "kinopub_id" IS NOT NULL AND ("plot" IS NULL OR "plot" = \'\');',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_kp_missing_year" ON "app_show" ("type", "id") WHERE "kinopub_id" IS NOT NULL AND "year" IS NULL;',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_kp_missing_status" ON "app_show" ("type", "id") WHERE "kinopub_id" IS NOT NULL AND ("status" IS NULL OR "status" = \'\');',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_kp_missing_imdb_id" ON "app_show" ("type", "id") WHERE "kinopub_id" IS NOT NULL AND ("imdb_id" IS NULL OR "imdb_id" = \'\');',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_tmdb_missing_year" ON "app_show" ("type", "id") WHERE "tmdb_id" IS NOT NULL AND "kinopub_id" IS NULL AND "year" IS NULL;',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_tmdb_missing_status" ON "app_show" ("type", "id") WHERE "tmdb_id" IS NOT NULL AND "kinopub_id" IS NULL AND ("status" IS NULL OR "status" = \'\');',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_tmdb_missing_plot" ON "app_show" ("type", "id") WHERE "tmdb_id" IS NOT NULL AND "kinopub_id" IS NULL AND ("plot" IS NULL OR "plot" = \'\');',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_tmdb_only" ON "app_show" ("type", "id") WHERE "tmdb_id" IS NOT NULL AND "kinopub_id" IS NULL;',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_missing_tmdb" ON "app_show" ("type", "id") WHERE "kinopub_id" IS NOT NULL AND "tmdb_id" IS NULL;',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_show_tmdb_no_kp" ON "app_show" ("type", "id") WHERE "tmdb_id" IS NOT NULL AND ("kinopoisk_url" IS NULL OR "kinopoisk_url" = \'\');',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_person_tmdb_dupe_source" ON "app_person" ("tmdb_photo_url") WHERE "master_person_id" IS NULL AND "tmdb_photo_url" IS NOT NULL AND "tmdb_photo_url" <> \'\';',
                        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_person_kp_dupe_source" ON "app_person" ("kp_photo_url") WHERE "master_person_id" IS NULL AND "kp_photo_url" IS NOT NULL AND "kp_photo_url" <> \'\';',
                    ],
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                *[migrations.AddIndex(model_name='show', index=index) for index in SHOW_INDEXES],
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['tmdb_photo_url'],
                        name='idx_person_tmdb_dupe_source',
                        condition=Q(master_person__isnull=True)
                        & Q(tmdb_photo_url__isnull=False)
                        & ~Q(tmdb_photo_url=''),
                    ),
                ),
                migrations.AddIndex(
                    model_name='person',
                    index=models.Index(
                        fields=['kp_photo_url'],
                        name='idx_person_kp_dupe_source',
                        condition=Q(master_person__isnull=True)
                        & Q(kp_photo_url__isnull=False)
                        & ~Q(kp_photo_url=''),
                    ),
                ),
            ],
        ),
    ]
