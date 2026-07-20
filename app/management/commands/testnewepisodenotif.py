import logging
import random
from django.core.management.base import CommandError
from app.management.base import LoggableBaseCommand
from app.models import Show, ViewUser
from app.tasks import notify_new_episode_task

class Command(LoggableBaseCommand):
    help = 'Sends a test new episode notification for a random show to active users or a specific telegram ID.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--telegram-id',
            type=int,
            dest='telegram_id',
            help='Specify a telegram ID to send the notification to.',
        )
        parser.add_argument(
            '--season',
            type=int,
            default=1,
            help='Season number for the test notification.',
        )
        parser.add_argument(
            '--episode',
            type=int,
            default=1,
            help='Episode number for the test notification.',
        )

    def handle(self, *args, **options):
        telegram_id = options.get('telegram_id')
        season = options.get('season')
        episode = options.get('episode')

        shows = Show.objects.all()
        if not shows.exists():
            raise CommandError('No shows found in the database. Please run runfullscan first.')

        random_show = random.choice(list(shows))
        logging.info(f'Picked random show: {random_show.title} (ID: {random_show.id})')

        if telegram_id:
            try:
                user = ViewUser.objects.get(telegram_id=telegram_id)
            except ViewUser.DoesNotExist:
                raise CommandError(f'User with telegram ID {telegram_id} does not exist.')

            from app.telegram_bot import TelegramSender
            sender = TelegramSender()
            sender.send_new_episode_notification(user, random_show, season, episode)
            logging.info(f'Sent test notification to user {telegram_id} for show {random_show.title}')
        else:
            notify_new_episode_task.delay(random_show.id, season, episode)
            logging.info(f'Triggered notify_new_episode_task for show {random_show.id} (S{season}E{episode})')