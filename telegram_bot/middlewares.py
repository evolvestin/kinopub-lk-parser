import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import client
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from services.bot_instance import BotInstance
from services.logger import TelegramLogger


class UserSyncMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User = data.get('event_from_user')

        if user:
            try:
                await client.register_user(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    language_code=user.language_code or 'en',
                )
            except Exception as e:
                logging.error(f'Middleware user sync error: {e}')

        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self._logger = None

    @property
    def logger(self):
        if self._logger is None:
            bot = BotInstance().main_bot
            self._logger = TelegramLogger(bot)
        return self._logger

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            event_json = event.model_dump_json(exclude_none=True)
            event_dict = json.loads(event_json)
            await client.log_telegram_event(event_dict)
        except Exception as e:
            logging.error(f'LoggingMiddleware (DB) error: {e}')

        try:
            await self.logger.log_update(event)
        except Exception as e:
            logging.error(f'LoggingMiddleware (Telegram Channel) error: {e}')

        return await handler(event, data)
