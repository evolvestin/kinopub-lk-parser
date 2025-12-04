import logging
import os

import aiohttp

BACKEND_URL = os.getenv('BACKEND_URL')
BOT_TOKEN = os.getenv('BOT_TOKEN')

HEADERS = {'X-Bot-Token': BOT_TOKEN, 'Content-Type': 'application/json'}


async def check_user_exists(telegram_id: int) -> bool:
    url = f'{BACKEND_URL}/api/bot/check/{telegram_id}/'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('exists', False)
                logging.error(f'API Check Error: {response.status}')
                return False
    except Exception as e:
        logging.error(f'API Connection Error: {e}')
        return False


async def register_user(
    telegram_id: int, username: str, first_name: str, language_code: str
) -> bool:
    url = f'{BACKEND_URL}/api/bot/register/'
    payload = {
        'telegram_id': telegram_id,
        'username': username,
        'first_name': first_name,
        'language_code': language_code,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=HEADERS, timeout=5) as response:
                return response.status == 200
    except Exception as e:
        logging.error(f'API Registration Error: {e}')
        return False


async def set_user_role(telegram_id: int, role: str, message_id: int) -> dict:
    url = f'{BACKEND_URL}/api/bot/set_role/'
    payload = {
        'telegram_id': telegram_id,
        'role': role,
        'message_id': message_id
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=HEADERS, timeout=5) as response:
                if response.status == 200:
                    return {'success': True}
                elif response.status == 409:
                    return {'success': False, 'error': 'outdated'}
                return {'success': False, 'error': 'api_error'}
    except Exception as e:
        logging.error(f'API Set Role Error: {e}')
        return {'success': False, 'error': str(e)}


async def update_user_data(
    telegram_id: int, 
    username: str, 
    first_name: str, 
    language_code: str,
    is_active: bool = None
) -> bool:
    url = f'{BACKEND_URL}/api/bot/update_user/'
    payload = {
        'telegram_id': telegram_id,
        'username': username,
        'first_name': first_name,
        'language_code': language_code,
    }
    # Теперь передаем is_active вместо is_blocked
    if is_active is not None:
        payload['is_active'] = is_active

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=HEADERS, timeout=5) as response:
                return response.status == 200
    except Exception as e:
        logging.error(f'API Update User Error: {e}')
        return False