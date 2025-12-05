import client
from aiogram import Bot
from aiogram.types import CallbackQuery


async def role_switch_handler(callback: CallbackQuery, bot: Bot):
    """
    Обрабатывает нажатие на кнопки смены ролей в админ-канале.
    Format: setrole_<user_id>_<role_value>
    """
    try:
        _, user_id, role = callback.data.split('_', 2)
        user_id = int(user_id)

        # Вызываем API бекенда для смены роли
        # Бекенд сам проверит актуальность message_id и вернет ошибку, если сообщение устарело
        result = await client.set_user_role(user_id, role, callback.message.message_id)

        if result.get('success'):
            # Бекенд сам обновит клавиатуру сообщения через Telegram API
            # Нам нужно только убрать часики загрузки у нажавшего
            await callback.answer(f'Роль успешно изменена на {role.upper()}')

        elif result.get('error') == 'outdated':
            await callback.answer(
                '⚠️ Это сообщение устарело. Используйте более новое сообщение для управления этим пользователем.',
                show_alert=True,
            )
        else:
            await callback.answer(f'Ошибка: {result.get("error")}', show_alert=True)

    except Exception as e:
        await callback.answer(f'Произошла ошибка: {e}', show_alert=True)
