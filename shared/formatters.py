def format_duration(seconds: int | float | None) -> str:
    if not seconds or seconds < 0:
        return '0м'

    total_seconds = int(seconds)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    parts = []
    if days > 0:
        parts.append(f'{days}д')
    if hours > 0:
        parts.append(f'{hours}ч')
    if minutes > 0 or not parts:
        parts.append(f'{minutes}м')

    return ' '.join(parts)


def format_se(season: int | None, episode: int | None) -> str:
    """
    Форматирует номер сезона и эпизода:
      - сезон без ведущих нулей
      - эпизод с ведущим нулём только для 1–9
    """
    if not season or not episode:
        return ''

    episode_number = f'{episode:02d}' if episode < 10 else str(episode)
    return f's{int(season)}' + f'e{episode_number}'
