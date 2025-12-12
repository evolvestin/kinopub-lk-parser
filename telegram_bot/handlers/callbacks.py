import client
import keyboards
from aiogram import Bot
from aiogram.types import CallbackQuery
from html_helper import italic
from shared.constants import UserRole


async def role_switch_handler(callback: CallbackQuery, bot: Bot):
    """
    Обрабатывает нажатие на кнопки смены ролей в админ-канале.
    Format: setrole_<user_id>_<role_value>
    """
    # Проверка прав: Только Админ
    user_id = callback.from_user.id
    current_role = await client.check_user_role(user_id)
    if current_role != UserRole.ADMIN:
        await callback.answer('⛔️ Только для администраторов.', show_alert=True)
        return

    try:
        parts = callback.data.split('_')
        # setrole, user_id, role
        if len(parts) < 3:
            raise ValueError("Invalid callback data format")
        
        target_user_id = int(parts[1])
        role = parts[2]

        result = await client.set_user_role(target_user_id, role, callback.message.message_id)

        if result.get('success'):
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
    Обрабатывает отмену привязки просмотра (из личного сообщения).
    Format: unclaim_<view_id>
    """
    # Проверка прав: Viewer или Admin
    user_id = callback.from_user.id
    role = await client.check_user_role(user_id)
    if role == UserRole.GUEST:
        await callback.answer('🔒 Гостям запрещено управлять просмотрами.', show_alert=True)
        return

    try:
        view_id = int(callback.data.split('_')[-1])
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


async def toggle_check_handler(callback: CallbackQuery, bot: Bot):
    """
    Обрабатывает переключение статуса просмотра (Учтено/Не учтено).
    Format: toggle_check_<view_id>
    """
    # Проверка прав: Только Админ
    user_id = callback.from_user.id
    role = await client.check_user_role(user_id)
    if role != UserRole.ADMIN:
        await callback.answer('⛔️ Только для администраторов.', show_alert=True)
        return

    try:
        view_id = int(callback.data.split('_')[-1])

        result = await client.toggle_view_check(view_id)

        if result and result.get('status') == 'ok':
            msg = result.get('message', 'Статус обновлен')
            await callback.answer(msg)
        else:
            err = result.get('error') if result else 'Unknown error'
            await callback.answer(f'Ошибка: {err}', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def claim_toggle_handler(callback: CallbackQuery, bot: Bot):
    """
    Обрабатывает нажатие 'Это я смотрю' в канале (Toggle).
    Format: claim_toggle_<view_id>
    """
    user = callback.from_user

    role = await client.check_user_role(user.id)
    if role == UserRole.GUEST:
        await callback.answer('🔒 Недостаточно прав (Guest). Обратитесь к администратору.', show_alert=True)
        return

    try:
        view_id = int(callback.data.split('_')[-1])
        
        result = await client.toggle_view_user(user.id, view_id)

        if result and result.get('status') == 'ok':
            action = result.get('action')
            text = "Вы добавлены в список просмотра" if action == 'added' else "Вы убраны из списка просмотра"
            await callback.answer(text)
        else:
            await callback.answer('Ошибка обновления статуса', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_show_start_handler(callback: CallbackQuery, bot: Bot):
    """
    Показывает клавиатуру с выбором оценки.
    Format: rate_start_<show_id>
    """
    try:
        show_id = int(callback.data.split('_')[-1])
        kb = keyboards.get_rating_keyboard(show_id)
        # Редактируем только клавиатуру
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_show_back_handler(callback: CallbackQuery, bot: Bot):
    """
    Возвращает клавиатуру карточки сериала.
    Format: rate_back_<show_id>
    """
    try:
        show_id = int(callback.data.split('_')[-1])
        kb = keyboards.get_show_card_keyboard(show_id)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_show_set_handler(callback: CallbackQuery, bot: Bot):
    """
    Устанавливает оценку и возвращает клавиатуру карточки.
    Format: rate_set_<show_id>_<rating>
    """
    user_id = callback.from_user.id
    try:
        parts = callback.data.split('_')
        show_id = int(parts[2])
        rating = float(parts[3])

        role = await client.check_user_role(user_id)
        if role == UserRole.GUEST:
            await callback.answer('🔒 Гости не могут ставить оценки.', show_alert=True)
            return

        result = await client.rate_show(user_id, show_id, rating)
        
        if result and result.get('status') == 'ok':
            await callback.answer(f'Оценка {int(rating)} установлена!')
            # Возвращаем исходную клавиатуру
            kb = keyboards.get_show_card_keyboard(show_id)
            await callback.message.edit_reply_markup(reply_markup=kb)
        else:
            await callback.answer('Ошибка сохранения оценки', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)
        

async def rate_episode_start_handler(callback: CallbackQuery, bot: Bot):
    try:
        parts = callback.data.split('_')
        show_id = int(parts[3])
        season = int(parts[4])
        episode = int(parts[5])

        kb = keyboards.get_episode_rating_keyboard(show_id, season, episode)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_episode_set_handler(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    try:
        parts = callback.data.split('_')
        show_id = int(parts[3])
        season = int(parts[4])
        episode = int(parts[5])
        rating = float(parts[6])

        role = await client.check_user_role(user_id)
        if role == UserRole.GUEST:
            await callback.answer('🔒 Гости не могут ставить оценки.', show_alert=True)
            return

        result = await client.rate_show(user_id, show_id, rating, season, episode)

        if result and result.get('status') == 'ok':
            await callback.answer(f'Оценка {int(rating)} для S{season}E{episode} принята!')
            # Убираем клавиатуру после оценки, чтобы не загромождать
            await callback.message.edit_reply_markup(reply_markup=None)
        else:
            await callback.answer('Ошибка сохранения оценки', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)