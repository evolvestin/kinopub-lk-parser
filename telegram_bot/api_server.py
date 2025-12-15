import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from aiohttp import web


def _get_validated_markup(markup_data):
    if not markup_data:
        return None
    try:
        return InlineKeyboardMarkup.model_validate(markup_data)
    except Exception as e:
        logging.error(f'Markup validation error: {e}')
        return None


async def handle_send_message(request):
    bot: Bot = request.app['bot']
    data = await request.json()

    chat_id = data.get('chat_id')
    text = data.get('text')
    parse_mode = data.get('parse_mode', 'HTML')
    disable_web_page_preview = data.get('disable_web_page_preview', False)
    
    reply_markup = _get_validated_markup(data.get('reply_markup'))

    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
        return web.json_response({'ok': True, 'result': {'message_id': message.message_id}})
    except TelegramAPIError as e:
        logging.error(f'Failed to send message: {e}')
        return web.json_response({'ok': False, 'description': str(e)}, status=400)


async def handle_delete_message(request):
    bot: Bot = request.app['bot']
    data = await request.json()

    chat_id = data.get('chat_id')
    message_id = data.get('message_id')

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return web.json_response({'ok': True, 'result': True})
    except TelegramAPIError as e:
        logging.warning(f'Failed to delete message: {e}')
        return web.json_response({'ok': False, 'description': str(e)})


async def handle_edit_message(request):
    bot: Bot = request.app['bot']
    data = await request.json()

    chat_id = data.get('chat_id')
    message_id = data.get('message_id')
    text = data.get('text')
    parse_mode = data.get('parse_mode', 'HTML')
    disable_web_page_preview = data.get('disable_web_page_preview', False)
    
    reply_markup = _get_validated_markup(data.get('reply_markup'))

    try:
        if text:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
            )
        elif reply_markup:
            await bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=reply_markup
            )
        else:
            return web.json_response(
                {'ok': False, 'description': 'No text or markup provided for edit'}, status=400
            )

        return web.json_response({'ok': True, 'result': True})
    except TelegramAPIError as e:
        if 'message is not modified' in str(e):
            return web.json_response({'ok': True, 'result': True})

        logging.warning(f'Failed to edit message: {e}')
        return web.json_response({'ok': False, 'description': str(e)})


async def handle_get_me(request):
    bot: Bot = request.app['bot']
    try:
        me = await bot.get_me()
        return web.json_response(
            {
                'ok': True,
                'result': {
                    'id': me.id,
                    'is_bot': me.is_bot,
                    'first_name': me.first_name,
                    'username': me.username,
                },
            }
        )
    except TelegramAPIError as e:
        logging.error(f'Failed to get bot info: {e}')
        return web.json_response({'ok': False, 'description': str(e)}, status=500)


async def start_api_server(bot: Bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_get('/api/get_me', handle_get_me)
    app.router.add_post('/api/send_message', handle_send_message)
    app.router.add_post('/api/edit_message', handle_edit_message)
    app.router.add_post('/api/delete_message', handle_delete_message)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8081)
    await site.start()
    logging.info('Internal Bot API server started on port 8081')
