import os
from datetime import datetime

from aiogram import Bot, types
from services.bot_instance import BotInstance

from shared.html_helper import blockquote, bold, code, html_secure

# Получаем ID канала для логов из окружения
ID_LOGS = os.getenv('LOG_CHANNEL_ID')


class EntitiesToHTML:
    """Handles the conversion of message entities into HTML tags for formatting purposes."""

    def __init__(self, message: types.Message):
        self.message: types.Message = message

    @staticmethod
    def generate_html_tags(entity: types.MessageEntity) -> tuple[str, str]:
        """Generates HTML opening and closing tags based on the entity type."""
        if entity.type == 'pre':
            if entity.language:
                return f'<pre><code class="language-{entity.language}">', '</code></pre>'
            else:
                return '<pre>', '</pre>'

        if entity.type in [
            'url',
            'email',
            'cashtag',
            'hashtag',
            'mention',
            'phone_number',
            'text_mention',
        ]:
            return '', ''

        html_tags_by_type = {
            'bold': ('<b>', '</b>'),
            'italic': ('<i>', '</i>'),
            'underline': ('<u>', '</u>'),
            'code': ('<code>', '</code>'),
            'strikethrough': ('<s>', '</s>'),
            'spoiler': ('<tg-spoiler>', '</tg-spoiler>'),
            'blockquote': ('<blockquote>', '</blockquote>'),
            'text_link': (f'<a href="{entity.url}">', '</a>'),
            'expandable_blockquote': ('<blockquote expandable>', '</blockquote>'),
        }
        return html_tags_by_type.get(entity.type) or html_tags_by_type['code']

    def convert(self) -> str:
        """Converts message entities to an HTML formatted string."""
        entities = self.message.entities or self.message.caption_entities
        text_list = list(self.message.text or self.message.caption or [])
        if entities:
            position = 0
            for entity in text_list:
                true_length = len(entity.encode('utf-16-le')) // 2
                while true_length > 1:
                    text_list.insert(position + 1, '')
                    true_length -= 1
                position += 1
            for entity in reversed(entities):
                end_index = entity.offset + entity.length - 1
                if entity.offset + entity.length >= len(text_list):
                    end_index = len(text_list) - 1

                tag_start, tag_end = self.generate_html_tags(entity)
                text_list[entity.offset] = f'{tag_start}{text_list[entity.offset]}'
                text_list[end_index] += tag_end
        return ''.join(text_list)


