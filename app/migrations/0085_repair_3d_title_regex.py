from django.db import migrations


THREED_TITLE_SUFFIX_PATTERN = r'\s*[\(\[\{]?\s*3\s*[-–—]?\s*[dд]\s*[\)\]\}]?\s*$'


def repair_3d_title_regex(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        # Bind the regex as a parameter. Using PostgreSQL E'...' here loses
        # the backslashes for some server settings and silently matches zero
        # rows, which is why the previous corrective migration was ineffective.
        cursor.execute(
            """
            UPDATE app_show
            SET title = regexp_replace(title, %s, '', 'i'),
                original_title = regexp_replace(original_title, %s, '', 'i')
            WHERE type = 'Movie' AND is_3d
            """,
            [THREED_TITLE_SUFFIX_PATTERN, THREED_TITLE_SUFFIX_PATTERN],
        )
        cursor.execute(
            """
            SELECT array_agg(id ORDER BY is_3d ASC, id ASC)
            FROM app_show
            WHERE type = 'Movie' AND NOT ignore_collision
            GROUP BY year, lower(trim(title)), lower(trim(original_title))
            HAVING bool_or(is_3d)
               AND bool_or(NOT is_3d)
               AND count(*) FILTER (WHERE NOT is_3d) = 1
               AND count(*) > 1
            """
        )
        groups = [row[0] for row in cursor.fetchall()]

    from app.services.show_merge import ShowMergeConflictError, merge_show_records

    for show_ids in groups:
        canonical_id = show_ids[0]
        for duplicate_id in show_ids[1:]:
            try:
                merge_show_records(canonical_id, duplicate_id)
            except ShowMergeConflictError:
                continue


class Migration(migrations.Migration):
    dependencies = [('app', '0084_repair_3d_merges_after_restore')]
    operations = [migrations.RunPython(repair_3d_title_regex, migrations.RunPython.noop)]
