import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


class BotInstance:
    _instance = None
    main_bot: Bot
    _bot_username: str | None = None

    def __new__(cls):
        if cls._instance is None:
            token = os.getenv('BOT_TOKEN')
            if not token:
                raise ValueError('BOT_TOKEN is not set')

            cls._instance = super().__new__(cls)
            cls._instance.main_bot = Bot(
                token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
        return cls._instance

    async def get_bot_username(self) -> str:
        """Возвращает username бота, кэшируя его после первого запроса."""
        if self._bot_username is None:
            me = await self.main_bot.get_me()
            self._bot_username = me.username
        return self._bot_username
