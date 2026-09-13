from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0077_person_kinopoisk_person_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='show',
            name='imdb_rating_updated_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='The last time the official IMDb ratings dataset updated this title.',
                null=True,
                verbose_name='IMDb rating updated at',
            ),
        ),
    ]
