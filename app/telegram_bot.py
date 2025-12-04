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
        if not settings.BOT_TOKEN or not settings.CODES_CHANNEL_ID:
            logger.error('BOT_TOKEN or CODES_CHANNEL_ID is not set in settings.')
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
        payload = {'chat_id': settings.CODES_CHANNEL_ID, 'text': message, 'parse_mode': 'HTML'}
        data = self._request('POST', 'sendMessage', payload)

        if data and data.get('ok'):
            msg_id = data['result']['message_id']
            logger.info(f"Sent to Telegram: '{message}' (msg_id: {msg_id})")
            return msg_id
        return None

    def edit_message_to_expired(self, message_id: int):
        payload = {
            'chat_id': settings.CODES_CHANNEL_ID,
            'message_id': message_id,
            'text': '<i>Code expired</i>',
            'parse_mode': 'HTML',
        }

        # Для editMessageText используем тот же механизм _request
        self._request('POST', 'editMessageText', payload)
        logger.info(f'Edited message {message_id} to Expired status (if successful).')

    def delete_message(self, chat_id, message_id):
        if not message_id:
            return
        payload = {'chat_id': chat_id, 'message_id': message_id}
        self._request('POST', 'deleteMessage', payload)

    def send_user_role_message(self, view_user):
        """Отправляет или переотправляет сообщение с управлением правами пользователя."""
        if not settings.USER_MANAGEMENT_CHANNEL_ID:
            logger.warning('USER_MANAGEMENT_CHANNEL_ID is not set.')
            return

        # Если есть старое сообщение, сначала чистим кнопки, затем удаляем
        if view_user.role_message_id:
            try:
                # 1. Убираем клавиатуру (чтобы кнопки не работали, если удаление не пройдет)
                self._request('POST', 'editMessageReplyMarkup', {
                    'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
                    'message_id': view_user.role_message_id,
                    'reply_markup': {'inline_keyboard': []}
                })
                # 2. Удаляем само сообщение
                self.delete_message(settings.USER_MANAGEMENT_CHANNEL_ID, view_user.role_message_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup old role message {view_user.role_message_id}: {e}")

        text = (
            f"👤 <b>User Registration / Role Management</b>\n\n"
            f"<b>Name:</b> {view_user.name or 'N/A'}\n"
            f"<b>Username:</b> @{view_user.username or 'N/A'}\n"
            f"<b>ID:</b> <code>{view_user.telegram_id}</code>\n"
            f"<b>Language:</b> {view_user.language}\n"
            f"<b>Registered:</b> {view_user.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

        keyboard = self._get_role_keyboard(view_user)
        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': keyboard}
        }

        data = self._request('POST', 'sendMessage', payload)
        if data and data.get('ok'):
            new_msg_id = data['result']['message_id']
            view_user.role_message_id = new_msg_id
            view_user.save(update_fields=['role_message_id'])
            logger.info(f"Role message sent for user {view_user.telegram_id} (msg_id: {new_msg_id})")

    def update_user_role_message(self, view_user):
        """Обновляет клавиатуру в существующем сообщении."""
        if not settings.USER_MANAGEMENT_CHANNEL_ID or not view_user.role_message_id:
            return

        keyboard = self._get_role_keyboard(view_user)
        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'message_id': view_user.role_message_id,
            'reply_markup': {'inline_keyboard': keyboard}
        }
        self._request('POST', 'editMessageReplyMarkup', payload)

    def _get_role_keyboard(self, view_user):
        from app.constants import UserRole  # Импорт внутри, чтобы избежать циклов
        buttons = []
        for role in UserRole:
            is_active = (role.value == view_user.role)
            label = f"✅ {role.name}" if is_active else role.name
            # callback_data: setrole_<user_id>_<role_value>
            buttons.append({
                'text': label,
                'callback_data': f"setrole_{view_user.telegram_id}_{role.value}"
            })
        return [buttons]