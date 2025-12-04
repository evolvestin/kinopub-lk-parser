from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
import client
import logging

class UserSyncMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user: User = data.get('event_from_user')
        
        if user:
            # Запускаем обновление данных в фоне (не блокируем обработку хендлера), 
            # либо ждем выполнения, если критично. Для скорости лучше await, т.к. бэкенд быстрый.
            try:
                # При активном действии пользователь точно не заблокировал бота (is_blocked=False)
                await client.update_user_data(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    language_code=user.language_code,
                    is_blocked=False 
                )
            except Exception as e:
                logging.error(f"Middleware user sync error: {e}")

        return await handler(event, data)