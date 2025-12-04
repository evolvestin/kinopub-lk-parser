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
            # Запускаем обновление данных в фоне
            try:
                # Если мидлварь сработала, значит пользователь взаимодействует с ботом,
                # следовательно, бот активен (is_active=True)
                await client.update_user_data(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    language_code=user.language_code,
                    is_active=True 
                )
            except Exception as e:
                logging.error(f"Middleware user sync error: {e}")

        return await handler(event, data)