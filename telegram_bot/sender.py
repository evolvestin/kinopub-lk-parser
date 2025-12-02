import asyncio
import logging
import re
from typing import Optional, Union

from aiogram import Bot, types
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from html_helper import html_secure


class MessageSender:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        keyboard: types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup = None,
        edit_message: Union[int, str, types.Message] = None,
        link_preview: bool = True,
        reply_id: int = None,
        parse_mode: str = 'HTML',
        attempt: int = 0,
    ) -> Optional[types.Message]:
        chat_id = int(chat_id)
        disable_link_preview = not link_preview
        response = None

        try:
            if edit_message:
                # Логика редактирования
                if isinstance(edit_message, (str, int)):
                    message_id = int(edit_message)
                    response = await self.bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=keyboard,
                        disable_web_page_preview=disable_link_preview,
                        parse_mode=parse_mode,
                    )
                elif isinstance(edit_message, types.Message):
                    # Простая проверка на изменение текста, чтобы не спамить API
                    current_text = edit_message.text or edit_message.caption or ''
                    clean_new_text = html_secure(re.sub('<.*?>', '', text), reverse=True).strip()

                    if (
                        current_text.strip() == clean_new_text
                        and edit_message.reply_markup == keyboard
                    ):
                        return edit_message

                    response = await self.bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=edit_message.message_id,
                        reply_markup=keyboard,
                        disable_web_page_preview=disable_link_preview,
                        parse_mode=parse_mode,
                    )
            else:
                # Логика отправки
                response = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    reply_to_message_id=reply_id,
                    disable_web_page_preview=disable_link_preview,
                    parse_mode=parse_mode,
                )

        except TelegramRetryAfter as e:
            logging.warning(f'Flood limit exceeded. Sleep {e.retry_after} seconds.')
            await asyncio.sleep(e.retry_after + 1)
            return await self.send_message(
                chat_id,
                text,
                keyboard,
                edit_message,
                link_preview,
                reply_id,
                parse_mode,
                attempt + 1,
            )

        except (TelegramNetworkError, TelegramServerError) as e:
            if attempt < 3:
                await asyncio.sleep(0.5 * (attempt + 1))
                return await self.send_message(
                    chat_id,
                    text,
                    keyboard,
                    edit_message,
                    link_preview,
                    reply_id,
                    parse_mode,
                    attempt + 1,
                )
            logging.error(f'Network error after retries: {e}')

        except Exception as e:
            # Игнорируем ошибки блокировки бота пользователем, чтобы не крашить поток
            err_str = str(e).lower()
            if any(
                x in err_str for x in ['blocked', 'user is deactivated', 'chat not found', 'kicked']
            ):
                logging.info(f'User {chat_id} is unavailable: {e}')
            elif 'message is not modified' in err_str:
                pass
            else:
                logging.error(f'Unexpected error sending message to {chat_id}: {e}')

        return response
