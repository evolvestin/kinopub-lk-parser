from django.conf import settings

from app.utils import get_proxied_image_url


def get_poster_url(show_id: int, size: str = 'small') -> str:
    poster_base = settings.POSTER_BASE_URL.rstrip('/')
    url = f'{poster_base}/{size}/{show_id}.jpg'
    return get_proxied_image_url(url)
