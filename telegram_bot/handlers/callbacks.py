import os

import client
import keyboards
from aiogram import Bot
from aiogram.types import CallbackQuery
from html_helper import bold, code
from sender import MessageSender

ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')


async def registration_callback_handler(callback: CallbackQuery, bot: Bot):
    sender = MessageSender(bot)
    user = callback.from_user

    if not ADMIN_CHANNEL_ID:
        await callback.answer(
            'Ошибка конфигурации: не задан канал администратора.', show_alert=True
        )
        return

    admin_text = (
        f'🆕 {bold("Новая заявка на регистрацию")}\n\n'
        f'👤 {bold("Имя:")} {user.full_name}\n'
        f'🆔 {bold("ID:")} {code(user.id)}\n'
        f'🔗 {bold("Username:")} @{user.username if user.username else "Нет"}'
    )

    # Отправка админу
    await sender.send_message(
        chat_id=ADMIN_CHANNEL_ID,
        text=admin_text,
        keyboard=keyboards.get_admin_approval_keyboard(
            user.id, user.username or '', user.first_name
        ),
    )

    # Ответ пользователю (редактируем старое сообщение)
    user_text = (
        f'⏳ {bold("Заявка отправлена!")}\n\n'
        'Пожалуйста, ожидайте решения администратора. '
        'Я пришлю уведомление, как только доступ будет открыт.'
    )
    await sender.send_message(chat_id=user.id, text=user_text, edit_message=callback.message)


async def admin_approve_handler(callback: CallbackQuery, bot: Bot):
    sender = MessageSender(bot)
    try:
        user_id = int(callback.data.split('_')[1])

        # Пытаемся получить актуальные данные юзера
        try:
            chat_member = await bot.get_chat_member(user_id, user_id)
            user = chat_member.user
            username = user.username
            first_name = user.first_name
            language_code = user.language_code or 'ru'
        except Exception:
            username = 'Unknown'
            first_name = 'User'
            language_code = 'ru'

        # Регистрируем на бекенде (асинхронно)
        success = await client.register_user(user_id, username, first_name, language_code)

        if success:
            await sender.send_message(
                chat_id=callback.message.chat.id,
                text=f'{callback.message.text}\n\n✅ {bold("Одобрено")}',
                edit_message=callback.message,
            )

            # Уведомляем пользователя
            await sender.send_message(
                chat_id=user_id,
                text=f'🎉 {bold("Поздравляем! Ваша заявка одобрена.")}\n\nТеперь вам доступен полный функционал бота.',
            )
        else:
            await callback.answer('Ошибка при создании пользователя на бекенде', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def admin_reject_handler(callback: CallbackQuery, bot: Bot):
    sender = MessageSender(bot)
    user_id = int(callback.data.split('_')[1])

    await sender.send_message(
        chat_id=callback.message.chat.id,
        text=f'{callback.message.text}\n\n❌ {bold("Отклонено")}',
        edit_message=callback.message,
    )

    await sender.send_message(
        chat_id=user_id,
        text=f'😔 {bold("Ваша заявка на регистрацию была отклонена администратором.")}',
    )
