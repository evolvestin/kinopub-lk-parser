import logging

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.models import Country, Genre, Person, Show, ShowCrew
from app.services.person_matching import find_person_for_tmdb
from app.services.show_duration import upsert_show_duration
from shared.constants import SHOW_TYPE_MAPPING, ShowType

logger = logging.getLogger(__name__)

TMDB_STATUS_MAPPING = {
    'Ended': 'Finished',
    'Canceled': 'Finished',
    'Returning Series': 'Ongoing',
    'In Production': 'Ongoing',
    'Planned': 'Pre Production',
    'Pilot': 'Pre Production',
    'Released': 'Finished',
    'Post Production': 'Post Production',
    'Rumored': 'Pre Production',
}

_tmdb_session = None


def get_tmdb_session():
    global _tmdb_session
    if _tmdb_session is None:
        _tmdb_session = requests.Session()
        proxy = settings.TMDB_PROXY
        if proxy:
            _tmdb_session.proxies = {
                'http': proxy,
                'https': proxy,
            }
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


class TMDBClient:
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_API_BASE_URL
        self.session = get_tmdb_session()

    def _get_headers_and_params(self) -> tuple[dict, dict]:
        headers = {}
        params = {'language': 'ru-RU'}
        if self.api_key:
            if self.api_key.startswith('ey'):
                headers['Authorization'] = f'Bearer {self.api_key}'
            else:
                params['api_key'] = self.api_key
        return headers, params

    def get_details(self, tmdb_id: int, media_type: str = 'movie') -> dict | None:
        if not self.api_key:
            return None
        endpoint = f'{self.base_url}/{media_type}/{tmdb_id}'
        headers, params = self._get_headers_and_params()
        params['append_to_response'] = 'external_ids,credits'

        try:
            response = self.session.get(endpoint, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f'TMDB get_details network issue for {media_type}/{tmdb_id}: {e}')
            raise
        return None

    def find_by_imdb_id(self, imdb_id: str) -> tuple[dict | None, str | None]:
        if not self.api_key or not imdb_id:
            return None, None
        endpoint = f'{self.base_url}/find/{imdb_id}'
        headers, params = self._get_headers_and_params()
        params['external_source'] = 'imdb_id'

        try:
            response = self.session.get(endpoint, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                movie_results = data.get('movie_results', [])
                if movie_results:
                    return movie_results[0], 'movie'
                tv_results = data.get('tv_results', [])
                if tv_results:
                    return tv_results[0], 'tv'
            elif response.status_code == 404:
                return None, None
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f'TMDB find_by_imdb_id network issue for {imdb_id}: {e}')
            raise
        return None, None


