import hashlib
import os

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

from shared.card_formatter import get_show_card_text
from shared.constants import UserRole
from shared.html_helper import bold
from shared.constants import UserRole, SHOW_TYPE_DISPLAY_RU
router = Router()


@router.inline_query(F.query.startswith('share_'))
async def inline_share_handler(query: InlineQuery):
    stat_id = query.query.replace('share_', '').strip()
    if not stat_id:
        return

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
        thumbnail_url='https://img.icons8.com/color/96/combo-chart--v1.png',
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

    role = await client.check_user_role(user_id)
    show_history_flag = role != UserRole.GUEST

    if not text:
        help_article = InlineQueryResultArticle(
            id='help',
            title='Поиск сериалов и фильмов',
            description='Введите название для поиска...',
            thumbnail_url='https://img.icons8.com/ios/50/search--v1.png',
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
            thumbnail_url='https://img.icons8.com/ios/50/nothing-found.png',
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
        original_title = item.get('original_title')
        year = item.get('year')
        poster = item.get('poster_url')

        card_text = get_show_card_text(
            show_id=show_id,
            title=title,
            original_title=original_title,
            kinopub_link=os.getenv('SITE_AUX_URL'),
            year=year,
            show_type=item.get('type'),
            status=item.get('status'),
            countries=item.get('countries'),
            genres=item.get('genres'),
            imdb_rating=item.get('imdb_rating'),
            imdb_url=item.get('imdb_url'),
            kinopoisk_rating=item.get('kinopoisk_rating'),
            kinopoisk_url=item.get('kinopoisk_url'),
            internal_rating=item.get('internal_rating'),
            user_ratings=item.get('user_ratings'),
            bot_username=bot_username,
            show_history=show_history_flag,
        )

        input_content = InputTextMessageContent(
            message_text=card_text,
            parse_mode='HTML',
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

        display_type = SHOW_TYPE_DISPLAY_RU.get(item.get("type"), item.get("type", "Show"))
        description = f'{year} | {display_type}'
        if original_title and original_title != title:
            description += f' | {original_title}'

        article_id = hashlib.md5(f'{show_id}'.encode()).hexdigest()

        article = InlineQueryResultArticle(
            id=article_id,
            title=title,
            description=description,
            thumbnail_url=poster,
            thumbnail_width=50,
            thumbnail_height=75,
            input_message_content=input_content,
            reply_markup=None,
        )
        articles.append(article)

    await query.answer(articles, cache_time=300, is_personal=True)
