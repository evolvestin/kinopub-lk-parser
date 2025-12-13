from enum import StrEnum

DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = f'{DATE_FORMAT} %H:%M:%S'
RATING_VALUES = [i / 2 for i in range(2, 21)]


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


SHOW_STATUS_MAPPING = {
    'окончен': 'Finished',
    'в эфире': 'Ongoing',
}


MONTHS_MAP = {
    'Январь': '01',
    'January': '01',
    'Февраль': '02',
    'February': '02',
    'Март': '03',
    'March': '03',
    'Апрель': '04',
    'April': '04',
    'Май': '05',
    'May': '05',
    'Июнь': '06',
    'June': '06',
    'Июль': '07',
    'July': '07',
    'Август': '08',
    'August': '08',
    'Сентябрь': '09',
    'September': '09',
    'Октябрь': '10',
    'October': '10',
    'Ноябрь': '11',
    'November': '11',
    'Декабрь': '12',
    'December': '12',
}
