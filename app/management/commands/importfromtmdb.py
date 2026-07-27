import gzip
import json
import logging
import os
import tempfile
import time
from datetime import timedelta

import requests
from django.utils import timezone

from app.management.base import LoggableBaseCommand
from app.models import Show
from shared.constants import ShowType

logger = logging.getLogger(__name__)


class Command(LoggableBaseCommand):
    help = 'Bulk imports shows from TMDB daily export JSON dumps.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['movie', 'tv', 'all'],
            default='all',
            help='Media type to import: movie, tv, or all (default: all).',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Dump date in MM_DD_YYYY format. Defaults to today/yesterday UTC.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=5000,
            help='Batch size for DB insertions (default: 5000).',
        )

    def handle(self, *args, **options):
        media_type = options.get('type', 'all')
        dump_date_str = options.get('date')
        batch_size = options.get('batch-size', 5000)

        types_to_process = []
        if media_type in ('movie', 'all'):
            types_to_process.append('movie')
        if media_type in ('tv', 'all'):
            types_to_process.append('tv')

        target_dates = self._resolve_dump_dates(dump_date_str)

        initial_db_count = Show.objects.count()
        existing_tmdb_ids = set(
            Show.objects.filter(tmdb_id__isnull=False).values_list('tmdb_id', flat=True)
        )

        total_processed_dump = 0
        total_added = 0
        total_already_existed = 0
        start_time = time.time()

        logging.info(f'Initial shows count in DB: {initial_db_count}')
        logging.info(f'Existing TMDB IDs in DB: {len(existing_tmdb_ids)}')

        for m_type in types_to_process:
            logging.info(f'--- Processing {m_type.upper()} dump ---')

            dump_file_path, used_date = self._download_dump(m_type, target_dates)
            if not dump_file_path:
                logging.error(f'Failed to download dump for {m_type}. Skipping.')
                continue

            logging.info(f'Successfully downloaded {m_type} dump for date {used_date}')

            processed, added, existed = self._process_dump_file(
                dump_file_path=dump_file_path,
                media_type=m_type,
                existing_tmdb_ids=existing_tmdb_ids,
                batch_size=batch_size,
            )

            total_processed_dump += processed
            total_added += added
            total_already_existed += existed

        final_db_count = Show.objects.count()
        elapsed_time = round(time.time() - start_time, 2)

        logging.info(
            f'IMPORT SUMMARY REPORT | Execution Time: {elapsed_time}s | '
            f'Initial Shows: {initial_db_count} | Read from Dump: {total_processed_dump} | '
            f'Already Existed: {total_already_existed} | New Added: {total_added} | '
            f'Final Shows: {final_db_count}'
        )

    def _resolve_dump_dates(self, custom_date_str: str | None) -> list[str]:
        if custom_date_str:
            return [custom_date_str]

        now = timezone.now()
        today_str = now.strftime('%m_%d_%Y')
        yesterday_str = (now - timedelta(days=1)).strftime('%m_%d_%Y')
        return [today_str, yesterday_str]

    def _download_dump(self, media_type: str, dates: list[str]) -> tuple[str | None, str | None]:
        file_prefix = 'movie_ids' if media_type == 'movie' else 'tv_series_ids'

        for d_str in dates:
            url = f'http://files.tmdb.org/p/exports/{file_prefix}_{d_str}.json.gz'
            logging.info(f'Attempting download: {url}')

            try:
                response = requests.get(url, stream=True, timeout=30)
                if response.status_code == 200:
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json.gz')
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            tmp_file.write(chunk)
                    tmp_file.close()
                    return tmp_file.name, d_str
            except requests.RequestException as e:
                logger.warning(f'Failed to download dump from {url}: {e}')

        return None, None

    def _process_dump_file(
        self,
        dump_file_path: str,
        media_type: str,
        existing_tmdb_ids: set[int],
        batch_size: int,
    ) -> tuple[int, int, int]:
        show_type_val = ShowType.MOVIE if media_type == 'movie' else ShowType.SERIES

        processed_count = 0
        added_count = 0
        already_existed_count = 0

        batch_to_create = []

        try:
            with gzip.open(dump_file_path, 'rt', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    processed_count += 1

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    tmdb_id = data.get('id')
                    if not tmdb_id:
                        continue

                    if tmdb_id in existing_tmdb_ids:
                        already_existed_count += 1
                        continue

                    orig_title = (
                        data.get('original_title') or data.get('original_name') or f'TMDB {tmdb_id}'
                    )
                    title = orig_title

                    show_obj = Show(
                        tmdb_id=tmdb_id,
                        title=title,
                        original_title=orig_title,
                        type=show_type_val,
                    )
                    batch_to_create.append(show_obj)
                    existing_tmdb_ids.add(tmdb_id)

                    if len(batch_to_create) >= batch_size:
                        created = Show.objects.bulk_create(batch_to_create, ignore_conflicts=True)
                        added_count += len(created)
                        batch_to_create.clear()

                        logging.info(
                            f'Progress ({media_type}): Processed {processed_count} | '
                            f'Added {added_count} | Already in DB {already_existed_count}'
                        )

            if batch_to_create:
                created = Show.objects.bulk_create(batch_to_create, ignore_conflicts=True)
                added_count += len(created)
                batch_to_create.clear()

        finally:
            if os.path.exists(dump_file_path):
                os.remove(dump_file_path)

        return processed_count, added_count, already_existed_count
