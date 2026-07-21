import functools
import logging
import os

import client
import keyboards
from aiogram import Bot
from aiogram.types import CallbackQuery
from sender import MessageSender
from services.bot_instance import BotInstance

from shared.card_formatter import get_ratings_report_blocks, get_show_card_text
from shared.constants import SERIES_TYPES, UserRole
from shared.formatters import format_se
from shared.html_helper import bold, italic


def get_args(data: str, *indices: int) -> list:
    """Извлекает аргументы из callback_data по индексам, приводя числа к int/float."""
    parts = data.split('_')
    results = []
    for i in indices:
        val = parts[i]
        # Простая эвристика: если похоже на число - конвертируем
        if val.replace('.', '', 1).isdigit():
            results.append(float(val) if '.' in val else int(val))
        else:
            results.append(val)
    return results if len(results) > 1 else results[0]


def safe_callback(func):
    """Декоратор для обработки ошибок и try-except блоков в колбэках."""

    @functools.wraps(func)
    async def wrapper(callback: CallbackQuery, bot: Bot, *args, **kwargs):
        try:
            await func(callback, bot, *args, **kwargs)
        except Exception as e:
            # Логируем полный трейсбек ошибки, он уйдет в базу данных через RemoteLogHandler

            logging.error(f'Error in callback {callback.data}: {e}', exc_info=True)
            try:
                await callback.answer(f'Произошла ошибка: {e}', show_alert=True)
            except Exception:
                pass

    return wrapper


async def _get_show_data_safe(callback: CallbackQuery, show_id: int):
    show_data = await client.get_show_details(show_id, telegram_id=callback.from_user.id)
    if not show_data:
        await callback.answer('Ошибка: не удалось получить данные шоу', show_alert=True)
        return None
    return show_data


async def _check_guest_restriction(callback: CallbackQuery, user_id: int) -> bool:
    role = await client.check_user_role(user_id)
    if role == UserRole.GUEST:
        await callback.answer('🔒 Функция недоступна.', show_alert=True)
        return True
    return False


async def _submit_rating(
    callback: CallbackQuery,
    bot: Bot,
    show_id: int,
    rating: float,
    season: int = None,
    episode: int = None,
):
    result = await client.rate_show(callback.from_user.id, show_id, rating, season, episode)

    if result and result.get('status') == 'ok':
        target = 'контента'

        if season and episode:
            target = format_se(season, episode)
        else:
            show_data = await client.get_show_details(show_id)
            if show_data:
                target = 'сериала' if show_data.get('type') in SERIES_TYPES else 'фильма'

        rating_str = str(int(rating)) if rating.is_integer() else str(rating)
        await callback.answer(f'Оценка {rating_str} для {target} принята!')
        await _update_show_message(callback.message, bot, callback.from_user.id, show_id)
    else:
        await callback.answer('Ошибка сохранения оценки', show_alert=True)


async def _update_show_message(message, bot: Bot, user_id, show_id):
    show_data = await client.get_show_details(show_id, telegram_id=user_id)
    if not show_data:
        return

    bot_username = await BotInstance().get_bot_username()
    role = await client.check_user_role(user_id)

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
        kinopoisk_rating=show_data.get('kinopoisk_rating'),
        kinopoisk_url=show_data.get('kinopoisk_url'),
        internal_rating=show_data.get('internal_rating'),
        user_ratings=show_data.get('user_ratings'),
        bot_username=bot_username,
        show_history=(role != UserRole.GUEST),
    )

    user_ratings_list = show_data.get('user_ratings')
    has_ratings = bool(user_ratings_list and len(user_ratings_list) > 0)

    channel_url = None
    if role != UserRole.GUEST:
        msg_id = show_data.get('channel_message_id')
        hist_channel_id = os.getenv('HISTORY_CHANNEL_ID', '')
        if msg_id and hist_channel_id and hist_channel_id.startswith('-100'):
            channel_url = f'https://t.me/c/{hist_channel_id[4:]}/{msg_id}'

    keyboard = keyboards.get_show_card_keyboard(
        show_id,
        show_type=show_data.get('type'),
        user_rating=show_data.get('personal_rating'),
        episodes_rated=show_data.get('personal_episodes_count', 0),
        has_any_ratings=has_ratings,
        channel_url=channel_url,
    )

    await message.edit_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)


