from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.operations import AddIndexConcurrently, CreateExtension
from django.db import migrations
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('app', '0060_showduration_unique_position'),
    ]

    operations = [
        CreateExtension('pg_trgm'),
        AddIndexConcurrently(
            model_name='show',
            index=GinIndex(
                OpClass(Upper('title'), name='gin_trgm_ops'),
                name='idx_show_title_upper_trgm',
            ),
        ),
        AddIndexConcurrently(
            model_name='show',
            index=GinIndex(
                OpClass(Upper('original_title'), name='gin_trgm_ops'),
                name='idx_show_original_upper_trgm',
            ),
        ),
        AddIndexConcurrently(
            model_name='show',
            index=GinIndex(
                OpClass(Upper('plot'), name='gin_trgm_ops'),
                name='idx_show_plot_upper_trgm',
            ),
        ),
        AddIndexConcurrently(
            model_name='person',
            index=GinIndex(
                OpClass(Upper('name'), name='gin_trgm_ops'),
                name='idx_person_name_upper_trgm',
            ),
        ),
        AddIndexConcurrently(
            model_name='person',
            index=GinIndex(
                OpClass(Upper('en_name'), name='gin_trgm_ops'),
                name='idx_person_en_name_upper_trgm',
            ),
        ),
    ]
