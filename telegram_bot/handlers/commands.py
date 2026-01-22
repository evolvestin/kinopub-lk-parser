import os
import re

import client
import keyboards
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sender import MessageSender
from services.bot_instance import BotInstance

from shared.card_formatter import get_ratings_report_blocks, get_show_card_text
from shared.constants import SERIES_TYPES, UserRole
from shared.formatters import format_se
from shared.html_helper import bold, html_link, html_secure, italic


async def bot_command_start_private(message: Message, bot: Bot, command: CommandObject = None):
    sender = MessageSender(bot)
    user = message.from_user

    success = await client.register_user(
        user.id, user.username, user.first_name, user.language_code or 'ru'
    )

    args = command.args if command else None

    if args:
        if args.startswith('toggle_claim_'):
            try:
                parts = args.split('_')
                view_id = int(parts[2])
                show_id = int(parts[3]) if len(parts) > 3 else None

                # Проверяем наличие групп у пользователя
                groups = await client.get_user_groups(user.id)

                if groups:
                    # Если есть группы, предлагаем выбор
                    await sender.send_message(
                        chat_id=user.id,
                        text=f'{bold("Выберите режим отметки просмотра:")}',
                        keyboard=keyboards.get_claim_mode_keyboard(view_id, groups, show_id),
                    )
                else:
                    # Старая логика (мгновенное переключение)
                    result = await client.toggle_view_user(user.id, view_id)

                    if result and result.get('status') == 'ok':
                        action = result.get('action')
                        if action == 'added':
                            await sender.send_message(user.id, '✅ Вы добавлены в список зрителей.')
                        else:
                            await sender.send_message(user.id, '🗑 Вы убраны из списка зрителей.')

                        if show_id:
                            await _send_history_report(sender, user.id, show_id)
                    else:
                        await sender.send_message(
                            user.id, '❌ Ошибка обновления статуса просмотра.'
                        )

            except (IndexError, ValueError):
                await sender.send_message(user.id, '❌ Некорректная ссылка.')
            return

        if args.startswith('claim_') or args.startswith('unclaim_'):
            try:
                parts = args.split('_')
                action = parts[0]
                view_id = int(parts[1])
                show_id = int(parts[2]) if len(parts) > 2 else None

                if action == 'claim':
                    groups = await client.get_user_groups(user.id)
                    if groups:
                        await sender.send_message(
                            chat_id=user.id,
                            text=f'{bold("Выберите режим отметки просмотра:")}',
                            keyboard=keyboards.get_claim_mode_keyboard(view_id, groups, show_id),
                        )
                        return

                    result = await client.assign_view(user.id, view_id)
                    if not (result and result.get('status') == 'ok'):
                        await sender.send_message(user.id, '❌ Не удалось добавить просмотр.')
                else:
                    success_unclaim = await client.unassign_view(user.id, view_id)
                    if not success_unclaim:
                        await sender.send_message(user.id, '❌ Не удалось убрать просмотр.')

                if show_id:
                    await _send_history_report(sender, user.id, show_id)
                else:
                    msg = '✅ Просмотр добавлен.' if action == 'claim' else '🗑 Просмотр убран.'
                    await sender.send_message(user.id, msg)

            except (IndexError, ValueError):
                await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка.')
            return

        if args.startswith('rate_'):
            try:
                parts = args.split('_')
                show_id = int(parts[1])
                season = int(parts[2])
                episode = int(parts[3])

                show_data = await client.get_show_details(show_id, telegram_id=user.id)

                if show_data:
                    await _send_show_card(sender, user.id, show_data, season, episode)
                else:
                    await sender.send_message(
                        chat_id=user.id, text='❌ Информация о шоу не найдена.'
                    )

            except (IndexError, ValueError):
                await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка на оценку.')
            return

        if args.startswith('show_'):
            try:
                show_id = int(args.split('_')[1])
                show_data = await client.get_show_details(show_id, telegram_id=user.id)

                if show_data:
                    await _send_show_card(sender, user.id, show_data)
                else:
                    await sender.send_message(user.id, '❌ Контент не найден.')
            except (IndexError, ValueError):
                await sender.send_message(user.id, '❌ Некорректная ссылка на шоу.')
            return

        if args.startswith('ratings_'):
            try:
                show_id = int(args.split('_')[1])
                await _send_ratings_report(sender, user.id, show_id)
            except (IndexError, ValueError):
                await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка на оценки.')
            return

        if args.startswith('history_'):
            role = await client.check_user_role(user.id)
            if role == UserRole.GUEST:
                return

            try:
                show_id = int(args.split('_')[1])
                await _send_history_report(sender, user.id, show_id)
            except (IndexError, ValueError):
                await sender.send_message(
                    chat_id=user.id, text='❌ Некорректная ссылка на историю.'
                )
            return

    if success:
        text = (
            f'👋 {bold(f"Привет, {html_secure(user.first_name)}!")}\n\n'
            'Я бот-помощник KinoPub Observer.\n'
            'Просто отправьте мне название фильма или сериала, и я проверю его наличие в базе.'
        )
    else:
        text = f'⚠️ {bold("Ошибка регистрации.")}\nПопробуйте позже.'

    await sender.send_message(chat_id=user.id, text=text)


