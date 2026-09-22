from django.conf import settings

from app import history_parser
from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Runs the history parser session manually.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--allow-kinopub',
            action='store_true',
            help='Explicitly allow a local KinoPub run when ENVIRONMENT is not PROD.',
        )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != 'PROD' and not options.get('allow_kinopub'):
            self.stdout.write(
                'History parser is disabled outside PROD; use --allow-kinopub for a manual run.'
            )
            return
        history_parser.run_parser_session()
