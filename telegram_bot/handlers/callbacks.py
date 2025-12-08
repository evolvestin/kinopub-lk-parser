import client
from aiogram import Bot
from aiogram.types import CallbackQuery
from app.telegram_bot.utils.formatting import italic


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
                '⚠️ Это сообщение устарело.'
                ' Используйте более новое сообщение для управления этим пользователем.',
                show_alert=True,
            )
        else:
            await callback.answer(f'Ошибка: {result.get("error")}', show_alert=True)

    except Exception as e:
        await callback.answer(f'Произошла ошибка: {e}', show_alert=True)


async def cancel_claim_handler(callback: CallbackQuery, bot: Bot):
    """
    Обрабатывает отмену привязки просмотра.
    Format: unclaim_<view_id>
    """
    try:
        _, view_id = callback.data.split('_', 1)
        view_id = int(view_id)
        user_id = callback.from_user.id

        success = await client.unassign_view(user_id, view_id)

        if success:
            await callback.message.edit_text(
                f'🗑 {italic("Привязка просмотра отменена.")}', reply_markup=None
            )
            await callback.answer('Отменено')
        else:
            await callback.answer('Ошибка при отмене', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)
