import logging

from django.db import connection, transaction
from django.utils import timezone

from app.models import Person, RejectedPersonPhoto
from app.services.metrics import invalidate_duplicate_photo_urls_cache
from app.utils import get_original_image_url

logger = logging.getLogger(__name__)


@transaction.atomic
def quarantine_tmdb_photo_conflicts(person_id: int) -> int:
    """Clear a shared TMDB photo from the person whose identity is unresolved.

    The indexed exact-URL lookup keeps this inexpensive on the production
    catalogue. A transaction-scoped advisory lock serializes writers for the
    same image so simultaneous imports cannot both miss each other's row.
    Confirmed TMDB identities are never cleared or merged by this helper.
    """
    photo_url = (
        Person.objects.filter(pk=person_id, master_person__isnull=True)
        .values_list('tmdb_photo_url', flat=True)
        .first()
    )
    if not photo_url:
        return 0

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))',
            [photo_url],
        )

    person = (
        Person.objects.select_for_update()
        .filter(pk=person_id, master_person__isnull=True)
        .first()
    )
    if not person or person.tmdb_photo_url != photo_url:
        return 0

    matching_people = Person.objects.filter(
        master_person__isnull=True,
        tmdb_photo_url=photo_url,
    ).exclude(pk=person_id)

    if person.tmdb_id is None:
        if not matching_people.filter(tmdb_id__isnull=False).exists():
            return 0
        unresolved_people = [person]
    else:
        unresolved_people = list(
            matching_people.filter(tmdb_id__isnull=True)
            .order_by('id')
            .select_for_update()
        )

    if not unresolved_people:
        return 0

    rejected_url = get_original_image_url(photo_url)
    if rejected_url:
        RejectedPersonPhoto.objects.bulk_create(
            [
                RejectedPersonPhoto(person_id=row.id, photo_url=rejected_url)
                for row in unresolved_people
            ],
            ignore_conflicts=True,
        )

    person_ids = [row.id for row in unresolved_people]
    updated = Person.objects.filter(
        pk__in=person_ids,
        master_person__isnull=True,
        tmdb_id__isnull=True,
        tmdb_photo_url=photo_url,
    ).update(
        tmdb_photo_url=None,
        is_photo_fetched=False,
        updated_at=timezone.now(),
    )

    if updated:
        transaction.on_commit(invalidate_duplicate_photo_urls_cache)
        logger.info(
            'Quarantined shared TMDB photo for %d unresolved Person row(s); '
            'confirmed TMDB identity=%s.',
            updated,
            person.tmdb_id,
        )
    return updated
