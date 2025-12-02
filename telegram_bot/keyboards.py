from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_registration_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📝 Подать заявку на регистрацию", callback_data="start_registration")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_approval_keyboard(user_id: int, username: str, first_name: str):
    # Упаковываем данные минимально, чтобы влезть в лимит callback_data (64 байта)
    # Если данные длинные, лучше использовать просто ID и кэш, но для простоты передадим ID
    uid = str(user_id)
    buttons = [
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{uid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{uid}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)