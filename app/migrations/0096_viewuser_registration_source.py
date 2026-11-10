from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0095_publicarticle_publicvisit'),
    ]

    operations = [
        migrations.AddField(
            model_name='viewuser',
            name='registration_source',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Источник перехода из Telegram deep link, например site.',
                max_length=100,
                verbose_name='Источник регистрации',
            ),
        ),
    ]
