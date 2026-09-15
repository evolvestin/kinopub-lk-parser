from django.conf import settings

from app.models import Show, ShowPoster
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

    return build_poster_url(show.kinopub_id, show.tmdb_poster_path, size)


def build_poster_url(
    kinopub_id: int | None, tmdb_poster_path: str | None, size: str = 'small'
) -> str | None:
    """Build a poster URL when the required show fields are already loaded."""
    if kinopub_id:
        poster_base = settings.POSTER_BASE_URL.rstrip('/')
        return get_proxied_image_url(f'{poster_base}/{size}/{kinopub_id}.jpg')

    if not tmdb_poster_path:
        return None

    tmdb_sizes = {'small': 'w200', 'medium': 'w342', 'big': 'w500'}
    tmdb_url = f'https://image.tmdb.org/t/p/{tmdb_sizes.get(size, "w342")}{tmdb_poster_path}'
    return get_proxied_image_url(tmdb_url)


def build_tmdb_poster_url(tmdb_poster_path: str | None, size: str = 'big') -> str | None:
    if not tmdb_poster_path:
        return None
    tmdb_sizes = {'small': 'w200', 'medium': 'w342', 'big': 'w500'}
    return get_proxied_image_url(
        f'https://image.tmdb.org/t/p/{tmdb_sizes.get(size, "w500")}{tmdb_poster_path}'
    )


def build_show_poster_options(show, size: str = 'big') -> list[dict]:
    """Return the unchanged primary poster followed by source alternatives."""
    primary = build_poster_url(show.kinopub_id, show.tmdb_poster_path, size)
    options = []
    seen = set()

    def add(url, source, variant='', is_primary=False):
        if not url or url in seen:
            return
        seen.add(url)
        options.append(
            {
                'url': url,
                'source': source,
                'variant': variant,
                'is_primary': is_primary,
            }
        )

    primary_source = 'kinopub' if show.kinopub_id else 'tmdb'
    add(primary, primary_source, 'main', True)
    if show.tmdb_poster_path and show.kinopub_id:
        add(build_tmdb_poster_url(show.tmdb_poster_path, size), 'tmdb')

    for poster in show.posters.all().order_by('id'):
        # The canonical KinoPub source is already represented by the primary
        # poster above. Keep it out of the alternatives to avoid a duplicate
        # dot for every migrated show.
        if (
            poster.source == ShowPoster.SOURCE_KINOPUB
            and poster.external_id == show.kinopub_id
        ):
            continue
        add(poster.url, poster.source, poster.variant)

    return options
