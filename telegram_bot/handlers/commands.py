import os
import re

import client
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from html_helper import bold, html_link, html_secure, italic
from sender import MessageSender

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')


async def bot_command_start_private(message: Message, bot: Bot, command: CommandObject = None):
    sender = MessageSender(bot)
    user = message.from_user

    # Регистрация / обновление данных пользователя
    success = await client.register_user(
        user.id, user.username, user.first_name, user.language_code or 'ru'
    )

    # Обработка Deep Linking (нажатие кнопки "Это я смотрю")
    args = command.args if command else None
    if args and args.startswith('claim_'):
        try:
            view_id = int(args.split('_')[1])
            result = await client.assign_view(user.id, view_id)

            if result and result.get('status') == 'ok':
                info = result.get('info', 'Unknown content')
                text = f'✅ <b>Просмотр зафиксирован за вами</b>\n{html_secure(info)}'
                # Кнопка отмены
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text='❌ Отменить', callback_data=f'unclaim_{view_id}'
                            )
                        ]
                    ]
                )
                await sender.send_message(chat_id=user.id, text=text, keyboard=kb)
            else:
                await sender.send_message(
                    chat_id=user.id,
                    text='❌ Не удалось привязать просмотр (возможно, запись удалена).',
                )
        except (IndexError, ValueError):
            await sender.send_message(chat_id=user.id, text='❌ Некорректная ссылка.')
        return

    # Стандартное приветствие для Гостя
    if success:
        text = (
            f'👋 {bold(f"Привет, {html_secure(user.first_name)}!")}\n\n'
            'Я бот-помощник KinoPub Observer.\n'
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


async def _send_show_card(sender: MessageSender, chat_id: int, show_data: dict):
    raw_title = html_secure(show_data['title'])
    original_title = html_secure(show_data['original_title'])

    site_url = os.getenv('SITE_AUX_URL', '').rstrip('/')
    if site_url:
        kp_link = f'{site_url}/item/view/{show_data["id"]}'
        title = html_link(kp_link, bold(raw_title))
    else:
        title = bold(raw_title)

    lines = [f'🎬 {title}']

    if raw_title != original_title:
        lines.append(italic(f'({original_title})'))

    if countries := show_data.get('countries', []):
        lines.append(', '.join(countries))

    description_line = []
    if year := show_data.get('year'):
        description_line.append(f'📅 {year}')
    if show_type := show_data.get('type'):
        description_line.append(f'🎭 {show_type}')
    if status := show_data.get('status'):
        description_line.append(status)
    if description_line:
        lines.append(' | '.join(description_line))

    ratings = []
    if imdb := show_data.get('imdb_rating'):
        val = f'IMDB: {imdb:.1f}'
        url = show_data.get('imdb_url')
        ratings.append(html_link(url, val) if url else val)

    if kp := show_data.get('kinopoisk_rating'):
        val = f'KP: {kp:.1f}'
        url = show_data.get('kinopoisk_url')
        ratings.append(html_link(url, val) if url else val)

    if ratings:
        lines.append(f'⭐ {" | ".join(ratings)}')

    # Жанры
    if genres := show_data.get('genres', []):
        lines.append(f'🏷 {", ".join(genres)}')

    await sender.send_message(chat_id=chat_id, text='\n'.join(lines))


async def handle_view_command(message: Message, bot: Bot):
    """Обработка команды /view_123"""
    match = re.match(r'/view_(\d+)', message.text)
    if not match:
        return

    show_id = int(match.group(1))
    sender = MessageSender(bot)

    show_data = await client.get_show_details(show_id)
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
        cmd = f'/view_{item["id"]}'

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
