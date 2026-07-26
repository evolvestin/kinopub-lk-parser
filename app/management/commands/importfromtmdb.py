import logging

from django.conf import settings

from app.management.base import LoggableBaseCommand
from app.services.tmdb_client import get_tmdb_session, sync_show_from_tmdb
from app.tasks import sync_tmdb_metadata_task


class Command(LoggableBaseCommand):
    help = 'Imports or updates a show directly from TMDB API by TMDB ID, IMDb ID or popular list.'

    def add_arguments(self, parser):
        parser.add_argument('--tmdb-id', type=int, help='TMDB ID of the show/movie to import.')
        parser.add_argument(
            '--imdb-id', type=str, help='IMDb ID of the show/movie (e.g. tt0816692).'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['movie', 'tv'],
            default='movie',
            help='Media type: movie or tv.',
        )
        parser.add_argument('--popular', type=int, help='Import N popular items from TMDB.')

    def handle(self, *args, **options):
        tmdb_id = options.get('tmdb_id')
        imdb_id = options.get('imdb_id')
        media_type = options.get('type', 'movie')
        popular_limit = options.get('popular')

        if tmdb_id or imdb_id:
            logging.info(f'Starting TMDB direct import for TMDB ID: {tmdb_id}, IMDb ID: {imdb_id}')
            show = sync_show_from_tmdb(tmdb_id=tmdb_id, imdb_id=imdb_id, media_type=media_type)
            if show:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully imported/linked show: "{show.title}" (ID: {show.id})'
                    )
                )
            else:
                self.stdout.write(self.style.ERROR('Failed to import show from TMDB.'))
            return

        if popular_limit:
            logging.info(f'Importing top {popular_limit} popular items ({media_type}) from TMDB...')
            session = get_tmdb_session()
            api_key = settings.TMDB_API_KEY
            headers = {}
            params = {'language': 'ru-RU', 'page': 1}

            if api_key.startswith('ey'):
                headers['Authorization'] = f'Bearer {api_key}'
            else:
                params['api_key'] = api_key

            imported_count = 0
            page = 1

            while imported_count < popular_limit and page <= 10:
                params['page'] = page
                url = f'https://api.themoviedb.org/3/{media_type}/popular'
                resp = session.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code != 200:
                    break

                results = resp.json().get('results', [])
                if not results:
                    break

                for item in results:
                    item_tmdb_id = item.get('id')
                    if item_tmdb_id:
                        sync_tmdb_metadata_task.delay(tmdb_id=item_tmdb_id, media_type=media_type)
                        imported_count += 1
                        if imported_count >= popular_limit:
                            break

                page += 1

            self.stdout.write(
                self.style.SUCCESS(f'Enqueued {imported_count} popular items from TMDB.')
            )
            return

        self.stdout.write(self.style.WARNING('Specify --tmdb-id, --imdb-id, or --popular limit.'))
