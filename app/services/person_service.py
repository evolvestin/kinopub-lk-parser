import logging
import re

import requests
from django.conf import settings
from django.db import DatabaseError

logger = logging.getLogger(__name__)


def fetch_person_photo_from_tmdb(person_instance) -> bool:
    if not settings.TMDB_API_KEY:
        logger.error('TMDB_API_KEY is not set.')
        return False

    raw_name = person_instance.name.replace('\xa0', ' ').strip()

    bracket_match = re.search(r'\((.*?)\)', raw_name)
    en_name_candidate = bracket_match.group(1).strip() if bracket_match else None

    ru_name_candidate = re.sub(r'\(.*?\)', '', raw_name).strip()

    search_scenarios = [
        {'query': ru_name_candidate, 'params': {'language': 'ru-RU'}},
    ]

    if en_name_candidate:
        search_scenarios.append({'query': en_name_candidate, 'params': {'language': 'en-US'}})

    search_scenarios.append({'query': ru_name_candidate, 'params': {}})

    base_url = 'https://api.themoviedb.org/3/search/person'
    found_path = None

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

            resp = requests.get(base_url, params=search_params, timeout=5)
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

        if found_path:
            person_instance.photo_url = f'https://image.tmdb.org/t/p/w200{found_path}'
        else:
            person_instance.photo_url = None

        person_instance.is_photo_fetched = True
        person_instance.save(update_fields=['photo_url', 'is_photo_fetched'])
        return True

    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f'Failed to fetch photo for {person_instance.name}: {e}')
        return False
