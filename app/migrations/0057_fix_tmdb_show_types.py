from django.db import migrations


def normalize_show_types(apps, schema_editor):
    Show = apps.get_model('app', 'Show')
    Show.objects.filter(type='movie').update(type='Movie')
    Show.objects.filter(type='serial').update(type='Series')


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0056_alter_showcrew_en_profession_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_show_types, reverse_code=migrations.RunPython.noop),
    ]
