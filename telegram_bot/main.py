import asyncio
import logging
import sys

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from api_server import start_api_server
from handlers import callbacks, commands, member
from middlewares import UserSyncMiddleware  # Импорт мидлвари
from services.bot_instance import BotInstance

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

    # --- Content Search & View ---
    router.message.register(commands.handle_explicit_search, F.text.startswith('/search'))
    router.message.register(commands.handle_imdb_lookup, F.text.regexp(r'(?i)^imdb:\s*\d+$'))
    router.message.register(commands.handle_show_command, F.text.regexp(r'^/show_\d+$'))
    router.message.register(commands.handle_ratings_command, F.text.regexp(r'^/ratings_\d+$'))
    router.message.register(commands.handle_search_text, F.chat.type == ChatType.PRIVATE, F.text)

    # --- Callbacks ---
    router.callback_query.register(callbacks.role_switch_handler, F.data.startswith('setrole_'))
    router.callback_query.register(callbacks.cancel_claim_handler, F.data.startswith('unclaim_'))
    router.callback_query.register(
        callbacks.toggle_check_handler, F.data.startswith('toggle_check_')
    )
    router.callback_query.register(
        callbacks.claim_toggle_handler, F.data.startswith('claim_toggle_')
    )

    # Рейтинг (Шоу)
    router.callback_query.register(
        callbacks.rate_show_start_handler, F.data.startswith('rate_start_')
    )
    router.callback_query.register(
        callbacks.rate_show_back_handler, F.data.startswith('rate_back_')
    )
    router.callback_query.register(
        callbacks.rate_mode_show_handler, F.data.startswith('rate_mode_show_')
    )
    router.callback_query.register(callbacks.rate_show_set_handler, F.data.startswith('rate_set_'))

    # Рейтинг (Навигация эпизодов)
    router.callback_query.register(
        callbacks.rate_mode_ep_handler, F.data.startswith('rate_mode_ep_')
    )
    router.callback_query.register(
        callbacks.rate_select_season_handler, F.data.startswith('rate_sel_seas_')
    )

    # Рейтинг (Выставление оценки эпизоду)
    router.callback_query.register(
        callbacks.rate_episode_start_handler, F.data.startswith('rate_ep_start_')
    )
    router.callback_query.register(
        callbacks.rate_episode_set_handler, F.data.startswith('rate_ep_set_')
    )

    # Просмотр списка оценок
    router.callback_query.register(
        callbacks.show_ratings_list_handler, F.data.startswith('show_ratings_')
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
