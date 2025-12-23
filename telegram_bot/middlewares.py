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


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Логируем входящее событие
        try:
            event_dict = event.model_dump(mode='json', exclude_none=True)
            chat_id = None
            message_id = None
            text = None

            if event.message:
                chat_id = event.message.chat.id
                message_id = event.message.message_id
                text = event.message.text or event.message.caption
            elif event.callback_query:
                chat_id = event.callback_query.message.chat.id
                message_id = event.callback_query.message.message_id
                text = f'[Callback] {event.callback_query.data}'
            elif event.my_chat_member:
                chat_id = event.my_chat_member.chat.id
                text = f'[StatusChange] {event.my_chat_member.new_chat_member.status}'

            await client.log_telegram_event(
                direction='IN',
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                raw_data=event_dict,
            )
        except Exception as e:
            logging.error(f'LoggingMiddleware error: {e}')

        return await handler(event, data)
