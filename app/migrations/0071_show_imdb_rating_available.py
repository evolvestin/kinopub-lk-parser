from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0070_repair_known_imdb_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='show',
            name='imdb_rating_available',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'IMDb published a rating for the current title in the latest ratings '
                    'dataset.'
                ),
                verbose_name='IMDb rating available',
            ),
        ),
    ]
