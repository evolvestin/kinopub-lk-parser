import csv
import gzip
import logging
import os
import re
import tempfile
from collections import defaultdict

import requests
from django.conf import settings
from django.db.models import Q

from app.management.base import LoggableBaseCommand
from app.models import ExternalRating, Show

logger = logging.getLogger(__name__)
IMDB_ID_PATTERN = re.compile(r'(tt\d+)', re.IGNORECASE)

IMDB_DATASETS = {
    'basics': 'title.basics.tsv.gz',
    'ratings': 'title.ratings.tsv.gz',
}
SUPPORTED_TITLE_TYPES = {
    'movie': 'Movie',
    'tvMovie': 'Movie',
    'tvSpecial': 'Movie',
    'tvShort': 'Movie',
    'tvSeries': 'Series',
    'tvMiniSeries': 'Series',
}


class Command(LoggableBaseCommand):
    help = (
        'Downloads the official daily IMDb datasets, updates IMDb ratings, '
        'and optionally adds rated movies/series missing from the local catalog.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-add-missing',
            action='store_false',
            dest='add_missing',
            default=True,
            help='Only update existing shows; do not create missing IMDb titles.',
        )
        parser.add_argument(
            '--types',
            default=','.join(SUPPORTED_TITLE_TYPES),
            help='Comma-separated IMDb titleType values to import.',
        )
        parser.add_argument('--batch-size', type=int, default=5000)

    def handle(self, *args, **options):
        requested_types = {value.strip() for value in options['types'].split(',') if value.strip()}
        title_types = {
            title_type: SUPPORTED_TITLE_TYPES[title_type]
            for title_type in requested_types
            if title_type in SUPPORTED_TITLE_TYPES
        }
        if not title_types:
            self.stderr.write('No supported IMDb title types were requested.')
            return

        batch_size = max(100, options['batch_size'])
        paths = {}
        try:
            for name, filename in IMDB_DATASETS.items():
                paths[name] = self._download_dataset(filename)
                logger.info('Downloaded IMDb %s dataset to %s.', name, paths[name])

            rated_ids = None
            if options['add_missing']:
                rated_ids = self._collect_rated_ids(paths['ratings'])
                logger.info('IMDb ratings contain %s rated titles.', len(rated_ids))

            existing_ids = set(
                Show.objects.exclude(imdb_id__isnull=True)
                .exclude(imdb_id='')
                .values_list('imdb_id', flat=True)
            )
            basics_stats = self._process_basics(
                paths['basics'],
                title_types,
                existing_ids,
                rated_ids,
                options['add_missing'],
                batch_size,
            )
            imdb_url_map = self._build_imdb_url_map()
            self._reset_imdb_rating_availability()
            rating_stats = self._process_ratings(paths['ratings'], batch_size, imdb_url_map)
            logger.info(
                'IMDb sync complete: basics=%s, new=%s, ratings=%s, URL fallbacks=%s, '
                'IDs backfilled=%s, external rows=%s.',
                basics_stats['processed'],
                basics_stats['created'],
                rating_stats['updated'],
                rating_stats['url_fallback'],
                rating_stats['ids_backfilled'],
                rating_stats['external_updated'],
            )
        finally:
            for path in paths.values():
                if path and os.path.exists(path):
                    os.remove(path)

    def _download_dataset(self, filename):
        base_url = settings.IMDB_DATASET_BASE_URL.rstrip('/')
        url = f'{base_url}/{filename}'
        response = requests.get(url, stream=True, timeout=(30, 180))
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.tsv.gz')
        try:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)
        finally:
            tmp.close()
            response.close()
        return tmp.name

    @staticmethod
    def _rows(path):
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as handle:
            yield from csv.DictReader(handle, delimiter='\t')

    def _collect_rated_ids(self, path):
        return {row['tconst'] for row in self._rows(path) if row.get('tconst')}

    @staticmethod
    def _extract_imdb_id(value):
        match = IMDB_ID_PATTERN.search(value or '')
        return match.group(1).lower() if match else None

    @classmethod
    def _build_imdb_url_map(cls):
        url_map = defaultdict(list)
        rows = (
            Show.objects.filter(imdb_url__isnull=False)
            .exclude(imdb_url='')
            .values_list('id', 'imdb_url')
        )
        for show_id, imdb_url in rows.iterator(chunk_size=10000):
            imdb_id = cls._extract_imdb_id(imdb_url)
            if imdb_id:
                url_map[imdb_id].append(show_id)
        return dict(url_map)

    def _process_basics(
        self,
        path,
        title_types,
        existing_ids,
        rated_ids,
        add_missing,
        batch_size,
    ):
        to_create = []
        to_fill_year = []
        processed = 0
        created = 0

        for row in self._rows(path):
            title_type = row.get('titleType')
            imdb_id = row.get('tconst')
            if title_type not in title_types or not imdb_id:
                continue

            processed += 1
            if imdb_id in existing_ids:
                year = self._parse_year(row.get('startYear'))
                if year is not None:
                    to_fill_year.append((imdb_id, year))
                if len(to_fill_year) >= batch_size:
                    self._fill_missing_years(to_fill_year)
                    to_fill_year.clear()
                continue

            if not add_missing or imdb_id not in rated_ids:
                continue

            primary_title = self._clean_text(row.get('primaryTitle')) or imdb_id
            original_title = self._clean_text(row.get('originalTitle')) or primary_title
            to_create.append(
                Show(
                    imdb_id=imdb_id,
                    imdb_url=f'https://www.imdb.com/title/{imdb_id}/',
                    title=primary_title,
                    original_title=original_title,
                    type=title_types[title_type],
                    year=self._parse_year(row.get('startYear')),
                )
            )
            existing_ids.add(imdb_id)

            if len(to_create) >= batch_size:
                created += len(Show.objects.bulk_create(to_create, ignore_conflicts=True))
                to_create.clear()
                logger.info(
                    'IMDb basics progress: %s titles inspected, %s created.',
                    processed,
                    created,
                )

        if to_fill_year:
            self._fill_missing_years(to_fill_year)
        if to_create:
            created += len(Show.objects.bulk_create(to_create, ignore_conflicts=True))

        return {'processed': processed, 'created': created}

    @staticmethod
    def _fill_missing_years(rows):
        year_by_imdb_id = dict(rows)
        shows = list(
            Show.objects.filter(
                imdb_id__in=year_by_imdb_id,
                year__isnull=True,
            ).only('id', 'imdb_id', 'year')
        )
        for show in shows:
            show.year = year_by_imdb_id[show.imdb_id]
        if shows:
            Show.objects.bulk_update(shows, ['year'], batch_size=1000)

    def _process_ratings(self, path, batch_size, imdb_url_map):
        rating_rows = []
        updated = 0
        url_fallback = 0
        ids_backfilled = 0
        external_updated = 0

        for row in self._rows(path):
            imdb_id = row.get('tconst')
            rating = self._parse_float(row.get('averageRating'))
            votes = self._parse_int(row.get('numVotes'))
            if not imdb_id or rating is None or votes is None:
                continue

            rating_rows.append((imdb_id, rating, votes))
            if len(rating_rows) >= batch_size:
                counts = self._save_rating_batch(rating_rows, imdb_url_map)
                updated += counts['updated']
                url_fallback += counts['url_fallback']
                ids_backfilled += counts['ids_backfilled']
                external_updated += counts['external_updated']
                rating_rows.clear()

        if rating_rows:
            counts = self._save_rating_batch(rating_rows, imdb_url_map)
            updated += counts['updated']
            url_fallback += counts['url_fallback']
            ids_backfilled += counts['ids_backfilled']
            external_updated += counts['external_updated']

        return {
            'updated': updated,
            'url_fallback': url_fallback,
            'ids_backfilled': ids_backfilled,
            'external_updated': external_updated,
        }

    @classmethod
    def _save_rating_batch(cls, rows, imdb_url_map):
        ids = [row[0] for row in rows]
        values = {imdb_id: (rating, votes) for imdb_id, rating, votes in rows}
        fallback_show_ids = {
            show_id for imdb_id in ids for show_id in imdb_url_map.get(imdb_id, ())
        }
        shows = list(
            Show.objects.filter(Q(imdb_id__in=ids) | Q(id__in=fallback_show_ids)).only(
                'id', 'imdb_id', 'imdb_url', 'imdb_rating', 'imdb_votes'
            )
        )
        if not shows:
            return {'updated': 0, 'url_fallback': 0, 'ids_backfilled': 0, 'external_updated': 0}

        owned_ids = {show.imdb_id for show in shows if show.imdb_id in values}
        url_fallback = 0
        ids_backfilled = 0
        shows_to_update = []

        for show in shows:
            direct_value = values.get(show.imdb_id)
            url_imdb_id = cls._extract_imdb_id(show.imdb_url)
            url_value = values.get(url_imdb_id)
            value = direct_value or url_value
            if value is None:
                continue

            if direct_value is None:
                url_fallback += 1

            show.imdb_rating, show.imdb_votes = value
            show.imdb_rating_available = True
            if not show.imdb_id and url_imdb_id and url_imdb_id not in owned_ids:
                show.imdb_id = url_imdb_id
                owned_ids.add(url_imdb_id)
                ids_backfilled += 1
            shows_to_update.append(show)

        if not shows_to_update:
            return {'updated': 0, 'url_fallback': 0, 'ids_backfilled': 0, 'external_updated': 0}

        Show.objects.bulk_update(
            shows_to_update,
            ['imdb_id', 'imdb_rating', 'imdb_votes', 'imdb_rating_available'],
            batch_size=1000,
        )

        show_id_to_rating = {show.id: show.imdb_rating for show in shows_to_update}
        external_rows = list(
            ExternalRating.objects.filter(show_id__in=show_id_to_rating).only(
                'id', 'show_id', 'imdb'
            )
        )
        for external in external_rows:
            external.imdb = show_id_to_rating[external.show_id]
        if external_rows:
            ExternalRating.objects.bulk_update(external_rows, ['imdb'], batch_size=1000)

        return {
            'updated': len(shows_to_update),
            'url_fallback': url_fallback,
            'ids_backfilled': ids_backfilled,
            'external_updated': len(external_rows),
        }

    @staticmethod
    def _reset_imdb_rating_availability():
        Show.objects.filter(
            Q(imdb_id__isnull=False) | Q(imdb_url__isnull=False, imdb_url__gt='')
        ).update(imdb_rating_available=False)

    @staticmethod
    def _clean_text(value):
        return value.strip() if value and value != r'\N' else None

    @staticmethod
    def _parse_year(value):
        value = Command._clean_text(value)
        return int(value) if value and value.isdigit() else None

    @staticmethod
    def _parse_float(value):
        value = Command._clean_text(value)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_int(value):
        value = Command._clean_text(value)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
