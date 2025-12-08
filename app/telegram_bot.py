import logging

import requests
from django.conf import settings

from shared.html_helper import bold, code, html_secure, italic

logger = logging.getLogger(__name__)


class TelegramSender:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.service_url = 'http://telegram-bot:8081/api'
            cls._instance._bot_username = None

            try:
                data = cls._instance._request('get_me', method='GET')
                if data and data.get('ok'):
                    cls._instance._bot_username = data['result']['username']
            except Exception as e:
                logger.error(f'Failed to fetch bot username at startup: {e}')

        return cls._instance

    def _request(self, endpoint: str, payload: dict = None, method: str = 'POST') -> dict | None:
        url = f'{self.service_url}/{endpoint}'
        try:
            if method == 'GET':
                response = requests.get(url, timeout=settings.REQUEST_TIMEOUT)
            else:
                response = requests.post(url, json=payload, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Internal Bot API request error ({endpoint}): {e}')
            return None

    def send_message(self, message: str) -> int | None:
        if not settings.CODES_CHANNEL_ID:
            return None

        payload = {'chat_id': settings.CODES_CHANNEL_ID, 'text': message, 'parse_mode': 'HTML'}
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
            f'👤 {bold("User Registration / Role Management")}\n\n'
            f'{bold("Name:")} {html_secure(view_user.name or "N/A")}\n'
            f'{bold("Username:")} @{html_secure(view_user.username or "N/A")}\n'
            f'{bold("ID:")} {code(view_user.telegram_id)}\n'
            f'{bold("Language:")} {view_user.language}\n'
            f'{bold("Registered:")} {view_user.created_at.strftime("%Y-%m-%d %H:%M")}'
        )

        keyboard = self._get_role_keyboard(view_user)

        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': keyboard},
        }

        data = self._request('send_message', payload)
        if data and data.get('ok'):
            new_msg_id = data['result']['message_id']
            view_user.role_message_id = new_msg_id
            view_user.save(update_fields=['role_message_id'])
            logger.info(f'Role message sent via Bot Service for user {view_user.telegram_id}')

    def update_user_role_message(self, view_user, empty_keyboard=False):
        if not settings.USER_MANAGEMENT_CHANNEL_ID or not view_user.role_message_id:
            return

        keyboard = [] if empty_keyboard else self._get_role_keyboard(view_user)

        text = (
            f'👤 {bold("User Registration / Role Management")}\n\n'
            f'{bold("Name:")} {html_secure(view_user.name or "N/A")}\n'
            f'{bold("Username:")} @{html_secure(view_user.username or "N/A")}\n'
            f'{bold("ID:")} {code(view_user.telegram_id)}\n'
            f'{bold("Language:")} {view_user.language}\n'
            f'{bold("Registered:")} {view_user.created_at.strftime("%Y-%m-%d %H:%M")}'
        )

        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'message_id': view_user.role_message_id,
            'text': text,
            'reply_markup': {'inline_keyboard': keyboard},
        }
        self._request('edit_message', payload)

    def _get_role_keyboard(self, view_user):
        from app.constants import UserRole

        buttons = []
        for role in UserRole:
            is_active = role.value == view_user.role
            label = f'✅ {role.name}' if is_active else role.name
            buttons.append(
                {'text': label, 'callback_data': f'setrole_{view_user.telegram_id}_{role.value}'}
            )
        return [buttons]

    def send_history_notification(self, view_history_obj):
        if not settings.HISTORY_CHANNEL_ID:
            return

        show = view_history_obj.show
        title = show.title or show.original_title or f'Show {show.id}'
        if show.title and show.original_title and show.title != show.original_title:
            title = f'{show.title} ({show.original_title})'

        season = view_history_obj.season_number
        episode = view_history_obj.episode_number

        if season and season > 0:
            content_info = f'📺 <b>{title}</b>\nS{season:02d}E{episode:02d}'
        else:
            content_info = f'🎬 <b>{title}</b>'

        text = (
            f'{content_info}\n'
            f'🗓 {view_history_obj.view_date.strftime("%d.%m.%Y")}\n'
            f'<i>Новый просмотр зафиксирован</i>'
        )

        url = f'https://t.me/{self.bot_username}?start=claim_{view_history_obj.id}'
        keyboard = [[{'text': '👀 Это я смотрю', 'url': url}]]

        payload = {
            'chat_id': settings.HISTORY_CHANNEL_ID,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': keyboard},
        }
        self._request('send_message', payload)

    def send_role_upgrade_notification(self, telegram_id, role):
        if not settings.HISTORY_CHANNEL_ID:
            return

        # Если ссылка не задана в settings, можно попробовать сформировать стандартную,
        # но для приватных каналов лучше использовать invite link.
        # Для упрощения примера предполагаем, что ID канала достаточно,
        # но в реальности пользователю нужна ссылка-приглашение.
        # Здесь выводим ID или заранее заготовленную ссылку из env, если есть.

        channel_info = 'Вам открыт доступ к каналу истории просмотров.'
        if (
            hasattr(settings, 'HISTORY_CHANNEL_INVITE_LINK')
            and settings.HISTORY_CHANNEL_INVITE_LINK
        ):
            channel_info += f'\nСсылка: {settings.HISTORY_CHANNEL_INVITE_LINK}'

        text = (
            f'🎉 <b>Ваш уровень доступа повышен до {role.upper()}!</b>\n\n'
            f'Теперь вам доступны расширенные возможности бота.\n'
            f'{channel_info}'
        )

        payload = {'chat_id': telegram_id, 'text': text, 'parse_mode': 'HTML'}
        self._request('send_message', payload)
