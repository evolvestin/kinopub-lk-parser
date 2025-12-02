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
