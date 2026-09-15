from django.db import migrations


def normalize_titles_and_merge(apps, schema_editor):
    # The first legacy migration normalized the type, but not titles such as
    # "300: Rise of an Empire 3D". Normalize those markers before grouping so
    # the 3D copy can match the ordinary movie row.
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            r"""
            UPDATE app_show
            SET title = regexp_replace(
                    title,
                    E'\s*[\(\[\{]?\s*3\s*[-–—]?\s*[dд]\s*[\)\]\}]?\s*$',
                    '', 'i'
                ),
                original_title = regexp_replace(
                    original_title,
                    E'\s*[\(\[\{]?\s*3\s*[-–—]?\s*[dд]\s*[\)\]\}]?\s*$',
                    '', 'i'
                )
            WHERE type = 'Movie' AND is_3d
            """
        )
        cursor.execute(
            """
            SELECT year, lower(trim(title)), lower(trim(original_title)),
                   array_agg(id ORDER BY is_3d ASC, id ASC)
            FROM app_show
            WHERE type = 'Movie' AND NOT ignore_collision
            GROUP BY year, lower(trim(title)), lower(trim(original_title))
            HAVING bool_or(is_3d) AND count(*) > 1
            ORDER BY year, lower(trim(title)), lower(trim(original_title))
            """
        )
        groups = cursor.fetchall()

    from app.services.show_merge import ShowMergeConflictError, merge_show_records

    for _year, _title, _original_title, show_ids in groups:
        canonical_id = show_ids[0]
        for duplicate_id in show_ids[1:]:
            try:
                merge_show_records(canonical_id, duplicate_id)
            except ShowMergeConflictError:
                # Keep ambiguous identity conflicts available for the explicit
                # maintenance command instead of risking data loss in migrate.
                continue


class Migration(migrations.Migration):
    dependencies = [('app', '0082_merge_legacy_3d_shows')]
    operations = [migrations.RunPython(normalize_titles_and_merge, migrations.RunPython.noop)]
