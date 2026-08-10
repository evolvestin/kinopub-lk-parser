from django.conf import settings

from app.models import Show
from app.utils import get_proxied_image_url


def get_poster_url(show_id: int, size: str = 'small') -> str | None:
    """Return a poster URL for a local ``Show`` record.

    KinoPub's poster service is keyed by ``kinopub_id`` rather than the local
    database primary key. TMDB-only records have no KinoPub poster, so they
    use their stored TMDB poster path instead.
    """
    show = Show.objects.filter(id=show_id).only('kinopub_id', 'tmdb_poster_path').first()
    if not show:
        return None

    if show.kinopub_id:
        poster_base = settings.POSTER_BASE_URL.rstrip('/')
        url = f'{poster_base}/{size}/{show.kinopub_id}.jpg'
        return get_proxied_image_url(url)

    if not show.tmdb_poster_path:
        return None

    tmdb_sizes = {'small': 'w200', 'medium': 'w342', 'big': 'w500'}
    tmdb_url = (
        f'https://image.tmdb.org/t/p/{tmdb_sizes.get(size, "w342")}{show.tmdb_poster_path}'
    )
    return get_proxied_image_url(tmdb_url)
