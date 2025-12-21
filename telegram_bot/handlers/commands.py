import os
import re

import client
import keyboards
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.types import Message
from sender import MessageSender
from services.bot_instance import BotInstance

from shared.card_formatter import get_ratings_report_blocks, get_show_card_text
from shared.constants import SERIES_TYPES
from shared.html_helper import bold, html_secure

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')


async def bot_command_start_private(message: Message, bot: Bot, command: CommandObject = None):
    sender = MessageSender(bot)
    user = message.from_user

    success = await client.register_user(
        user.id, user.username, user.first_name, user.language_code or 'ru'
    )

    args = command.args if command else None

    if args:
        if args.startswith('claim_'):
            try:
                view_id = int(args.split('_')[1])
                result = await client.assign_view(user.id, view_id)

                if result and result.get('status') == 'ok':
                    info = result.get('info', 'Unknown content')
                    text = f'✅ <b>Просмотр зафиксирован за вами</b>\n{html_secure(info)}'
                    kb = keyboards.get_unclaim_keyboard(view_id)
                    await sender.send_message(chat_id=user.id, text=text, keyboard=kb)
                else:
                    await sender.send_message(
                        chat_id=user.id,
                        text='❌ Не удалось привязать просмотр (возможно, запись удалена).',
                    )
            except (IndexError, ValueError):
                await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка.')
            return

        if args.startswith('rate_'):
            # Format: rate_showId_season_episode
            try:
                parts = args.split('_')
                show_id = int(parts[1])
                season = int(parts[2])
                episode = int(parts[3])

                # Получаем полную информацию о шоу
                show_data = await client.get_show_details(show_id, telegram_id=user.id)

                if show_data:
                    # Отправляем карточку, передавая данные о конкретном эпизоде для кнопок
                    await _send_show_card(sender, user.id, show_data, season, episode)
                else:
                    await sender.send_message(
                        chat_id=user.id, text='❌ Информация о шоу не найдена.'
                    )

            except (IndexError, ValueError):
                await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка на оценку.')
            return

        if args.startswith('ratings_'):
            try:
                show_id = int(args.split('_')[1])
                await _send_ratings_report(sender, user.id, show_id)
            except (IndexError, ValueError):
                await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка на оценки.')
            return

    if success:
        text = (
            f'👋 {bold(f"Привет, {html_secure(user.first_name)}!")}\n\n'
            'Я бот-помощник KinoPub Parser.\n'
            'Пока ваш статус <b>Guest</b>, вам доступны следующие функции:\n\n'
            f'🔍 {bold("Поиск контента")}\n'
            'Просто отправьте мне название фильма или сериала, и я проверю его наличие в базе.\n\n'
            'ℹ️ Для получения доступа к истории просмотров и статистике обратитесь к администратору.'
        )
    else:
        text = f'⚠️ {bold("Ошибка регистрации.")}\nПопробуйте позже.'

    await sender.send_message(chat_id=user.id, text=text)


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

    header, separator, blocks = get_ratings_report_blocks(
        show_data.get('type'),
        show_data.get('user_ratings', []),
        ratings_details,
        show_data.get('internal_rating'),
    )

    if not blocks:
        await sender.send_message(chat_id, 'Оценок пока нет.')
        return

    await sender.send_smart_split_text(
        chat_id=chat_id, text_blocks=blocks, header=bold(header), separator=separator
    )
