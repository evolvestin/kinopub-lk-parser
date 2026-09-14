from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations
from django.db.models.functions import Upper
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0078_show_imdb_rating_updated_at'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='show',
            index=GinIndex(
                OpClass(Upper('imdb_id'), name='gin_trgm_ops'),
                name='idx_show_imdb_id_upper_trgm',
            ),
        ),
        AddIndexConcurrently(
            model_name='show',
            index=GinIndex(
                OpClass(Upper('imdb_url'), name='gin_trgm_ops'),
                name='idx_show_imdb_url_upper_trgm',
            ),
        ),
    ]
