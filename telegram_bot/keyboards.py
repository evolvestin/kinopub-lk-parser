from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.constants import RATING_VALUES


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
        callback_data = callback_template.format(val=label)

        if current_rating is not None and value == current_rating:
            text = f'★ {label}'
        else:
            text = label

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
    buttons = [
        [
            InlineKeyboardButton(
                text='📝 Подать заявку на регистрацию', callback_data='start_registration'
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_approval_keyboard(user_id: int, username: str, first_name: str):
    uid = str(user_id)
    buttons = [
        [
            InlineKeyboardButton(text='✅ Принять', callback_data=f'approve_{uid}'),
            InlineKeyboardButton(text='❌ Отклонить', callback_data=f'reject_{uid}'),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_unclaim_keyboard(view_id: int):
    buttons = [[InlineKeyboardButton(text='❌ Отменить', callback_data=f'unclaim_{view_id}')]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_show_card_keyboard(show_id: int, season: int = None, episode: int = None, user_rating: float = None):
    buttons = []

    # Если передан контекст эпизода, даем возможность оценить именно его
    if season and episode:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f'⭐️ Оценить s{season}e{episode}',
                    callback_data=f'rate_ep_start_{show_id}_{season}_{episode}',
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(text='⭐️ Оценить', callback_data=f'rate_start_{show_id}')
            ]
        )
    else:
        # Обычный просмотр (Фильм или Сериал в общем контексте)
        if user_rating is not None:
            rating_str = str(int(user_rating)) if user_rating.is_integer() else str(user_rating)
            label = f'⭐️ Изменить оценку ({rating_str})'
        else:
            label = '⭐️ Оценить'

        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f'rate_start_{show_id}')]
        )

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
    if user_rating is not None:
        rating_str = str(int(user_rating)) if user_rating.is_integer() else str(user_rating)
        show_btn_text = f'⭐️ Изменить оценку сериала ({rating_str}/10)'
    else:
        show_btn_text = '⭐️ Оценить сериал'

    if episodes_rated > 0:
        ep_btn_text = f'📺 Оценить эпизод (оценено: {episodes_rated})'
    else:
        ep_btn_text = '📺 Оценить эпизод'

    buttons = [
        [
            InlineKeyboardButton(
                text=show_btn_text, callback_data=f'rate_mode_show_{show_id}'
            ),
        ],
        [InlineKeyboardButton(text=ep_btn_text, callback_data=f'rate_mode_ep_{show_id}')],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data=f'rate_back_{show_id}')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_seasons_keyboard(show_id: int, season_stats: dict):
    buttons = []
    row = []
    for s in sorted(season_stats.keys()):
        count = season_stats[s]
        label = f'S{s}'
        if count > 0:
            label += f' ({count})'

        row.append(InlineKeyboardButton(text=label, callback_data=f'rate_sel_seas_{show_id}_{s}'))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=f'rate_start_{show_id}')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def get_episodes_keyboard(show_id: int, season: int, episodes_data: list[dict]):
    buttons = []
    row = []
    
    sorted_episodes = sorted(episodes_data, key=lambda x: x['episode_number'])

    for item in sorted_episodes:
        e = item['episode_number']
        rating = item.get('rating')

        label = f'E{e}'
        if rating:
            rating_val = int(rating) if rating.is_integer() else rating
            label += f' (★ {rating_val})'

        row.append(
            InlineKeyboardButton(
                text=label, callback_data=f'rate_ep_start_{show_id}_{season}_{e}'
            )
        )
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=f'rate_mode_ep_{show_id}')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
