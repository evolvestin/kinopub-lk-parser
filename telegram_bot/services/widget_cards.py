"""Poster-free Telegram movie widgets for private bot chats.

The earlier poster iteration is preserved in commit c49ff7b
(`git show c49ff7b:app/services/widget_poster.py`).
"""

import json
import logging
import zlib
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

import client
from aiogram.methods import TelegramMethod
from aiogram.types import Message

_HTML_PATH = Path(__file__).resolve().parents[1] / 'widgets' / 'movie_card.html'
_HELPERS_PATH = Path(__file__).resolve().parents[1] / 'widgets' / 'widget_helpers.js'
_MAX_STATE_BYTES = 1024
_MAX_HTML_BYTES = 32768
_MAX_COMPRESSED_HTML_BYTES = 4096
_WIDGET_HEIGHT = 450
_CAPTION = 'KinoPub Observer · карточка фильма'


class SendWidget(TelegramMethod[Message]):
    """Bot API 10.4 sendWidget method, for aiogram versions without its model."""

    __returning__ = Message
    __api_method__: ClassVar[str] = 'sendWidget'

    chat_id: int | str
    html: str
    caption: str | None = None
    height: int | None = None
    public_data: str | None = None
    chat_data: str | None = None
    allow_queries: bool | None = None


@lru_cache(maxsize=1)
def _widget_html() -> str:
    html = _HTML_PATH.read_text(encoding='utf-8')
    raw = html.encode('utf-8')
    if '\x00' in html or len(raw) > _MAX_HTML_BYTES:
        raise ValueError('Widget HTML is invalid or too large')
    if len(zlib.compress(raw, 9)) > _MAX_COMPRESSED_HTML_BYTES:
        raise ValueError('Compressed widget HTML is too large')
    if 'poster' in html.lower() or '__poster' in html:
        raise ValueError('Poster code is not allowed in this widget')
    return html


def _encode_state(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if len(encoded.encode('utf-8')) > _MAX_STATE_BYTES:
        raise ValueError('Widget state exceeds Telegram limit')
    return encoded


@lru_cache(maxsize=1)
def _widget_helpers() -> str:
    helpers = _HELPERS_PATH.read_text(encoding='utf-8')
    if 'poster' in helpers.lower() or '__poster' in helpers:
        raise ValueError('Poster code is not allowed in this widget')
    return helpers


def build_widget_method(chat_id: int | str, show: dict) -> SendWidget:
    """Build and validate one stable-height widget from the backend show data."""
    fields = (
        'id', 'title', 'original', 'year', 'type', 'status', 'status_label',
        'duration', 'kp', 'imdb', 'local', 'genres', 'countries',
        'imdb_url', 'kinopoisk_url',
    )
    state = [show.get(field) for field in fields]
    for index in (11, 12):
        state[index] = [
            [item.get('name'), item.get('id'), item.get('emoji')]
            if index == 12
            else [item.get('name'), item.get('id')]
            for item in (state[index] or [])
            if isinstance(item, dict)
        ]

    plot = show.get('plot') or ''
    truncated = bool(show.get('plot_truncated'))
    helpers = _widget_helpers()
    while True:
        public_base = {
            'p': plot or 'Описание отсутствует',
            'truncated': truncated,
            'theme': show.get('theme') or 'dark',
        }
        for split in range(len(helpers) + 1):
            try:
                public_data = _encode_state({**public_base, 'j': helpers[:split]})
                chat_data = _encode_state({'s': state, 'j': helpers[split:]})
            except ValueError:
                continue
            return SendWidget(
                chat_id=chat_id,
                html=_widget_html(),
                caption=_CAPTION,
                height=_WIDGET_HEIGHT,
                public_data=public_data,
                chat_data=chat_data,
                allow_queries=True,
            )
        if not plot:
            raise ValueError('Widget state exceeds Telegram limit')
        cut = max(0, len(plot) - 20)
        boundary = plot.rfind(' ', 0, cut)
        plot = plot[:boundary] if boundary > cut - 40 else plot[:cut]
        truncated = True


async def send_show_widget(bot, chat_id: int | str, telegram_id: int, show_id: int) -> bool:
    """Send a movie/series widget to the user's private chat with the bot."""
    show = await client._execute_request(
        'widget/',
        method='POST',
        payload={'telegram_id': telegram_id, 'command': f's:{show_id}:full'},
    )
    if not isinstance(show, dict) or show.get('error'):
        return False
    try:
        await bot(build_widget_method(chat_id, show))
    except Exception as exc:
        logging.warning('Unable to send movie widget (%s)', type(exc).__name__)
        return False
    return True
