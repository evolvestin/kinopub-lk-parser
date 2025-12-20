import os
import functools
import client
import keyboards
from aiogram import Bot
from aiogram.types import CallbackQuery
from html_helper import italic
from shared.card_formatter import get_show_card_text
from sender import MessageSender
from shared.html_helper import bold, code
from shared.constants import SERIES_TYPES, UserRole
from shared.formatters import format_se


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
            await callback.answer(f'Ошибка: {e}', show_alert=True)
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
        await callback.answer('🔒 Гости не могут ставить оценки.', show_alert=True)
        return True
    return False


async def _submit_rating(callback: CallbackQuery, show_id: int, rating: float, season: int = None, episode: int = None):
    if await _check_guest_restriction(callback, callback.from_user.id):
        return

    result = await client.rate_show(callback.from_user.id, show_id, rating, season, episode)

    if result and result.get('status') == 'ok':
        target = f'S{season}E{episode}' if season and episode else 'сериала/фильма'
        await callback.answer(f'Оценка {int(rating)} для {target} принята!')
        await _update_show_message(callback.message, callback.from_user.id, show_id)
    else:
        await callback.answer('Ошибка сохранения оценки', show_alert=True)


async def _update_show_message(message, user_id, show_id):
    show_data = await client.get_show_details(show_id, telegram_id=user_id)
    if not show_data:
        return

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
    )
    
    # Проверяем наличие любых оценок для отображения кнопки
    user_ratings_list = show_data.get('user_ratings')
    has_ratings = bool(user_ratings_list and len(user_ratings_list) > 0)

    keyboard = keyboards.get_show_card_keyboard(
        show_id,
        show_type=show_data.get('type'),
        user_rating=show_data.get('personal_rating'),
        episodes_rated=show_data.get('personal_episodes_count', 0),
        has_any_ratings=has_ratings
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
        await callback.message.edit_text(f'🗑 {italic("Привязка просмотра отменена.")}', reply_markup=None)
        await callback.answer('Отменено')
    else:
        await callback.answer('Ошибка при отмене', show_alert=True)


@safe_callback
async def toggle_check_handler(callback: CallbackQuery, bot: Bot):
    if await client.check_user_role(callback.from_user.id) != UserRole.ADMIN:
        await callback.answer('⛔️ Только для администраторов.', show_alert=True)
        return

    view_id = get_args(callback.data, -1)
    result = await client.toggle_view_check(view_id)
    if result and result.get('status') == 'ok':
        await callback.answer(result.get('message', 'Статус обновлен'))
        if payload := result.get('payload'):
            await MessageSender(bot).send_message(
                chat_id=callback.message.chat.id,
                text=payload['text'],
                keyboard=payload['keyboard'],
                edit_message=callback.message
            )
    else:
        await callback.answer(f'Ошибка: {result.get("error") if result else "Unknown"}', show_alert=True)


@safe_callback
async def claim_toggle_handler(callback: CallbackQuery, bot: Bot):
    if await _check_guest_restriction(callback, callback.from_user.id):
        return

    view_id = get_args(callback.data, -1)
    result = await client.toggle_view_user(callback.from_user.id, view_id)
    if result and result.get('status') == 'ok':
        text = 'Вы добавлены в список просмотра' if result.get('action') == 'added' else 'Вы убраны из списка просмотра'
        await callback.answer(text)
        if payload := result.get('payload'):
            await MessageSender(bot).send_message(
                chat_id=callback.message.chat.id,
                text=payload['text'],
                keyboard=payload['keyboard'],
                edit_message=callback.message
            )
    else:
        await callback.answer('Ошибка обновления статуса', show_alert=True)


@safe_callback
async def rate_show_start_handler(callback: CallbackQuery, bot: Bot):
    show_id = get_args(callback.data, -1)
    show_data = await _get_show_data_safe(callback, show_id)
    if not show_data:
        return

    if show_data.get('type') in SERIES_TYPES:
        kb = keyboards.get_rate_mode_keyboard(
            show_id, 
            user_rating=show_data.get('personal_rating'), 
            episodes_rated=show_data.get('personal_episodes_count', 0)
        )
    else:
        kb = keyboards.get_rating_keyboard(show_id, current_rating=show_data.get('personal_rating'))

    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_mode_show_handler(callback: CallbackQuery, bot: Bot):
    show_id = get_args(callback.data, -1)
    show_data = await _get_show_data_safe(callback, show_id)
    rating = show_data.get('personal_rating') if show_data else None

    kb = keyboards.get_rating_keyboard(show_id, current_rating=rating)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_show_set_handler(callback: CallbackQuery, bot: Bot):
    show_id, rating = get_args(callback.data, 2, 3)
    await _submit_rating(callback, show_id, rating)


@safe_callback
async def rate_episode_start_handler(callback: CallbackQuery, bot: Bot):
    show_id, season, episode = get_args(callback.data, 3, 4, 5)

    episodes_data = await client.get_show_episodes(show_id, telegram_id=callback.from_user.id)
    current_rating = next(
        (i.get('rating') for i in episodes_data if i['season_number'] == season and i['episode_number'] == episode), 
        None
    )

    kb = keyboards.get_episode_rating_keyboard(show_id, season, episode, current_rating=current_rating)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_episode_set_handler(callback: CallbackQuery, bot: Bot):
    show_id, season, episode, rating = get_args(callback.data, 3, 4, 5, 6)
    await _submit_rating(callback, show_id, rating, season, episode)


@safe_callback
async def rate_mode_ep_handler(callback: CallbackQuery, bot: Bot):
    show_id = int(callback.data.split('_')[-1])
    episodes_data = await client.get_show_episodes(show_id, telegram_id=callback.from_user.id)

    if not episodes_data:
        await callback.answer('Нет информации об эпизодах.', show_alert=True)
        return

    season_stats = {}
    for item in episodes_data:
        s = item['season_number']
        season_stats[s] = season_stats.get(s, 0) + (1 if item.get('rating') else 0)

    kb = keyboards.get_seasons_keyboard(show_id, season_stats)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@safe_callback
async def rate_select_season_handler(callback: CallbackQuery, bot: Bot):
    show_id, season = get_args(callback.data, 3, 4)

    episodes_data = await client.get_show_episodes(show_id, telegram_id=callback.from_user.id)
    season_episodes = [i for i in episodes_data if i['season_number'] == season]

    keyboard = keyboards.get_episodes_keyboard(show_id, season, season_episodes)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@safe_callback
async def rate_show_back_handler(callback: CallbackQuery, bot: Bot):
    show_id = get_args(callback.data, -1)
    await _update_show_message(callback.message, callback.from_user.id, show_id)
    await callback.answer()


@safe_callback
async def show_ratings_list_handler(callback: CallbackQuery, bot: Bot):    
    show_id = get_args(callback.data, -1)
    show_data = await client.get_show_details(show_id)
    
    if not show_data:
        await callback.answer('Ошибка получения данных.', show_alert=True)
        return

    user_ratings_summary = show_data.get('user_ratings', [])
    header = f'📋 Все оценки'
    if internal_rating := show_data.get('internal_rating'):
        header += f' ({internal_rating:.1f}/10):'
    
    blocks = []
    if show_data.get('type') in SERIES_TYPES:
        separator = '\n\n'
        ratings_details = await client.get_show_ratings_details(show_id)
        if not ratings_details:
            await callback.answer('Оценок пока нет.', show_alert=True)
            return

        for i, user_data in enumerate(ratings_details, 1):
            user_rating = None
            for ur in user_ratings_summary:
                if ur['label'] == user_data['user']:
                    user_rating = ur['rating']
                    break

            lines = []
            user_header = f'{i}. {user_data["user"]}:'
            if user_rating:
                user_header += f' {bold(f"{user_rating:.1f}")}'
            lines.append(user_header)
            
            if user_data.get('show_rating'):
                lines.append(f'Общая: {user_data["show_rating"]}')
            
            episodes = user_data.get('episodes', [])
            for ep in episodes:
                lines.append(f'  {italic(format_se(ep["s"], ep["e"]))}: {ep["r"]}')
            
            blocks.append('\n'.join(lines))
    else:
        header += '\n'
        separator = '\n'
        if not user_ratings_summary:
            await callback.answer('Оценок пока нет.', show_alert=True)
            return

        for i, data in enumerate(user_ratings_summary, 1):
            blocks.append(f'{i}. {data["label"]}: {bold(f"{data['rating']:.1f}")}')

    await callback.answer()
        
    await MessageSender(bot).send_smart_split_text(
        chat_id=callback.from_user.id,
        text_blocks=blocks,
        header=bold(header),
        separator=separator
    )