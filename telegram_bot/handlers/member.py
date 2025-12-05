import logging

import client
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated

router = Router()


@router.my_chat_member(F.chat.type == 'private')
async def on_user_status_changed(event: ChatMemberUpdated):
    """
    Обрабатывает блокировку/разблокировку бота пользователем в ЛС.
    """
    new_state = event.new_chat_member.status
    user = event.from_user

    is_active = None

    if new_state == ChatMemberStatus.KICKED:
        logging.info(f'User {user.id} blocked the bot.')
        is_active = False
    elif new_state == ChatMemberStatus.MEMBER:
        logging.info(f'User {user.id} unblocked the bot.')
        is_active = True

    if is_active is not None:
        await client.update_user_data(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            language_code=user.language_code,
            is_active=is_active,
        )
