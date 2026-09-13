from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0076_code_source_uid'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='kinopoisk_person_id',
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text=(
                    'Source person ID from the existing Poiskkino movie response; '
                    'not unique locally.'
                ),
                null=True,
                verbose_name='Kinopoisk person ID',
            ),
        ),
    ]
