import logging
import time
from datetime import timedelta

from django.db import OperationalError
from django.db.models import F, Q
from django.utils import timezone

from app.management.base import LoggableBaseCommand
from app.models import Country, ExternalRating, Genre, Person, Show, ShowCrew, ShowPoster
from app.services.poiskkino_client import PoiskkinoClient
from app.tasks import get_kp_mapping
from app.utils import normalize_country_name
from shared.constants import SHOW_STATUS_MAPPING

FREE_DAILY_REQUEST_LIMIT = 200
POISKKINO_BATCH_SIZE = 250
POISKKINO_REFRESH_DAYS = 3
DEADLOCK_RETRY_ATTEMPTS = 4


class Command(LoggableBaseCommand):
    help = (
        'Refreshes Poiskkino data for shows with a KinoPoisk ID. '
        'The oldest records are processed first.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Optional cap for shows in this run (default: 200 * 250).',
        )

    @staticmethod
    def _object_list(item, field_name):
        value = item.get(field_name) if isinstance(item, dict) else None
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]

    @staticmethod
    def _coerce_person_id(value):
        """Return a valid source person ID without making another API request."""
        if value in (None, ''):
            return None
        try:
            person_id = int(value)
        except (TypeError, ValueError):
            return None
        return person_id if person_id > 0 else None

    @staticmethod
    def _is_deadlock(error):
        cause = getattr(error, '__cause__', None)
        sqlstate = getattr(cause, 'sqlstate', None) or getattr(cause, 'pgcode', None)
        return sqlstate == '40P01' or 'deadlock detected' in str(error).lower()

    @classmethod
    def _with_deadlock_retry(cls, operation, description):
        """Retry an idempotent write when another catalog writer wins a race."""
        for attempt in range(DEADLOCK_RETRY_ATTEMPTS):
            try:
                return operation()
            except OperationalError as error:
                if not cls._is_deadlock(error) or attempt == DEADLOCK_RETRY_ATTEMPTS - 1:
                    raise

                delay = 0.5 * (2**attempt)
                logging.warning(
                    'Deadlock while %s; retrying in %.1fs (%s/%s).',
                    description,
                    delay,
                    attempt + 1,
                    DEADLOCK_RETRY_ATTEMPTS - 1,
                )
                time.sleep(delay)

    def handle(self, *args, **options):
        requested_limit = options.get('limit')
        selection_limit = FREE_DAILY_REQUEST_LIMIT * POISKKINO_BATCH_SIZE
        if requested_limit is not None:
            selection_limit = min(max(requested_limit, 0), selection_limit)

        now = timezone.now()
        stale_cutoff = now - timedelta(days=POISKKINO_REFRESH_DAYS)
        kp_mapping = get_kp_mapping()
        reverse_kp_mapping = {show_id: kp_id for kp_id, show_id in kp_mapping.items()}
        kp_show_ids = list(reverse_kp_mapping)
        freshness_filter = Q(poiskkino_updated_at__isnull=True) | Q(
            poiskkino_updated_at__lt=stale_cutoff
        )

        selected_ids = list(
            Show.objects.filter(id__in=kp_show_ids)
            .filter(freshness_filter)
            .order_by(F('poiskkino_updated_at').asc(nulls_first=True), 'id')
            .values_list('id', flat=True)[:selection_limit]
        )
        kp_ids = [reverse_kp_mapping[show_id] for show_id in selected_ids]

        logging.info(
            'Poiskkino refresh selection: %s shows with a KinoPoisk ID, '
            'cutoff=%s, request budget=%s.',
            len(selected_ids),
            stale_cutoff.isoformat(),
            FREE_DAILY_REQUEST_LIMIT,
        )

        if not kp_ids:
            logging.info('No Poiskkino records are older than three days.')
            return

        client = PoiskkinoClient()
        result = client.fetch_ratings_by_ids(
            kp_ids,
            max_requests=FREE_DAILY_REQUEST_LIMIT,
        )

        checked_show_ids = {
            kp_mapping[kp_id]
            for kp_id in result.checked_values
            if kp_id in kp_mapping
        }

        logging.info(
            'Poiskkino checked %s/%s IDs in %s requests; completed=%s.',
            len(result.checked_values),
            len(kp_ids),
            result.requests_made,
            result.completed,
        )

        if not result.data:
            if checked_show_ids:
                self._with_deadlock_retry(
                    lambda: Show.objects.filter(id__in=checked_show_ids).update(
                        poiskkino_updated_at=now,
                        kinopoisk_rating_available=False,
                        kinopoisk_rating=None,
                        kinopoisk_votes=None,
                    ),
                    'clearing empty Poiskkino ratings',
                )
            logging.info('Poiskkino returned no records for the selected IDs.')
            return

        unique_data = {
            item['id']: item for item in result.data if isinstance(item, dict) and item.get('id')
        }.values()
        data_list = list(unique_data)
        logging.info('Saving %s unique Poiskkino records.', len(data_list))

        # Start from the authoritative negative state. Returned items with a
        # rating set the flag back to True in _process_batch below.
        if checked_show_ids:
            self._with_deadlock_retry(
                lambda: Show.objects.filter(id__in=checked_show_ids).update(
                    kinopoisk_rating_available=False,
                    kinopoisk_rating=None,
                    kinopoisk_votes=None,
                ),
                'clearing stale Poiskkino ratings',
            )

        total_processed = 0
        for i in range(0, len(data_list), 1000):
            batch = data_list[i : i + 1000]
            self._with_deadlock_retry(
                lambda batch=batch: self._process_batch(batch, kp_mapping, now),
                'saving a Poiskkino batch',
            )
            total_processed += len(batch)
            logging.info('Saved batch %s/%s.', total_processed, len(data_list))

        if checked_show_ids:
            self._with_deadlock_retry(
                lambda: Show.objects.filter(id__in=checked_show_ids).update(
                    poiskkino_updated_at=now
                ),
                'marking Poiskkino records as refreshed',
            )
        logging.info('Successfully synchronized %s Poiskkino records.', total_processed)

    def _process_batch(self, batch_data, kp_mapping, now):
        data_map = {}
        for item in batch_data:
            kp_id = item.get('id')
            show_id = kp_mapping.get(kp_id)
            if show_id:
                data_map[show_id] = item

        if not data_map:
            return

        # Keep lock acquisition and write order deterministic across workers.
        # This substantially reduces the chance of two bulk updates waiting on
        # the same app_show rows in opposite orders.
        show_ids = sorted(data_map)
        existing_shows = (
            Show.objects.filter(id__in=show_ids).order_by('id').in_bulk(field_name='id')
        )

        all_genre_names = {
            genre_data['name']
            for item in data_map.values()
            for genre_data in self._object_list(item, 'genres')
            if genre_data.get('name')
        }
        all_country_names = {
            normalize_country_name(country_data['name'])
            for item in data_map.values()
            for country_data in self._object_list(item, 'countries')
            if country_data.get('name')
        }
        all_person_names = {
            person_data['name']
            for item in data_map.values()
            for person_data in self._object_list(item, 'persons')
            if person_data.get('name')
        }
        person_ids = {
            person_id
            for item in data_map.values()
            for person_data in self._object_list(item, 'persons')
            if (person_id := self._coerce_person_id(person_data.get('id'))) is not None
        }

        existing_genres = {
            genre.name: genre for genre in Genre.objects.filter(name__in=all_genre_names)
        }
        existing_countries = {
            country.name: country for country in Country.objects.filter(name__in=all_country_names)
        }
        persons_by_name = {
            person.name: person for person in Person.objects.filter(name__in=all_person_names)
        }
        persons_by_kp_id = {}
        if person_ids:
            # The source ID is the primary identity.  Existing duplicate rows
            # are allowed by policy, so choose a canonical row deterministically
            # when more than one local row already has the same source ID.
            existing_by_kp_id = Person.objects.filter(
                kinopoisk_person_id__in=person_ids
            ).order_by(F('master_person_id').asc(nulls_first=True), 'id')
            for person in existing_by_kp_id:
                persons_by_kp_id.setdefault(person.kinopoisk_person_id, person)

        new_genres = [Genre(name=name) for name in all_genre_names if name not in existing_genres]
        if new_genres:
            existing_genres.update(
                {
                    genre.name: genre
                    for genre in Genre.objects.bulk_create(new_genres, batch_size=500)
                }
            )

        new_countries = [
            Country(name=name) for name in all_country_names if name not in existing_countries
        ]
        if new_countries:
            existing_countries.update(
                {
                    country.name: country
                    for country in Country.objects.bulk_create(new_countries, batch_size=500)
                }
            )

        # Resolve every source person before creating anything.  This keeps a
        # single local row for one KP ID even when a batch contains name
        # variants for that person.
        pending_persons = {}
        resolved_persons = {}
        for show_id in show_ids:
            for person_index, person_data in enumerate(
                self._object_list(data_map[show_id], 'persons')
            ):
                person_name = person_data.get('name')
                if not person_name:
                    continue

                source_person_id = self._coerce_person_id(person_data.get('id'))
                person = (
                    persons_by_kp_id.get(source_person_id)
                    if source_person_id is not None
                    else None
                )

                if person is None:
                    person = persons_by_name.get(person_name)

                pending_key = (
                    ('kp', source_person_id)
                    if source_person_id is not None
                    else ('name', person_name)
                )
                if person is None:
                    person = pending_persons.get(pending_key)
                if person is None:
                    person = Person(
                        name=person_name,
                        kinopoisk_person_id=source_person_id,
                    )
                    pending_persons[pending_key] = person

                if source_person_id is not None:
                    persons_by_kp_id.setdefault(source_person_id, person)
                persons_by_name.setdefault(person_name, person)
                resolved_persons[(show_id, person_index)] = person

        if pending_persons:
            created_persons = Person.objects.bulk_create(
                list(pending_persons.values()), batch_size=500
            )
            for person in created_persons:
                if person.kinopoisk_person_id is not None:
                    persons_by_kp_id.setdefault(person.kinopoisk_person_id, person)
                persons_by_name.setdefault(person.name, person)

        shows_to_update = []
        shows_with_source_status = []
        ext_ratings_to_update = []
        posters_to_update = []
        crew_objects = []
        persons_to_update = {}

        for show_id in show_ids:
            item = data_map[show_id]
            show = existing_shows.get(show_id)
            if not show:
                continue

            rating_data = item.get('rating') or {}
            votes_data = item.get('votes') or {}
            updated_fields = []

            if kp_id := item.get('id'):
                kp_url = f'https://www.kinopoisk.ru/film/{kp_id}/'
                if not show.kinopoisk_url:
                    show.kinopoisk_url = kp_url
                    updated_fields.append('kinopoisk_url')

            if rating_data.get('kp') is not None:
                show.kinopoisk_rating = rating_data['kp']
                show.kinopoisk_rating_available = True
                updated_fields.append('kinopoisk_rating')
                updated_fields.append('kinopoisk_rating_available')
            if votes_data.get('kp') is not None:
                show.kinopoisk_votes = votes_data['kp']
                updated_fields.append('kinopoisk_votes')
            if item.get('year') is not None:
                show.year = item['year']
                updated_fields.append('year')
            if item.get('description'):
                show.plot = item['description']
                updated_fields.append('plot')
            if item.get('status'):
                show.status = SHOW_STATUS_MAPPING.get(item['status'], item['status'])
                updated_fields.append('status')
                shows_with_source_status.append(show)

            if updated_fields:
                shows_to_update.append(show)

            # IMDb fields are intentionally omitted: IMDb owns them now.
            ext_ratings_to_update.append(
                ExternalRating(
                    show_id=show_id,
                    kp=rating_data.get('kp'),
                    imdb=show.imdb_rating,
                    tmdb=rating_data.get('tmdb'),
                    film_critics=rating_data.get('filmCritics'),
                    russian_film_critics=rating_data.get('russianFilmCritics'),
                    await_rating=rating_data.get('await'),
                    updated_at=now,
                )
            )

            poster_url = self._extract_poster_url(item.get('poster'))
            if poster_url:
                posters_to_update.append(
                    ShowPoster(
                        show_id=show_id,
                        source=ShowPoster.SOURCE_KINOPOISK,
                        variant='main',
                        external_id=kp_id,
                        url=poster_url,
                    )
                )

            for genre_data in self._object_list(item, 'genres'):
                genre = existing_genres.get(genre_data.get('name'))
                if genre:
                    show.genres.add(genre)

            for country_data in self._object_list(item, 'countries'):
                country_name = normalize_country_name(country_data.get('name', ''))
                country = existing_countries.get(country_name)
                if country:
                    show.countries.add(country)

            for person_index, person_data in enumerate(self._object_list(item, 'persons')):
                person_name = person_data.get('name')
                person = resolved_persons.get((show_id, person_index))
                if not person_name or not person:
                    continue

                needs_update = False
                source_person_id = self._coerce_person_id(person_data.get('id'))
                if source_person_id is not None and person.kinopoisk_person_id is None:
                    person.kinopoisk_person_id = source_person_id
                    needs_update = True

                if person_data.get('enName') and person.en_name != person_data['enName']:
                    person.en_name = person_data['enName']
                    needs_update = True

                photo = person_data.get('photo')
                if (
                    photo
                    and not any(
                        marker in photo
                        for marker in ('iphone360_0.jpeg', 'no-poster', 'no-photo', 'avatar_empty')
                    )
                    and person.kp_photo_url != photo
                ):
                    person.kp_photo_url = photo
                    needs_update = True

                if needs_update:
                    persons_to_update[person.id] = person

                crew_objects.append(
                    ShowCrew(
                        show_id=show_id,
                        person_id=person.id,
                        profession=person_data.get('profession'),
                        en_profession=person_data.get('enProfession'),
                    )
                )

        if shows_to_update:
            Show.objects.bulk_update(
                shows_to_update,
                [
                    'kinopoisk_url',
                    'kinopoisk_rating',
                    'kinopoisk_votes',
                    'kinopoisk_rating_available',
                    'year',
                    'plot',
                ],
                batch_size=500,
            )

        # ``existing_shows`` is read before the rest of this batch is prepared.
        # Do not include its stale status value in a later bulk update when
        # Poiskkino omitted the field: a KinoPub details refresh may have
        # populated it in the meantime.
        if shows_with_source_status:
            Show.objects.bulk_update(
                shows_with_source_status,
                ['status'],
                batch_size=500,
            )

        if crew_objects:
            ShowCrew.objects.bulk_create(crew_objects, ignore_conflicts=True, batch_size=2000)

        if ext_ratings_to_update:
            ExternalRating.objects.bulk_create(
                ext_ratings_to_update,
                update_conflicts=True,
                unique_fields=['show_id'],
                update_fields=[
                    'kp',
                    'tmdb',
                    'film_critics',
                    'russian_film_critics',
                    'await_rating',
                    'updated_at',
                ],
                batch_size=500,
            )

        if posters_to_update:
            self._save_posters(posters_to_update, now)

        if persons_to_update:
            for person in persons_to_update.values():
                person.auto_resolve_kp_duplicate()
            Person.objects.bulk_update(
                persons_to_update.values(),
                ['en_name', 'kp_photo_url', 'kinopoisk_person_id', 'master_person'],
                batch_size=500,
            )

        logging.info('Successfully synchronized %s shows.', len(shows_to_update))

    @staticmethod
    def _save_posters(posters, now):
        """Save KP posters without letting an identity collision abort ratings."""
        if not posters:
            return

        show_ids = {poster.show_id for poster in posters}
        external_ids = {
            poster.external_id for poster in posters if poster.external_id is not None
        }
        existing = ShowPoster.objects.filter(source=ShowPoster.SOURCE_KINOPOISK).filter(
            Q(show_id__in=show_ids, variant='main') | Q(external_id__in=external_ids)
        )
        existing_by_variant = {(poster.show_id, poster.variant): poster for poster in existing}
        existing_by_external_id = {
            poster.external_id: poster
            for poster in existing
            if poster.external_id is not None
        }

        updates = []
        creates = []
        reserved_external_ids = set(existing_by_external_id)
        skipped = 0

        for poster in posters:
            current = existing_by_variant.get((poster.show_id, poster.variant))
            owner = existing_by_external_id.get(poster.external_id)

            # Keep the existing source identity. A poster collision must not
            # abort saving ratings and the rest of the Poiskkino payload.
            if owner is not None and owner.pk != getattr(current, 'pk', None):
                skipped += 1
                logging.warning(
                    'Skipping conflicting Kinopoisk poster: show=%s external_id=%s '
                    'already belongs to show=%s.',
                    poster.show_id,
                    poster.external_id,
                    owner.show_id,
                )
                continue

            if current is not None:
                current.external_id = poster.external_id
                current.url = poster.url
                current.updated_at = now
                updates.append(current)
                existing_by_external_id[poster.external_id] = current
                continue

            # Two records in one response can carry the same source ID. Keep
            # the first deterministic owner and avoid a batch conflict.
            if poster.external_id in reserved_external_ids:
                skipped += 1
                logging.warning(
                    'Skipping duplicate Kinopoisk poster in batch: show=%s external_id=%s.',
                    poster.show_id,
                    poster.external_id,
                )
                continue

            creates.append(poster)
            reserved_external_ids.add(poster.external_id)

        if updates:
            ShowPoster.objects.bulk_update(
                updates,
                ['external_id', 'url', 'updated_at'],
                batch_size=500,
            )
        if creates:
            ShowPoster.objects.bulk_create(creates, batch_size=500)
        if skipped:
            logging.warning('Skipped %s conflicting Kinopoisk poster writes.', skipped)

    @staticmethod
    def _extract_poster_url(value):
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            for key in ('url', 'original', 'big', 'medium', 'preview', 'src'):
                result = Command._extract_poster_url(value.get(key))
                if result:
                    return result
        return None
