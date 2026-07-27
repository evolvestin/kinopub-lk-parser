from enum import StrEnum

DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = f'{DATE_FORMAT} %H:%M:%S'
RATING_VALUES = [i / 2 for i in range(2, 21)]


class RedisQueue(StrEnum):
    UPDATE_DETAILS = 'queue:update_details'
    UPDATE_DURATIONS = 'queue:update_durations'
    PRIORITY_RATINGS_SYNC = 'queue:priority_ratings_sync'
    ERRORS = 'queue:errors'


class RedisLock(StrEnum):
    SELENIUM_GLOBAL = 'selenium_global_lock'
    BACKUP = 'backup_lock'
    COOKIES_BACKUP = 'cookies_backup_lock'
    PROCESS_QUEUES = 'process_queues_lock'
    FETCH_PERSON_PHOTOS = 'fetch_person_photos_lock'
    SYNC_POISKKINO_RATINGS = 'sync_poiskkino_ratings'
    ENRICH_TMDB_SHOWS = 'enrich_tmdb_shows_lock'


class ParserSessionType(StrEnum):
    MAIN = 'main'
    AUX = 'aux'


class DatePrecision(StrEnum):
    EXACT = 'exact'
    MONTH = 'month'
    YEAR = 'year'
    UNKNOWN = 'unknown'


class TaskRunStatus(StrEnum):
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    STOPPED = 'STOPPED'


