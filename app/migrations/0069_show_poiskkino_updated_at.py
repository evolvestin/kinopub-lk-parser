from django.db import migrations, models


def reset_old_backfill_markers(apps, schema_editor):
    # The old field meant "historical lookup completed", not "last Poiskkino
    # refresh". It cannot be used as a freshness timestamp after the policy
    # change, so force one complete three-day cycle.
    apps.get_model('app', 'Show').objects.filter(kinopoisk_url__isnull=False).exclude(
        kinopoisk_url=''
    ).update(poiskkino_updated_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0068_normalize_country_boundary_whitespace'),
    ]

    operations = [
        migrations.RenameField(
            model_name='show',
            old_name='poiskkino_backfill_checked_at',
            new_name='poiskkino_updated_at',
        ),
        migrations.AlterField(
            model_name='show',
            name='poiskkino_updated_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name='Poiskkino updated at',
            ),
        ),
        migrations.RunPython(reset_old_backfill_markers, migrations.RunPython.noop),
    ]
