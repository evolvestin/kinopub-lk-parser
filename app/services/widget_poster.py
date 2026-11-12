"""Fetch and compact posters for Telegram's offline HTML widgets."""

import base64
from io import BytesIO
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from PIL import Image, ImageEnhance

from app.models import Show

_CACHE_TIMEOUT = 60 * 60 * 24 * 30
_MAX_SOURCE_BYTES = 2 * 1024 * 1024
_MAX_ANSWER_POSTER_CHARS = 950
_POSTER_LEVELS = range(1, 11)
_POSTER_SIZE_CAPS = (24, 28, 32, 36, 40, 44, 48, 52, 56, 60)


def _poster_sources(show):
    sources = []
    if show.tmdb_poster_path:
        path = show.tmdb_poster_path
        if path.startswith('/') and all(part not in path for part in ('..', '?', '#')):
            sources.append((f'https://image.tmdb.org/t/p/w342{path}', True))
    if show.kinopub_id:
        base = settings.POSTER_BASE_URL.rstrip('/')
        parsed = urlparse(base)
        if parsed.scheme in {'http', 'https'} and parsed.hostname:
            sources.append((f'{base}/big/{int(show.kinopub_id)}.jpg', False))
    return sources


def _palette_candidate(image, size, colors):
    frame = image.copy()
    frame.thumbnail(size, Image.Resampling.LANCZOS)
    frame = frame.quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    output = BytesIO()
    bits = 2 if colors <= 4 else 4
    frame.save(output, format='PNG', optimize=True, bits=bits)
    return base64.b64encode(output.getvalue()).decode('ascii')


def _download_poster(show):
    sources = _poster_sources(show)
    if not sources:
        return None

    chunks = None
    for url, is_tmdb in sources:
        proxies = None
        if is_tmdb and settings.TMDB_PROXY:
            proxies = {'http': settings.TMDB_PROXY, 'https': settings.TMDB_PROXY}
        try:
            with requests.get(url, timeout=(1.5, 3), stream=True, proxies=proxies) as response:
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '').split(';', 1)[0].lower()
                if content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
                    continue
                candidate = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    if chunk:
                        candidate.extend(chunk)
                    if len(candidate) > _MAX_SOURCE_BYTES:
                        break
                if candidate and len(candidate) <= _MAX_SOURCE_BYTES:
                    chunks = candidate
                    break
        except requests.RequestException:
            continue
    if chunks is None:
        return None

    image = Image.open(BytesIO(chunks))
    if image.width * image.height > 20_000_000:
        return None
    return ImageEnhance.Contrast(image.convert('RGB')).enhance(1.06)


def _compact_posters(show):
    """Fetch once, then generate ten color-preserving progressive poster levels."""
    image = _download_poster(show)
    if image is None:
        return {}
    posters = {}
    try:
        max_width = _POSTER_SIZE_CAPS[0]
        for width in _POSTER_SIZE_CAPS[1:]:
            candidate = _palette_candidate(image, (width, width * 3 // 2), 4)
            if len(candidate) > _MAX_ANSWER_POSTER_CHARS:
                break
            max_width = width
        for level in _POSTER_LEVELS:
            width = round(24 + (max_width - 24) * (level - 1) / 9)
            size = (width, width * 3 // 2)
            for colors in (8, 6, 4):
                encoded = _palette_candidate(image, size, colors)
                if len(encoded) <= _MAX_ANSWER_POSTER_CHARS:
                    posters[level] = encoded
                    break
    except (OSError, ValueError, KeyError):
        return posters
    return posters


def widget_poster(show_id, level=10):
    """Return a cached palette PNG small enough for one widget query."""
    if level not in _POSTER_LEVELS:
        return None
    key = f'telegram_widget_posters_v9:{show_id}'
    posters = cache.get(key)
    if posters is not None:
        return posters.get(str(level))
    show = Show.objects.only('id', 'kinopub_id', 'tmdb_poster_path').filter(pk=show_id).first()
    if not show:
        return None
    try:
        posters = _compact_posters(show)
    except (OSError, requests.RequestException, ValueError, Image.DecompressionBombError):
        posters = {}
    # Store string keys so this remains compatible with JSON-backed cache aliases.
    posters = {str(k): value for k, value in posters.items()}
    cache.set(key, posters, _CACHE_TIMEOUT if posters else 60 * 5)
    return posters.get(str(level))
