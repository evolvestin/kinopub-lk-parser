import asyncio
import logging
import sys

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from handlers import callbacks, commands
from services.bot_instance import BotInstance

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def register_router() -> Router:
    """
    Registers all the bot's handlers for different types of messages and events.
    """
    router = Router()

    # --- Callbacks ---
    router.callback_query.register(
        callbacks.registration_callback_handler, F.data == 'start_registration'
    )
    router.callback_query.register(callbacks.admin_approve_handler, F.data.startswith('approve_'))
    router.callback_query.register(callbacks.admin_reject_handler, F.data.startswith('reject_'))

    # --- Commands ---
    # Private chat start
    router.message.register(
        commands.bot_command_start_private, CommandStart(), F.chat.type == ChatType.PRIVATE
    )
    # Group chat start
    router.message.register(
        commands.bot_command_start_group,
        CommandStart(),
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
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
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
