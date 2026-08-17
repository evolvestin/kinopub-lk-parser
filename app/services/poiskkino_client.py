import logging
from dataclasses import dataclass
from datetime import date

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class PoiskkinoFetchResult:
    data: list[dict]
    checked_values: list[int | str]
    completed: bool
    requests_made: int


class PoiskkinoClient:
    BASE_URL = 'https://api.poiskkino.dev/v1.5/movie'
    _SELECT_FIELDS = [
        'id',
        'year',
        'description',
        'genres',
        'countries',
        'persons',
        'poster',
        'type',
        'status',
        'rating',
        'votes',
    ]

    def __init__(self):
        self.api_key = settings.POISKKINO_API_KEY
        self.session = requests.Session()

        retry_strategy = Retry(
            total=5,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['GET'],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def fetch_updated_ratings(
        self, start_date: date, end_date: date, max_requests: int = 150
    ) -> PoiskkinoFetchResult:
        if not self.api_key:
            return PoiskkinoFetchResult([], [], False, 0)

        date_str = f'{start_date.strftime("%d.%m.%Y")}-{end_date.strftime("%d.%m.%Y")}'
        headers = {'X-API-KEY': self.api_key}

        params = {'limit': 250, 'updatedAt': date_str, 'selectFields': self._SELECT_FIELDS}

        results = []
        next_cursor = None
        request_count = 0
        completed = False

        while request_count < max_requests:
            if next_cursor:
                params['next'] = next_cursor

            try:
                response = self.session.get(
                    self.BASE_URL, headers=headers, params=params, timeout=20
                )

                if response.status_code == 403:
                    logging.warning(
                        'Poiskkino API daily limit reached (403). Returning partial results.'
                    )
                    break

                response.raise_for_status()
                data = response.json()

                results.extend(data.get('docs', []))
                request_count += 1

                next_cursor = data.get('next')
                if not data.get('hasNext') or not next_cursor:
                    completed = True
                    break
            except requests.RequestException as e:
                logging.error(f'Poiskkino fetch_updated_ratings error: {e}')
                break

        return PoiskkinoFetchResult(results, [], completed, request_count)

    def fetch_ratings_by_ids(
        self, show_ids: list[int], max_requests: int = 200
    ) -> PoiskkinoFetchResult:
        if not self.api_key or not show_ids:
            return PoiskkinoFetchResult([], [], False, 0)

        headers = {'X-API-KEY': self.api_key}
        results = []
        checked_values = []
        chunk_size = 250
        requests_made = 0

        for i in range(0, len(show_ids), chunk_size):
            if requests_made >= max_requests:
                break
            chunk = show_ids[i : i + chunk_size]
            params = {
                'limit': chunk_size,
                'id': chunk,
                'selectFields': self._SELECT_FIELDS,
            }

            try:
                response = self.session.get(
                    self.BASE_URL, headers=headers, params=params, timeout=20
                )

                if response.status_code == 403:
                    logging.warning('Poiskkino API limit reached (403) during ID fetch. Stopping.')
                    break

                response.raise_for_status()
                data = response.json()
                results.extend(data.get('docs', []))
                checked_values.extend(chunk)
                requests_made += 1
            except requests.RequestException as e:
                logging.error(f'Poiskkino fetch_ratings_by_ids error: {e}')
                break

        return PoiskkinoFetchResult(
            results,
            checked_values,
            len(checked_values) == len(show_ids),
            requests_made,
        )

    def fetch_ratings_by_imdb_ids(self, imdb_ids: list[str]) -> PoiskkinoFetchResult:
        if not self.api_key or not imdb_ids:
            return PoiskkinoFetchResult([], [], False, 0)

        headers = {'X-API-KEY': self.api_key}
        results = []
        checked_values = []
        chunk_size = 250
        requests_made = 0

        for i in range(0, len(imdb_ids), chunk_size):
            chunk = imdb_ids[i : i + chunk_size]
            params = {
                'limit': chunk_size,
                'externalId.imdb': chunk,
                'selectFields': self._SELECT_FIELDS + ['externalId'],
            }

            try:
                response = self.session.get(
                    self.BASE_URL, headers=headers, params=params, timeout=20
                )

                if response.status_code == 403:
                    logging.warning(
                        'Poiskkino API limit reached (403) during IMDb ID fetch. Stopping.'
                    )
                    break

                response.raise_for_status()
                data = response.json()
                results.extend(data.get('docs', []))
                checked_values.extend(chunk)
                requests_made += 1
            except requests.RequestException as e:
                logging.error(f'Poiskkino fetch_ratings_by_imdb_ids error: {e}')
                break

        return PoiskkinoFetchResult(
            results,
            checked_values,
            len(checked_values) == len(imdb_ids),
            requests_made,
        )
