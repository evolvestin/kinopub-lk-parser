import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from app.models import Person
from app.services.metrics import invalidate_duplicate_photo_urls_cache


class Command(BaseCommand):
    help = (
        'Clear duplicate TMDB photos only from canonical Persons without a TMDB ID. '
        'Dry-run by default; this does not delete Persons or relations.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Clear the selected photo fields. Without this flag the command is read-only.',
        )
        parser.add_argument(
            '--audit-file',
            help='Optional CSV path to write the exact rows selected before applying changes.',
        )

    def handle(self, *args, **options):
        duplicate_urls = (
            Person.objects.filter(master_person__isnull=True)
            .exclude(tmdb_photo_url__isnull=True)
            .exclude(tmdb_photo_url='')
            .values('tmdb_photo_url')
            .annotate(row_count=Count('id'))
            .filter(row_count__gt=1)
            .values('tmdb_photo_url')
        )
        selected = (
            Person.objects.filter(
                master_person__isnull=True,
                tmdb_id__isnull=True,
                tmdb_photo_url__in=duplicate_urls,
            )
            .only(
                'id',
                'name',
                'en_name',
                'tmdb_photo_url',
                'kp_photo_url',
                'is_photo_fetched',
            )
            .order_by('id')
        )

        row_count = selected.count()
        group_count = selected.values('tmdb_photo_url').distinct().count()
        self.stdout.write(
            f'Candidates: rows={row_count} groups={group_count} '
            f'mode={"APPLY" if options["apply"] else "DRY-RUN"}'
        )

        audit_file = options.get('audit_file')
        if audit_file:
            path = Path(audit_file)
            if path.exists() and options['apply']:
                raise CommandError(f'Refusing to overwrite existing audit file: {path}')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    [
                        'id',
                        'name',
                        'en_name',
                        'tmdb_photo_url',
                        'kp_photo_url',
                        'is_photo_fetched',
                    ]
                )
                for person in selected.iterator(chunk_size=5000):
                    writer.writerow(
                        [
                            person.id,
                            person.name,
                            person.en_name,
                            person.tmdb_photo_url,
                            person.kp_photo_url,
                            person.is_photo_fetched,
                        ]
                    )
            self.stdout.write(f'Audit written: {path}')

        if not options['apply']:
            return

        with transaction.atomic():
            updated = selected.update(
                tmdb_photo_url=None,
                is_photo_fetched=False,
            )
        if updated != row_count:
            raise CommandError(f'Unexpected update count: selected={row_count}, updated={updated}')

        invalidate_duplicate_photo_urls_cache()
        self.stdout.write(self.style.SUCCESS(f'Cleared TMDB photos: {updated}'))
