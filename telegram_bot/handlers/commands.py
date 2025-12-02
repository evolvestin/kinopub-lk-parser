import os

import client
import keyboards
from aiogram import Bot
from aiogram.types import Message
from html_helper import bold
from sender import MessageSender

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')


async def bot_command_start_private(message: Message, bot: Bot):
    sender = MessageSender(bot)
    user_id = message.from_user.id
    first_name = message.from_user.first_name

    # Проверяем наличие пользователя (асинхронно)
    exists = await client.check_user_exists(user_id)

    if exists:
        text = (
            f'👋 {bold(f"С возвращением, {first_name}!")}\n\n'
            'Вы уже зарегистрированы в системе. '
            'Я готов показывать вашу статистику и новые эпизоды.'
        )
        await sender.send_message(chat_id=user_id, text=text)
    else:
        text = (
            f'👋 {bold(f"Привет, {first_name}!")}\n\n'
            'Я — бот для сбора статистики по фильмам и сериалам на основе KinoPub.\n'
            'Для доступа к функциям необходимо пройти процедуру регистрации.\n\n'
            f'⚠️ {bold(f"Заявки обрабатываются вручную администратором (@{ADMIN_USERNAME}).")}'
        )
        await sender.send_message(
            chat_id=user_id, text=text, keyboard=keyboards.get_registration_keyboard()
        )


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
