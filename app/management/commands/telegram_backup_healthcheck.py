from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.telegram_backup import TelegramBackupError, TelegramBotApi


class Command(BaseCommand):
    help = 'Check access to the configured Telegram backup channel.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BACKUP_ENABLED and not options['force']:
            raise CommandError('Telegram backup is disabled')
        try:
            chat = TelegramBotApi().probe()
        except TelegramBackupError as error:
            raise CommandError(str(error)) from error
        title = chat.get('title') or chat.get('username') or 'configured channel'
        self.stdout.write(self.style.SUCCESS(f'Telegram backup channel is reachable: {title}'))
