from django.conf import settings

from app.models import Show
from app.utils import get_proxied_image_url


def get_poster_url(show_id: int, size: str = 'small') -> str:
    """Return a poster URL for both KinoPub-backed and TMDB-only shows.

    The poster service is keyed by the local Show id only for records imported
    from KinoPub. TMDB-only records must use their stored TMDB poster path.
    """
    show = Show.objects.filter(id=show_id).only('kinopub_id', 'tmdb_poster_path').first()
    if show and not show.kinopub_id and show.tmdb_poster_path:
        tmdb_sizes = {'small': 'w200', 'medium': 'w342', 'big': 'w500'}
        tmdb_url = (
            f"https://image.tmdb.org/t/p/{tmdb_sizes.get(size, 'w342')}"
            f"{show.tmdb_poster_path}"
        )
        return get_proxied_image_url(tmdb_url)

    poster_base = settings.POSTER_BASE_URL.rstrip('/')
    url = f'{poster_base}/{size}/{show_id}.jpg'
    return get_proxied_image_url(url)
