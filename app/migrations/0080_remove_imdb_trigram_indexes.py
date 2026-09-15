from django.db import migrations


class Migration(migrations.Migration):
    """Remove indexes left by the long-running IMDb search migration."""

    atomic = False

    dependencies = [
        ('app', '0079_show_imdb_search_trigram_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'DROP INDEX CONCURRENTLY IF EXISTS '
                '"idx_show_imdb_id_upper_trgm";',
                'DROP INDEX CONCURRENTLY IF EXISTS '
                '"idx_show_imdb_url_upper_trgm";',
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
