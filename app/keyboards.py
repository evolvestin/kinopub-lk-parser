from shared.buttons import get_rating_label_text, get_show_control_buttons
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


def get_history_notification_keyboard(
    view_history_obj,
    bot_username=None,
    user_rating=None,
    episodes_rated=0,
    is_channel=False,
    channel_url=None,
):
    show_id = view_history_obj.show.id
    show_type = view_history_obj.show.type
    season = view_history_obj.season_number
    episode = view_history_obj.episode_number
    view_id = view_history_obj.id

    if is_channel:
        buttons = []
        status_btn_text = 'Учесть' if not view_history_obj.is_checked else 'Не учитывать'
        watch_btn_text = '👀 Это я смотрю / Не смотрю'

        buttons.append(
            [
                {
                    'text': f'📊 {status_btn_text} в статистике',
                    'callback_data': f'toggle_check_{view_id}',
                }
            ]
        )
        
        if bot_username:
            url_watch = (
                f'https://t.me/{bot_username}?start=toggle_claim_{view_id}_{show_id}'
            )
            buttons.append([{'text': watch_btn_text, 'url': url_watch}])
        else:
            buttons.append([{'text': watch_btn_text, 'callback_data': f'claim_toggle_{view_id}'}])

        if bot_username:
            season_number = season if season else 0
            episode_number = episode if episode else 0
            url = (
                f'https://t.me/{bot_username}?start=rate_{show_id}_{season_number}_{episode_number}'
            )

            label = '🌟 Оценить'
            if user_rating:
                label += f' (Ваша: {get_rating_label_text(user_rating)})'
            buttons.append([{'text': label, 'url': url}])

        return buttons

    return get_show_control_buttons(
        show_id=show_id,
        show_type=show_type,
        season=season,
        episode=episode,
        user_rating=user_rating,
        episodes_rated=episodes_rated,
        channel_url=channel_url,
        is_notify=True,
    )
