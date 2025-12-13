import os
import client
import keyboards
from aiogram import Bot
from aiogram.types import CallbackQuery
from html_helper import italic
from shared.card_formatter import get_show_card_text
from shared.constants import SHOW_TYPE_MAPPING, SHOW_TYPES_TRACKED_VIA_NEW_EPISODES, UserRole


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
            raise ValueError('Invalid callback data format')

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
        await callback.answer(
            '🔒 Недостаточно прав (Guest). Обратитесь к администратору.', show_alert=True
        )
        return

    try:
        view_id = int(callback.data.split('_')[-1])

        result = await client.toggle_view_user(user.id, view_id)

        if result and result.get('status') == 'ok':
            action = result.get('action')
            text = (
                'Вы добавлены в список просмотра'
                if action == 'added'
                else 'Вы убраны из списка просмотра'
            )
            await callback.answer(text)
        else:
            await callback.answer('Ошибка обновления статуса', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_show_start_handler(callback: CallbackQuery, bot: Bot):
    """
    Нажатие кнопки 'Оценить'. Проверяет тип шоу и либо показывает грид, либо меню выбора.
    Format: rate_start_<show_id>
    """
    try:
        show_id = int(callback.data.split('_')[-1])
        user_id = callback.from_user.id

        show_data = await client.get_show_details(show_id, telegram_id=user_id)
        if not show_data:
            await callback.answer('Ошибка: не удалось получить данные шоу', show_alert=True)
            return

        show_type = show_data.get('type')
        personal_rating = show_data.get('personal_rating')

        if show_type in [SHOW_TYPE_MAPPING[t] for t in SHOW_TYPES_TRACKED_VIA_NEW_EPISODES]:
            episodes_count = show_data.get('personal_episodes_count', 0)
            
            kb = keyboards.get_rate_mode_keyboard(show_id, user_rating=personal_rating, episodes_rated=episodes_count)
            await callback.message.edit_reply_markup(reply_markup=kb)
        else:
            # Для фильмов передаем текущую оценку, чтобы она подсветилась звездочкой
            kb = keyboards.get_rating_keyboard(show_id, current_rating=personal_rating)
            await callback.message.edit_reply_markup(reply_markup=kb)

        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_mode_show_handler(callback: CallbackQuery, bot: Bot):
    """Выбрана оценка сериала целиком (или это фильм). Показываем грид."""
    try:
        show_id = int(callback.data.split('_')[-1])
        user_id = callback.from_user.id

        show_data = await client.get_show_details(show_id, telegram_id=user_id)
        current_rating = None
        if show_data:
            current_rating = show_data.get('personal_rating')

        kb = keyboards.get_rating_keyboard(show_id, current_rating=current_rating)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_show_set_handler(callback: CallbackQuery, bot: Bot):
    """
    Устанавливает оценку и возвращает клавиатуру карточки с обновленным текстом.
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

            show_data = await client.get_show_details(show_id)
            if show_data:
                text = get_show_card_text(
                    show_id=show_data.get('id'),
                    title=show_data.get('title', ''),
                    original_title=show_data.get('original_title'),
                    kinopub_link=os.getenv('SITE_AUX_URL'),
                    year=show_data.get('year'),
                    show_type=show_data.get('type'),
                    status=show_data.get('status'),
                    countries=show_data.get('countries', []),
                    genres=show_data.get('genres', []),
                    imdb_rating=show_data.get('imdb_rating'),
                    imdb_url=show_data.get('imdb_url'),
                    kp_rating=show_data.get('kinopoisk_rating'),
                    kp_url=show_data.get('kinopoisk_url'),
                    internal_rating=show_data.get('internal_rating'),
                    user_ratings=show_data.get('user_ratings'),
                )
                # Передаем новую оценку, чтобы кнопка обновилась на "Изменить оценку (X)"
                kb = keyboards.get_show_card_keyboard(show_id, user_rating=rating)
                await callback.message.edit_text(text=text, reply_markup=kb, disable_web_page_preview=True)
            else:
                kb = keyboards.get_show_card_keyboard(show_id, user_rating=rating)
                await callback.message.edit_reply_markup(reply_markup=kb)
        else:
            await callback.answer('Ошибка сохранения оценки', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_episode_start_handler(callback: CallbackQuery, bot: Bot):
    """Открывает сетку оценок для конкретного эпизода, подсвечивая текущую."""
    user_id = callback.from_user.id
    try:
        parts = callback.data.split('_')
        show_id = int(parts[3])
        season = int(parts[4])
        episode = int(parts[5])

        # Получаем данные, чтобы найти текущую оценку
        episodes_data = await client.get_show_episodes(show_id, telegram_id=user_id)
        
        current_rating = None
        for item in episodes_data:
            if item['season_number'] == season and item['episode_number'] == episode:
                current_rating = item.get('rating')
                break

        kb = keyboards.get_episode_rating_keyboard(show_id, season, episode, current_rating=current_rating)
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

            show_data = await client.get_show_details(show_id)
            if show_data:
                text = get_show_card_text(
                    show_id=show_data.get('id'),
                    title=show_data.get('title', ''),
                    original_title=show_data.get('original_title'),
                    kinopub_link=os.getenv('SITE_AUX_URL'),
                    year=show_data.get('year'),
                    show_type=show_data.get('type'),
                    status=show_data.get('status'),
                    countries=show_data.get('countries', []),
                    genres=show_data.get('genres', []),
                    imdb_rating=show_data.get('imdb_rating'),
                    imdb_url=show_data.get('imdb_url'),
                    kp_rating=show_data.get('kinopoisk_rating'),
                    kp_url=show_data.get('kinopoisk_url'),
                    internal_rating=show_data.get('internal_rating'),
                    user_ratings=show_data.get('user_ratings'),
                )
                kb = keyboards.get_show_card_keyboard(show_id, season, episode)
                await callback.message.edit_text(text=text, reply_markup=kb, disable_web_page_preview=True)
            else:
                kb = keyboards.get_show_card_keyboard(show_id, season, episode)
                await callback.message.edit_reply_markup(reply_markup=kb)
        else:
            await callback.answer('Ошибка сохранения оценки', show_alert=True)

    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_mode_ep_handler(callback: CallbackQuery, bot: Bot):
    try:
        show_id = int(callback.data.split('_')[-1])
        user_id = callback.from_user.id
        episodes_data = await client.get_show_episodes(show_id, telegram_id=user_id)

        if not episodes_data:
            await callback.answer('Нет информации об эпизодах.', show_alert=True)
            return

        season_stats = {}
        for item in episodes_data:
            s = item['season_number']
            if s not in season_stats:
                season_stats[s] = 0
            
            if item.get('rating'):
                season_stats[s] += 1

        kb = keyboards.get_seasons_keyboard(show_id, season_stats)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_sel_seas_handler(callback: CallbackQuery, bot: Bot):
    """Выбран сезон. Показываем эпизоды с учетом уже выставленных оценок."""
    user_id = callback.from_user.id
    try:
        parts = callback.data.split('_')
        show_id = int(parts[3])
        season = int(parts[4])

        # Запрашиваем эпизоды вместе с оценками текущего пользователя
        episodes_data = await client.get_show_episodes(show_id, telegram_id=user_id)
        
        # Фильтруем данные только для выбранного сезона
        season_episodes = [
            item for item in episodes_data if item['season_number'] == season
        ]

        kb = keyboards.get_episodes_keyboard(show_id, season, season_episodes)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)


async def rate_show_back_handler(callback: CallbackQuery, bot: Bot):
    """
    Кнопка 'Назад' в меню оценок.
    Если мы были в гриде оценки фильма/сериала целиком -> возвращаемся в карточку.
    Но если мы зашли в "Оценить сериал целиком" из меню выбора, по идее надо назад в меню выбора?
    Для простоты: rate_back_ всегда возвращает в карточку (исходное состояние).
    А внутри вложенных меню есть свои кнопки Назад.
    """
    try:
        show_id = int(callback.data.split('_')[-1])
        kb = keyboards.get_show_card_keyboard(show_id)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f'Ошибка: {e}', show_alert=True)
