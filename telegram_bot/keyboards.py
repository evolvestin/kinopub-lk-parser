from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.constants import RATING_VALUES


def _create_rating_grid(callback_template: str, back_callback: str = None, items_per_row: int = 5):
    """
    Универсальный генератор клавиатуры рейтинга на основе RATING_VALUES.
    :param callback_template: строка формата 'prefix_{val}', куда подставится значение.
    :param back_callback: callback_data для кнопки "Назад".
    :param items_per_row: количество кнопок в ряду.
    """
    buttons = []
    row = []

    for value in RATING_VALUES:
        # Если число целое, отображаем без точки (1, 2...), иначе с точкой (0.5, 1.5...)
        label = str(int(value)) if value.is_integer() else str(value)
        # В callback передаем число как есть (или float, если нужно)
        callback_data = callback_template.format(val=label)

        row.append(InlineKeyboardButton(text=label, callback_data=callback_data))

        if len(row) == items_per_row:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    if back_callback:
        buttons.append([InlineKeyboardButton(text='🔙 Назад', callback_data=back_callback)])

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


def get_show_card_keyboard(show_id: int, season: int = None, episode: int = None):
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
                InlineKeyboardButton(
                    text='⭐️ Оценить сериал целиком', callback_data=f'rate_start_{show_id}'
                )
            ]
        )
    else:
        # Обычный просмотр
        buttons.append(
            [InlineKeyboardButton(text='⭐️ Оценить', callback_data=f'rate_start_{show_id}')]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_rating_keyboard(show_id: int):
    return _create_rating_grid(
        callback_template=f'rate_set_{show_id}_{{val}}', back_callback=f'rate_back_{show_id}'
    )


def get_episode_rating_keyboard(show_id: int, season: int, episode: int):
    # Добавляем кнопку назад, возвращающую к списку эпизодов этого сезона
    return _create_rating_grid(
        callback_template=f'rate_ep_set_{show_id}_{season}_{episode}_{{val}}',
        back_callback=f'rate_sel_seas_{show_id}_{season}',
    )


def get_rate_mode_keyboard(show_id: int):
    buttons = [
        [
            InlineKeyboardButton(
                text='⭐️ Оценить сериал целиком', callback_data=f'rate_mode_show_{show_id}'
            ),
        ],
        [InlineKeyboardButton(text='📺 Оценить эпизод', callback_data=f'rate_mode_ep_{show_id}')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data=f'rate_back_{show_id}')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_seasons_keyboard(show_id: int, seasons: list[int]):
    buttons = []
    row = []
    for s in sorted(seasons):
        row.append(InlineKeyboardButton(text=f'S{s}', callback_data=f'rate_sel_seas_{show_id}_{s}'))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text='🔙 Назад', callback_data=f'rate_start_{show_id}')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_episodes_keyboard(show_id: int, season: int, episodes: list[int]):
    buttons = []
    row = []
    for e in sorted(episodes):
        row.append(
            InlineKeyboardButton(
                text=f'E{e}', callback_data=f'rate_ep_start_{show_id}_{season}_{e}'
            )
        )
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text='🔙 Назад', callback_data=f'rate_mode_ep_{show_id}')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
