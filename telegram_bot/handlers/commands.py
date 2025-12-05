import os
import re

import client
import keyboards
from aiogram import Bot
from aiogram.types import Message
from html_helper import bold, code, html_link, html_secure
from sender import MessageSender

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')


async def bot_command_start_private(message: Message, bot: Bot):
    sender = MessageSender(bot)
    user = message.from_user

    success = await client.register_user(
        user.id, user.username, user.first_name, user.language_code or 'ru'
    )

    if success:
        text = (
            f'👋 {bold(f"Привет, {html_secure(user.first_name)}!")}\n\n'
            'Я бот-помощник KinoPub Observer.\n'
            'Вы можете искать информацию о фильмах и сериалах в нашей базе.\n\n'
            f'🔍 {bold("Просто отправьте мне название")}, и я найду контент.'
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
    title = html_secure(show_data['title'])
    orig_title = html_secure(show_data['original_title'])
    year = show_data.get('year') or 'N/A'
    type_ = show_data.get('type') or 'Unknown'
    status = show_data.get('status')

    # Формируем ссылку на кинопаб
    site_url = os.getenv('SITE_AUX_URL', '').rstrip('/')
    if site_url:
        kp_main_link = f'{site_url}/item/view/{show_data["id"]}'
        title_line = html_link(kp_main_link, bold(title))
    else:
        title_line = bold(title)

    # Рейтинги
    kp = show_data.get('kinopoisk_rating')
    imdb = show_data.get('imdb_rating')
    kp_str = f'{kp:.1f}' if kp else '-'
    imdb_str = f'{imdb:.1f}' if imdb else '-'

    kp_url = show_data.get('kinopoisk_url')
    imdb_url = show_data.get('imdb_url')

    kp_link = html_link(kp_url, f'KP: {kp_str}') if kp_url else f'KP: {kp_str}'
    imdb_link = html_link(imdb_url, f'IMDB: {imdb_str}') if imdb_url else f'IMDB: {imdb_str}'

    countries = ', '.join(show_data.get('countries', [])) or '-'
    genres = ', '.join(show_data.get('genres', [])) or '-'

    status_line = f' | {status}' if status else ''

    if orig_title.lower() != title.lower():
        orig_line = f'🇺🇸 {orig_title}\n\n'
    else:
        orig_line = ''

    text = (
        f'🎬 {title_line}\n'
        f'{orig_line}'
        f'📅 {year} | 🎭 {type_}{status_line}\n'
        f'⭐ {kp_link} | {imdb_link}\n\n'
        f'🌍 {countries}\n'
        f'🏷 {genres}'
    )

    await sender.send_message(chat_id=chat_id, text=text)


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


async def handle_search_text(message: Message, bot: Bot):
    query = message.text.strip()
    if not query or query.startswith('/'):
        return

    sender = MessageSender(bot)
    results = await client.search_shows(query)

    if not results:
        await sender.send_message(
            message.chat.id, f'😔 По запросу {bold(query)} ничего не найдено.'
        )
        return

    if len(results) == 1:
        full_info = await client.get_show_details(results[0]['id'])
        if full_info:
            await _send_show_card(sender, message.chat.id, full_info)
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

    await sender.send_message(message.chat.id, '\n'.join(text_lines))
