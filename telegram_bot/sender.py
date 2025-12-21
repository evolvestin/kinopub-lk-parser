import asyncio
import logging

from aiogram import Bot, types
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from shared.html_helper import html_secure, sub_tag

MAX_LENGTH = 4096


class MessageSender:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        keyboard: types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup = None,
        edit_message: int | str | types.Message = None,
        link_preview: bool = False,
        reply_id: int = None,
        parse_mode: str = 'HTML',
        attempt: int = 0,
    ) -> types.Message | None:
        chat_id = int(chat_id)
        disable_link_preview = not link_preview
        response = None

        try:
            if edit_message:
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
                    current_text = edit_message.text or edit_message.caption or ''
                    clean_new_text = html_secure(sub_tag(text), reverse=True).strip()

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

    async def send_smart_split_text(
        self,
        chat_id: int | str,
        text_blocks: list[str],
        header: str = '',
        separator: str = '\n',
        parse_mode: str = 'HTML',
    ):
        """
        Универсальный метод для отправки списка текстовых блоков.
        Гарантирует, что сообщение не превысит лимит 4096 символов.
        Старается не разрывать блоки.
        """
        current_message = header

        for block in text_blocks:
            # Проверяем длину: текущее сообщение + разделитель + блок
            # Если превышает, отправляем текущее и начинаем новое
            if len(current_message) + len(separator) + len(block) > MAX_LENGTH:
                if current_message.strip():
                    await self.send_message(chat_id, current_message, parse_mode=parse_mode)
                current_message = block
            else:
                if current_message:
                    current_message += separator + block
                else:
                    current_message = block

        # Отправляем остаток
        if current_message.strip():
            await self.send_message(chat_id, current_message, parse_mode=parse_mode)
