from dataclasses import dataclass

from django.db import transaction

from app.models import (
    CasinoSpin,
    ExternalRating,
    MutedShowNotification,
    Show,
    ShowCrew,
    ShowDuration,
    UserRating,
    ViewHistory,
    WishlistItem,
)


class ShowMergeConflictError(Exception):
    """Raised when two shows contain incompatible identity values."""


@dataclass
class ShowMergeStats:
    canonical_id: int
    duplicate_id: int
    crew_moved: int = 0
    crew_deduplicated: int = 0
    durations_moved: int = 0
    durations_deduplicated: int = 0
    histories_moved: int = 0
    histories_deduplicated: int = 0
    ratings_moved: int = 0
    ratings_deduplicated: int = 0
    external_ratings_moved: int = 0
    external_ratings_deduplicated: int = 0
    wishlist_items_moved: int = 0
    casino_spins_moved: int = 0
    muted_notifications_moved: int = 0
    muted_notifications_deduplicated: int = 0


def _same_or_fill(canonical, duplicate, field_name):
    canonical_value = getattr(canonical, field_name)
    duplicate_value = getattr(duplicate, field_name)
    if canonical_value in (None, '') and duplicate_value not in (None, ''):
        setattr(canonical, field_name, duplicate_value)
        return True
    if (
        canonical_value not in (None, '')
        and duplicate_value not in (None, '')
        and canonical_value != duplicate_value
        and field_name in {'kinopub_id', 'tmdb_id', 'imdb_id'}
    ):
        raise ShowMergeConflictError(
            f'Conflicting {field_name}: {canonical.id}={canonical_value}, '
            f'{duplicate.id}={duplicate_value}'
        )
    return False


def _merge_show_fields(canonical, duplicate, allow_tmdb_conflict=False):
    identity_fields = ('kinopub_id', 'tmdb_id', 'imdb_id')
    identity_to_transfer = {}
    for field_name in identity_fields:
        canonical_value = getattr(canonical, field_name)
        duplicate_value = getattr(duplicate, field_name)
        if (
            canonical_value not in (None, '')
            and duplicate_value not in (None, '')
            and canonical_value != duplicate_value
        ):
            if field_name == 'tmdb_id' and allow_tmdb_conflict:
                # The TMDB details response can prove that two TMDB rows
                # represent the same IMDb title. Keep the canonical record's
                # established TMDB identity and discard the duplicate's one.
                Show.objects.filter(pk=duplicate.id, tmdb_id=duplicate_value).update(tmdb_id=None)
                duplicate.tmdb_id = None
                continue
            raise ShowMergeConflictError(
                f'Conflicting {field_name}: {canonical.id}={canonical_value}, '
                f'{duplicate.id}={duplicate_value}'
            )
        if canonical_value in (None, '') and duplicate_value not in (None, ''):
            identity_to_transfer[field_name] = duplicate_value

    # These fields are unique. Free them on the duplicate before assigning
    # them to the canonical row; PostgreSQL checks the unique index per UPDATE.
    if identity_to_transfer:
        Show.objects.filter(pk=duplicate.id).update(
            **{field_name: None for field_name in identity_to_transfer}
        )
        for field_name, value in identity_to_transfer.items():
            setattr(duplicate, field_name, None)
            setattr(canonical, field_name, value)

    fill_fields = (
        'title',
        'original_title',
        'year',
        'status',
        'kinopub_id',
        'kinopoisk_url',
        'kinopoisk_rating',
        'kinopoisk_votes',
        'imdb_url',
        'imdb_rating',
        'imdb_votes',
        'tmdb_poster_path',
        'plot',
        'tmdb_enrichment_checked_at',
        'poiskkino_updated_at',
    )
    changed_fields = set(identity_fields)
    for field_name in fill_fields:
        if _same_or_fill(canonical, duplicate, field_name):
            changed_fields.add(field_name)

    if canonical.type in (None, '', 'Unknown') and duplicate.type not in (None, '', 'Unknown'):
        canonical.type = duplicate.type
        changed_fields.add('type')

    for field_name in ('imdb_rating_available', 'kinopoisk_rating_available', 'ignore_collision'):
        value = getattr(canonical, field_name) or getattr(duplicate, field_name)
        if value != getattr(canonical, field_name):
            setattr(canonical, field_name, value)
            changed_fields.add(field_name)

    if changed_fields:
        changed_fields.add('updated_at')
        canonical.save(update_fields=changed_fields)


def _merge_crew(canonical_id, duplicate_id, stats):
    for row in ShowCrew.objects.filter(show_id=duplicate_id).order_by('id'):
        existing = ShowCrew.objects.filter(
            show_id=canonical_id,
            person_id=row.person_id,
            profession=row.profession,
        ).first()
        if existing:
            changed_fields = []
            if not existing.en_profession and row.en_profession:
                existing.en_profession = row.en_profession
                changed_fields.append('en_profession')
            if not existing.canonical_person_id and row.canonical_person_id:
                existing.canonical_person_id = row.canonical_person_id
                changed_fields.append('canonical_person')
            if changed_fields:
                existing.save(update_fields=changed_fields)
            row.delete()
            stats.crew_deduplicated += 1
        else:
            ShowCrew.objects.filter(pk=row.pk).update(show_id=canonical_id)
            stats.crew_moved += 1


