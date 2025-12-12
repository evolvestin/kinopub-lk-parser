def format_se(season: int | None, episode: int | None) -> str:
    """
    Форматирует номер сезона и эпизода:
      - сезон без ведущих нулей
      - эпизод с ведущим нулём только для 1–9
    """
    if not season or not episode:
        return ''

    episode_number = f"{episode:02d}" if episode < 10 else str(episode)
    return f"s{int(season)}" + f'e{episode_number}'