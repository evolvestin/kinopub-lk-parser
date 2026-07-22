import logging
import re
from time import sleep

import requests
from celery.exceptions import SoftTimeLimitExceeded
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


def _is_valid_tmdb_match(query: str, tmdb_result: dict) -> bool:
    """
    Проверяет, соответствует ли найденный профиль TMDB запрошенному человеку.
    Использует строгое сравнение имен, чтобы исключить ложные срабатывания (дубликаты).
    """
    q_lower = query.lower().strip()

    name = (tmdb_result.get('name') or '').lower().strip()
    orig_name = (tmdb_result.get('original_name') or '').lower().strip()

    # Точное совпадение имени или оригинального имени
    possible_exact = {name, orig_name}
    possible_exact.discard('')

    if q_lower in possible_exact:
        return True

    # Имена короче 4 символов слишком неоднозначны для частичного поиска
    if len(q_lower) <= 4:
        return False

    # Разбиваем запрос и имена на слова для проверки полноты совпадения
    q_words = set(re.findall(r'\w+', q_lower))
    name_words = set(re.findall(r'\w+', name))
    orig_name_words = set(re.findall(r'\w+', orig_name))

    # Если запрос состоит из 2+ слов (Имя + Фамилия), требуем полного вхождения
    # всех слов запроса в одно из полей имени (устраняет проблему Вуд vs Вудсон)
    if len(q_words) >= 2:
        if q_words.issubset(name_words) or q_words.issubset(orig_name_words):
            return True

    return False


def fetch_person_photo_from_tmdb(person_instance) -> bool:
    if not settings.TMDB_API_KEY:
        logger.error('TMDB_API_KEY is not set.')
        return False

    rejected_urls = set(person_instance.rejected_photos.values_list('photo_url', flat=True))

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

    db_shows_meta = []
    try:
        for s in person_instance.shows_as_crew.all():
            db_shows_meta.append(
                {
                    'title': s.title.lower().strip() if s.title else '',
                    'original_title': s.original_title.lower().strip() if s.original_title else '',
                    'year': s.year,
                }
            )
    except SoftTimeLimitExceeded:
        raise
    except Exception as e:
        logger.error(f'Error fetching shows meta for {person_instance.name}: {e}')

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

                valid_candidates = []
                for res in results:
                    profile_path = res.get('profile_path')
                    if profile_path:
                        full_url = f'https://image.tmdb.org/t/p/w200{profile_path}'
                        if full_url in rejected_urls:
                            continue

                    if _is_valid_tmdb_match(query, res):
                        score = 0
                        known_for_list = res.get('known_for', [])
                        for work in known_for_list:
                            work_titles = []
                            for title_field in ['title', 'original_title', 'name', 'original_name']:
                                if t := work.get(title_field):
                                    work_titles.append(t.lower().strip())

                            work_date = work.get('release_date') or work.get('first_air_date') or ''
                            work_year = None
                            if len(work_date) >= 4 and work_date[:4].isdigit():
                                work_year = int(work_date[:4])

                            for db_show in db_shows_meta:
                                if (
                                    db_show['title'] in work_titles
                                    or db_show['original_title'] in work_titles
                                ):
                                    if (
                                        work_year
                                        and db_show['year']
                                        and abs(work_year - db_show['year']) <= 1
                                    ):
                                        score += 100
                                    else:
                                        score += 10

                        valid_candidates.append(
                            {'data': res, 'score': score, 'popularity': res.get('popularity', 0.0)}
                        )

                if valid_candidates:
                    valid_candidates.sort(key=lambda x: (x['score'], x['popularity']), reverse=True)
                    best_candidate = valid_candidates[0]

                    if best_candidate['score'] > 0:
                        found_path = best_candidate['data'].get('profile_path')
                        break
                    elif len(valid_candidates) == 1:
                        found_path = best_candidate['data'].get('profile_path')
                        break
                    else:
                        logger.info(
                            f'Ambiguous match for {person_instance.name} (query: {query}) '
                            f'with no filmography match. Skipping.'
                        )

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

    except SoftTimeLimitExceeded:
        raise
    except requests.RequestException as e:
        logger.warning(f'TMDB connectivity issue for {person_instance.name}: {e}')
        raise
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f'Unexpected error on {person_instance.name}: {e}')
        return False
