import re
from django.db import migrations


def populate_imdb_ids(apps, schema_editor):
    Show = apps.get_model('app', 'Show')

    existing_imdb_ids = set(
        Show.objects.exclude(imdb_id__isnull=True)
        .exclude(imdb_id='')
        .values_list('imdb_id', flat=True)
    )

    shows_to_update = []
    seen_in_batch = set()

    qs = Show.objects.exclude(imdb_url__isnull=True).exclude(imdb_url='').filter(imdb_id__isnull=True)

    for show in qs.iterator():
        match = re.search(r'(tt\d+)', show.imdb_url)
        if match:
            extracted_id = match.group(1)
            if extracted_id not in existing_imdb_ids and extracted_id not in seen_in_batch:
                show.imdb_id = extracted_id
                shows_to_update.append(show)
                seen_in_batch.add(extracted_id)

    if shows_to_update:
        Show.objects.bulk_update(shows_to_update, fields=['imdb_id'], batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0054_person_tmdb_id_show_imdb_id_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_imdb_ids, reverse_code=migrations.RunPython.noop),
    ]