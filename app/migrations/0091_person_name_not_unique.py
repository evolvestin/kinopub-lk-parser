from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0090_metrics_last_action_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='name',
            field=models.CharField(max_length=255),
        ),
    ]
