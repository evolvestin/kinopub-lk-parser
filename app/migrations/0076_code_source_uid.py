from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0075_alter_showcrew_profession_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='code',
            name='source_uid',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
