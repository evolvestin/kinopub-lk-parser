from django.conf import settings


def get_poster_url(show_id: int, size: str = 'small') -> str:
    poster_base = settings.POSTER_BASE_URL.rstrip('/')
    print(f'{poster_base}/{size}/{show_id}.jpg')
    return f'{poster_base}/{size}/{show_id}.jpg'
