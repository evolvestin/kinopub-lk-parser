from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0097_publicarticle_content_blocks'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicvisit',
            name='visitor_fingerprint',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='pages',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='referrer_host',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='user_agent',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='accept_language',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='browser',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='operating_system',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='publicvisit',
            name='device_type',
            field=models.CharField(blank=True, max_length=24),
        ),
    ]
