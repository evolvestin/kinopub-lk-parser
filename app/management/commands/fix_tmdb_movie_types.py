import logging

from django.core.management.base import BaseCommand

from app.models import Show
from app.services.tmdb_client import TMDBClient
from shared.constants import SERIES_TYPES

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Find series records whose TMDB ID resolves to a movie and optionally change '
        'their type to Movie.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Persist corrections. Without this flag the command only reports candidates.',
        )
        parser.add_argument(
            '--show-id',
            type=int,
            help='Check only one local Show ID.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of records checked.',
        )

    def handle(self, *args, **options):
        queryset = Show.objects.filter(
            type__in=SERIES_TYPES,
            tmdb_id__isnull=False,
        ).order_by('id')
        if options.get('show_id'):
            queryset = queryset.filter(id=options['show_id'])
        if options.get('limit'):
            queryset = queryset[: options['limit']]

        client = TMDBClient()
        checked = 0
        candidates = 0
        fixed = 0
        errors = 0

        for show in queryset.iterator():
            checked += 1
            try:
                movie_details = client.get_details(show.tmdb_id, media_type='movie')
            except Exception as exc:
                errors += 1
                self.stderr.write(
                    self.style.WARNING(
                        f'ID {show.id} ({show.title}): TMDB check failed: {exc}'
                    )
                )
                continue

            if not movie_details:
                continue

            candidates += 1
            self.stdout.write(
                f'candidate: show_id={show.id} tmdb_id={show.tmdb_id} '
                f'title={show.title!r} type={show.type} -> Movie'
            )

            if options['apply']:
                show.type = 'Movie'
                show.save(update_fields=['type', 'updated_at'])
                fixed += 1

        action = 'fixed' if options['apply'] else 'would fix'
        self.stdout.write(
            self.style.SUCCESS(
                f'Checked: {checked}; candidates: {candidates}; {action}: {fixed}; '
                f'errors: {errors}'
            )
        )
