from enum import StrEnum

DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = f'{DATE_FORMAT} %H:%M:%S'
RATING_VALUES = [i / 2 for i in range(2, 21)]


PROFESSIONS_MAPPING_RU = {
    'Актёр': ['актеры', 'Актер', 'В ролях', 'актеры дубляжа'],
    'Актёр дубляжа': ['актеры дубляжа'],
    'Режиссёр': ['режиссеры', 'Режиссер', 'Создатель', 'Режиссёр'],
    'Продюссер': ['продюсеры'],
    'Сценарист': ['сценаристы'],
    'Художник': ['художники'],
    'Монтажёр': ['монтажеры'],
    'Оператор': ['операторы'],
    'Композитор': ['композиторы'],
}

PROFESSIONS_MAPPING_EN = {
    'Actor': ['actor', 'Actor', 'voice_actor'],
    'Dubbing actor': ['voiceover'],
    'Director': ['director', 'Director'],
    'Producer': ['producer'],
    'Writer': ['writer'],
    'Designer': ['designer', 'design'],
    'Editor': ['editor'],
    'Operator': ['operator'],
    'Composer': ['composer'],
}

RAW_TO_NORMALIZED_RU = {raw: norm for norm, raws in PROFESSIONS_MAPPING_RU.items() for raw in raws}

RAW_TO_NORMALIZED_EN = {raw: norm for norm, raws in PROFESSIONS_MAPPING_EN.items() for raw in raws}

ACTOR_ROLES = PROFESSIONS_MAPPING_RU['Актёр'] + PROFESSIONS_MAPPING_EN['Actor']
DIRECTOR_ROLES = PROFESSIONS_MAPPING_RU['Режиссёр'] + PROFESSIONS_MAPPING_EN['Director']


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

SERIES_TYPES = [SHOW_TYPE_MAPPING[t] for t in SHOW_TYPES_TRACKED_VIA_NEW_EPISODES]


SHOW_STATUS_MAPPING = {
    'окончен': 'Finished',
    'в эфире': 'Ongoing',
    'COMPLETED': 'Finished',
    'FILMING': 'Filming',
    'POST_PRODUCTION': 'Post Production',
    'PRE_PRODUCTION': 'Pre Production',
    'UNKNOWN': None,
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
