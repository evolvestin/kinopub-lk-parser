from django.db import migrations


THREED_TITLE_SUFFIX_PATTERN = r'\s*[\(\[\{]?\s*3\s*[-–—]?\s*[dд]\s*[\)\]\}]?\s*$'


def classify_legacy_3d_titles_and_merge(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        # Some old imports stored a 3D item as a normal Movie and only kept
        # the format marker in one of its titles.
        cursor.execute(
            """
            UPDATE app_show
            SET is_3d = TRUE,
                title = regexp_replace(title, %s, '', 'i'),
                original_title = regexp_replace(original_title, %s, '', 'i')
            WHERE type = 'Movie'
              AND (
                  title ~* %s
                  OR original_title ~* %s
              )
            """,
            [
                THREED_TITLE_SUFFIX_PATTERN,
                THREED_TITLE_SUFFIX_PATTERN,
                THREED_TITLE_SUFFIX_PATTERN,
                THREED_TITLE_SUFFIX_PATTERN,
            ],
        )
        # Merge only an unambiguous 3D group: exactly one non-3D canonical
        # row, plus one or more 3D source rows. This avoids collapsing two
        # unrelated same-name movies that happen to have no identity IDs.
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
                # Conflicting external identities are a signal to leave both
                # records intact for manual review.
                continue


class Migration(migrations.Migration):
    dependencies = [('app', '0085_repair_3d_title_regex')]

    operations = [
        migrations.RunPython(
            classify_legacy_3d_titles_and_merge,
            migrations.RunPython.noop,
        )
    ]