class ChatMemberLogHandler:
    """Handles logging of chat member updates in Telegram chats."""

    PERMISSIONS_MAP = {
        'can_manage_chat': 'управлять {chat_type}ом',
        'can_post_messages': 'отправлять сообщения',
        'can_edit_messages': 'редактировать сообщения',
        'can_delete_messages': 'удалять сообщения',
        'can_restrict_members': 'банить пользователей',
        'can_post_stories': 'публиковать истории',
        'can_edit_stories': 'редактировать истории',
        'can_delete_stories': 'удалять истории',
        'can_manage_video_chats': 'управлять видео чатами',
        'can_promote_members': 'назначать пользователей админом',
        'can_manage_voice_chats': 'управлять голосовыми чатами',
        'can_be_edited': 'бот редактировать этого {user_type}',
        'can_send_messages': 'отправлять сообщения',
        'can_send_photos': 'отправлять фотографии',
        'can_send_videos': 'отправлять видео',
        'can_send_video_notes': 'отправлять видео-сообщение',
        'can_send_audios': 'отправлять аудио',
        'can_send_voice_notes': 'отправлять голосовые сообщения',
        'can_send_documents': 'отправлять документы',
        'can_send_other_messages': 'отправлять стикеры и анимации',
        'can_send_media_messages': 'отправлять медиа сообщения',
        'can_add_web_page_previews': 'добавлять пред-просмотры ссылок',
        'can_send_polls': 'отправлять опросы',
        'can_invite_users': 'добавлять пользователей',
        'can_manage_topics': 'управлять темами форума',
        'can_pin_messages': 'закреплять сообщения',
        'can_change_info': 'изменять информацию о {chat_type}е',
    }

    def __init__(self, message: types.ChatMemberUpdated):
        self.message: types.ChatMemberUpdated = message
        self.old_member = message.old_chat_member
        self.new_member = message.new_chat_member
        self.old_status = message.old_chat_member.status
        self.new_status = message.new_chat_member.status
        self.ru_user_type = 'бота' if message.new_chat_member.user.is_bot else 'пользователя'
        self.ru_chat_type = 'канал' if message.chat.type == 'channel' else 'чат'

    def get_action_for_old_member(self) -> tuple[str, str]:
        """Determines the action and hashtag based on the old member status."""
        if self.old_status in ['left', 'kicked']:
            if self.message.chat.id < 0:
                return self.handle_chat_entry_or_kick()
            return f'Разблокировал {self.ru_user_type}', 'unblocked'
        else:
            if self.message.chat.id < 0:
                return self.handle_chat_removal_or_change()
            return f'Заблокировал {self.ru_user_type}', 'block'

    def handle_chat_entry_or_kick(self) -> tuple[str, str]:
        if self.new_status == 'left':
            return f'Разрешил вход {self.ru_user_type} в {self.ru_chat_type}', 'changed'
        elif self.new_status == 'kicked':
            return f'Запретил вход {self.ru_user_type} в {self.ru_chat_type}', 'changed'
        elif self.new_status == 'administrator':
            return f'Добавил {self.ru_user_type} как админа в {self.ru_chat_type}', 'added'
        return f'Добавил {self.ru_user_type} в {self.ru_chat_type}', 'added'

    def handle_chat_removal_or_change(self) -> tuple[str, str]:
        if self.new_status in ['left', 'kicked']:
            admin = '-админа' if self.old_status == 'administrator' else ''
            return f'Удалил {self.ru_user_type}{admin} из {self.ru_chat_type}а', 'kicked'
        elif self.old_status == 'administrator' and self.new_status == 'administrator':
            return f'Изменил {self.ru_user_type} как админа в {self.ru_chat_type}е', 'changed'
        elif self.new_status == 'administrator':
            return f'Назначил {self.ru_user_type} админом в {self.ru_chat_type}е', 'changed'
        elif self.old_status == 'restricted' and self.new_status == 'restricted':
            return f'Изменил ограничения {self.ru_user_type} в {self.ru_chat_type}е', 'changed'
        elif self.old_status == 'restricted' and self.new_status != 'restricted':
            return f'Снял ограничения {self.ru_user_type} в {self.ru_chat_type}е', 'changed'
        elif self.new_status == 'restricted':
            return f'Ограничил {self.ru_user_type} в {self.ru_chat_type}е', 'changed'
        return f'Забрал роль админа у {self.ru_user_type} в {self.ru_chat_type}е', 'changed'

    def compare_permissions(self) -> str:
        changes = []
        format_ctx = {'chat_type': self.ru_chat_type, 'user_type': self.ru_user_type}

        if self.old_status == self.new_status:
            for permission, desc_template in self.PERMISSIONS_MAP.items():
                old_val = getattr(self.message.old_chat_member, permission, None)
                new_val = getattr(self.message.new_chat_member, permission, None)

                if old_val is not None and new_val is not None and old_val != new_val:
                    description = desc_template.format(**format_ctx)
                    action = 'Разрешил' if new_val else 'Запретил'
                    changes.append(bold(f'{action} {description} #{permission}'))

        elif self.new_status in ['administrator', 'restricted']:
            for permission, desc_template in self.PERMISSIONS_MAP.items():
                new_val = getattr(self.message.new_chat_member, permission, None)
                if new_val is not None:
                    description = desc_template.format(**format_ctx)
                    state = 'Может' if new_val else 'Не может'
                    changes.append(bold(f'{state} {description} #{permission}'))

        return '\n'.join(changes) or ''

    def handle_self_action(self) -> tuple[str, str]:
        if self.old_status in ['left', 'kicked']:
            return f'Зашел в {self.ru_chat_type} по ссылке', 'added'
        return f'Вышел из {self.ru_chat_type}а', 'left'


