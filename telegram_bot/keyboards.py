from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from shared.constants import RATING_VALUES


def _build_grid_keyboard(buttons: list[InlineKeyboardButton], items_per_row: int, back_callback: str = None):
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


def _get_action_button_text(base_text: str, user_rating: float = None) -> str:
    if user_rating is not None:
        rating_str = str(int(user_rating)) if user_rating.is_integer() else str(user_rating)
        return f'{base_text} ({rating_str}/10)'
    return base_text


def _create_rating_grid(
    callback_template: str,
    back_callback: str = None,
    items_per_row: int = 5,
    current_rating: float = None,
):
    buttons = []
    row = []

    for value in RATING_VALUES:
        label = str(int(value)) if value.is_integer() else str(value)
        text = _get_rating_label(value, current_rating)
        callback_data = callback_template.format(val=label)
        
        row.append(InlineKeyboardButton(text=text, callback_data=callback_data))

        if len(row) == items_per_row:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    if back_callback:
        buttons.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_registration_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='📝 Подать заявку на регистрацию', callback_data='start_registration')
    ]])


def get_admin_approval_keyboard(user_id: int, username: str, first_name: str):
    uid = str(user_id)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Принять', callback_data=f'approve_{uid}'),
        InlineKeyboardButton(text='❌ Отклонить', callback_data=f'reject_{uid}'),
    ]])


def get_unclaim_keyboard(view_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='❌ Отменить', callback_data=f'unclaim_{view_id}')
    ]])


def get_show_card_keyboard(
    show_id: int,
    show_type: str = None,
    season: int = None,
    episode: int = None,
    user_rating: float = None,
    episodes_rated: int = 0,
    has_any_ratings: bool = False,
):
    buttons = []
    series_types = ['Series', 'Documentary Series', 'TV Show']
    
    if show_type in series_types:
        show_label = _get_action_button_text('⭐️ Изменить оценку сериала' if user_rating else '⭐️ Оценить сериал', user_rating)
        buttons.append([InlineKeyboardButton(text=show_label, callback_data=f'rate_mode_show_{show_id}')])

        if season and episode:
            buttons.append([InlineKeyboardButton(
                text=f'📺 Оценить s{season}e{episode}',
                callback_data=f'rate_ep_start_{show_id}_{season}_{episode}'
            )])

        ep_label = f'📺 Оценить эпизод (оценено: {episodes_rated})' if episodes_rated > 0 else '📺 Оценить эпизод'
        buttons.append([InlineKeyboardButton(text=ep_label, callback_data=f'rate_mode_ep_{show_id}')])

    else:
        label = _get_action_button_text('⭐️ Изменить оценку' if user_rating else '⭐️ Оценить', user_rating)
        buttons.append([InlineKeyboardButton(text=label, callback_data=f'rate_start_{show_id}')])

    # Добавляем кнопку просмотра детальных оценок, если они есть
    if has_any_ratings:
        buttons.append([InlineKeyboardButton(text='📋 Все оценки', callback_data=f'show_ratings_{show_id}')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_rating_keyboard(show_id: int, current_rating: float = None):
    return _create_rating_grid(
        callback_template=f'rate_set_{show_id}_{{val}}',
        back_callback=f'rate_back_{show_id}',
        current_rating=current_rating,
    )


def get_episode_rating_keyboard(show_id: int, season: int, episode: int, current_rating: float = None):
    return _create_rating_grid(
        callback_template=f'rate_ep_set_{show_id}_{season}_{episode}_{{val}}',
        back_callback=f'rate_sel_seas_{show_id}_{season}',
        current_rating=current_rating,
    )


def get_rate_mode_keyboard(show_id: int, user_rating: float = None, episodes_rated: int = 0):
    show_btn_text = _get_action_button_text('⭐️ Изменить оценку сериала' if user_rating else '⭐️ Оценить сериал', user_rating)
    ep_btn_text = f'📺 Оценить эпизод (оценено: {episodes_rated})' if episodes_rated > 0 else '📺 Оценить эпизод'

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=show_btn_text, callback_data=f'rate_mode_show_{show_id}')],
        [InlineKeyboardButton(text=ep_btn_text, callback_data=f'rate_mode_ep_{show_id}')],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data=f'rate_back_{show_id}')],
    ])


def get_seasons_keyboard(show_id: int, season_stats: dict):
    buttons = []
    for s in sorted(season_stats.keys()):
        label = f'S{s}'
        if season_stats[s] > 0:
            label += f' ({season_stats[s]})'
        buttons.append(InlineKeyboardButton(text=label, callback_data=f'rate_sel_seas_{show_id}_{s}'))

    return _build_grid_keyboard(buttons, items_per_row=5, back_callback=f'rate_back_{show_id}')


def get_episodes_keyboard(show_id: int, season: int, episodes_data: list[dict]):
    buttons = []
    for item in sorted(episodes_data, key=lambda x: x['episode_number']):
        episode_number = item['episode_number']
        rating = item.get('rating')

        label = f'E{episode_number}'
        if rating:
            label += f' ({_get_rating_label(rating)})'
        
        buttons.append(InlineKeyboardButton(
            text=label, callback_data=f'rate_ep_start_{show_id}_{season}_{episode_number}'
        ))

    return _build_grid_keyboard(buttons, items_per_row=4, back_callback=f'rate_mode_ep_{show_id}')