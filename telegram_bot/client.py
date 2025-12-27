import logging
import os
from typing import Any

import aiohttp

from shared.constants import UserRole

BACKEND_URL = os.getenv('BACKEND_URL')
BOT_TOKEN = os.getenv('BOT_TOKEN')

HEADERS = {'X-Bot-Token': BOT_TOKEN, 'Content-Type': 'application/json'}


async def _execute_request(
    path: str, method: str = 'GET', payload: dict = None, params: dict = None
) -> Any | None:
    url = f'{BACKEND_URL}/api/bot/{path}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=payload, params=params, headers=HEADERS, timeout=5
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 409:
                    return {'success': False, 'error': 'outdated'}

                logging.error(f'API Error ({url}): Status {response.status}')
                return None
    except Exception as e:
        logging.error(f'API Connection Error ({url}): {e}')
        return None


async def register_user(
    telegram_id: int, username: str, first_name: str, language_code: str
) -> bool:
    payload = {
        'telegram_id': telegram_id,
        'username': username,
        'first_name': first_name,
        'language_code': language_code,
    }
    data = await _execute_request('register/', method='POST', payload=payload)
    return bool(data)


async def set_user_role(telegram_id: int, role: str, message_id: int) -> dict:
    payload = {'telegram_id': telegram_id, 'role': role, 'message_id': message_id}
    data = await _execute_request('set_role/', method='POST', payload=payload)

    if data:
        if 'error' in data:
            return data
        return {'success': True}

    return {'success': False, 'error': 'api_error'}


async def update_user_data(
    telegram_id: int, username: str, first_name: str, language_code: str, is_active: bool = None
) -> bool:
    payload = {
        'telegram_id': telegram_id,
        'username': username,
        'first_name': first_name,
        'language_code': language_code,
    }
    if is_active is not None:
        payload['is_active'] = is_active

    data = await _execute_request('update_user/', method='POST', payload=payload)
    return bool(data)


async def search_shows(query: str) -> list:
    data = await _execute_request('search/', params={'q': query})
    return data.get('results', []) if data else []


async def get_show_details(show_id: int, telegram_id: int = None) -> dict | None:
    params = {}
    if telegram_id:
        params['telegram_id'] = telegram_id
    return await _execute_request(f'show/{show_id}/', params=params)


async def get_show_by_imdb_id(imdb_id: str) -> dict | None:
    return await _execute_request(f'imdb/{imdb_id}/')


async def assign_view(telegram_id: int, view_id: int) -> dict | None:
    payload = {'telegram_id': telegram_id, 'view_id': view_id}
    return await _execute_request('assign_view/', method='POST', payload=payload)


async def unassign_view(telegram_id: int, view_id: int) -> bool:
    payload = {'telegram_id': telegram_id, 'view_id': view_id}
    data = await _execute_request('unassign_view/', method='POST', payload=payload)
    return bool(data)


async def toggle_view_check(view_id: int, telegram_id: int = None) -> dict | None:
    payload = {'view_id': view_id}
    if telegram_id:
        payload['telegram_id'] = telegram_id
    return await _execute_request('toggle_check/', method='POST', payload=payload)


async def check_user_role(telegram_id: int) -> str:
    data = await _execute_request(f'check/{telegram_id}/')
    if data and data.get('exists'):
        return data.get('role', UserRole.GUEST)
    return UserRole.GUEST


async def toggle_claim(telegram_id: int, view_id: int) -> dict | None:
    payload = {'telegram_id': telegram_id, 'view_id': view_id}
    return await _execute_request('toggle_claim/', method='POST', payload=payload)


async def toggle_view_user(telegram_id: int, view_id: int) -> dict | None:
    payload = {'telegram_id': telegram_id, 'view_id': view_id}
    return await _execute_request('toggle_view_user/', method='POST', payload=payload)


async def rate_show(
    telegram_id: int, show_id: int, rating: float, season: int = None, episode: int = None
) -> dict | None:
    payload = {
        'telegram_id': telegram_id,
        'show_id': show_id,
        'rating': rating,
        'season': season,
        'episode': episode,
    }
    return await _execute_request('rate/', method='POST', payload=payload)


async def get_show_episodes(show_id: int, telegram_id: int = None) -> list:
    params = {}
    if telegram_id:
        params['telegram_id'] = telegram_id
    data = await _execute_request(f'show/{show_id}/episodes/', params=params)
    return data.get('episodes', []) if data else []


async def get_show_ratings_details(show_id: int) -> list:
    data = await _execute_request(f'show/{show_id}/ratings/')
    return data.get('ratings', []) if data else []


async def log_telegram_event(raw_data: dict):
    """
    Отправляет лог события (сообщения) в Django API.
    Принимает только сырые данные, логика разбора находится на стороне получателя (Admin).
    """
    # Используем fire-and-forget
    try:
        await _execute_request('log/', method='POST', payload=raw_data)
    except Exception:
        pass


async def send_log_entry(level: str, module: str, message: str):
    """
    Отправляет системный лог (ошибку/предупреждение) в базу Django.
    Ошибки при отправке игнорируются или выводятся в stderr, чтобы избежать рекурсии логгера.
    """
    payload = {
        'level': level,
        'module': module,
        'message': message,
    }
    url = f'{BACKEND_URL}/api/bot/log_entry/'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=HEADERS, timeout=5) as response:
                if response.status != 200:
                    print(f'Failed to send log entry to backend. Status: {response.status}')
    except Exception as e:
        print(f'Connection error while sending log entry: {e}')