class ProcessMessage:
    """Handles processing of various types of messages in Telegram."""

    def __init__(self, message: types.Message):
        self.message: types.Message = message

    def get_chat_action_description(self) -> str | None:
        if self.message.new_chat_title:
            return f'{bold("Изменил название чата")} #new_chat_title'
        elif self.message.delete_chat_photo:
            return f'{bold("Удалил аватар чата")} #delete_chat_photo'
        elif self.message.left_chat_member:
            return f'{bold("Участник покинул чат")} #left_chat_member'
        elif self.message.new_chat_members:
            return f'{bold("Добавил новых участников в чат")} #new_chat_members'
        elif self.message.pinned_message:
            return f'{bold("Закрепил сообщение")} #pinned_message'
        elif self.message.forum_topic_created:
            return f'{bold("Создал тему форума")} #forum_topic_created'
        elif self.message.forum_topic_edited:
            return f'{bold("Отредактировал тему форума")} #forum_topic_edited'
        elif self.message.forum_topic_closed:
            return f'{bold("Закрыл тему форума")} #forum_topic_closed'
        elif self.message.forum_topic_reopened:
            return f'{bold("Открыл тему форума")} #forum_topic_reopened'
        else:
            return None


class TelegramLogger:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @staticmethod
    def get_header(chat: types.Chat | types.User, date: datetime = None) -> str:
        """Constructs a formatted header string with chat/user details."""
        parts = []
        if date:
            parts.append(code(date.strftime('%Y-%m-%d %H:%M:%S')))
        parts.append(html_secure(chat.full_name))
        if chat.username:
            parts.append(f'[@{chat.username}]')
        if chat.id:
            parts.append(code(chat.id))
        return ' '.join(parts)

    async def send_log(self, text: str) -> None:
        """Sends the log text to the log channel."""
        if not ID_LOGS:
            return
        try:
            # Simple chunking if needed, though usually short logs fit
            if len(text) > 4096:
                for chunk in [text[i : i + 4096] for i in range(0, len(text), 4096)]:
                    await self.bot.send_message(
                        ID_LOGS, chunk, parse_mode='HTML', disable_web_page_preview=True
                    )
            else:
                await self.bot.send_message(
                    ID_LOGS, text, parse_mode='HTML', disable_web_page_preview=True
                )
        except Exception as e:
            print(f'Logger send error: {e}')

    async def process_chat_member_update(self, event: types.ChatMemberUpdated) -> None:
        bot_username = await BotInstance().get_bot_username()
        member_text = ''
        header = f'{self.get_header(event.chat, event.date)}:\n'

        # Если действие совершил не сам бот (изменение прав бота), то покажем инициатора
        if event.from_user:
            header += f'👤 {self.get_header(event.from_user)}:\n'

        new_member = event.new_chat_member.user
        chat_member_logger = ChatMemberLogHandler(event)

        if new_member.id != event.from_user.id:
            permissions = chat_member_logger.compare_permissions()
            action_text, action_hashtag = chat_member_logger.get_action_for_old_member()
            member_text = f'\n{"🤖" if new_member.is_bot else "👤"} {self.get_header(new_member)}'
            if permissions:
                member_text += f'\n{permissions}'
        else:
            action_text, action_hashtag = chat_member_logger.handle_self_action()

        is_me = new_member.username == bot_username

        log_text = (
            f'{header}'
            f'{action_text} #{"bot" if new_member.is_bot else "user"}_{action_hashtag}'
            f'{" #me" if is_me else ""}'
            f'{member_text}'
        )
        await self.send_log(blockquote(log_text))

    async def process_message(self, message: types.Message) -> None:
        # Игнорируем сообщения в самом канале логов
        if str(message.chat.id) == str(ID_LOGS):
            return

        header_parts = [f'{self.get_header(message.chat, message.date)}:']

        # Если это группа, добавляем автора сообщения
        if message.chat.id < 0 and message.from_user:
            header_parts.append(f'👤 {self.get_header(message.from_user)}:')

        log_body = None

        if message.text:
            log_body = EntitiesToHTML(message).convert()
        elif message.caption:
            log_body = f'[Media] {EntitiesToHTML(message).convert()}'
        else:
            # Сервисные сообщения или просто медиа без подписи
            action = ProcessMessage(message).get_chat_action_description()
            if action:
                header_parts.append(action)
            else:
                # Просто медиа или неизвестный тип
                content_type = message.content_type
                log_body = f'[{content_type}]'

        full_log = '\n'.join(header_parts)
        if log_body:
            full_log += f'\n{log_body}'

        await self.send_log(blockquote(full_log))

    async def log_update(self, event: types.TelegramObject):
        """Main entry point called from Middleware."""
        try:
            if isinstance(event, types.ChatMemberUpdated):
                await self.process_chat_member_update(event)
            elif isinstance(event, types.Message):
                await self.process_message(event)
        except Exception as e:
            print(f'Error inside TelegramLogger: {e}')
