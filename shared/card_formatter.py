from shared.constants import SERIES_TYPES
from shared.html_helper import bold, html_link, html_secure, italic

RATINGS_TRUNCATE_COUNT = 6


def get_show_card_text(
    show_id: int | None,
    title: str,
    original_title: str | None,
    kinopub_link: str | None,
    year: int | str | None,
    show_type: str | None,
    status: str | None,
    countries: list[str] | None,
    genres: list[str] | None,
    imdb_rating: float | None,
    imdb_url: str | None,
    kinopoisk_rating: float | None,
    kinopoisk_url: str | None,
    internal_rating: float | None = None,
    user_ratings: list[dict] | None = None,
    bot_username: str | None = None,
) -> str:
    """
    Генерирует стандартизированный текст карточки сериала/фильма
    для использования как в Django-приложении, так и в Telegram-боте.
    """
    raw_title = html_secure(title)
    original_title = html_secure(original_title)

    if kinopub_link and show_id:
        link = html_link(f'{kinopub_link.rstrip("/")}/item/view/{show_id}', '🔗')
        lines = [f'🎬{link} {bold(raw_title)}']
    else:
        lines = [f'🎬 {bold(raw_title)}']

    if raw_title != original_title:
        lines.append(italic(f'({original_title})'))

    if countries:
        lines.append(', '.join(countries))

    meta_data = []
    if year:
        meta_data.append(f'📅 {year}')
    if show_type:
        meta_data.append(f'🎭 {show_type}')
    if status:
        meta_data.append(status)

    if meta_data:
        lines.append(' | '.join(meta_data))

    ratings = []
    if imdb_rating:
        rating = f'IMDB: {imdb_rating:.1f}'
        ratings.append(html_link(imdb_url, rating) if imdb_url else rating)
    if kinopoisk_rating:
        rating = f'KP: {kinopoisk_rating:.1f}'
        ratings.append(html_link(kinopoisk_url, rating) if kinopoisk_url else rating)
    if internal_rating:
        rating = f'LR: {internal_rating:.1f}'
        ratings.append(rating)

    if ratings:
        lines.append(f'⭐ {" | ".join(ratings)}')

    if genres:
        lines.append(f'🏷 {", ".join(genres)}')

    if user_ratings:
        lines.append('')

        truncated = len(user_ratings) > RATINGS_TRUNCATE_COUNT

        ratings_command = ''
        if show_type in SERIES_TYPES or truncated:
            if bot_username:
                url = f'https://t.me/{bot_username}?start=ratings_{show_id}'
                ratings_command = f' ({html_link(url, "/ratings")})'
            else:
                ratings_command = f' (/ratings_{show_id})'

        lines.append(f'🌟 {bold("Оценки зрителей")}{ratings_command}:')

        if len(user_ratings) > 1:
            for idx, data in enumerate(user_ratings[:RATINGS_TRUNCATE_COUNT], 1):
                lines.append(f'{idx}. {data["label"]}: {data["rating"]:.1f}')
            if truncated:
                lines.append('...')
        else:
            data = user_ratings[0]
            lines.append(f'{data["label"]}: {data["rating"]:.1f}')

    return '\n'.join(lines)


def get_ratings_report_blocks(
    show_type: str,
    user_ratings_summary: list[dict],
    ratings_details: list[dict] = None,
    internal_rating: float | None = None,
) -> tuple[str, str, list[str]]:
    from shared.formatters import format_se

    header = f'📋 Все оценки'
    if internal_rating:
        header += f' ({internal_rating:.1f}/10):'

    blocks = []
    separator = '\n'

    if show_type in SERIES_TYPES:
        separator = '\n\n'
        if ratings_details:
            for i, user_data in enumerate(ratings_details, 1):
                user_rating = None
                for ur in user_ratings_summary:
                    if ur['label'] == user_data['user']:
                        user_rating = ur['rating']
                        break

                lines = []
                user_header = f'{i}. {user_data["user"]}:'
                if user_rating:
                    user_header += f' {bold(f"{user_rating:.1f}")}'
                lines.append(user_header)

                if user_data.get('show_rating'):
                    lines.append(f'Общая: {user_data["show_rating"]}')

                episodes = user_data.get('episodes', [])
                for episode_data in episodes:
                    formatted_se = format_se(episode_data['season'], episode_data['episode'])
                    lines.append(f'  {italic(formatted_se)}: {episode_data["rating"]}')

                blocks.append('\n'.join(lines))
    else:
        header += '\n'
        separator = '\n'
        if user_ratings_summary:
            for i, data in enumerate(user_ratings_summary, 1):
                blocks.append(f'{i}. {data["label"]}: {bold(f"{data["rating"]:.1f}")}')

    return header, separator, blocks