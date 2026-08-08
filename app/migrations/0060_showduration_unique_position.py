from django.db import migrations, models
from django.db.models import Count


def deduplicate_show_durations(apps, schema_editor):
    ShowDuration = apps.get_model('app', 'ShowDuration')

    duplicate_keys = (
        ShowDuration.objects.values('show_id', 'season_number', 'episode_number')
        .annotate(row_count=Count('id'))
        .filter(row_count__gt=1)
    )

    for key in duplicate_keys.iterator():
        rows = ShowDuration.objects.filter(
            show_id=key['show_id'],
            season_number=key['season_number'],
            episode_number=key['episode_number'],
        ).order_by('is_estimated', '-updated_at', '-id')
        keep_id = rows.values_list('id', flat=True).first()
        rows.exclude(id=keep_id).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0059_showcrew_canonical_person'),
    ]

    operations = [
        migrations.RunPython(deduplicate_show_durations, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='showduration',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='showduration',
            constraint=models.UniqueConstraint(
                fields=('show', 'season_number', 'episode_number'),
                name='uniq_show_duration_position',
                nulls_distinct=False,
            ),
        ),
    ]
