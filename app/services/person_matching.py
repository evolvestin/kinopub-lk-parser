"""Helpers for matching imported people without creating avoidable aliases."""

from django.db.models import Value
from django.db.models.functions import Lower, Replace, Trim

from app.models import Person


def normalize_person_name(value):
    """Normalize a name for conservative matching (including Russian ё/е)."""
    if not value:
        return ''
    return (
        ' '.join(value.replace('\xa0', ' ').split())
        .strip()
        .lower()
        .replace('ё', 'е')
        .replace('э', 'е')
    )


def _normalized_field(field_name):
    expression = Lower(Trim(field_name))
    expression = Replace(Replace(expression, Value('ё'), Value('е')), Value('Ё'), Value('Е'))
    return Replace(Replace(expression, Value('э'), Value('е')), Value('Э'), Value('Е'))


def _canonical_people_queryset(name, en_name=None):
    queryset = Person.objects.filter(master_person__isnull=True).annotate(
        normalized_name=_normalized_field('name'),
        normalized_en_name=_normalized_field('en_name'),
    )
    queryset = queryset.filter(normalized_name=normalize_person_name(name))
    if en_name:
        queryset = queryset.filter(normalized_en_name=normalize_person_name(en_name))
    return queryset


def find_person_for_tmdb(*, name, en_name=None, tmdb_id=None, show=None):
    """Find an existing canonical Person for a TMDB credit.

    A TMDB ID is authoritative. A local record without a TMDB ID may be reused
    only when the normalized names identify one unambiguous candidate; a show
    already shared with that candidate is preferred and disambiguates common
    names. Records carrying another TMDB ID are never reused.
    """
    if tmdb_id:
        person = Person.objects.filter(tmdb_id=tmdb_id).select_related('master_person').first()
        if person:
            # The TMDB row is the authoritative identity.  Returning its
            # canonical parent here can lose the ID when an older/partially
            # merged alias still owns it, and the caller would then try to
            # assign the same unique ID to the parent.
            return person

    candidates = _canonical_people_queryset(name, en_name).filter(tmdb_id__isnull=True)
    if show is not None:
        shared = candidates.filter(showcrew__show=show).distinct()
        if shared.count() == 1:
            return shared.first()

    if candidates.count() == 1:
        return candidates.first()
    return None


def find_person_for_kinopub(*, name, show=None):
    """Find a canonical Person for a KinoPub-only credit when unambiguous."""
    candidates = _canonical_people_queryset(name)
    if show is not None:
        shared = candidates.filter(showcrew__show=show).distinct()
        if shared.count() == 1:
            return shared.first()
    return candidates.first() if candidates.count() == 1 else None
