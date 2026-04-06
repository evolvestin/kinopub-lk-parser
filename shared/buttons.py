from shared.constants import SERIES_TYPES
from shared.formatters import format_se


def get_rating_label_text(rating: float) -> str:
    if rating is None:
        return ''
    return str(int(rating)) if rating.is_integer() else str(rating)


def get_rate_main_button_data(
    show_id: int, show_type: str, user_rating: float = None, is_notify: bool = False
) -> dict:
    suffix = '_n' if is_notify else ''
    is_series = show_type in SERIES_TYPES

    if is_series:
        label = '🌟 Изменить оценку сериала' if user_rating else '🌟 Оценить сериал'
        callback = f'rate_mode_show_{show_id}{suffix}'
    else:
        label = '🌟 Изменить оценку' if user_rating else '🌟 Оценить'
        callback = f'rate_start_{show_id}{suffix}'

    if user_rating:
        label += f' ({get_rating_label_text(user_rating)}/10)'

    return {'text': label, 'callback_data': callback}


def get_rate_episodes_button_data(
    show_id: int, episodes_rated: int = 0, is_notify: bool = False
) -> dict:
    suffix = '_n' if is_notify else ''
    label = '🌟 Оценить эпизод'
    if episodes_rated:
        label += f' (оценено: {episodes_rated})'
    return {'text': label, 'callback_data': f'rate_mode_ep_{show_id}{suffix}'}


def get_show_control_buttons(
    show_id: int,
    show_type: str,
    season: int = None,
    episode: int = None,
    user_rating: float = None,
    episodes_rated: int = 0,
    channel_url: str = None,
    is_notify: bool = False,
    webapp_url: str = None,
) -> list[list[dict]]:
    suffix = '_n' if is_notify else ''
    buttons = []

    if webapp_url:
        buttons.append([{'text': '📱 Подробнее', 'web_app': {'url': webapp_url}}])

    if show_type in SERIES_TYPES:
        buttons.append([get_rate_main_button_data(show_id, show_type, user_rating, is_notify)])

        if season and episode:
            buttons.append(
                [
                    {
                        'text': f'🌟 Оценить {format_se(season, episode)}',
                        'callback_data': f'rate_ep_start_{show_id}_{season}_{episode}{suffix}',
                    }
                ]
            )

        buttons.append([get_rate_episodes_button_data(show_id, episodes_rated, is_notify)])
    else:
        buttons.append([get_rate_main_button_data(show_id, show_type, user_rating, is_notify)])

    if channel_url:
        buttons.append([{'text': '🔗 Просмотр', 'url': channel_url}])

    return buttons
