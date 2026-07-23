from django.db import migrations, models


def copy_id_to_kinopub_id(apps, schema_editor):
    Show = apps.get_model('app', 'Show')
    Show.objects.filter(kinopub_id__isnull=True).update(kinopub_id=models.F('id'))


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0049_rejectedpersonphoto'),
    ]

    operations = [
        migrations.AddField(
            model_name='show',
            name='kinopub_id',
            field=models.IntegerField(
                blank=True,
                db_index=True,
                null=True,
                unique=True,
                verbose_name='KinoPub ID',
            ),
        ),
        migrations.RunPython(copy_id_to_kinopub_id, reverse_code=migrations.RunPython.noop),
    ]
