from django.db import migrations


class Migration(migrations.Migration):
    """Repair databases that applied the first draft of migration 0061."""

    atomic = False

    dependencies = [
        ('app', '0061_search_trigram_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_title_trgm";',
                'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_original_title_trgm";',
                'DROP INDEX CONCURRENTLY IF EXISTS "idx_show_plot_trgm";',
                'DROP INDEX CONCURRENTLY IF EXISTS "idx_person_name_trgm";',
                'DROP INDEX CONCURRENTLY IF EXISTS "idx_person_en_name_trgm";',
                (
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    '"idx_show_title_upper_trgm" ON "app_show" USING gin '
                    '((UPPER("title")) gin_trgm_ops);'
                ),
                (
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    '"idx_show_original_upper_trgm" ON "app_show" USING gin '
                    '((UPPER("original_title")) gin_trgm_ops);'
                ),
                (
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    '"idx_show_plot_upper_trgm" ON "app_show" USING gin '
                    '((UPPER("plot")) gin_trgm_ops);'
                ),
                (
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    '"idx_person_name_upper_trgm" ON "app_person" USING gin '
                    '((UPPER("name")) gin_trgm_ops);'
                ),
                (
                    'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                    '"idx_person_en_name_upper_trgm" ON "app_person" USING gin '
                    '((UPPER("en_name")) gin_trgm_ops);'
                ),
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
