from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0099_publicvisit_ip_address')]

    operations = [
        migrations.AddField(
            model_name='viewuser',
            name='webapp_theme',
            field=models.CharField(
                choices=[('dark', 'Dark'), ('light', 'Light')], default='dark', max_length=5
            ),
        ),
    ]
