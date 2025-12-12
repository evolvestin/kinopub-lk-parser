import logging
from collections.abc import Awaitable, Callable
from typing import Any

import client
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User


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
