from django.db import migrations


def reset_show_sequence(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('app_show', 'id'), COALESCE(MAX(id), 1)) FROM app_show;"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0051_alter_show_id'),
    ]

    operations = [
        migrations.RunPython(reset_show_sequence, reverse_code=migrations.RunPython.noop),
    ]