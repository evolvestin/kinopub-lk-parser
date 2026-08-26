from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0074_person_duplicate_identity_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='showcrew',
            name='en_profession',
            field=models.TextField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='showcrew',
            name='profession',
            field=models.TextField(blank=True, db_index=True, null=True),
        ),
    ]
