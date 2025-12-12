from enum import StrEnum


class UserRole(StrEnum):
    GUEST = 'guest'
    VIEWER = 'viewer'
    ADMIN = 'admin'


class ShowType(StrEnum):
    SERIES = 'serial'
    MOVIE = 'movie'
    MOVIE_3D = '3d'
    DOCUMENTARY_MOVIE = 'documovie'
    DOCUMENTARY_SERIES = 'docuserial'
    TV_SHOW = 'tvshow'
    CONCERT = 'concert'


SHOW_TYPE_MAPPING = {
    ShowType.SERIES: 'Series',
    ShowType.MOVIE: 'Movie',
    ShowType.CONCERT: 'Concert',
    ShowType.DOCUMENTARY_MOVIE: 'Documentary Movie',
    ShowType.DOCUMENTARY_SERIES: 'Documentary Series',
    ShowType.TV_SHOW: 'TV Show',
    ShowType.MOVIE_3D: '3D Movie',
}

SHOW_TYPES_TRACKED_VIA_NEW_EPISODES = [
    ShowType.SERIES,
    ShowType.DOCUMENTARY_SERIES,
    ShowType.TV_SHOW,
]


RATING_VALUES = [float(i) for i in range(1, 11)]
