import logging

from app.management.base import LoggableBaseCommand
from app.services.tmdb_client import parse_tmdb_library, sync_show_from_tmdb


class Command(LoggableBaseCommand):
    help = 'Imports or updates shows directly from TMDB API or parses the TMDB library.'

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
        parser.add_argument(
            '--mode',
            type=str,
            choices=['discover', 'popular', 'top_rated', 'trending'],
            default='discover',
            help='Library parsing mode.',
        )
        parser.add_argument(
            '--pages',
            type=int,
            default=10,
            help='Number of library pages to parse.',
        )
        parser.add_argument(
            '--sort-by',
            type=str,
            default='popularity.desc',
            help='Sorting order for discover mode.',
        )
        parser.add_argument(
            '--popular',
            type=int,
            help='Import N popular items from TMDB (legacy argument).',
        )
        parser.add_argument(
            '--eager',
            action='store_true',
            help='Process items synchronously instead of queueing tasks.',
        )

    def handle(self, *args, **options):
        tmdb_id = options.get('tmdb_id')
        imdb_id = options.get('imdb_id')
        media_type = options.get('type', 'movie')
        mode = options.get('mode', 'discover')
        pages = options.get('pages', 10)
        sort_by = options.get('sort_by', 'popularity.desc')
        popular_limit = options.get('popular')
        eager = options.get('eager', False)

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
            mode = 'popular'
            pages = max(1, (popular_limit + 19) // 20)

        logging.info(f'Parsing TMDB library (mode={mode}, type={media_type}, pages={pages})...')
        count = parse_tmdb_library(
            media_type=media_type, mode=mode, pages=pages, sort_by=sort_by, sync_eager=eager
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully parsed and processed {count} items from TMDB library.'
            )
        )