import os
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

import client
import keyboards
from html_helper import bold, code
from sender import MessageSender

router = Router()
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# --- Private Chat Handlers ---

@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start_private(message: Message, bot: Bot):
    sender = MessageSender(bot)
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # 1. Проверяем наличие пользователя (асинхронно)
    exists = await client.check_user_exists(user_id)
    
    if exists:
        text = (
            f"👋 {bold(f'С возвращением, {first_name}!')}\n\n"
            "Вы уже зарегистрированы в системе. "
            "Я готов показывать вашу статистику и новые эпизоды."
        )
        await sender.send_message(chat_id=user_id, text=text)
    else:
        text = (
            f"👋 {bold(f'Привет, {first_name}!')}\n\n"
            "Я — бот для сбора статистики по фильмам и сериалам на основе KinoPub.\n"
            "Для доступа к функциям необходимо пройти процедуру регистрации.\n\n"
            f"⚠️ {bold(f'Заявки обрабатываются вручную администратором (@{ADMIN_USERNAME}).')}"
        )
        await sender.send_message(chat_id=user_id, text=text, keyboard=keyboards.get_registration_keyboard())

@router.callback_query(F.data == "start_registration")
async def callback_register(callback: CallbackQuery, bot: Bot):
    sender = MessageSender(bot)
    user = callback.from_user
    
    if not ADMIN_CHANNEL_ID:
        await callback.answer("Ошибка конфигурации: не задан канал администратора.", show_alert=True)
        return

    admin_text = (
        f"🆕 {bold('Новая заявка на регистрацию')}\n\n"
        f"👤 {bold('Имя:')} {user.full_name}\n"
        f"🆔 {bold('ID:')} {code(user.id)}\n"
        f"🔗 {bold('Username:')} @{user.username if user.username else 'Нет'}"
    )
    
    # Отправка админу
    await sender.send_message(
        chat_id=ADMIN_CHANNEL_ID,
        text=admin_text,
        keyboard=keyboards.get_admin_approval_keyboard(user.id, user.username or "", user.first_name)
    )
    
    # Ответ пользователю (редактируем старое сообщение)
    user_text = (
        f"⏳ {bold('Заявка отправлена!')}\n\n"
        "Пожалуйста, ожидайте решения администратора. "
        "Я пришлю уведомление, как только доступ будет открыт."
    )
    await sender.send_message(
        chat_id=user.id, 
        text=user_text, 
        edit_message=callback.message
    )

# --- Group Chat Handlers ---

@router.message(CommandStart(), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_start_group(message: Message, bot: Bot):
    sender = MessageSender(bot)
    text = (
        f"🤖 {bold('Приветствую всех участников чата!')}\n\n"
        "К сожалению, зарегистрировать целый чат для просмотра статистики нельзя — "
        "этот функционал доступен только для личных аккаунтов.\n\n"
        f"📉 Если вы хотите получать персональную статистику, пожалуйста, "
        f"напишите мне в {bold('личные сообщения')} и пройдите регистрацию."
    )
    await sender.send_message(chat_id=message.chat.id, text=text)

# --- Admin Handlers (Callbacks) ---

@router.callback_query(F.data.startswith("approve_"))
async def admin_approve(callback: CallbackQuery, bot: Bot):
    sender = MessageSender(bot)
    try:
        user_id = int(callback.data.split("_")[1])
        
        # Пытаемся получить актуальные данные юзера
        try:
            chat_member = await bot.get_chat_member(user_id, user_id)
            user = chat_member.user
            username = user.username
            first_name = user.first_name
            language_code = user.language_code or "ru"
        except Exception:
            username = "Unknown"
            first_name = "User"
            language_code = "ru"

        # Регистрируем на бекенде (асинхронно)
        success = await client.register_user(user_id, username, first_name, language_code)
        
        if success:
            await sender.send_message(
                chat_id=callback.message.chat.id,
                text=f"{callback.message.text}\n\n✅ {bold('Одобрено')}",
                edit_message=callback.message
            )
            
            # Уведомляем пользователя
            await sender.send_message(
                chat_id=user_id,
                text=f"🎉 {bold('Поздравляем! Ваша заявка одобрена.')}\n\nТеперь вам доступен полный функционал бота."
            )
        else:
            await callback.answer("Ошибка при создании пользователя на бекенде", show_alert=True)
            
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data.startswith("reject_"))
async def admin_reject(callback: CallbackQuery, bot: Bot):
    sender = MessageSender(bot)
    user_id = int(callback.data.split("_")[1])
    
    await sender.send_message(
        chat_id=callback.message.chat.id,
        text=f"{callback.message.text}\n\n❌ {bold('Отклонено')}",
        edit_message=callback.message
    )

    await sender.send_message(
        chat_id=user_id,
        text=f"😔 {bold('Ваша заявка на регистрацию была отклонена администратором.')}"
    )
