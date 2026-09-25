from django.db import migrations


def repair_zero_kp_rating_flags(apps, schema_editor):
    Show = apps.get_model('app', 'Show')
    ExternalRating = apps.get_model('app', 'ExternalRating')
    show_ids = ExternalRating.objects.filter(kp__isnull=True).values('show_id')
    Show.objects.filter(
        id__in=show_ids,
        kinopoisk_rating_available=True,
        kinopoisk_rating__isnull=False,
        kinopoisk_rating__lte=0,
        poiskkino_updated_at__isnull=False,
    ).update(
        kinopoisk_rating=None,
        kinopoisk_votes=None,
        kinopoisk_rating_available=False,
    )


class Migration(migrations.Migration):
    dependencies = [('app', '0091_person_name_not_unique')]

    operations = [
        migrations.RunPython(repair_zero_kp_rating_flags, migrations.RunPython.noop),
    ]
