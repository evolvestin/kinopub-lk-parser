from shared.constants import UserRole
from shared.constants import SERIES_TYPES


def get_role_management_keyboard(view_user):
    buttons = []
    for role in UserRole:
        is_active = role.value == view_user.role
        label = f'✅ {role.name}' if is_active else role.name
        buttons.append(
            {'text': label, 'callback_data': f'setrole_{view_user.telegram_id}_{role.value}'}
        )
    return [buttons]


def get_history_notification_keyboard(view_history_obj, bot_username=None, user_rating=None, episodes_rated=0):
    status_btn_text = 'Учесть' if not view_history_obj.is_checked else 'Не учитывать'
    watch_btn_text = '👀 Это я смотрю / Не смотрю'
    show_id = view_history_obj.show.id
    show_type = view_history_obj.show.type
    season = view_history_obj.season_number
    episode = view_history_obj.episode_number

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

    if show_type in SERIES_TYPES:
        label = '⭐️ Изменить оценку сериала' if user_rating else '⭐️ Оценить сериал'
        if user_rating:
            rating_str = str(int(user_rating)) if user_rating.is_integer() else str(user_rating)
            label += f' ({rating_str}/10)'
        
        buttons.append([{'text': label, 'callback_data': f'rate_mode_show_{show_id}'}])

        if season and episode:
            buttons.append([{
                'text': f'📺 Оценить s{season}e{episode}',
                'callback_data': f'rate_ep_start_{show_id}_{season}_{episode}'
            }])

        ep_label = f'📺 Оценить эпизод (оценено: {episodes_rated})' if episodes_rated > 0 else '📺 Оценить эпизод'
        buttons.append([{'text': ep_label, 'callback_data': f'rate_mode_ep_{show_id}'}])
    else:
        label = '⭐️ Изменить оценку' if user_rating else '⭐️ Оценить'
        if user_rating:
            rating_str = str(int(user_rating)) if user_rating.is_integer() else str(user_rating)
            label += f' ({rating_str}/10)'
        buttons.append([{'text': label, 'callback_data': f'rate_start_{show_id}'}])

    return buttons