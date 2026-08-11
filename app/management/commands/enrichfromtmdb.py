import logging
import time

import requests
from celery.exceptions import SoftTimeLimitExceeded
from django import db
from django.db.models import Q
from django.utils import timezone

from app.management.base import LoggableBaseCommand
from app.models import Show
from app.services.tmdb_client import sync_show_from_tmdb

logger = logging.getLogger(__name__)


class Command(LoggableBaseCommand):
    help = 'Enriches bare TMDB shows with metadata, genres, countries, and crew.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=5000,
            help='Maximum number of shows to enrich in one execution.',
        )

    def handle(self, *args, **options):
        limit = options.get('limit', 5000)
        logging.info(f'Starting TMDB enrichment task. Target limit: {limit}')

        candidates = list(
            Show.objects.filter(tmdb_id__isnull=False)
            .filter(tmdb_enrichment_checked_at__isnull=True)
            .filter(
                Q(plot__isnull=True)
                | Q(plot='')
                | Q(genres__isnull=True)
                | Q(countries__isnull=True)
                | Q(year__isnull=True)
                | Q(showcrew__isnull=True)
            )
            .order_by('updated_at')
            .values_list('id', 'tmdb_id', 'type')
            .distinct()[:limit]
        )

        if not candidates:
            logging.info('No shows found requiring TMDB enrichment.')
            return

        processed_count = 0
        success_count = 0
        no_data_count = 0
        consecutive_errors = 0
        error_threshold = 10

        try:
            for show_id, tmdb_id, show_type in candidates:
                try:
                    media_type = (
                        'tv'
                        if show_type in ('Series', 'Documentary Series', 'TV Show')
                        else 'movie'
                    )
                    updated_show = sync_show_from_tmdb(
                        show_id=show_id, tmdb_id=tmdb_id, media_type=media_type
                    )

                    if updated_show:
                        success_count += 1
                    else:
                        no_data_count += 1
                        Show.objects.filter(id=show_id).update(updated_at=timezone.now())

                    # A successful TMDB request is terminal for this enrichment pass:
                    # fields absent from the response are genuine missing data and must
                    # not cause the same show to be selected on every hourly run.
                    Show.objects.filter(id=show_id).update(
                        tmdb_enrichment_checked_at=timezone.now()
                    )

                    processed_count += 1
                    consecutive_errors = 0
                    time.sleep(0.04)

                except SoftTimeLimitExceeded:
                    raise
                except requests.RequestException as e:
                    consecutive_errors += 1
                    logging.warning(
                        f'TMDB API request failed for show_id={show_id} (tmdb_id={tmdb_id}): {e}'
                    )
                    if getattr(e.response, 'status_code', None) == 429:
                        time.sleep(3)

                    if consecutive_errors >= error_threshold:
                        logging.error(
                            'Aborting TMDB enrichment: Too many consecutive network errors.'
                        )
                        break
                except Exception as e:
                    processed_count += 1
                    logging.error(f'Error enriching show_id={show_id}: {e}', exc_info=True)

                if processed_count % 500 == 0:
                    logging.info(
                        f'Enrichment progress: {processed_count}/{len(candidates)} processed...'
                    )
                    db.reset_queries()

        except SoftTimeLimitExceeded:
            logging.warning(
                'Soft time limit reached during TMDB enrichment. Saving progress and exiting.'
            )

        logging.info(
            f'TMDB enrichment completed. Processed: {processed_count}, '
            f'Successfully updated: {success_count}, No data from TMDB: {no_data_count}'
        )