def _merge_durations(canonical_id, duplicate_id, stats):
    for row in ShowDuration.objects.filter(show_id=duplicate_id).order_by('id'):
        existing = ShowDuration.objects.filter(
            show_id=canonical_id,
            season_number=row.season_number,
            episode_number=row.episode_number,
        ).first()
        if existing:
            if existing.is_estimated and not row.is_estimated:
                existing.duration_seconds = row.duration_seconds
                existing.is_estimated = False
                existing.save(update_fields=['duration_seconds', 'is_estimated', 'updated_at'])
            row.delete()
            stats.durations_deduplicated += 1
        else:
            ShowDuration.objects.filter(pk=row.pk).update(show_id=canonical_id)
            stats.durations_moved += 1


def _merge_histories(canonical_id, duplicate_id, stats):
    rows = ViewHistory.objects.filter(show_id=duplicate_id).prefetch_related('users').order_by('id')
    for row in rows:
        existing = ViewHistory.objects.filter(
            show_id=canonical_id,
            view_date=row.view_date,
            season_number=row.season_number,
            episode_number=row.episode_number,
        ).first()
        if existing:
            existing.users.add(*row.users.all())
            changed_fields = []
            if not row.is_checked and existing.is_checked:
                existing.is_checked = False
                changed_fields.append('is_checked')
            if not existing.telegram_message_id and row.telegram_message_id:
                existing.telegram_message_id = row.telegram_message_id
                changed_fields.append('telegram_message_id')
            if (
                existing.source == ViewHistory.SOURCE_MANUAL
                and row.source == ViewHistory.SOURCE_KINOPUB
            ):
                existing.source = row.source
                changed_fields.append('source')
            if changed_fields:
                existing.save(update_fields=changed_fields)
            row.delete()
            stats.histories_deduplicated += 1
        else:
            ViewHistory.objects.filter(pk=row.pk).update(show_id=canonical_id)
            stats.histories_moved += 1


def _merge_ratings(canonical_id, duplicate_id, stats):
    for row in UserRating.objects.filter(show_id=duplicate_id).order_by('id'):
        existing = UserRating.objects.filter(
            user_id=row.user_id,
            show_id=canonical_id,
            season_number=row.season_number,
            episode_number=row.episode_number,
        ).first()
        if existing:
            if row.updated_at > existing.updated_at:
                existing.rating = row.rating
                existing.save(update_fields=['rating', 'updated_at'])
            row.delete()
            stats.ratings_deduplicated += 1
        else:
            UserRating.objects.filter(pk=row.pk).update(show_id=canonical_id)
            stats.ratings_moved += 1


def _merge_external_ratings(canonical_id, duplicate_id, stats):
    duplicate_rating = ExternalRating.objects.filter(show_id=duplicate_id).first()
    if not duplicate_rating:
        return

    canonical_rating = ExternalRating.objects.filter(show_id=canonical_id).first()
    if not canonical_rating:
        ExternalRating.objects.filter(pk=duplicate_rating.pk).update(show_id=canonical_id)
        stats.external_ratings_moved += 1
        return

    changed_fields = []
    for field_name in (
        'kp',
        'imdb',
        'tmdb',
        'film_critics',
        'russian_film_critics',
        'await_rating',
    ):
        if (
            getattr(canonical_rating, field_name) is None
            and getattr(duplicate_rating, field_name) is not None
        ):
            setattr(canonical_rating, field_name, getattr(duplicate_rating, field_name))
            changed_fields.append(field_name)
    if changed_fields:
        canonical_rating.save(update_fields=changed_fields + ['updated_at'])
    duplicate_rating.delete()
    stats.external_ratings_deduplicated += 1


def _merge_simple_relations(canonical_id, duplicate_id, stats):
    stats.wishlist_items_moved = WishlistItem.objects.filter(show_id=duplicate_id).update(
        show_id=canonical_id
    )
    stats.casino_spins_moved = CasinoSpin.objects.filter(show_id=duplicate_id).update(
        show_id=canonical_id
    )

    for row in MutedShowNotification.objects.filter(show_id=duplicate_id).order_by('id'):
        existing = MutedShowNotification.objects.filter(
            show_id=canonical_id,
            user_id=row.user_id,
        ).first()
        if existing:
            if row.is_active and not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=['is_active', 'updated_at'])
            row.delete()
            stats.muted_notifications_deduplicated += 1
        else:
            MutedShowNotification.objects.filter(pk=row.pk).update(show_id=canonical_id)
            stats.muted_notifications_moved += 1


@transaction.atomic
def merge_show_records(
    canonical_id: int, duplicate_id: int, allow_tmdb_conflict=False
) -> ShowMergeStats:
    if canonical_id == duplicate_id:
        raise ShowMergeConflictError('Cannot merge a show into itself')

    locked = list(
        Show.objects.select_for_update().filter(id__in=[canonical_id, duplicate_id]).order_by('id')
    )
    shows = {show.id: show for show in locked}
    if set(shows) != {canonical_id, duplicate_id}:
        raise ShowMergeConflictError(f'Missing show for merge: {canonical_id} <- {duplicate_id}')

    canonical = shows[canonical_id]
    duplicate = shows[duplicate_id]
    stats = ShowMergeStats(canonical_id=canonical_id, duplicate_id=duplicate_id)

    _merge_show_fields(canonical, duplicate, allow_tmdb_conflict=allow_tmdb_conflict)
    canonical.countries.add(*duplicate.countries.all())
    canonical.genres.add(*duplicate.genres.all())
    _merge_crew(canonical_id, duplicate_id, stats)
    _merge_durations(canonical_id, duplicate_id, stats)
    _merge_histories(canonical_id, duplicate_id, stats)
    _merge_ratings(canonical_id, duplicate_id, stats)
    _merge_external_ratings(canonical_id, duplicate_id, stats)
    _merge_simple_relations(canonical_id, duplicate_id, stats)

    duplicate.delete()
    return stats
