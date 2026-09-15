from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower, Trim


def merge_legacy_3d_shows(apps, schema_editor):
    # Use the live model implementation so the migration applies exactly the
    # same relation-union rules as the explicit maintenance command.
    from app.models import Show
    from app.services.show_merge import ShowMergeConflictError, merge_show_records

    groups = (
        Show.objects.filter(type='Movie', is_3d=True, ignore_collision=False)
        .annotate(title_key=Lower(Trim('title')), original_title_key=Lower(Trim('original_title')))
        .values('year', 'title_key', 'original_title_key')
        .annotate(total=Count('id'))
        .order_by('year', 'title_key', 'original_title_key')
    )
    for group in groups.iterator():
        rows = list(
            Show.objects.filter(
                type='Movie',
                ignore_collision=False,
                year=group['year'],
                title__iexact=group['title_key'],
                original_title__iexact=group['original_title_key'],
            ).order_by('id')
        )
        if len(rows) < 2:
            continue

        canonical = next((row for row in rows if not row.is_3d), rows[0])
        for duplicate in rows:
            if duplicate.id == canonical.id:
                continue
            try:
                merge_show_records(canonical.id, duplicate.id)
            except ShowMergeConflictError:
                # An identity conflict is not safe to resolve during a
                # migration; leave that pair for the explicit command/admin.
                continue


class Migration(migrations.Migration):
    dependencies = [('app', '0081_show_3d_and_posters')]
    operations = [migrations.RunPython(merge_legacy_3d_shows, migrations.RunPython.noop)]
