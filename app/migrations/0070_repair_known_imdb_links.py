from django.db import migrations

KNOWN_FIXES = (
    {
        'kinopub_id': 66502,
        'imdb_id': 'tt9104218',
        'imdb_url': 'https://www.imdb.com/title/tt9104218/',
        'imdb_rating': 8.6,
        'imdb_votes': 31,
    },
    {
        'kinopub_id': 44515,
        'imdb_id': 'tt31050020',
        'imdb_url': 'https://www.imdb.com/title/tt31050020/',
        'imdb_rating': 7.1,
        'imdb_votes': 2701,
    },
)


def repair_known_imdb_links(apps, schema_editor):
    Show = apps.get_model('app', 'Show')
    ExternalRating = apps.get_model('app', 'ExternalRating')

    for fix in KNOWN_FIXES:
        target = Show.objects.filter(kinopub_id=fix['kinopub_id']).first()
        if not target:
            continue

        conflicting_show = Show.objects.filter(imdb_id=fix['imdb_id']).exclude(pk=target.pk).first()
        if conflicting_show:
            # Keep the IMDb identity on the KinoPub record. The imported TMDB
            # duplicate remains available by title/TMDB ID but must not own it.
            if conflicting_show.kinopub_id is not None:
                continue
            conflicting_show.imdb_id = None
            conflicting_show.save(update_fields=['imdb_id'])

        target.imdb_id = fix['imdb_id']
        target.imdb_url = fix['imdb_url']
        target.imdb_rating = fix['imdb_rating']
        target.imdb_votes = fix['imdb_votes']
        target.save(update_fields=['imdb_id', 'imdb_url', 'imdb_rating', 'imdb_votes'])

        ExternalRating.objects.filter(show_id=target.pk).update(imdb=fix['imdb_rating'])


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0069_show_poiskkino_updated_at'),
    ]

    operations = [
        migrations.RunPython(repair_known_imdb_links, reverse_code=migrations.RunPython.noop),
    ]
