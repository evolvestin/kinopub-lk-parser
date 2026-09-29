import logging
import re

from django.db import transaction
from django.db.models import Q

from app.models import Show, ShowPoster
from shared.media import build_poster_url
from shared.constants import SHOW_TYPE_MAPPING, ShowType


logger = logging.getLogger(__name__)


MOVIE_TYPE = SHOW_TYPE_MAPPING[ShowType.MOVIE]
_THREED_TITLE_SUFFIX_RE = re.compile(
    r'\s*[\(\[\{]?\s*3\s*[-–—]?\s*[dд]\s*[\)\]\}]?\s*$',
    re.IGNORECASE,
)


def normalize_movie_title(value: str | None) -> str:
    """Remove a source's trailing 3D marker from a movie title."""
    return _THREED_TITLE_SUFFIX_RE.sub('', str(value or '')).strip()


def normalize_show_type(value: str | None) -> tuple[str | None, bool]:
    """Return the canonical UI type and whether the source item is a 3D copy.

    KinoPub stores compact values such as ``serial`` and ``docuserial``, while
    the web app uses the display-oriented values from ``SHOW_TYPE_MAPPING``.
    Accept both forms so legacy records cannot leak their storage value into
    API responses or change a series into a movie in the UI.
    """
    raw = str(value or '').strip()
    raw_key = raw.casefold()
    for source_type, canonical_type in SHOW_TYPE_MAPPING.items():
        if raw_key in {source_type.value.casefold(), canonical_type.casefold()}:
            if source_type == ShowType.MOVIE_3D:
                return MOVIE_TYPE, True
            return canonical_type, False
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
    title = normalize_movie_title(title)
    original_title = normalize_movie_title(original_title)
    if not title or not original_title:
        return None

    queryset = Show.objects.filter(
        type=MOVIE_TYPE,
    )
    title_variants = {title, f'{title} 3D', f'{title} 3-D', f'{title} (3D)', f'{title} (3-D)'}
    original_variants = {
        original_title,
        f'{original_title} 3D',
        f'{original_title} 3-D',
        f'{original_title} (3D)',
        f'{original_title} (3-D)',
    }
    title_query = Q()
    for variant in title_variants:
        title_query |= Q(title__iexact=variant)
    original_query = Q()
    for variant in original_variants:
        original_query |= Q(original_title__iexact=variant)
    queryset = queryset.filter(title_query, original_query)
    if year is not None:
        queryset = queryset.filter(year=year)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    if not include_3d:
        queryset = queryset.filter(is_3d=False)

    matches = [
        match
        for match in queryset.order_by('id')[:20]
        if normalize_movie_title(match.title).casefold() == title.casefold()
        and normalize_movie_title(match.original_title).casefold() == original_title.casefold()
    ]
    matches = matches[:2]
    if len(matches) == 1:
        return matches[0]
    if include_3d:
        normal_matches = [match for match in matches if not match.is_3d]
        if len(normal_matches) == 1:
            return normal_matches[0]
    return None


def find_exact_show_content_match(
    title: str | None,
    original_title: str | None,
    show_type: str,
    plot: str | None = None,
    exclude_id: int | None = None,
):
    """Find one unambiguous cross-source match using the full content identity."""
    title = ' '.join(str(title or '').split()).casefold()
    original_title = ' '.join(str(original_title or '').split()).casefold()
    plot = ' '.join(str(plot or '').split()).casefold()
    if not title or not original_title or not plot or not show_type:
        return None

    queryset = Show.objects.filter(
        type=show_type,
        kinopub_id__isnull=False,
        title__iexact=title,
        original_title__iexact=original_title,
    )
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)

    matches = [
        match
        for match in queryset.order_by('id')[:20]
        if ' '.join(str(match.title or '').split()).casefold() == title
        and ' '.join(str(match.original_title or '').split()).casefold() == original_title
        and ' '.join(str(match.plot or '').split()).casefold() == plot
    ]
    return matches[0] if len(matches) == 1 else None


def kinopub_poster_variant(is_3d: bool) -> str:
    return '3d' if is_3d else 'main'


def record_kinopub_source(show, kinopub_id: int, is_3d: bool = False):
    """Retain a KinoPub item ID and its poster without changing the main ID."""
    if not kinopub_id:
        return None

    source = ShowPoster.SOURCE_KINOPUB
    variant = kinopub_poster_variant(is_3d)
    poster_url = build_poster_url(kinopub_id, None, 'big') or ''

    # A show can be encountered through more than one KinoPub item (most
    # commonly when the catalog contains several copies of a 3D title). The
    # database has two independent uniqueness rules: one for source IDs and
    # one for a show's source/variant slot. Looking up only by external_id
    # therefore attempts an invalid INSERT when the slot already exists.
    with transaction.atomic():
        # Serialize poster writes for this show. This closes the race where
        # two parser processes both observe an empty source/variant slot and
        # then try to insert it simultaneously.
        Show.objects.select_for_update().get(pk=show.id)
        current = ShowPoster.objects.select_for_update().filter(
            show_id=show.id,
            source=source,
            variant=variant,
        ).first()
        owner = ShowPoster.objects.select_for_update().filter(
            source=source,
            external_id=kinopub_id,
        ).first()

        if owner is not None and owner.show_id != show.id:
            logger.warning(
                'Skipping conflicting KinoPub poster: show=%s external_id=%s '
                'already belongs to show=%s.',
                show.id,
                kinopub_id,
                owner.show_id,
            )
            return owner

        if owner is not None:
            # The source ID is already retained for this show. If it is in the
            # requested slot, refresh only its URL; if another slot already
            # owns it, keep that existing identity rather than violating the
            # slot constraint or silently moving a source ID between variants.
            if current is not None and current.pk != owner.pk:
                return owner
            owner.variant = variant
            owner.url = poster_url
            owner.save(update_fields=['variant', 'url', 'updated_at'])
            return owner

        if current is not None:
            # Replace the retained ID for this logical source/variant. This is
            # the same conflict-safe policy used by the Kinopoisk poster sync:
            # keep one deterministic poster slot and never let a second row
            # crash the surrounding scan.
            current.external_id = kinopub_id
            current.url = poster_url
            current.save(update_fields=['external_id', 'url', 'updated_at'])
            return current

        return ShowPoster.objects.create(
            show_id=show.id,
            source=source,
            external_id=kinopub_id,
            variant=variant,
            url=poster_url,
        )
