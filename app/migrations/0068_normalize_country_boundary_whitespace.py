from collections import defaultdict

from django.db import migrations, models
from django.db.models.functions import Trim


def normalize_country_names(apps, schema_editor):
    Country = apps.get_model('app', 'Country')
    Show = apps.get_model('app', 'Show')
    show_countries = Show.countries.through

    grouped = defaultdict(list)
    for country in Country.objects.order_by('id'):
        grouped[country.name.strip()].append(country)

    for normalized_name, countries in grouped.items():
        if not normalized_name:
            raise RuntimeError(f'Country {countries[0].pk} has an empty name after trimming')

        master = min(
            countries,
            key=lambda country: (
                not bool(country.iso_code),
                not bool(country.emoji_flag),
                country.id,
            ),
        )

        for duplicate in countries:
            if duplicate.pk == master.pk:
                continue

            show_ids = show_countries.objects.filter(country_id=duplicate.pk).values_list(
                'show_id', flat=True
            )
            show_countries.objects.bulk_create(
                [show_countries(show_id=show_id, country_id=master.pk) for show_id in show_ids],
                ignore_conflicts=True,
            )
            show_countries.objects.filter(country_id=duplicate.pk).delete()
            duplicate.delete()

        master.name = normalized_name
        if not master.iso_code:
            master.iso_code = next(
                (country.iso_code for country in countries if country.iso_code), None
            )
        if not master.emoji_flag:
            master.emoji_flag = next(
                (country.emoji_flag for country in countries if country.emoji_flag), None
            )
        master.save()


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0067_show_poiskkino_backfill_checked_at'),
    ]

    operations = [
        migrations.RunPython(normalize_country_names, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='country',
            constraint=models.CheckConstraint(
                condition=models.Q(name=Trim('name')),
                name='country_name_no_outer_whitespace',
            ),
        ),
    ]
