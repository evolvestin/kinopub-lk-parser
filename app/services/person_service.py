import logging
import re

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

    search_scenarios = []
    if person_instance.en_name:
        search_scenarios.append({'query': person_instance.en_name, 'params': {'language': 'en-US'}})

    raw_name = person_instance.name.replace('\xa0', ' ').strip()
    bracket_match = re.search(r'\((.*?)\)', raw_name)
    en_name_candidate = bracket_match.group(1).strip() if bracket_match else None
    ru_name_candidate = re.sub(r'\(.*?\)', '', raw_name).strip()

    search_scenarios.append({'query': ru_name_candidate, 'params': {'language': 'ru-RU'}})
    if en_name_candidate:
        search_scenarios.append({'query': en_name_candidate, 'params': {'language': 'en-US'}})
    search_scenarios.append({'query': ru_name_candidate, 'params': {}})

    base_url = 'https://api.themoviedb.org/3/search/person'
    found_path = None
    session = get_tmdb_session()

    try:
        for scenario in search_scenarios:
            if not scenario['query']:
                continue

            search_params = {
                'api_key': settings.TMDB_API_KEY,
                'query': scenario['query'],
                'include_adult': 'false',
                **scenario['params'],
            }

            try:
                resp = session.get(base_url, params=search_params, timeout=10)
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
            except (requests.ConnectionError, requests.Timeout) as e:
                logger.warning(f'TMDB connectivity issue for {person_instance.name}: {e}')
                raise

        person_instance.tmdb_photo_url = (
            f'https://image.tmdb.org/t/p/w200{found_path}' if found_path else None
        )
        person_instance.is_photo_fetched = True
        person_instance.save(update_fields=['tmdb_photo_url', 'is_photo_fetched', 'updated_at'])
        return True

    except DatabaseError:
        raise
    except Exception as e:
        if not isinstance(e, requests.RequestException):
            logger.error(f'Unexpected error on {person_instance.name}: {e}')
        return False