def sync_show_from_tmdb(
    show_id: int = None, tmdb_id: int = None, imdb_id: str = None, media_type: str = 'movie'
) -> Show | None:
    show = None
    if show_id:
        show = Show.objects.filter(id=show_id).first()
    if not show and tmdb_id:
        show = Show.objects.filter(tmdb_id=tmdb_id).first()
    if not show and imdb_id:
        show = Show.objects.filter(imdb_id=imdb_id).first()

    client = TMDBClient()
    target_tmdb_id = tmdb_id or (show.tmdb_id if show else None)
    target_imdb_id = imdb_id or (show.imdb_id if show else None)

    if not target_tmdb_id and target_imdb_id:
        found_data, detected_type = client.find_by_imdb_id(target_imdb_id)
        if found_data:
            target_tmdb_id = found_data.get('id')
            if detected_type:
                media_type = detected_type

    if not target_tmdb_id:
        return None

    details = client.get_details(target_tmdb_id, media_type=media_type)
    if not details:
        return None

    external_ids = details.get('external_ids', {})
    found_imdb_id = external_ids.get('imdb_id') or target_imdb_id

    if not show and found_imdb_id:
        show = Show.objects.filter(imdb_id=found_imdb_id).first()

    if not show:
        show = Show()

    show.tmdb_id = target_tmdb_id
    if found_imdb_id:
        if not Show.objects.filter(imdb_id=found_imdb_id).exclude(id=show.id).exists():
            show.imdb_id = found_imdb_id
            if not show.imdb_url:
                show.imdb_url = f'https://www.imdb.com/title/{found_imdb_id}/'

    raw_title = details.get('title') or details.get('name')
    if raw_title:
        show.title = raw_title

    raw_orig_title = details.get('original_title') or details.get('original_name')
    if raw_orig_title:
        show.original_title = raw_orig_title

    date_str = details.get('release_date') or details.get('first_air_date')
    if date_str and len(date_str) >= 4 and date_str[:4].isdigit():
        show.year = int(date_str[:4])

    overview = details.get('overview')
    if overview:
        show.plot = overview

    poster_path = details.get('poster_path')
    if poster_path:
        show.tmdb_poster_path = poster_path

    status_str = details.get('status')
    if status_str:
        show.status = TMDB_STATUS_MAPPING.get(status_str, status_str)

    # TMDB's endpoint is authoritative for the media kind. Do not preserve a
    # stale value from an earlier dump import (movie IDs can be misclassified
    # as TV when the two daily dumps are processed independently).
    show.type = (
        SHOW_TYPE_MAPPING[ShowType.SERIES]
        if media_type == 'tv'
        else SHOW_TYPE_MAPPING[ShowType.MOVIE]
    )

    show.save()

    for g_data in details.get('genres', []):
        g_name = g_data.get('name')
        if g_name:
            genre_obj, _ = Genre.objects.get_or_create(name=g_name)
            show.genres.add(genre_obj)

    for c_data in details.get('production_countries', []):
        c_name = c_data.get('name')
        if c_name:
            country_obj, _ = Country.objects.get_or_create(name=c_name)
            show.countries.add(country_obj)

    credits_data = details.get('credits', {})
    cast_data = credits_data.get('cast', [])
    crew_data = credits_data.get('crew', [])

    for person_data in cast_data[:30]:
        p_tmdb_id = person_data.get('id')
        p_name = person_data.get('name')
        if not p_name:
            continue

        person = find_person_for_tmdb(
            name=p_name,
            en_name=person_data.get('original_name'),
            tmdb_id=p_tmdb_id,
            show=show,
        )
        if not person:
            person, _ = Person.objects.get_or_create(name=p_name)
            person = person.canonical

        if p_tmdb_id and not person.tmdb_id:
            person.tmdb_id = p_tmdb_id

        p_en_name = person_data.get('original_name')
        if p_en_name and not person.en_name:
            person.en_name = p_en_name

        profile_path = person_data.get('profile_path')
        if profile_path and not person.tmdb_photo_url:
            person.tmdb_photo_url = f'https://image.tmdb.org/t/p/w200{profile_path}'
            person.is_photo_fetched = True

        person.save()

        character = person_data.get('character') or 'Актёр'
        ShowCrew.objects.get_or_create(
            show=show,
            person=person,
            profession=character,
            defaults={'en_profession': 'Actor'},
        )

    for person_data in crew_data:
        job = person_data.get('job')
        if job not in ['Director', 'Producer', 'Writer', 'Executive Producer']:
            continue

        p_tmdb_id = person_data.get('id')
        p_name = person_data.get('name')
        if not p_name:
            continue

        person = find_person_for_tmdb(
            name=p_name,
            en_name=person_data.get('original_name'),
            tmdb_id=p_tmdb_id,
            show=show,
        )
        if not person:
            person, _ = Person.objects.get_or_create(name=p_name)
            person = person.canonical

        if p_tmdb_id and not person.tmdb_id:
            person.tmdb_id = p_tmdb_id

        p_en_name = person_data.get('original_name')
        if p_en_name and not person.en_name:
            person.en_name = p_en_name

        profile_path = person_data.get('profile_path')
        if profile_path and not person.tmdb_photo_url:
            person.tmdb_photo_url = f'https://image.tmdb.org/t/p/w200{profile_path}'
            person.is_photo_fetched = True

        person.save()

        ShowCrew.objects.get_or_create(
            show=show,
            person=person,
            profession=job,
            defaults={'en_profession': person_data.get('department')},
        )

    if media_type == 'movie':
        runtime = details.get('runtime')
        if runtime and runtime > 0:
            upsert_show_duration(
                show=show,
                season_number=None,
                episode_number=None,
                duration_seconds=runtime * 60,
                is_estimated=True,
                preserve_exact=True,
            )

    return show
