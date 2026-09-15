from django.db import migrations


def repair_3d_merges_after_restore(apps, schema_editor):
    """Repair 3D data restored from a backup with migration history intact."""
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
                continue


class Migration(migrations.Migration):
    dependencies = [('app', '0083_normalize_3d_titles_and_merge')]
    operations = [
        migrations.RunPython(repair_3d_merges_after_restore, migrations.RunPython.noop)
    ]
