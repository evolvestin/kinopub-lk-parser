from shared.constants import UserRole


def get_role_management_keyboard(view_user):
    buttons = []
    for role in UserRole:
        is_active = role.value == view_user.role
        label = f'✅ {role.name}' if is_active else role.name
        buttons.append(
            {'text': label, 'callback_data': f'setrole_{view_user.telegram_id}_{role.value}'}
        )
    return [buttons]


def get_history_notification_keyboard(view_history_obj, bot_username=None):
    status_btn_text = 'Учесть' if not view_history_obj.is_checked else 'Не учитывать'
    watch_btn_text = '👀 Это я смотрю / Не смотрю'

    buttons = [
        [
            {
                'text': f'📊 {status_btn_text} в статистике',
                'callback_data': f'toggle_check_{view_history_obj.id}',
            }
        ],
        [
            {
                'text': watch_btn_text,
                'callback_data': f'claim_toggle_{view_history_obj.id}',
            }
        ],
    ]

    if view_history_obj.season_number and view_history_obj.episode_number and bot_username:
        url = f'https://t.me/{bot_username}?start=rate_{view_history_obj.show.id}_{view_history_obj.season_number}_{view_history_obj.episode_number}'
        buttons.append([
            {
                'text': '⭐️ Оценить эпизод',
                'url': url,
            }
        ])

    return buttons