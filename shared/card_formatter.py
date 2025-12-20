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
) -> str:
    """
    Генерирует стандартизированный текст карточки сериала/фильма
    для использования как в Django-приложении, так и в Telegram-боте.
    """
    raw_title = html_secure(title)
    original_title = html_secure(original_title)

    if kinopub_link and show_id:
        link = html_link(f'{kinopub_link.rstrip("/")}/item/view/{show_id}', '🔗')
        lines = [ f'🎬{link} {bold(raw_title)}' ]
    else:
        lines = [ f'🎬 {bold(raw_title)}' ]

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