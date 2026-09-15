from django.conf import settings
from django.db import migrations, models
from django.db.models.deletion import CASCADE
from django.db.models import Q


def normalize_3d_shows(apps, schema_editor):
    Show = apps.get_model('app', 'Show')
    ShowPoster = apps.get_model('app', 'ShowPoster')
    poster_base = settings.POSTER_BASE_URL.rstrip('/')

    Show.objects.filter(type__iexact='3D Movie').update(type='Movie', is_3d=True)
    Show.objects.filter(type__iexact='3d').update(type='Movie', is_3d=True)
    for show in Show.objects.filter(kinopub_id__isnull=False).only('id', 'kinopub_id', 'is_3d'):
        ShowPoster.objects.get_or_create(
            source='kinopub',
            external_id=show.kinopub_id,
            defaults={
                'show_id': show.id,
                'variant': '3d' if show.is_3d else 'main',
                'url': f'{poster_base}/big/{show.kinopub_id}.jpg',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('app', '0080_remove_imdb_trigram_indexes')]

    operations = [
        migrations.AddField(
            model_name='show',
            name='is_3d',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='У фильма существует отдельная 3D-версия в источнике KinoPub.',
                verbose_name='Есть 3D-копия',
            ),
        ),
        migrations.CreateModel(
            name='ShowPoster',
            fields=[
                (
                    'id',
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'source',
                    models.CharField(
                        choices=[('kinopub', 'KinoPub'), ('tmdb', 'TMDB'), ('kinopoisk', 'Kinopoisk')],
                        max_length=20,
                    ),
                ),
                (
                    'variant',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='Например, main или 3d для разных копий одного источника.',
                        max_length=20,
                    ),
                ),
                ('external_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('url', models.URLField(blank=True, max_length=1000)),
                (
                    'show',
                    models.ForeignKey(
                        on_delete=CASCADE,
                        related_name='posters',
                        to='app.show',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Show poster',
                'verbose_name_plural': 'Show posters',
                'indexes': [models.Index(fields=['show', 'source'], name='app_showpos_show_id_0d20d2_idx')],
                'constraints': [
                    models.UniqueConstraint(
                        condition=Q(external_id__isnull=False),
                        fields=('source', 'external_id'),
                        name='uniq_show_poster_source_external_id',
                    ),
                    models.UniqueConstraint(
                        fields=('show', 'source', 'variant'),
                        name='uniq_show_poster_variant',
                    ),
                ],
            },
        ),
        migrations.RunPython(normalize_3d_shows, migrations.RunPython.noop),
    ]
