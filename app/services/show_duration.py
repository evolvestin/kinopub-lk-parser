from django.db import transaction

from app.models import Show, ShowDuration


def upsert_show_duration(
    show: Show,
    season_number: int | None,
    episode_number: int | None,
    duration_seconds: int,
    is_estimated: bool,
    preserve_exact: bool = False,
) -> ShowDuration | None:
    """Create/update one duration and remove legacy duplicates for its key."""
    with transaction.atomic():
        # Lock the parent row because a missing duration row cannot be locked.
        Show.objects.select_for_update().get(pk=show.pk)
        matching = ShowDuration.objects.filter(
            show_id=show.pk,
            season_number=season_number,
            episode_number=episode_number,
        ).order_by('is_estimated', '-updated_at', '-id')

        if preserve_exact and matching.filter(is_estimated=False).exists():
            return None

        duration = matching.first()
        if duration is None:
            return ShowDuration.objects.create(
                show_id=show.pk,
                season_number=season_number,
                episode_number=episode_number,
                duration_seconds=duration_seconds,
                is_estimated=is_estimated,
            )

        ShowDuration.objects.filter(pk__in=matching.exclude(pk=duration.pk)).delete()
        duration.duration_seconds = duration_seconds
        duration.is_estimated = is_estimated
        duration.save(update_fields=['duration_seconds', 'is_estimated', 'updated_at'])
        return duration
