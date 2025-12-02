import logging
import time
from typing import Optional

import requests
from django.conf import settings
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

logger = logging.getLogger(__name__)


class TelegramSender:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramSender, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.session = requests.Session()
        self.api_base = f'https://api.telegram.org/bot{settings.BOT_TOKEN}'
        self._initialized = True

    def _request(self, method: str, endpoint: str, payload: dict, attempt: int = 0) -> dict | None:
        if not settings.BOT_TOKEN or not settings.CHAT_ID:
            logger.error('BOT_TOKEN or CHAT_ID is not set in settings.')
            return None

        url = f'{self.api_base}/{endpoint}'

        try:
            response = self.session.request(
                method=method, url=url, data=payload, timeout=settings.REQUEST_TIMEOUT
            )

            # Обработка Flood Limit (429 Too Many Requests)
            if response.status_code == 429:
                try:
                    retry_after = int(response.json().get('parameters', {}).get('retry_after', 5))
                except (ValueError, AttributeError):
                    retry_after = 5

                logger.warning(f'Flood limit exceeded. Sleep {retry_after} seconds.')
                time.sleep(retry_after + 1)
                # Рекурсивный повтор с увеличением счетчика попыток
                return self._request(method, endpoint, payload, attempt + 1)

            # Обработка ошибок сервера (5xx) - считаем их временными
            if 500 <= response.status_code < 600:
                raise HTTPError(f'Server Error: {response.status_code}')

            response.raise_for_status()
            return response.json()

        except (ConnectionError, Timeout, HTTPError) as e:
            if attempt < settings.MAX_RETRIES:
                sleep_time = 0.5 * (attempt + 1)
                logger.warning(f'Telegram Network/Server error: {e}. Retrying in {sleep_time}s...')
                time.sleep(sleep_time)
                return self._request(method, endpoint, payload, attempt + 1)

            logger.error(
                f'Failed to request Telegram API ({endpoint}) after {attempt} retries: {e}'
            )
            return None

        except RequestException as e:
            # Специфичная обработка 400 Bad Request, если сообщение не изменилось
            if (
                'response' in locals()
                and response.status_code == 400
                and 'message is not modified' in response.text
            ):
                logger.info(f'Telegram API info: {response.text}')
                return None

            logger.error(f'Telegram Request Error ({endpoint}): {e}')
            return None

    def send_message(self, message: str) -> int | None:
        payload = {'chat_id': settings.CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        data = self._request('POST', 'sendMessage', payload)

        if data and data.get('ok'):
            msg_id = data['result']['message_id']
            logger.info(f"Sent to Telegram: '{message}' (msg_id: {msg_id})")
            return msg_id
        return None

    def edit_message_to_expired(self, message_id: int):
        payload = {
            'chat_id': settings.CHAT_ID,
            'message_id': message_id,
            'text': '<i>Code expired</i>',
            'parse_mode': 'HTML',
        }

        # Для editMessageText используем тот же механизм _request
        self._request('POST', 'editMessageText', payload)
        logger.info(f'Edited message {message_id} to Expired status (if successful).')
