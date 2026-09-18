import urllib.parse

from django.core.cache import cache
from django.db import migrations


DUPLICATE_PHOTO_CACHE_VERSION_KEY = 'metrics:duplicate_photo_urls:cache_version'


def normalize_proxy_url(value):
    if not value:
        return value

    parsed = urllib.parse.urlparse(value)
    if parsed.path.rstrip('/') == '/api/image_proxy':
        return urllib.parse.parse_qs(parsed.query).get('url', [None])[0] or value
    return value


def repair_rejected_person_photos(apps, schema_editor):
    RejectedPersonPhoto = apps.get_model('app', 'RejectedPersonPhoto')
    Person = apps.get_model('app', 'Person')

    for rejected in RejectedPersonPhoto.objects.all().iterator():
        normalized_url = normalize_proxy_url(rejected.photo_url)
        if normalized_url == rejected.photo_url:
            continue

        duplicate = RejectedPersonPhoto.objects.filter(
            person_id=rejected.person_id,
            photo_url=normalized_url,
        ).exclude(pk=rejected.pk).first()
        if duplicate:
            rejected.delete()
        else:
            rejected.photo_url = normalized_url
            rejected.save(update_fields=['photo_url'])

    rejected_by_person = {}
    for row in RejectedPersonPhoto.objects.values('person_id', 'photo_url').iterator():
        rejected_by_person.setdefault(row['person_id'], set()).add(row['photo_url'])

    for person in Person.objects.filter(pk__in=rejected_by_person):
        if person.tmdb_photo_url in rejected_by_person[person.pk]:
            person.tmdb_photo_url = None
            person.is_photo_fetched = False
            person.save(update_fields=['tmdb_photo_url', 'is_photo_fetched'])

    version = cache.get(DUPLICATE_PHOTO_CACHE_VERSION_KEY, 1)
    cache.set(DUPLICATE_PHOTO_CACHE_VERSION_KEY, int(version) + 1, timeout=None)
    cache.delete('metrics:duplicate_photo_urls:warmup_lock')
    cache.delete('metrics:all:warmup_lock')


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0088_telegram_backup'),
    ]

    operations = [
        migrations.RunPython(repair_rejected_person_photos, migrations.RunPython.noop),
    ]