async def handle_history_command(message: Message, bot: Bot):
    match = re.match(r'/history_(\d+)', message.text)
    if not match:
        return

    user_id = message.from_user.id
    role = await client.check_user_role(user_id)
    if role == UserRole.GUEST:
        return

    show_id = int(match.group(1))
    sender = MessageSender(bot)
    await _send_history_report(sender, message.chat.id, show_id)


async def _send_history_report(sender: MessageSender, chat_id: int, show_id: int):
    show_data = await client.get_show_details(show_id, telegram_id=chat_id)
    if not show_data:
        await sender.send_message(chat_id, '❌ Ошибки получения данных.')
        return

    title = html_secure(show_data.get('title', 'Unknown'))
    bot_username = await BotInstance().get_bot_username()

    if bot_username:
        url = f'https://t.me/{bot_username}?start=show_{show_id}'
        title_link = html_link(url, title)
    else:
        title_link = title

    history = show_data.get('view_history', [])

    header = f'📜 История просмотров: {bold(title_link)}\n'
    text_blocks = []

    if not history:
        text_blocks.append('Просмотров нет.')
    else:
        channel_id = os.getenv('HISTORY_CHANNEL_ID')
        for item in history:
            date_str = item['date']
            view_id = item.get('id')
            season = item.get('season')
            episode = item.get('episode')

            if item.get('message_id') and channel_id:
                link = None
                if channel_id.startswith('-100'):
                    link = f'https://t.me/c/{channel_id[4:]}/{item["message_id"]}'

                if link:
                    date_str = html_link(link, date_str)

            se_info = ''
            if season and season > 0:
                se_info = f' {italic(format_se(season, episode))}'

            cmd_part = ''
            if view_id:
                if item.get('is_viewer'):
                    url = f'https://t.me/{bot_username}?start=unclaim_{view_id}_{show_id}'
                    cmd_part = f' ({html_link(url, "unclaim")})'
                else:
                    url = f'https://t.me/{bot_username}?start=claim_{view_id}_{show_id}'
                    cmd_part = f' ({html_link(url, "claim")})'

            line = f'{date_str}{se_info}{cmd_part}'

            if users := item['users']:
                line += f': {", ".join(users)}'

            text_blocks.append(line)

    await sender.send_smart_split_text(
        chat_id=chat_id, text_blocks=text_blocks, header=header, separator='\n'
    )


async def bot_command_start_group(message: Message, bot: Bot):
    sender = MessageSender(bot)
    text = (
        f'🤖 {bold("Приветствую!")}\n\n'
        'Чтобы искать фильмы и получать информацию, напишите мне в личные сообщения.'
    )
    await sender.send_message(chat_id=message.chat.id, text=text)


async def _send_show_card(
    sender: MessageSender,
    chat_id: int,
    show_data: dict,
    season: int = None,
    episode: int = None,
):
    show_id = show_data.get('id')
    keyboard = None
    if show_id:
        personal_rating = show_data.get('personal_rating')
        episodes_count = show_data.get('personal_episodes_count', 0)
        show_type = show_data.get('type')

        user_ratings_list = show_data.get('user_ratings')
        has_ratings = bool(user_ratings_list and len(user_ratings_list) > 0)

        keyboard = keyboards.get_show_card_keyboard(
            show_id,
            show_type=show_type,
            season=season,
            episode=episode,
            user_rating=personal_rating,
            episodes_rated=episodes_count,
            has_any_ratings=has_ratings,
            channel_url=None,
        )

    bot_username = await BotInstance().get_bot_username()
    role = await client.check_user_role(chat_id)

    await sender.send_message(
        chat_id=chat_id,
        text=get_show_card_text(
            show_id=show_id,
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
        ),
        keyboard=keyboard,
    )


async def handle_show_command(message: Message, bot: Bot):
    """Обработка команды /show_123"""
    match = re.match(r'/show_(\d+)', message.text)
    if not match:
        return

    show_id = int(match.group(1))
    sender = MessageSender(bot)

    show_data = await client.get_show_details(show_id, telegram_id=message.from_user.id)
    if show_data:
        await _send_show_card(sender, message.chat.id, show_data)
    else:
        await sender.send_message(message.chat.id, '❌ Контент не найден или был удален.')


