import hashlib
import html
import os
from urllib.parse import urlsplit

import client
from aiogram import F, Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions,
)
from services.bot_instance import BotInstance

from shared.constants import (
    SERIES_TYPES,
    SHOW_STATUS_DISPLAY_RU,
    SHOW_TYPE_DISPLAY_RU,
)
from shared.html_helper import bold

router = Router()


def _inline_show_card_text(item: dict) -> str:
    """Build the compact, poster-free card used by production inline results."""
    title = html.escape(str(item.get('title') or 'Без названия'), quote=False)
    original = item.get('original_title')
    lines = [f'🎬 <b>{title}</b>']
    if original and original != item.get('title'):
        lines.append(f'<i>{html.escape(str(original), quote=False)}</i>')

    countries = item.get('countries') or []
    if countries:
        lines.append(' · '.join(html.escape(str(country), quote=False) for country in countries[:3]))

    show_type = item.get('type')
    metadata = []
    if item.get('year'):
        metadata.append(f'📅 {item["year"]}')
    if show_type:
        metadata.append(f'🎭 {SHOW_TYPE_DISPLAY_RU.get(show_type, show_type)}')
    status = item.get('status')
    if status and (show_type in SERIES_TYPES or status not in ('Finished', 'Ongoing')):
        metadata.append(f'✅ {SHOW_STATUS_DISPLAY_RU.get(status, status)}')
    if metadata:
        lines.append(' · '.join(metadata))

    ratings = []
    for key, label, emoji in (
        ('kinopoisk_rating', 'КП', '🔴'),
        ('imdb_rating', 'IMDb', '🟡'),
        ('internal_rating', 'Локальный', '⭐'),
    ):
        value = item.get(key)
        if value is not None:
            ratings.append(f'{emoji} {label} {float(value):.1f}')
    if ratings:
        lines.append(' · '.join(ratings))

    genres = item.get('genres') or []
    if genres:
        lines.append('🏷 ' + ' · '.join(html.escape(str(genre), quote=False) for genre in genres[:5]))
    return '\n'.join(lines)


@router.inline_query(F.query.startswith('share_'))
async def inline_share_handler(query: InlineQuery):
    stat_id = query.query.replace('share_', '').strip()
    if not stat_id:
        return

    # Production inline results cannot carry HTML widgets, so keep this share
    # flow as a compact text result. The previous poster implementation is
    # recoverable from commit c49ff7b.
    bot_username = await BotInstance().get_bot_username()
    env = os.getenv('ENVIRONMENT', 'DEV')

    # На проде используем прямой запуск Mini App (требует настройки в BotFather)
    # Формат: https://t.me/bot_username/app_name?startapp=query
    if env == 'PROD':
        app_name = os.getenv('WEBAPP_SHORT_NAME', 'stats')
        url = f'https://t.me/{bot_username}/{app_name}?startapp=stat_{stat_id}'
        btn_text = 'Открыть статистику'
    else:
        # В DEV режиме (туннель) идем через Deep Link бота, чтобы избежать BOT_INVALID
        url = f'https://t.me/{bot_username}?start=stat_{stat_id}'
        btn_text = 'Перейти к статистике'

    article = InlineQueryResultArticle(
        id=f'share_{stat_id}',
        title='Поделиться статистикой',
        description='Нажмите, чтобы отправить статистику',
        input_message_content=InputTextMessageContent(
            message_text=f'📊 {bold("Смотри мою статистику!")}',
            parse_mode='HTML',
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=btn_text, url=url)]]
        ),
    )

    await query.answer([article], cache_time=10, is_personal=False)


@router.inline_query(~F.query.startswith('share_'))
async def inline_search_handler(query: InlineQuery):
    text = query.query.strip()
    user_id = query.from_user.id

    if not text:
        help_article = InlineQueryResultArticle(
            id='help',
            title='Поиск сериалов и фильмов',
            description='Введите название для поиска...',
            input_message_content=InputTextMessageContent(
                message_text='Введите название фильма или сериала после имени бота для поиска.',
                parse_mode='HTML',
            ),
        )
        await query.answer([help_article], cache_time=1, is_personal=True)
        return

    if len(text) < 2:
        return

    results_data = await client.search_shows(text, telegram_id=user_id)

    if not results_data:
        not_found_article = InlineQueryResultArticle(
            id='not_found',
            title='Ничего не найдено',
            description=f'По запросу "{text}" ничего не найдено',
            input_message_content=InputTextMessageContent(
                message_text=f'😔 По запросу {bold(text)} ничего не найдено.',
                parse_mode='HTML',
            ),
        )
        await query.answer([not_found_article], cache_time=5, is_personal=False)
        return

    bot_username = await BotInstance().get_bot_username()
    articles = []

    for item in results_data:
        show_id = item['id']
        title = item['title']
        year = item.get('year')
        poster = item.get('poster_url')
        if poster:
            parsed_poster = urlsplit(poster)
            if parsed_poster.scheme not in {'http', 'https'} or not parsed_poster.netloc:
                poster = None
        card_text = _inline_show_card_text(item)

        input_content = InputTextMessageContent(
            message_text=card_text,
            parse_mode='HTML',
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

        display_type = SHOW_TYPE_DISPLAY_RU.get(item.get('type'), item.get('type', 'Show'))
        description_parts = [
            str(value)
            for value in (year, display_type, *(item.get('genres') or [])[:2])
            if value
        ]
        description = ' · '.join(description_parts)[:255]

        article_id = hashlib.md5(f'{show_id}'.encode()).hexdigest()

        article = InlineQueryResultArticle(
            id=article_id,
            title=title,
            description=description,
            thumbnail_url=poster,
            thumbnail_width=50,
            thumbnail_height=75,
            input_message_content=input_content,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text='Открыть в приложении ↗',
                        url=(
                            f'https://t.me/{bot_username}/'
                            f'{os.getenv("WEBAPP_SHORT_NAME", "stats")}?startapp=show_{show_id}'
                        ),
                    )
                ]]
            ),
        )
        articles.append(article)

    await query.answer(articles, cache_time=300, is_personal=True)