@safe_callback
async def role_switch_handler(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    current_role = await client.check_user_role(user_id)
    if current_role != UserRole.ADMIN:
        await callback.answer('⛔️ Только для администраторов.', show_alert=True)
        return

    target_user_id, role = get_args(callback.data, 1, 2)
    result = await client.set_user_role(target_user_id, role, callback.message.message_id)

    if result.get('success'):
        await callback.answer(f'Роль успешно изменена на {role.upper()}')
    elif result.get('error') == 'outdated':
        await callback.answer('⚠️ Это сообщение устарело.', show_alert=True)
    else:
        await callback.answer(f'Ошибка: {result.get("error")}', show_alert=True)


@safe_callback
async def cancel_claim_handler(callback: CallbackQuery, bot: Bot):
    if await _check_guest_restriction(callback, callback.from_user.id):
        return

    view_id = get_args(callback.data, -1)
    success = await client.unassign_view(callback.from_user.id, view_id)
    if success:
        await callback.message.edit_text(
            f'🗑 {italic("Привязка просмотра отменена.")}', reply_markup=None
        )
        await callback.answer('Отменено')
    else:
        await callback.answer('Ошибка при отмене', show_alert=True)


@safe_callback
async def toggle_check_handler(callback: CallbackQuery, bot: Bot):
    # Разрешаем доступ Admin и Viewer (логика проверки привязки к просмотру находится на бэкенде)
    role = await client.check_user_role(callback.from_user.id)
    if role == UserRole.GUEST:
        await callback.answer('⛔️ У вас нет прав.', show_alert=True)
        return

    view_id = get_args(callback.data, -1)
    result = await client.toggle_view_check(view_id, telegram_id=callback.from_user.id)

    if result and result.get('status') == 'ok':
        # Сообщение в канале обновляется бэкендом (app/views.py -> TelegramSender),
        # нам нужно только уведомить пользователя всплывашкой.
        await callback.answer(result.get('message', 'Статус обновлен'))
    else:
        error_text = result.get('error') if result else 'Неизвестная ошибка'
        await callback.answer(f'Ошибка: {error_text}', show_alert=True)


@safe_callback
async def claim_toggle_handler(callback: CallbackQuery, bot: Bot):
    if await _check_guest_restriction(callback, callback.from_user.id):
        return

    view_id = get_args(callback.data, -1)
    result = await client.toggle_view_user(callback.from_user.id, view_id)

    if result and result.get('status') == 'ok':
        text = (
            'Вы добавлены в список просмотра'
            if result.get('action') == 'added'
            else 'Вы убраны из списка просмотра'
        )
        await callback.answer(text)
    else:
        await callback.answer('Ошибка обновления статуса', show_alert=True)


@safe_callback
async def rate_show_start_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    show_id = int(parts[2])
    is_notify = parts[-1] == 'n'

    show_data = await _get_show_data_safe(callback, show_id)
    if not show_data:
        return

    if show_data.get('type') in SERIES_TYPES:
        kb = keyboards.get_rate_mode_keyboard(
            show_id,
            user_rating=show_data.get('personal_rating'),
            episodes_rated=show_data.get('personal_episodes_count', 0),
            is_notify=is_notify,
        )
    else:
        kb = keyboards.get_rating_keyboard(
            show_id, current_rating=show_data.get('personal_rating'), is_notify=is_notify
        )

    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_mode_show_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    show_id = int(parts[3])
    is_notify = parts[-1] == 'n'

    show_data = await _get_show_data_safe(callback, show_id)
    rating = show_data.get('personal_rating') if show_data else None

    kb = keyboards.get_rating_keyboard(show_id, current_rating=rating, is_notify=is_notify)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


async def check_privacy_and_prompt(callback: CallbackQuery, bot: Bot) -> bool:
    user_info = await client.get_user_info(callback.from_user.id)
    if user_info and not user_info.get('privacy_choice_made'):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        text = (
            "🛑 <b>Настройки приватности оценок</b>\n\n"
            "Перед тем как оставить свою первую оценку, выберите, как другие пользователи будут её видеть:\n\n"
            "🕶 <b>Анонимно</b> (По умолчанию)\n"
            "Ваше имя скрыто. Другие увидят «Анонимный зритель», а вы — «Вы».\n\n"
            "🌐 <b>Публично</b>\n"
            "Другие увидят ваше имя и юзернейм в списках оценивших.\n\n"
            "<i>Вы сможете изменить это в любой момент через настройки WebApp.</i>"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🕶 Анонимно", callback_data="set_priv_1")],
            [InlineKeyboardButton(text="🌐 Публично", callback_data="set_priv_0")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="delete_msg")]
        ])
        
        await bot.send_message(callback.from_user.id, text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return False
    return True


@safe_callback
async def rate_show_set_handler(callback: CallbackQuery, bot: Bot):
    if not await check_privacy_and_prompt(callback, bot):
        return
    show_id, rating = get_args(callback.data, 2, 3)
    await _submit_rating(callback, bot, show_id, rating)


@safe_callback
async def rate_episode_start_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    show_id = int(parts[3])
    season = int(parts[4])
    episode = int(parts[5])
    is_notify = parts[-1] == 'n'

    episodes_data = await client.get_show_episodes(show_id, telegram_id=callback.from_user.id)
    current_rating = next(
        (
            i.get('rating')
            for i in episodes_data
            if i['season_number'] == season and i['episode_number'] == episode
        ),
        None,
    )

    kb = keyboards.get_episode_rating_keyboard(
        show_id, season, episode, current_rating=current_rating, is_notify=is_notify
    )
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_episode_set_handler(callback: CallbackQuery, bot: Bot):
    if not await check_privacy_and_prompt(callback, bot):
        return
    show_id, season, episode, rating = get_args(callback.data, 3, 4, 5, 6)
    await _submit_rating(callback, bot, show_id, rating, season, episode)

@safe_callback
async def privacy_choice_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    is_anon = parts[2] == '1'
    
    await client.set_user_privacy(callback.from_user.id, is_anon)
    await callback.message.delete()
    await callback.message.answer("✅ Настройки приватности сохранены.\nПожалуйста, нажмите на оценку еще раз.")
    await callback.answer()

@safe_callback
async def rate_mode_ep_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    show_id = int(parts[3])
    is_notify = parts[-1] == 'n'

    episodes_data = await client.get_show_episodes(show_id, telegram_id=callback.from_user.id)

    if not episodes_data:
        await callback.answer('Нет информации об эпизодах.', show_alert=True)
        return

    season_stats = {}
    for item in episodes_data:
        s = item['season_number']
        season_stats[s] = season_stats.get(s, 0) + (1 if item.get('rating') else 0)

    kb = keyboards.get_seasons_keyboard(show_id, season_stats, is_notify=is_notify)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_select_season_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    show_id = int(parts[3])
    season = int(parts[4])
    is_notify = parts[-1] == 'n'

    episodes_data = await client.get_show_episodes(show_id, telegram_id=callback.from_user.id)
    season_episodes = [i for i in episodes_data if i['season_number'] == season]

    keyboard = keyboards.get_episodes_keyboard(
        show_id, season, season_episodes, is_notify=is_notify
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@safe_callback
async def rate_show_back_handler(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split('_')
    show_id = int(parts[2])

    # Используем общую функцию обновления, чтобы избежать дублирования логики
    await _update_show_message(callback.message, bot, callback.from_user.id, show_id)
    await callback.answer()


@safe_callback
async def show_ratings_list_handler(callback: CallbackQuery, bot: Bot):
    show_id = get_args(callback.data, -1)
    show_data = await client.get_show_details(show_id, telegram_id=callback.from_user.id)

    if not show_data:
        await callback.answer('Ошибка получения данных.', show_alert=True)
        return

    ratings_details = None
    if show_data.get('type') in SERIES_TYPES:
        ratings_details = await client.get_show_ratings_details(show_id, telegram_id=callback.from_user.id)

    bot_username = await BotInstance().get_bot_username()

    header, separator, blocks = get_ratings_report_blocks(
        show_type=show_data.get('type'),
        user_ratings_summary=show_data.get('user_ratings', []),
        ratings_details=ratings_details,
        internal_rating=show_data.get('internal_rating'),
        title=show_data.get('title'),
        show_id=show_id,
        bot_username=bot_username,
    )

    if not blocks:
        await callback.answer('Оценок пока нет.', show_alert=True)
        return

    await callback.answer()

    await MessageSender(bot).send_smart_split_text(
        chat_id=callback.from_user.id, text_blocks=blocks, header=bold(header), separator=separator
    )


@safe_callback
async def claim_group_handler(callback: CallbackQuery, bot: Bot):
    if await _check_guest_restriction(callback, callback.from_user.id):
        return

    view_id, group_id = get_args(callback.data, 2, 3)
    result = await client.assign_group_view(callback.from_user.id, group_id, view_id)

    if result and result.get('status') == 'ok':
        added = result.get('added_count', 0)
        gname = result.get('group_name', 'Group')
        await callback.message.edit_text(
            f'✅ Группа {bold(gname)} учтена ({added} новых зрителей).', reply_markup=None
        )
    else:
        await callback.answer('Ошибка при добавлении группы', show_alert=True)


@safe_callback
async def claim_self_handler(callback: CallbackQuery, bot: Bot):
    if await _check_guest_restriction(callback, callback.from_user.id):
        return

    view_id = get_args(callback.data, -1)
    # Используем старую логику переключения для себя
    result = await client.toggle_view_user(callback.from_user.id, view_id)

    if result and result.get('status') == 'ok':
        text = (
            '✅ Вы добавлены в список зрителей.'
            if result.get('action') == 'added'
            else '🗑 Вы убраны из списка зрителей.'
        )
        await callback.message.edit_text(text, reply_markup=None)
    else:
        await callback.answer('Ошибка обновления статуса', show_alert=True)


@safe_callback
async def delete_msg_handler(callback: CallbackQuery, bot: Bot):
    await callback.message.delete()
