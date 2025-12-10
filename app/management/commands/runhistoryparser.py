from app import history_parser
from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Runs the history parser session manually.'

    def handle(self, *args, **options):
        history_parser.run_parser_session()