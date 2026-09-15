from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import Lower, Trim

from app.models import Show
from app.services.show_merge import ShowMergeConflictError, merge_show_records


class Command(BaseCommand):
    help = 'Find and merge duplicate Movie records where one KinoPub copy is marked as 3D.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply the planned merges.')
        parser.add_argument('--limit', type=int, default=0, help='Maximum number of merges.')

    def handle(self, *args, **options):
        groups = (
            Show.objects.filter(type='Movie', is_3d=True, ignore_collision=False)
            .annotate(title_key=Lower(Trim('title')), original_title_key=Lower(Trim('original_title')))
            .values('year', 'title_key', 'original_title_key')
            .annotate(total=Count('id'))
            .filter(total__gte=1)
            .order_by('year', 'title_key', 'original_title_key')
        )
        candidates = []
        for group in groups:
            rows = list(
                Show.objects.filter(
                    type='Movie',
                    ignore_collision=False,
                    year=group['year'],
                    title__iexact=group['title_key'],
                    original_title__iexact=group['original_title_key'],
                ).order_by('id')
            )
            if len(rows) < 2:
                continue
            canonical = next((row for row in rows if not row.is_3d), rows[0])
            for duplicate in rows:
                if duplicate.id != canonical.id:
                    candidates.append((canonical.id, duplicate.id))

        if options['limit']:
            candidates = candidates[: options['limit']]

        mode = 'APPLY' if options['apply'] else 'DRY-RUN'
        self.stdout.write(f'Candidates: {len(candidates)} mode={mode}')
        if not options['apply']:
            for canonical_id, duplicate_id in candidates:
                self.stdout.write(f'  canonical={canonical_id} duplicate={duplicate_id}')
            return

        merged = 0
        skipped = 0
        for canonical_id, duplicate_id in candidates:
            try:
                merge_show_records(canonical_id, duplicate_id)
            except ShowMergeConflictError as exc:
                skipped += 1
                self.stderr.write(self.style.WARNING(f'Skipped {canonical_id} <- {duplicate_id}: {exc}'))
            else:
                merged += 1
        self.stdout.write(self.style.SUCCESS(f'Merged shows: {merged}; skipped conflicts: {skipped}'))