async def _process_search(bot: Bot, chat_id: int, query: str):
    sender = MessageSender(bot)
    results = await client.search_shows(query)

    if not results:
        await sender.send_message(chat_id, f'😔 По запросу {bold(query)} ничего не найдено.')
        return

    if len(results) == 1:
        full_info = await client.get_show_details(results[0]['id'])
        if full_info:
            await _send_show_card(sender, chat_id, full_info)
        return

    text_lines = [f'🔎 Результаты по запросу {bold(query)}:\n']

    for item in results:
        title = html_secure(item['title'])
        original_title = html_secure(item.get('original_title') or '')
        year = item.get('year') or '?'
        cmd = f'/show_{item["id"]}'

        if original_title and original_title != title:
            display_title = f'{title} ({original_title})'
        else:
            display_title = title

        text_lines.append(f'▪️ {display_title} ({year}) — {cmd}')

    await sender.send_message(chat_id, '\n'.join(text_lines))


async def handle_search_text(message: Message, bot: Bot):
    query = message.text.strip()
    if not query or query.startswith('/'):
        return

    await _process_search(bot, message.chat.id, query)


async def handle_explicit_search(message: Message, bot: Bot):
    """Обработка команды /search <запрос> в группах"""
    query = re.sub(r'\s+', ' ', message.text).strip()
    query = re.sub(r'^/search', '', message.text, flags=re.IGNORECASE).strip()
    if len(query) == 0:
        sender = MessageSender(bot)
        await sender.send_message(message.chat.id, '⚠️ Введите название для поиска после команды.')
        return

    await _process_search(bot, message.chat.id, query=query)


async def handle_imdb_lookup(message: Message, bot: Bot):
    """Обработка сообщения вида imdb: 123456"""
    match = re.search(r'imdb:\s*(\d+)', message.text, re.IGNORECASE)
    if not match:
        return

    imdb_id = match.group(1)
    sender = MessageSender(bot)

    show_data = await client.get_show_by_imdb_id(imdb_id)
    if show_data:
        await _send_show_card(sender, message.chat.id, show_data)


async def handle_ratings_command(message: Message, bot: Bot):
    """Обработка команды /ratings_123"""
    match = re.match(r'/ratings_(\d+)', message.text)
    if not match:
        return

    show_id = int(match.group(1))
    sender = MessageSender(bot)
    await _send_ratings_report(sender, message.chat.id, show_id)


async def _send_ratings_report(sender: MessageSender, chat_id: int, show_id: int):
    """Общая логика отправки отчета с оценками (используется в start и команде)"""
    show_data = await client.get_show_details(show_id)
    if not show_data:
        await sender.send_message(chat_id, '❌ Ошибки получения данных.')
        return

    ratings_details = None
    if show_data.get('type') in SERIES_TYPES:
        ratings_details = await client.get_show_ratings_details(show_id)

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
        await sender.send_message(chat_id, text=f'{bold(header)}\nОценок пока нет.')
        return

    await sender.send_smart_split_text(
        chat_id=chat_id, text_blocks=blocks, header=bold(header), separator=separator
    )


async def handle_history_action_command(message: Message, bot: Bot):
    match = re.match(r'^/(claim|unclaim)_(\d+)_(\d+)$', message.text)
    if not match:
        return

    action, view_id, show_id = match.groups()
    view_id, show_id = int(view_id), int(show_id)
    user_id = message.from_user.id
    sender = MessageSender(bot)

    if action == 'claim':
        result = await client.assign_view(user_id, view_id)
        if not (result and result.get('status') == 'ok'):
            await sender.send_message(user_id, '❌ Не удалось добавить просмотр.')
            return
    else:
        success = await client.unassign_view(user_id, view_id)
        if not success:
            await sender.send_message(user_id, '❌ Не удалось убрать просмотр.')
            return

    # Обновляем список, присылая новое сообщение
    await _send_history_report(sender, user_id, show_id)


async def handle_stats_command(message: Message, bot: Bot):
    """
    Отправляет кнопку для открытия WebApp со статистикой.
    """
    web_app_url = f'{os.getenv("BACKEND_URL").rstrip("/")}/webapp/'

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='📊 Моя статистика', web_app=WebAppInfo(url=web_app_url))]
        ]
    )

    await message.answer(
        text=f'{bold("Личная статистика")}\nНажмите на кнопку ниже, чтобы открыть приложение.',
        reply_markup=keyboard,
    )
