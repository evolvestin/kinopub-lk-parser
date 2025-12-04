import logging
import requests
from django.conf import settings
from shared.html_helper import html_secure, bold, code, italic

logger = logging.getLogger(__name__)


class TelegramSender:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramSender, cls).__new__(cls)
            cls._instance.service_url = 'http://telegram-bot:8081/api'
        return cls._instance

    def _request(self, endpoint: str, payload: dict) -> dict | None:
        url = f'{self.service_url}/{endpoint}'
        try:
            response = requests.post(url, json=payload, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Internal Bot API request error ({endpoint}): {e}')
            return None

    def send_message(self, message: str) -> int | None:
        if not settings.CODES_CHANNEL_ID:
            return None
            
        payload = {
            'chat_id': settings.CODES_CHANNEL_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        data = self._request('send_message', payload)

        if data and data.get('ok'):
            msg_id = data['result']['message_id']
            logger.info(f"Sent via Bot Service: '{message}' (msg_id: {msg_id})")
            return msg_id
        return None

    def edit_message_to_expired(self, message_id: int):
        if not settings.CODES_CHANNEL_ID or not message_id:
            return

        payload = {
            'chat_id': settings.CODES_CHANNEL_ID,
            'message_id': message_id,
            'text': italic('Code expired'),
            'parse_mode': 'HTML',
        }
        self._request('edit_message', payload)

    def delete_message(self, chat_id, message_id):
        if not message_id:
            return
        
        payload = {'chat_id': chat_id, 'message_id': message_id}
        self._request('delete_message', payload)

    def send_user_role_message(self, view_user):
        if not settings.USER_MANAGEMENT_CHANNEL_ID:
            logger.error('USER_MANAGEMENT_CHANNEL_ID is not set.')
            return

        if view_user.role_message_id:
            self.update_user_role_message(view_user, empty_keyboard=True)
            self.delete_message(settings.USER_MANAGEMENT_CHANNEL_ID, view_user.role_message_id)

        text = (
            f"👤 {bold('User Registration / Role Management')}\n\n"
            f"{bold('Name:')} {html_secure(view_user.name or 'N/A')}\n"
            f"{bold('Username:')} @{html_secure(view_user.username or 'N/A')}\n"
            f"{bold('ID:')} {code(view_user.telegram_id)}\n"
            f"{bold('Language:')} {view_user.language}\n"
            f"{bold('Registered:')} {view_user.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

        keyboard = self._get_role_keyboard(view_user)
        
        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': keyboard}
        }

        data = self._request('send_message', payload)
        if data and data.get('ok'):
            new_msg_id = data['result']['message_id']
            view_user.role_message_id = new_msg_id
            view_user.save(update_fields=['role_message_id'])
            logger.info(f"Role message sent via Bot Service for user {view_user.telegram_id}")

    def update_user_role_message(self, view_user, empty_keyboard=False):
        if not settings.USER_MANAGEMENT_CHANNEL_ID or not view_user.role_message_id:
            return

        keyboard = [] if empty_keyboard else self._get_role_keyboard(view_user)
        
        text = (
            f"👤 {bold('User Registration / Role Management')}\n\n"
            f"{bold('Name:')} {html_secure(view_user.name or 'N/A')}\n"
            f"{bold('Username:')} @{html_secure(view_user.username or 'N/A')}\n"
            f"{bold('ID:')} {code(view_user.telegram_id)}\n"
            f"{bold('Language:')} {view_user.language}\n"
            f"{bold('Registered:')} {view_user.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'message_id': view_user.role_message_id,
            'text': text,
            'reply_markup': {'inline_keyboard': keyboard}
        }
        self._request('edit_message', payload)

    def _get_role_keyboard(self, view_user):
        from app.constants import UserRole
        buttons = []
        for role in UserRole:
            is_active = (role.value == view_user.role)
            label = f"✅ {role.name}" if is_active else role.name
            buttons.append({
                'text': label,
                'callback_data': f"setrole_{view_user.telegram_id}_{role.value}"
            })
        return [buttons]
