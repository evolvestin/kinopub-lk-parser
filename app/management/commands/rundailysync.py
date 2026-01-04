import logging

from django.core.management import call_command

from app.management.base import LoggableBaseCommand


class Command(LoggableBaseCommand):
    help = 'Runs daily synchronization: New Episodes + Full Scan + Updates details/durations.'

    def handle(self, *args, **options):
        logging.info('Starting Daily Synchronization Command.')

        call_command('runnewepisodes')

        new_items_count = int(call_command('runfullscan') or 0)
        logging.info(f'Full scan finished. New items found: {new_items_count}')

        if new_items_count > 0:
            logging.info(f'Updating details for {new_items_count} new items...')
            call_command('updatedetails', limit=new_items_count)

            logging.info(f'Updating durations for {new_items_count} new items...')
            call_command('updatedurations', limit=new_items_count)

        logging.info('Daily Synchronization Command Completed.')
