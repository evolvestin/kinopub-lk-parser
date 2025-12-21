from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.buttons import get_show_control_buttons
from shared.constants import RATING_VALUES
from shared.formatters import format_se
from shared.buttons import get_rate_episodes_button_data, get_rate_main_button_data
from shared.constants import ShowType


def _build_grid_keyboard(
    buttons: list[InlineKeyboardButton], items_per_row: int, back_callback: str = None
):
    """Строит InlineKeyboardMarkup из плоского списка кнопок."""
    grid = []
    row = []
    for btn in buttons:
        row.append(btn)
        if len(row) == items_per_row:
            grid.append(row)
            row = []

    if row:
        grid.append(row)

    if back_callback:
        grid.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=grid)


def _get_rating_label(label: str | float, current_rating: float = None) -> str:
    val = float(label)
    text = str(int(val)) if val.is_integer() else str(val)
    if current_rating is not None and val == current_rating:
        return f'★ {text}'
    return text


def _create_rating_grid(
    callback_template: str,
    back_callback: str = None,
    items_per_row: int = 5,
    current_rating: float = None,
):
    buttons = []

    for value in RATING_VALUES:
        label = str(int(value)) if value.is_integer() else str(value)
        text = _get_rating_label(value, current_rating)
        callback_data = callback_template.format(val=label)
        buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))

    return _build_grid_keyboard(buttons, items_per_row, back_callback)


def get_registration_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='📝 Подать заявку на регистрацию', callback_data='start_registration'
                )
            ]
        ]
    )


def get_admin_approval_keyboard(user_id: int, username: str, first_name: str):
    uid = str(user_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='✅ Принять', callback_data=f'approve_{uid}'),
                InlineKeyboardButton(text='❌ Отклонить', callback_data=f'reject_{uid}'),
            ]
        ]
    )


def get_unclaim_keyboard(view_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='❌ Отменить', callback_data=f'unclaim_{view_id}')]
        ]
    )


def get_show_card_keyboard(
    show_id: int,
    show_type: str = None,
    season: int = None,
    episode: int = None,
    user_rating: float = None,
    episodes_rated: int = 0,
    has_any_ratings: bool = False,
    channel_url: str = None,
):
    # Получаем структуру кнопок из общего модуля
    # В боте обычно is_notify=False, если это прямой просмотр, но 
    # если это пришло из уведомления, логика навигации обрабатывается в handlers
    raw_buttons = get_show_control_buttons(
        show_id=show_id,
        show_type=show_type,
        season=season,
        episode=episode,
        user_rating=user_rating,
        episodes_rated=episodes_rated,
        channel_url=channel_url,
        is_notify=False 
    )

    # Конвертируем словари в объекты Aiogram InlineKeyboardButton
    aiogram_buttons = []
    for row in raw_buttons:
        aiogram_row = []
        for btn_data in row:
            if 'url' in btn_data:
                aiogram_row.append(InlineKeyboardButton(text=btn_data['text'], url=btn_data['url']))
            else:
                aiogram_row.append(InlineKeyboardButton(text=btn_data['text'], callback_data=btn_data['callback_data']))
        aiogram_buttons.append(aiogram_row)

    return InlineKeyboardMarkup(inline_keyboard=aiogram_buttons)


def get_rating_keyboard(show_id: int, current_rating: float = None, is_notify: bool = False):
    suffix = '_n' if is_notify else ''
    return _create_rating_grid(
        callback_template=f'rate_set_{show_id}_{{val}}',
        back_callback=f'rate_back_{show_id}{suffix}',
        current_rating=current_rating,
    )


def get_episode_rating_keyboard(
    show_id: int, season: int, episode: int, current_rating: float = None, is_notify: bool = False
):
    suffix = '_n' if is_notify else ''
    return _create_rating_grid(
        callback_template=f'rate_ep_set_{show_id}_{season}_{episode}_{{val}}',
        back_callback=f'rate_sel_seas_{show_id}_{season}{suffix}',
        current_rating=current_rating,
    )


def get_rate_mode_keyboard(
    show_id: int, user_rating: float = None, episodes_rated: int = 0, is_notify: bool = False
):
    suffix = '_n' if is_notify else ''

    # Используем общую логику из shared/buttons.py
    # Принудительно передаем тип Series, так как это меню выбора режима только для сериалов
    main_btn_data = get_rate_main_button_data(
        show_id, ShowType.SERIES, user_rating, is_notify
    )
    ep_btn_data = get_rate_episodes_button_data(show_id, episodes_rated, is_notify)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=main_btn_data['text'], callback_data=main_btn_data['callback_data'])],
            [InlineKeyboardButton(text=ep_btn_data['text'], callback_data=ep_btn_data['callback_data'])],
            [InlineKeyboardButton(text='⬅️ Назад', callback_data=f'rate_back_{show_id}{suffix}')],
        ]
    )


def get_seasons_keyboard(show_id: int, season_stats: dict, is_notify: bool = False):
    suffix = '_n' if is_notify else ''
    buttons = []
    for s in sorted(season_stats.keys()):
        label = f'S{s}'
        if season_stats[s] > 0:
            label += f' ({season_stats[s]})'
        buttons.append(
            InlineKeyboardButton(text=label, callback_data=f'rate_sel_seas_{show_id}_{s}{suffix}')
        )

    return _build_grid_keyboard(buttons, items_per_row=5, back_callback=f'rate_back_{show_id}{suffix}')


def get_episodes_keyboard(show_id: int, season: int, episodes_data: list[dict], is_notify: bool = False):
    suffix = '_n' if is_notify else ''
    buttons = []
    for item in sorted(episodes_data, key=lambda x: x['episode_number']):
        episode_number = item['episode_number']
        rating = item.get('rating')

        label = f'E{episode_number}'
        if rating:
            label += f' ({_get_rating_label(rating)})'

        buttons.append(
            InlineKeyboardButton(
                text=label, callback_data=f'rate_ep_start_{show_id}_{season}_{episode_number}{suffix}'
            )
        )

    return _build_grid_keyboard(buttons, items_per_row=4, back_callback=f'rate_mode_ep_{show_id}{suffix}')