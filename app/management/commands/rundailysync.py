import logging

from django.core.management import call_command

from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Runs daily synchronization: New Episodes + Full Scan + Updates details/durations.'

    def handle(self, *args, **options):
        logging.info('Starting Daily Synchronization Command.')

        # 1. Синхронизация сериалов
        call_command('runnewepisodes')

        # 2. Синхронизация остальных типов
        new_items_count = call_command('runfullscan') or 0
        logging.info(f'Full scan finished. New items found: {new_items_count}')

        # 3. Обновление деталей и длительностей, если найдены новые элементы
        if new_items_count > 0:
            logging.info(f'Updating details for {new_items_count} new items...')
            call_command('updatedetails', new_items_count)

            logging.info(f'Updating durations for {new_items_count} new items...')
            call_command('updatedurations', new_items_count)

        logging.info('Daily Synchronization Command Completed.')
