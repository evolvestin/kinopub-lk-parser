import asyncio
import logging
import sys

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from handlers import callbacks, commands, member
from middlewares import UserSyncMiddleware  # Импорт мидлвари
from services.bot_instance import BotInstance
from api_server import start_api_server

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def register_router() -> Router:
    """
    Registers all the bot's handlers for different types of messages and events.
    """
    router = Router()

    # --- Middlewares ---
    router.message.middleware(UserSyncMiddleware())
    router.callback_query.middleware(UserSyncMiddleware())

    # --- Member Status Updates (Block/Unblock) ---
    router.include_router(member.router)

    # --- Commands ---
    router.message.register(
        commands.bot_command_start_private, CommandStart(), F.chat.type == ChatType.PRIVATE
    )
    router.message.register(
        commands.bot_command_start_group,
        CommandStart(),
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    )

    # --- Callbacks ---
    router.callback_query.register(
        callbacks.role_switch_handler,
        F.data.startswith('setrole_')
    )

    return router


async def main():
    """
    Initializes the handlers and starts the bot.
    """
    # Initialize Bot Instance
    bot = BotInstance().main_bot

    # Register handlers
    dispatcher = Dispatcher()
    router = register_router()
    dispatcher.include_router(router)

    logging.info('Starting Telegram Bot...')
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем API сервер и поллинг параллельно
    await start_api_server(bot)
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
