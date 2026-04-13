import logging
import re
from time import sleep

import requests
from django.conf import settings
from django.db import DatabaseError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_tmdb_session = None


def get_tmdb_session():
    global _tmdb_session
    if _tmdb_session is None:
        _tmdb_session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['GET'],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        _tmdb_session.mount('http://', adapter)
        _tmdb_session.mount('https://', adapter)
    return _tmdb_session


def fetch_person_photo_from_tmdb(person_instance) -> bool:
    if not settings.TMDB_API_KEY:
        logger.error('TMDB_API_KEY is not set.')
        return False

    def clean_name(n):
        if not n:
            return None
        return n.replace('\xa0', ' ').replace('  ', ' ').strip()

    search_scenarios = []

    en_name = clean_name(person_instance.en_name)
    if en_name:
        search_scenarios.append(en_name)

    raw_name = clean_name(person_instance.name)
    if raw_name:
        bracket_match = re.search(r'\((.*?)\)', raw_name)
        if bracket_match:
            en_candidate = clean_name(bracket_match.group(1))
            if en_candidate and en_candidate != en_name:
                search_scenarios.append(en_candidate)

        ru_candidate = clean_name(re.sub(r'\(.*?\)', '', raw_name))
        if ru_candidate:
            search_scenarios.append(ru_candidate)

    base_url = 'https://api.themoviedb.org/3/search/person'
    found_path = None
    session = get_tmdb_session()

    api_key = settings.TMDB_API_KEY
    headers = {}
    default_params = {'include_adult': 'false'}

    if api_key.startswith('ey'):
        headers['Authorization'] = f'Bearer {api_key}'
    else:
        default_params['api_key'] = api_key

    try:
        for query in search_scenarios:
            if not query:
                continue

            search_params = {**default_params, 'query': query}

            resp = session.get(base_url, params=search_params, headers=headers, timeout=10)

            sleep(0.25)

            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                for res in results:
                    path = res.get('profile_path')
                    if path:
                        found_path = path
                        break
                if found_path:
                    break

        person_instance.tmdb_photo_url = (
            f'https://image.tmdb.org/t/p/w200{found_path}' if found_path else None
        )
        person_instance.is_photo_fetched = True
        person_instance.save(update_fields=['tmdb_photo_url', 'is_photo_fetched', 'updated_at'])

        if found_path:
            logger.info(f'Fetched photo for {person_instance.name}')
        else:
            logger.debug(f'No photo found for {person_instance.name} after all scenarios')

        return True

    except (requests.ConnectionError, requests.Timeout) as e:
        logger.warning(f'TMDB connectivity issue for {person_instance.name}: {e}')
        raise
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f'Unexpected error on {person_instance.name}: {e}')
        return False