PROFESSIONS_MAPPING_RU = {
    'Актёр': ['актеры', 'Актер', 'В ролях'],
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

PROFESSION_TRANS_MAP = {
    'Актёр': 'Actor',
    'Актёр дубляжа': 'Dubbing actor',
    'Режиссёр': 'Director',
    'Продюссер': 'Producer',
    'Сценарист': 'Writer',
    'Художник': 'Designer',
    'Монтажёр': 'Editor',
    'Оператор': 'Operator',
    'Композитор': 'Composer',
}

PROFESSIONS_PLURAL_MAP_RU = {
    'Актёр': 'Актёры',
    'Актёр дубляжа': 'Актёры дубляжа',
    'Режиссёр': 'Режиссёры',
    'Продюссер': 'Продюссеры',
    'Сценарист': 'Сценаристы',
    'Художник': 'Художники',
    'Монтажёр': 'Монтажёры',
    'Оператор': 'Операторы',
    'Композитор': 'Композиторы',
    'Создатель': 'Создатели',
    'Другое': 'Другие',
}

RAW_TO_NORMALIZED_RU = {raw: norm for norm, raws in PROFESSIONS_MAPPING_RU.items() for raw in raws}
RAW_TO_NORMALIZED_EN = {raw: norm for norm, raws in PROFESSIONS_MAPPING_EN.items() for raw in raws}

ACTOR_ROLES = PROFESSIONS_MAPPING_RU['Актёр'] + PROFESSIONS_MAPPING_EN['Actor']
DIRECTOR_ROLES = PROFESSIONS_MAPPING_RU['Режиссёр'] + PROFESSIONS_MAPPING_EN['Director']
WRITER_ROLES = PROFESSIONS_MAPPING_RU['Сценарист'] + PROFESSIONS_MAPPING_EN['Writer']
PRODUCER_ROLES = PROFESSIONS_MAPPING_RU['Продюссер'] + PROFESSIONS_MAPPING_EN['Producer']

GENRES_MAPPING = {
    'Короткометражка': ['короткометражка', 'Короткометражка'],
    'Ток-шоу': ['ток-шоу', 'Ток-шоу'],
    'Документальный': ['документальный', 'Документальный'],
    'Детектив': ['детектив', 'Детектив'],
    'Приключения': ['приключения', 'Приключения'],
    'Семейный': ['семейный', 'Семейный'],
    'Триллер': ['триллер', 'Триллер'],
    'Драма': ['драма', 'Драма'],
    'Комедия': ['комедия', 'Комедия'],
    'История': ['история', 'История', 'Исторический'],
    'Ужасы': ['ужасы', 'Ужасы'],
    'Эротика': ['для взрослых', 'Эротика'],
    'Военный': ['военный', 'Военный'],
    'Мультфильм': ['мультфильм', 'Мультфильм'],
    'Мюзикл': ['мюзикл', 'Музыкальный'],
    'Концерт': ['концерт'],
    'Нуар': ['фильм-нуар', 'Нуар'],
    'Музыка': ['музыка', 'Музыка'],
    'Боевик': ['боевик', 'Боевик', 'Боевик и Приключения'],
    'Вестерн': ['вестерн', 'Вестерн'],
    'Мелодрама': ['мелодрама', 'Мелодрама'],
    'Новости': ['новости'],
    'Спорт': ['спорт', 'Спорт'],
    'Биография': ['биография', 'Биография'],
    'Детский': ['детский'],
    'Фантастика': ['фантастика', 'Фантастика', 'НФ и Фэнтези'],
    'Церемония': ['церемония'],
    'Реалити-шоу': ['реальное ТВ', 'Реалити-шоу'],
    'Аниме': ['аниме', 'Аниме'],
    'Криминал': ['криминал', 'Криминал'],
    'Фэнтези': ['фэнтези', 'Фэнтези'],
    'ТВ фильм': ['ТВ фильм', 'телевизионный фильм', 'ТВ-фильм', 'телефильм'],
    'Игра': ['игра'],
    'Он и она': ['Он и она'],
    'Интеллектуальные': ['Интелектуальные'],
    'K-pop': ['K-pop'],
    'New Age': ['New Age'],
    'Industrial': ['Industrial'],
    'Easy Listening': ['Easy Listening'],
    'Trip-Hop': ['Trip-Hop'],
    'Кулинария': ['Кулинария'],
    'Reggae': ['Reggae'],
    'Chillout': ['Chillout'],
    'Latin': ['Latin'],
    'World': ['World'],
    'Развлекательные': ['Развлекательные'],
    'Обучающее видео': ['Обучающее видео'],
    'Пришельцы': ['Пришельцы'],
    'Курсы': ['Курсы'],
    'Вселенная': ['Вселенная'],
    'Мода': ['Мода'],
    'Лженаука': ['Лженаука'],
    'Физиология': ['Физиология'],
    'Экология': ['Экология'],
    'Выживание': ['Выживание'],
    'Бизнес': ['Бизнес'],
    'Золото': ['Золото'],
    'Психология': ['Психология'],
    'Строительство': ['Строительство'],
    'Хобби': ['Хобби'],
    'Автомобили': ['Автомобили'],
    'Религия': ['Религия'],
    'Открытия': ['Открытия'],
    'Флот': ['Флот'],
    'Авиация': ['Авиация'],
    'Фотография': ['Фотография'],
    'Океан': ['Океан'],
    'Техника': ['Техника'],
    'Наука': ['Наука'],
    'Все обо всем': ['Все обо всем'],
    'Катастрофы': ['Катастрофы'],
    'Литература': ['Литература'],
    'Знаменитости': ['Знаменитости'],
    'Downtempo': ['Downtempo'],
    'Dance': ['Dance'],
    'Country': ['Country'],
    'Кино': ['Кино'],
    'Путешествия': ['Путешествия'],
    'Trance': ['Trance'],
    'Искусство': ['Искусство'],
    'Progressive': ['Progressive'],
    'Космос': ['Космос'],
    'Политика': ['Политика'],
    'Opera': ['Opera'],
    'Балет': ['Балет'],
    'Instrumental': ['Instrumental'],
    'Classical': ['Classical'],
    'Природа': ['Природа'],
    'Мир животных': ['Мир животных'],
    'Jazz': ['Jazz'],
    'Blues': ['Blues'],
    'House': ['House'],
    'Hip-Hop/Rap': ['Hip-Hop/Rap'],
    'Indie': ['Indie'],
    'R&B/Soul': ['R&B/Soul'],
    'Electronic': ['Electronic'],
    'Metal': ['Metal'],
    'Pop': ['Pop'],
    'Rock': ['Rock'],
    'Folk': ['Folk'],
    'Vocal': ['Vocal'],
    'Alternative': ['Alternative'],
    'Оружие / Война': ['Оружие / Война'],
    'Дорама': ['Дорама'],
    'IT технологии': ['IT технологии'],
    'Водевиль': ['Водевиль'],
    'Стендап': ['Стендап'],
    'Спектакль': ['Спектакль'],
    'Люди': ['Люди'],
    'Аномалии': ['Аномалии'],
    'Мистика': ['Мистика'],
    'Расследование': ['Расследование'],
    'Здоровье и медицина': ['Здоровье и медицина'],
    'Эксклюзив': ['Эксклюзив'],
}

RAW_TO_NORMALIZED_GENRE = {raw: norm for norm, raws in GENRES_MAPPING.items() for raw in raws}

RAW_TO_NORMALIZED_COUNTRY = {
    'Afghanistan': 'Афганистан',
    'Albania': 'Албания',
    'Algeria': 'Алжир',
    'Angola': 'Ангола',
    'Argentina': 'Аргентина',
    'Australia': 'Австралия',
    'Austria': 'Австрия',
    'Azerbaijan': 'Азербайджан',
    'Bahamas': 'Багамы',
    'Bangladesh': 'Бангладеш',
    'Belarus': 'Беларусь',
    'Belgium': 'Бельгия',
    'Bosnia and Herzegovina': 'Босния и Герцеговина',
    'Botswana': 'Ботсвана',
    'Brazil': 'Бразилия',
    'Bulgaria': 'Болгария',
    'Cambodia': 'Камбоджа',
    'Cameroon': 'Камерун',
    'Canada': 'Канада',
    'Chile': 'Чили',
    'China': 'Китай',
    'Colombia': 'Колумбия',
    'Costa Rica': 'Коста-Рика',
    'Croatia': 'Хорватия',
    'Cuba': 'Куба',
    'Cyprus': 'Кипр',
    'Czech Republic': 'Чехия',
    'Czechoslovakia': 'Чехословакия',
    'Denmark': 'Дания',
    'Dominican Republic': 'Доминикана',
    'Ecuador': 'Эквадор',
    'Egypt': 'Египет',
    'El Salvador': 'Сальвадор',
    'Estonia': 'Эстония',
    'Ethiopia': 'Эфиопия',
    'Finland': 'Финляндия',
    'France': 'Франция',
    'Gabon': 'Габон',
    'Georgia': 'Грузия',
    'Germany': 'Германия',
    'Ghana': 'Гана',
    'Greece': 'Греция',
    'Guadaloupe': 'Гваделупа',
    'Hong Kong': 'Гонконг',
    'Hungary': 'Венгрия',
    'Iceland': 'Исландия',
    'India': 'Индия',
    'Indonesia': 'Индонезия',
    'Iran': 'Иран',
    'Iraq': 'Ирак',
    'Ireland': 'Ирландия',
    'Israel': 'Израиль',
    'Italy': 'Италия',
    'Jamaica': 'Ямайка',
    'Japan': 'Япония',
    'Jordan': 'Иордания',
    'Kazakhstan': 'Казахстан',
    'Kenya': 'Кения',
    'Kosovo': 'Косово',
    'Kuwait': 'Кувейт',
    'Kyrgyz Republic': 'Кыргызстан',
    'Latvia': 'Латвия',
    'Lebanon': 'Ливан',
    'Lithuania': 'Литва',
    'Luxembourg': 'Люксембург',
    'Macao': 'Макао',
    'Macedonia': 'Северная Македония',
    'Malawi': 'Малави',
    'Malaysia': 'Малайзия',
    'Malta': 'Мальта',
    'Mexico': 'Мексика',
    'Mongolia': 'Монголия',
    'Montenegro': 'Черногория',
    'Morocco': 'Марокко',
    'Myanmar': 'Мьянма',
    'Namibia': 'Намибия',
    'Nepal': 'Непал',
    'Netherlands': 'Нидерланды',
    'Netherlands Antilles': 'Антильские Острова',
    'New Zealand': 'Новая Зеландия',
    'Nigeria': 'Нигерия',
    'Northern Ireland': 'Великобритания',
    'Norway': 'Норвегия',
    'Pakistan': 'Пакистан',
    'Palestinian Territory': 'Палестина',
    'Paraguay': 'Парагвай',
    'Peru': 'Перу',
    'Philippines': 'Филиппины',
    'Poland': 'Польша',
    'Portugal': 'Португалия',
    'Puerto Rico': 'Пуэрто Рико',
    'Qatar': 'Катар',
    'Romania': 'Румыния',
    'Russia': 'Россия',
    'Saudi Arabia': 'Саудовская Аравия',
    'Serbia': 'Сербия',
    'Singapore': 'Сингапур',
    'Slovakia': 'Словакия',
    'Slovenia': 'Словения',
    'South Africa': 'ЮАР',
    'South Korea': 'Южная Корея',
    'Soviet Union': 'СССР',
    'Spain': 'Испания',
    'Sri Lanka': 'Шри-Ланка',
    'St. Kitts and Nevis': 'Сент-Китс и Невис',
    'Sudan': 'Судан',
    'Sweden': 'Швеция',
    'Switzerland': 'Швейцария',
    'Syrian Arab Republic': 'Сирия',
    'Taiwan': 'Тайвань',
    'Thailand': 'Таиланд',
    'Tunisia': 'Тунис',
    'Turkey': 'Турция',
    'Ukraine': 'Украина',
    'United Arab Emirates': 'ОАЭ',
    'United Kingdom': 'Великобритания',
    'United States of America': 'США',
    'Uruguay': 'Уругвай',
    'Uzbekistan': 'Узбекистан',
    'Venezuela': 'Венесуэла',
    'Vietnam': 'Вьетнам',
    'Yugoslavia': 'Югославия',
    'Босния': 'Босния и Герцеговина',
    'Босния-Герцеговина': 'Босния и Герцеговина',
    'Германия (ГДР)': 'Германия',
    'Германия (ФРГ)': 'Германия',
    'Доминика': 'Доминикана',
    'Доминиканская Республика': 'Доминикана',
    'Корея Северная': 'Северная Корея',
    'Корея Южная': 'Южная Корея',
    'Македония': 'Северная Македония',
    'Югославия (ФР)': 'Югославия',
}


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

SHOW_TYPE_DISPLAY_RU = {
    'Series': 'Сериал',
    'Movie': 'Фильм',
    'Concert': 'Концерт',
    'Documentary Movie': 'Док. фильм',
    'Documentary Series': 'Док. сериал',
    'TV Show': 'ТВ-шоу',
    '3D Movie': '3D фильм',
}

SHOW_STATUS_DISPLAY_RU = {
    'Finished': 'Завершен',
    'Ongoing': 'В эфире',
    'Filming': 'Съемки',
    'Post Production': 'Постпродакшен',
    'Pre Production': 'Препродакшен',
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
    'completed': 'Finished',
    'FILMING': 'Filming',
    'filming': 'Filming',
    'POST_PRODUCTION': 'Post Production',
    'post-production': 'Post Production',
    'PRE_PRODUCTION': 'Pre Production',
    'pre-production': 'Pre Production',
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
