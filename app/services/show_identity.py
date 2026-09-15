from app.models import Show, ShowPoster
from shared.media import build_poster_url
from shared.constants import SHOW_TYPE_MAPPING, ShowType


MOVIE_TYPE = SHOW_TYPE_MAPPING[ShowType.MOVIE]
THREED_TYPE = SHOW_TYPE_MAPPING[ShowType.MOVIE_3D]


def normalize_show_type(value: str | None) -> tuple[str | None, bool]:
    """Return the stored type and whether the source item is a 3D copy."""
    raw = str(value or '').strip()
    if raw.lower() in {
        ShowType.MOVIE.value,
        MOVIE_TYPE.lower(),
        ShowType.MOVIE_3D.value,
        THREED_TYPE.lower(),
    }:
        return MOVIE_TYPE, raw.lower() in {ShowType.MOVIE_3D.value, THREED_TYPE.lower()}
    return raw or None, False


def get_show_by_kinopub_id(kinopub_id: int | None):
    """Resolve both the canonical KinoPub ID and a retained variant ID."""
    if not kinopub_id:
        return None
    show = Show.objects.filter(kinopub_id=kinopub_id).first()
    if show:
        return show
    return (
        Show.objects.filter(
            posters__source=ShowPoster.SOURCE_KINOPUB,
            posters__external_id=kinopub_id,
        )
        .distinct()
        .first()
    )


def find_exact_movie_match(
    title: str | None,
    original_title: str | None,
    year: int | None = None,
    exclude_id: int | None = None,
    include_3d: bool = False,
):
    """Find one safe movie identity match for a source variant.

    Exact normalized titles are intentionally used only for movies and only
    when the group is unambiguous. This prevents unrelated same-name films
    from being silently collapsed.
    """
    title = (title or '').strip()
    original_title = (original_title or '').strip()
    if not title or not original_title:
        return None

    queryset = Show.objects.filter(
        type=MOVIE_TYPE,
        title__iexact=title,
        original_title__iexact=original_title,
    )
    if year is not None:
        queryset = queryset.filter(year=year)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    if not include_3d:
        queryset = queryset.filter(is_3d=False)

    matches = list(queryset.order_by('id')[:2])
    if len(matches) == 1:
        return matches[0]
    if include_3d:
        normal_matches = [match for match in matches if not match.is_3d]
        if len(normal_matches) == 1:
            return normal_matches[0]
    return None


def kinopub_poster_variant(is_3d: bool) -> str:
    return '3d' if is_3d else 'main'


def record_kinopub_source(show, kinopub_id: int, is_3d: bool = False):
    """Retain a KinoPub item ID and its poster without changing the main ID."""
    if not kinopub_id:
        return
    ShowPoster.objects.update_or_create(
        source=ShowPoster.SOURCE_KINOPUB,
        external_id=kinopub_id,
        defaults={
            'show_id': show.id,
            'variant': kinopub_poster_variant(is_3d),
            'url': build_poster_url(kinopub_id, None, 'big') or '',
        },
    )
