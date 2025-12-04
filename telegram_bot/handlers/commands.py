import os

import client
import keyboards
from aiogram import Bot
from aiogram.types import Message
from html_helper import bold, html_secure
from sender import MessageSender

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')


async def bot_command_start_private(message: Message, bot: Bot):
    sender = MessageSender(bot)
    user = message.from_user

    success = await client.register_user(
        user.id,
        user.username,
        user.first_name,
        user.language_code or 'ru'
    )

    if success:
        text = (
            f'👋 {bold(f"Привет, {html_secure(user.first_name)}!")}\n\n'
            'Вы успешно зарегистрированы в системе.\n'
            f'По умолчанию вам присвоена роль {bold("Guest")}.\n\n'
            'Если вам нужен доступ к дашборду или админ-панели, '
            'обратитесь к администратору для повышения прав.'
        )
    else:
        text = f'⚠️ {bold("Ошибка регистрации.")}\nПопробуйте позже или свяжитесь с администратором.'

    await sender.send_message(chat_id=user.id, text=text)


async def bot_command_start_group(message: Message, bot: Bot):
    sender = MessageSender(bot)
    text = (
        f'🤖 {bold("Приветствую всех участников чата!")}\n\n'
        'К сожалению, зарегистрировать целый чат для просмотра статистики нельзя — '
        'этот функционал доступен только для личных аккаунтов.\n\n'
        f'📉 Если вы хотите получать персональную статистику, пожалуйста, '
        f'напишите мне в {bold("личные сообщения")} и пройдите регистрацию.'
    )
    await sender.send_message(chat_id=message.chat.id, text=text)
