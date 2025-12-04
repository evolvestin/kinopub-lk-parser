import logging
from aiohttp import web
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError

async def handle_send_message(request):
    bot: Bot = request.app['bot']
    data = await request.json()
    
    chat_id = data.get('chat_id')
    text = data.get('text')
    parse_mode = data.get('parse_mode', 'HTML')
    reply_markup_data = data.get('reply_markup')
    
    reply_markup = None
    if reply_markup_data:
        try:
            reply_markup = InlineKeyboardMarkup.model_validate(reply_markup_data)
        except Exception as e:
            logging.error(f"Markup validation error: {e}")

    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return web.json_response({'ok': True, 'result': {'message_id': message.message_id}})
    except TelegramAPIError as e:
        logging.error(f"Failed to send message: {e}")
        return web.json_response({'ok': False, 'description': str(e)}, status=400)

async def handle_edit_message(request):
    bot: Bot = request.app['bot']
    data = await request.json()
    
    chat_id = data.get('chat_id')
    message_id = data.get('message_id')
    text = data.get('text')
    parse_mode = data.get('parse_mode', 'HTML')
    reply_markup_data = data.get('reply_markup')
    
    reply_markup = None
    if reply_markup_data:
        try:
            reply_markup = InlineKeyboardMarkup.model_validate(reply_markup_data)
        except Exception:
            pass

    try:
        if not text and not reply_markup:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return web.json_response({'ok': True, 'result': True})
            
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return web.json_response({'ok': True, 'result': True})
    except TelegramAPIError as e:
        logging.warning(f"Failed to edit/delete message: {e}")
        return web.json_response({'ok': False, 'description': str(e)})

async def start_api_server(bot: Bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_post('/api/send_message', handle_send_message)
    app.router.add_post('/api/edit_message', handle_edit_message)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8081)
    await site.start()
    logging.info("Internal Bot API server started on port 8081")