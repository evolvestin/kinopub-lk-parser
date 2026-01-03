import logging
import re
import sys
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.utils import timezone
from selenium.webdriver.common.by import By

from app import history_parser
from app.history_parser import (
    close_driver,
    initialize_driver_session,
    parse_new_episodes_list,
    process_show_durations,
    update_show_details,
)
from shared.constants import SHOW_TYPE_MAPPING


def _get_windows_chrome_version():
    import winreg

    try:
        key_path = r'Software\Google\Chrome\BLBeacon'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            version, _ = winreg.QueryValueEx(key, 'version')
            if version:
                logging.info(f'Detected local Chrome version (Registry): {version}')
                return int(version.split('.')[0])
    except Exception as e:
        logging.warning(f'Could not detect Chrome version via registry: {e}')
    return None


class Command(BaseCommand):
    help = 'Runs a single parser session locally without database (Mock mode).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account',
            type=str,
            choices=['main', 'aux'],
            default='main',
            help='The account to use: "main" (history/durations) or "aux" (details).',
        )
        parser.add_argument(
            '--task',
            type=str,
            choices=['history', 'details', 'durations'],
            default=None,
            help='Specific task to run. If not set, defaults based on account.',
        )
        parser.add_argument(
            '--type',
            type=str,
            dest='type',
            help='Filter shows by type (e.g. serial, movie).',
        )

    def _get_live_ids(self, driver, base_url, account, url_type='serial', limit=5):
        if account == 'aux':
            # Aux аккаунт не видит new-serial-episodes, берем из каталога
            logging.info(f'Fetching live IDs from Catalog /{url_type} (Aux mode)...')
            url = f'{base_url}{url_type}'
            driver.get(url)

            unique_ids = set()
            try:
                # Парсим ссылки из плиток каталога
                elements = driver.find_elements(By.CSS_SELECTOR, '.item-title a')
                for el in elements:
                    href = el.get_attribute('href')
                    match = re.search(r'/item/view/(\d+)', href)
                    if match:
                        unique_ids.add(int(match.group(1)))
                    if len(unique_ids) >= limit:
                        break
            except Exception as e:
                logging.error(f'Error scraping catalog: {e}')

            result = list(unique_ids)
        else:
            # Main аккаунт видит новые эпизоды
            logging.info('Fetching live IDs from "New Episodes" page to test parsers...')
            url = f'{base_url}media/new-serial-episodes'
            driver.get(url)
            time.sleep(5)
            items = parse_new_episodes_list(driver)
            if not items:
                logging.warning('No items found on new episodes page.')
                return []
            result = list({item['show_id'] for item in items})[:limit]

        logging.info(f'Found IDs for testing: {result}')
        return result

    def _setup_mocks(self):
        logging.info('Setting up database Mocks...')

        # Helper to create auxiliary models (Country, Genre, Person)
        def create_aux_mock(name):
            m = MagicMock(name=name)
            # update_or_create must return tuple (obj, created)
            m.objects.update_or_create.return_value = (MagicMock(), True)
            m.objects.get_or_create.return_value = (MagicMock(), True)
            return m

        def mock_add_relation(*args):
            print(f'   [MockDB] Added Relation: {args}')

        mock_show_instance = MagicMock()
        mock_show_instance.year = None
        # Use timezone-aware datetime for comparison compatibility
        mock_show_instance.updated_at = timezone.now() - timedelta(days=3650)
        mock_show_instance.countries.add = MagicMock(side_effect=mock_add_relation)
        mock_show_instance.genres.add = MagicMock(side_effect=mock_add_relation)
        mock_show_instance.directors.add = MagicMock(side_effect=mock_add_relation)
        mock_show_instance.actors.add = MagicMock(side_effect=mock_add_relation)

        def save_side_effect(*args, **kwargs):
            fields = vars(mock_show_instance)
            useful_fields = {
                k: v for k, v in fields.items() if not k.startswith('_') and not callable(v)
            }
            print(f'   [MockDB] Saving Show: {useful_fields}')

        mock_show_instance.save = MagicMock(side_effect=save_side_effect)

        def mock_update_or_create_show(**kwargs):
            print(f'   [MockDB] Show update_or_create: {kwargs}')
            return (mock_show_instance, True)

        def mock_bulk_create_shows(objs, **kwargs):
            print(f'   [MockDB] Bulk create Shows: {len(objs)} items')

        mock_show_model = MagicMock()
        # CRITICAL: Fix for TypeError (catching non-exception class)
        mock_show_model.DoesNotExist = ObjectDoesNotExist
        mock_show_model.objects.get.return_value = mock_show_instance
        mock_show_model.objects.filter.return_value.exists.return_value = False
        mock_show_model.objects.filter.return_value.first.return_value = mock_show_instance
        mock_show_model.objects.update_or_create.side_effect = mock_update_or_create_show
        mock_show_model.objects.bulk_create.side_effect = mock_bulk_create_shows

        def mock_update_or_create_duration(**kwargs):
            print(f'   [MockDB] Duration update_or_create: {kwargs}')
            return (MagicMock(), True)

        mock_show_duration_model = MagicMock()
        mock_show_duration_model.objects.update_or_create.side_effect = (
            mock_update_or_create_duration
        )
        mock_show_duration_model.objects.filter.return_value.exists.return_value = False

        def mock_bulk_create_history(objs, **kwargs):
            print(f'   [MockDB] ViewHistory bulk_create: {len(objs)} items')
            return objs

        mock_view_history_model = MagicMock()
        mock_view_history_model.objects.bulk_create.side_effect = mock_bulk_create_history
        mock_view_history_model.objects.count.return_value = 0
        mock_view_history_model.objects.filter.return_value.aggregate.return_value = {
            'max_date': None
        }

        mock_code_model = MagicMock()
        mock_code_model.objects.filter.return_value.order_by.return_value.first.return_value = None

        # Create mocks for auxiliary models
        mock_country = create_aux_mock('Country')
        mock_genre = create_aux_mock('Genre')
        mock_person = create_aux_mock('Person')

        return (
            mock_show_model,
            mock_show_duration_model,
            mock_view_history_model,
            mock_code_model,
            mock_country,
            mock_genre,
            mock_person,
        )

    @patch('app.history_parser.get_chrome_major_version', side_effect=_get_windows_chrome_version)
    def handle(self, *args, **options):
        sys.stdout.reconfigure(encoding='utf-8')

        for name in [None, 'app', 'django', 'celery']:
            logger = logging.getLogger(name)
            for handler in logger.handlers[:]:
                if handler.__class__.__name__ == 'DatabaseLogHandler':
                    logger.removeHandler(handler)

        for name in ['django', 'celery', 'urllib3']:
            logging.getLogger(name).setLevel(logging.WARNING)
        logging.getLogger('app').setLevel(logging.INFO)

        account = options['account']
        task = options['task'] or ('history' if account == 'main' else 'details')

        show_type_arg = options.get('type')
        url_type = 'serial'

        if show_type_arg:
            if show_type_arg in SHOW_TYPE_MAPPING:
                url_type = show_type_arg
            else:
                for k, v in SHOW_TYPE_MAPPING.items():
                    if v.lower() == show_type_arg.lower():
                        url_type = k
                        break

        show_type_display = SHOW_TYPE_MAPPING.get(url_type, 'Series')
        base_url = settings.SITE_AUX_URL if account == 'aux' else settings.SITE_URL

        print(f'--- Starting local script (Account: {account}, Task: {task}) ---', flush=True)
        print('--- Note: Database is MOCKED. No data will be saved. ---', flush=True)

        (
            mock_show_model,
            mock_show_duration_model,
            mock_view_history_model,
            mock_code_model,
            mock_country,
            mock_genre,
            mock_person,
        ) = self._setup_mocks()

        with (
            patch('app.history_parser.Show', mock_show_model),
            patch('app.history_parser.ShowDuration', mock_show_duration_model),
            patch('app.history_parser.ViewHistory', mock_view_history_model),
            patch('app.history_parser.Code', mock_code_model),
            patch('app.history_parser.Country', mock_country),
            patch('app.history_parser.Genre', mock_genre),
            patch('app.history_parser.Person', mock_person),
        ):
            driver = None
            try:
                driver = initialize_driver_session(headless=False, session_type=account)
                if driver is None:
                    logging.error('Failed to initialize driver.')
                    return

                if task == 'history':
                    logging.info('Running History Parser (Mock Mode)...')
                    history_parser.run_parser_session(headless=False, driver_instance=driver)

                elif task == 'details':
                    logging.info('Running Details Updater (Mock Mode)...')
                    ids = self._get_live_ids(driver, base_url, account, url_type)
                    for show_id in ids:
                        logging.info(f'Processing details for ID {show_id}...')
                        update_show_details(driver, show_id)

                elif task == 'durations':
                    logging.info('Running Durations Updater (Mock Mode)...')
                    ids = self._get_live_ids(driver, base_url, account, url_type)
                    for show_id in ids:
                        logging.info(f'Processing durations for ID {show_id}...')
                        mock_show = mock_show_model.objects.get()
                        mock_show.id = show_id
                        mock_show.type = show_type_display
                        process_show_durations(driver, mock_show)

            except Exception as e:
                logging.error(f'Critical error in local run: {e}', exc_info=True)
            finally:
                close_driver(driver)

        logging.info('--- Local script finished ---')
