import logging

import requests
from django.apps import apps
from django.conf import settings

from app.keyboards import get_history_notification_keyboard, get_role_management_keyboard
from app.services.error_aggregator import ErrorAggregator
from app.utils import get_webapp_base_url
from shared.card_formatter import get_show_card_text
from shared.constants import DATE_FORMAT, SHOW_TYPE_DISPLAY_RU, UserRole
from shared.formatters import format_se
from shared.html_helper import bold, code, html_secure, italic

logger = logging.getLogger(__name__)


class TelegramSender:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.service_url = (
                f'http://{settings.BOT_API_HOST}:{settings.BOT_API_PORT}/api'
            )
            cls._instance._bot_username = None
        return cls._instance

    @property
    def bot_username(self):
        if self._bot_username is None:
            try:
                data = self._request('get_me', method='GET')
                if data and data.get('ok'):
                    self._bot_username = data['result']['username']
            except Exception as e:
                logger.error(f'Failed to fetch bot username: {e}')
        return self._bot_username

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
        except ValueError as e:
            logger.error(
                f'Invalid JSON response from {endpoint}: {e}. Content: {response.text[:200]}'
            )
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

    def _get_role_message_text(self, view_user):
        return (
            f'👤 {bold("User Registration / Role Management")}\n\n'
            f'{bold("Name:")} {html_secure(view_user.name or "N/A")}\n'
            f'{bold("Username:")} @{html_secure(view_user.username or "N/A")}\n'
            f'{bold("ID:")} {code(view_user.telegram_id)}\n'
            f'{bold("Language:")} {view_user.language}\n'
            f'{bold("Registered:")} {view_user.created_at.strftime("%Y-%m-%d %H:%M")}'
        )

    def send_user_role_message(self, view_user):
        if not settings.USER_MANAGEMENT_CHANNEL_ID:
            logger.error('USER_MANAGEMENT_CHANNEL_ID is not set.')
            return

        if view_user.role_message_id:
            self.update_user_role_message(view_user, empty_keyboard=True)
            self.delete_message(settings.USER_MANAGEMENT_CHANNEL_ID, view_user.role_message_id)

        text = self._get_role_message_text(view_user)
        keyboard = get_role_management_keyboard(view_user)

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

        keyboard = [] if empty_keyboard else get_role_management_keyboard(view_user)
        text = self._get_role_message_text(view_user)

        payload = {
            'chat_id': settings.USER_MANAGEMENT_CHANNEL_ID,
            'message_id': view_user.role_message_id,
            'text': text,
            'reply_markup': {'inline_keyboard': keyboard},
        }
        self._request('edit_message', payload)

    def _get_channel_post_url(self, message_id):
        if not message_id or not settings.HISTORY_CHANNEL_ID:
            return None

        channel_id = str(settings.HISTORY_CHANNEL_ID)
        if channel_id.startswith('-100'):
            clean_id = channel_id[4:]
            return f'https://t.me/c/{clean_id}/{message_id}'
        return None

    def _build_message_payload(self, view_history_obj, for_user=None, is_channel=False):
        UserRating = apps.get_model('app', 'UserRating')
        ViewUser = apps.get_model('app', 'ViewUser')

        lines = []
        season = view_history_obj.season_number
        episode = view_history_obj.episode_number

        if season and season > 0:
            lines = [f'📺 Новый просмотр ({italic(format_se(season, episode))}):', '']
        else:
            lines = ['📺 Новый просмотр:', '']

        show = view_history_obj.show
        internal_rating, user_ratings = show.get_internal_rating_data()

        show_history = True

        lines.extend(
            [
                get_show_card_text(
                    show_id=show.id,
                    title=show.title,
                    original_title=show.original_title,
                    kinopub_link=settings.SITE_AUX_URL if show.kinopub_id else None,
                    year=show.year,
                    show_type=show.type,
                    status=show.status,
                    countries=[str(country) for country in show.countries.all()],
                    genres=show.display_genres,
                    imdb_rating=show.imdb_rating,
                    imdb_url=show.imdb_url,
                    kinopoisk_rating=show.kinopoisk_rating,
                    kinopoisk_url=show.kinopoisk_url,
                    internal_rating=internal_rating,
                    user_ratings=user_ratings,
                    bot_username=self.bot_username,
                    show_history=show_history,
                    kinopub_id=show.kinopub_id,
                ),
                '',
                f'🗓 Дата просмотра: {view_history_obj.view_date.strftime(DATE_FORMAT)}',
            ]
        )

        # Логика видимости участников
        all_viewers = view_history_obj.users.all()
        visible_names = []

        if is_channel:
            # Для канала: показываем только тех, кто является Viewer или Admin.
            # Гости не отображаются в общем канале для приватности.
            visible_names = [
                f'@{u.username}' if u.username else str(u.name)
                for u in all_viewers
                if u.role != UserRole.GUEST
            ]

            if view_history_obj.is_checked:
                lines.append(f'✅ {italic("Учитывается в статистике")}')
            else:
                lines.append(f'❌ {italic("Не учитывается в статистике")}')

        elif for_user:
            # Для приватного сообщения: показываем себя и сокомандников.
            allowed_ids = {for_user.id}
            if for_user.role != UserRole.GUEST:
                mate_ids = ViewUser.objects.filter(groups__users=for_user).values_list(
                    'id', flat=True
                )
                allowed_ids.update(mate_ids)

            visible_names = [
                f'@{u.username}' if u.username else str(u.name)
                for u in all_viewers
                if u.id in allowed_ids
            ]

        if len(visible_names) == 1:
            lines.append(f'👀 Смотрит: {visible_names[0]}')
        elif len(visible_names) > 0:
            lines.append('👀 Смотрят:')
            for i, name in enumerate(visible_names, start=1):
                lines.append(f'{i}. {name}')

        personal_rating = None
        episodes_count = 0
        if for_user:
            rating_obj = UserRating.objects.filter(
                user=for_user, show=show, season_number__isnull=True
            ).first()
            if rating_obj:
                personal_rating = rating_obj.rating
            episodes_count = UserRating.objects.filter(
                user=for_user, show=show, season_number__isnull=False
            ).count()

        channel_url = None
        if not is_channel:
            # Ссылка на канал не должна быть доступна гостям
            if for_user and for_user.role != UserRole.GUEST:
                channel_url = self._get_channel_post_url(view_history_obj.telegram_message_id)

        keyboard = get_history_notification_keyboard(
            view_history_obj,
            self.bot_username,
            user_rating=personal_rating,
            episodes_rated=episodes_count,
            is_channel=is_channel,
            channel_url=channel_url,
        )

        return '\n'.join(lines), keyboard

    def send_history_notification(self, view_history_obj):
        if not settings.HISTORY_CHANNEL_ID:
            return

        text, keyboard = self._build_message_payload(view_history_obj, is_channel=True)

        payload = {
            'chat_id': settings.HISTORY_CHANNEL_ID,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': keyboard},
            'disable_web_page_preview': True,
        }
        data = self._request('send_message', payload)

        if data and data.get('ok'):
            msg_id = data['result']['message_id']
            view_history_obj.telegram_message_id = msg_id
            view_history_obj.save(update_fields=['telegram_message_id'])

    def update_history_message(self, view_history_obj):
        view_history_obj.refresh_from_db()

        if not settings.HISTORY_CHANNEL_ID or not view_history_obj.telegram_message_id:
            return

        channel_text, channel_keyboard = self._build_message_payload(
            view_history_obj, for_user=None, is_channel=True
        )

        payload = {
            'chat_id': settings.HISTORY_CHANNEL_ID,
            'message_id': view_history_obj.telegram_message_id,
            'text': channel_text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': channel_keyboard},
            'disable_web_page_preview': True,
        }
        self._request('edit_message', payload)

    def send_role_upgrade_notification(self, telegram_id, role):
        if not settings.HISTORY_CHANNEL_ID:
            return

        channel_info = 'Вам открыт доступ к каналу истории просмотров.'
        if (
            hasattr(settings, 'HISTORY_CHANNEL_INVITE_LINK')
            and settings.HISTORY_CHANNEL_INVITE_LINK
        ):
            channel_info += f'\nСсылка: {settings.HISTORY_CHANNEL_INVITE_LINK}'

        text = (
            f'🎉 {bold("Ваш уровень доступа повышен!")}\n\n'
            f'Теперь вам доступны расширенные возможности бота.\n'
            f'{channel_info}'
        )

        payload = {'chat_id': telegram_id, 'text': text, 'parse_mode': 'HTML'}
        self._request('send_message', payload)

    def send_private_history_notification(self, telegram_id, view_history_obj):
        ViewUser = apps.get_model('app', 'ViewUser')
        user = ViewUser.objects.filter(telegram_id=telegram_id).first()

        text, keyboard = self._build_message_payload(
            view_history_obj, for_user=user, is_channel=False
        )
        payload = {
            'chat_id': telegram_id,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': keyboard},
            'disable_web_page_preview': True,
        }
        self._request('send_message', payload)

    def send_dev_log(self, level: str, module: str, message: str, traceback_str: str | None = None):
        if not settings.DEV_CHANNEL_ID:
            return

        for pattern in settings.LOG_IGNORE_PATTERNS:
            if pattern in message:
                return

        try:
            aggregator = ErrorAggregator()
            aggregator.push_error(level, module, message, traceback_str)
        except Exception as e:
            print(f'Failed to push dev log to aggregator: {e}')

    def send_batch_logs(self, logs: list[dict]):
        """Метод для отправки пачки логов (вызывается из Celery задачи)."""
        if not settings.DEV_CHANNEL_ID or not logs:
            return

        env_label = settings.ENVIRONMENT or 'unknown'

        for log in logs:
            # Формируем блоки для ОДНОЙ конкретной ошибки
            text_blocks = []

            # 1. Заголовок ошибки
            header = f'{bold(log["level"])} | {env_label} | {code(log["module"])}'

            # 2. Сообщение
            text_blocks.append(html_secure(log['message']))

            # 3. Трейсбек (если есть)
            if log.get('traceback'):
                # Ограничиваем размер трейсбека разумными пределами (на всякий случай),
                # но оставляем достаточно много, так как send_split_message разобьет его.
                tb_content = log['traceback']
                if len(tb_content) > 3000:
                    tb_content = f'{tb_content[:1000]}\n...[cut]...\n{tb_content[-2000:]}'

                text_blocks.append(code(html_secure(tb_content)))

            try:
                # Отправляем каждую ошибку отдельным "разбиваемым" сообщением
                self._request(
                    'send_split_message',
                    payload={
                        'chat_id': settings.DEV_CHANNEL_ID,
                        'text_blocks': text_blocks,
                        'header': header,
                        'separator': '\n\n',
                        'parse_mode': 'HTML',
                    },
                )
            except Exception as e:
                logger.error(f'Failed to send log entry: {e}')

    def send_message_to_user(self, telegram_id: int, text: str):
        payload = {'chat_id': telegram_id, 'text': text, 'parse_mode': 'HTML'}
        return self._request('send_message', payload)

    def send_new_episode_notification(self, view_user, show, season, episode):
        se_text = format_se(season, episode)
        show_title = show.title or show.original_title

        text = (
            f'🆕 {bold("Вышла новая серия!")}\n\n'
            f'📺 {bold(html_secure(show_title))}\n'
            f'🎞 Серия: {code(se_text)}\n'
        )

        base_url = get_webapp_base_url()
        show_webapp_url = f'{base_url}/webapp/?start_param=show_{show.id}'
        unsub_webapp_url = f'{base_url}/webapp/?start_param=unsub_{show.id}'

        show_type_ru = SHOW_TYPE_DISPLAY_RU.get(show.type, show.type)
        kb_data = [
            [
                {'text': f'🎬 {show_type_ru}', 'web_app': {'url': show_webapp_url}},
                {'text': '🔕 Отписаться', 'web_app': {'url': unsub_webapp_url}},
            ]
        ]

        payload = {
            'chat_id': view_user.telegram_id,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': kb_data},
        }

        self._request('send_message', payload)
        logger.info(f'New episode notification sent to {view_user.telegram_id} for show {show.id}')
