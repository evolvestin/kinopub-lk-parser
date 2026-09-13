from django.conf import settings

from app import history_parser
from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Runs the history parser session manually.'

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != 'PROD':
            self.stdout.write('History parser is disabled outside PROD; skipping local run.')
            return
        history_parser.run_parser_session()
