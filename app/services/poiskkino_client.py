import logging
from datetime import date

import requests
from django.conf import settings


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

    def fetch_updated_ratings(self, start_date: date, end_date: date) -> list[dict]:
        if not self.api_key:
            return []

        date_str = f'{start_date.strftime("%d.%m.%Y")}-{end_date.strftime("%d.%m.%Y")}'
        headers = {'X-API-KEY': self.api_key}

        params = {'limit': 250, 'updatedAt': date_str, 'selectFields': self._SELECT_FIELDS}

        results = []
        next_cursor = None
        max_requests = 190
        request_count = 0

        while request_count < max_requests:
            if next_cursor:
                params['next'] = next_cursor

            try:
                response = requests.get(self.BASE_URL, headers=headers, params=params, timeout=20)

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
                    break
            except requests.RequestException as e:
                logging.error(f'Poiskkino fetch_updated_ratings error: {e}')
                break

        return results

    def fetch_ratings_by_ids(self, show_ids: list[int]) -> list[dict]:
        if not self.api_key or not show_ids:
            return []

        headers = {'X-API-KEY': self.api_key}
        results = []
        chunk_size = 250

        for i in range(0, len(show_ids), chunk_size):
            chunk = show_ids[i : i + chunk_size]
            params = {
                'limit': chunk_size,
                'id': chunk,
                'selectFields': self._SELECT_FIELDS,
            }

            try:
                response = requests.get(self.BASE_URL, headers=headers, params=params, timeout=20)

                if response.status_code == 403:
                    logging.warning('Poiskkino API limit reached (403) during ID fetch. Stopping.')
                    break

                response.raise_for_status()
                data = response.json()
                results.extend(data.get('docs', []))
            except requests.RequestException as e:
                logging.error(f'Poiskkino fetch_ratings_by_ids error: {e}')
                break

        return results
