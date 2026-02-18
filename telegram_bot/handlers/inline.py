import hashlib
import os

import client
from aiogram import Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from services.bot_instance import BotInstance

from shared.card_formatter import get_show_card_text

router = Router()


@router.inline_query()
async def inline_search_handler(query: InlineQuery):
    text = query.query.strip()
    if len(text) < 2:
        return

    results_data = await client.search_shows(text)
    if not results_data:
        return

    bot_username = await BotInstance().get_bot_username()
    articles = []

    for item in results_data:
        show_id = item['id']
        title = item['title']
        original_title = item.get('original_title')
        year = item.get('year')
        poster = item.get('poster_url')

        # Генерируем текст карточки используя общую функцию
        # Передаем базовые данные, так как персональные рейтинги в инлайне недоступны
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
            internal_rating=None,  # Нет данных в поиске
            user_ratings=None,  # Нет данных в поиске
            bot_username=bot_username,
            show_history=False,  # Скрываем историю в общем виде
        )

        # Клавиатура с переходом в бота для действий
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text='🔗 Открыть / Действия',
                        url=f'https://t.me/{bot_username}?start=show_{show_id}',
                    )
                ]
            ]
        )

        input_content = InputTextMessageContent(
            message_text=card_text,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )

        description = f'{year} | {item.get("type", "Show")}'
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
            reply_markup=keyboard,
        )
        articles.append(article)

    await query.answer(articles, cache_time=300, is_personal=False)
