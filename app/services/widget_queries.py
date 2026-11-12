"""Size-bounded data and personal actions for Telegram's in-message widgets."""

import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from app.models import Country, Genre, Person, Show, ShowDuration, UserRating, ViewHistory, ViewUser
from django.db.models import Avg, Count, Sum
from app.services.show_identity import normalize_show_type
from shared.constants import (
    GENRES_MAPPING,
    RAW_TO_NORMALIZED_COUNTRY,
    RAW_TO_NORMALIZED_GENRE,
    SHOW_STATUS_DISPLAY_RU,
    SHOW_TYPE_MAPPING,
)

MAX_ANSWER_BYTES = 1024
PAGE_SIZE = 12


def _episode_action(viewer, parts):
    """Apply a rating or a personal episode watched-state action."""
    if len(parts) not in (5, 6) or parts[0] not in {'v', 'w'}:
        return {'error': 'Некорректный запрос'}
    if not all(part.isdigit() for part in parts[1:4]):
        return {'error': 'Некорректный запрос'}
    show_id, season, episode = map(int, parts[1:4])
    if show_id < 1 or season < 0 or episode < 0 or bool(season) != bool(episode):
        return {'error': 'Некорректный запрос'}
    if season and not ShowDuration.objects.filter(
        show_id=show_id, season_number=season, episode_number=episode
    ).exists():
        return {'error': 'Эпизод не найден'}

    if parts[0] == 'w' and len(parts) == 6 and parts[4] == 'del' and parts[5].isdigit():
        record = ViewHistory.objects.filter(
            pk=int(parts[5]), show_id=show_id, season_number=season,
            episode_number=episode, users=viewer,
        ).first()
        if not record:
            return {'error': 'Просмотр не найден'}
        year = record.view_date.year if record.view_date else None
        record.users.remove(viewer)
        _invalidate_widget_stats(viewer, {year} if year else set())
        remains = ViewHistory.objects.filter(
            show_id=show_id, season_number=season, episode_number=episode, users=viewer
        ).order_by('-id').values('id', 'view_date', 'date_precision').first()
        return {
            'ok': True,
            'watched': bool(remains),
            'view': ({
                'id': remains['id'],
                'label': _view_label(remains['view_date'], remains['date_precision']),
            } if remains else None),
        }

    if parts[0] == 'v':
        if len(parts) != 5 or not parts[4].isdigit():
            return {'error': 'Некорректная оценка'}
        score = int(parts[4])
        if score == 0:
            UserRating.objects.filter(
                user=viewer, show_id=show_id,
                season_number=season or None, episode_number=episode or None,
            ).delete()
            years = set(
                ViewHistory.objects.filter(show_id=show_id, users=viewer)
                .exclude(view_date__isnull=True)
                .values_list('view_date__year', flat=True)
            )
            _invalidate_widget_stats(viewer, years)
            return {'ok': True, 'rating': None}
        rating = score / 2
        if not 1 <= rating <= 10:
            return {'error': 'Оценка должна быть от 1 до 10'}
        years = set(
            ViewHistory.objects.filter(show_id=show_id, users=viewer)
            .exclude(view_date__isnull=True)
            .values_list('view_date__year', flat=True)
        )
        UserRating.objects.update_or_create(
            user=viewer,
            show_id=show_id,
            season_number=season or None,
            episode_number=episode or None,
            defaults={'rating': rating},
        )
        _invalidate_widget_stats(viewer, years)
        return {'ok': True, 'rating': rating}

    # Old sent widgets may still issue w:id:season:episode:0|1.
    if len(parts) == 5 and parts[4] in {'0', '1'}:
        watched = parts[4] == '1'
        if not watched:
            records = ViewHistory.objects.filter(
                show_id=show_id, season_number=season, episode_number=episode, users=viewer
            )
            years = set(records.exclude(view_date__isnull=True).values_list('view_date__year', flat=True))
            records_list = list(records)
            for record in records_list:
                record.users.remove(viewer)
            if records_list:
                _invalidate_widget_stats(viewer, years)
            return {'ok': True, 'watched': False}
        precision, view_date = 'exact', timezone.localdate()
    else:
        if len(parts) != 6 or parts[4] not in {'exact', 'month', 'year', 'unknown'}:
            return {'error': 'Некорректная дата просмотра'}
        precision, date_value = parts[4], parts[5]
        if precision == 'exact' and len(date_value) == 8:
            view_date = datetime.strptime(date_value, '%Y%m%d').date()
        elif precision == 'month' and len(date_value) == 6:
            view_date = datetime.strptime(date_value, '%Y%m').date()
        elif precision == 'year' and len(date_value) == 4:
            view_date = datetime.strptime(date_value, '%Y').date()
        elif precision == 'unknown' and date_value == '0':
            view_date = None
        else:
            return {'error': 'Некорректная дата просмотра'}

    with transaction.atomic():
        record = ViewHistory.objects.filter(
            show_id=show_id,
            season_number=season,
            episode_number=episode,
            view_date=view_date,
        ).first()
        if record is None:
            record = ViewHistory.objects.create(
                show_id=show_id,
                season_number=season,
                episode_number=episode,
                view_date=view_date,
                date_precision=precision,
                is_checked=True,
                source=ViewHistory.SOURCE_MANUAL,
            )
        record.users.add(viewer)
        years = {view_date.year} if view_date else set()
        _invalidate_widget_stats(viewer, years)
    return {
        'ok': True,
        'watched': True,
        'date_precision': precision,
        'view': {
            'id': record.id,
            'label': _view_label(record.view_date, record.date_precision),
        },
    }

def _invalidate_widget_stats(viewer, years):
    for period in {*years, 'all', timezone.localdate().year}:
        cache.delete(f'user_stats_v6:{viewer.id}:{period}')
        cache.delete(f'group_stats_v6:{viewer.id}:{period}')


def _serialize(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def _view_label(view_date, precision):
    if view_date is None:
        return 'Дата неизвестна'
    return view_date.strftime({'month': '%m.%Y', 'year': '%Y'}.get(precision, '%d.%m.%Y'))


def _safe_external_url(value):
    if not value:
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {'http', 'https'} and parsed.netloc else None


def widget_query(telegram_id, command):
    """Handle catalog reads and explicit per-viewer actions from the widget.

    The bot supplies the viewer ID from Telegram's update, never from widget data.
    This endpoint intentionally offers no writes or personal history.
    """
    viewer = ViewUser.objects.filter(telegram_id=telegram_id).first()
    if not viewer:
        return {'error': 'Сначала откройте бота и нажмите Start'}
    if not isinstance(command, str) or len(command.encode('utf-8')) > 64:
        return {'error': 'Некорректный запрос'}
    if command == 't':
        return {'theme': viewer.webapp_theme}
    parts = command.split(':')
    if parts[0] in {'v', 'w'}:
        return _episode_action(viewer, parts)
    if (
        len(parts) == 3
        and parts[0] == 's'
        and parts[1].isdigit()
        and parts[2] in {'show', 'full'}
    ):
        show = (
            Show.objects.select_related('ext_rating')
            .prefetch_related('genres', 'countries')
            .get(pk=int(parts[1]))
        )
        local, _ = show.get_internal_rating_data()
        duration = sum(
            ShowDuration.objects.filter(show=show).values_list('duration_seconds', flat=True)
        )
        countries = {}
        source_countries = list(show.countries.all())
        normalized_names = {
            RAW_TO_NORMALIZED_COUNTRY.get(country.name, country.name)
            for country in source_countries
        }
        normalized_countries = {
            name: (pk, emoji)
            for name, pk, emoji in Country.objects.filter(name__in=normalized_names)
            .values_list('name', 'id', 'emoji_flag')
        }
        for country in source_countries:
            name = RAW_TO_NORMALIZED_COUNTRY.get(country.name, country.name)
            country_id, emoji = normalized_countries.get(
                name, (country.id, country.emoji_flag)
            )
            countries.setdefault(name, {'id': country_id, 'emoji': emoji or country.emoji_flag})
        genres = {}
        for genre in show.genres.all():
            name = RAW_TO_NORMALIZED_GENRE.get(genre.name, genre.name)
            genres.setdefault(name, genre.id)
        result = {
            'id': show.pk,
            'title': show.title[:80],
            'original': show.original_title[:80],
            'year': show.year,
            'type': normalize_show_type(show.type)[0],
            'status': show.status,
            'status_label': SHOW_STATUS_DISPLAY_RU.get(show.status, show.status),
            'plot': show.plot or '',
            'plot_truncated': False,
            'duration': duration,
            'kp': getattr(getattr(show, 'ext_rating', None), 'kp', None),
            'imdb': show.imdb_rating,
            'local': round(local, 1) if local is not None else None,
            'genres': [{'id': pk, 'name': name} for name, pk in list(genres.items())[:5]],
            'countries': [
                {'id': item['id'], 'name': name, **({'emoji': item['emoji']} if item['emoji'] else {})}
                for name, item in list(countries.items())[:5]
            ],
            'imdb_url': _safe_external_url(show.imdb_url),
            'kinopoisk_url': _safe_external_url(show.kinopoisk_url),
        }
        max_show_bytes = 2048 if parts[2] == 'full' else MAX_ANSWER_BYTES
        while len(_serialize(result).encode('utf-8')) > max_show_bytes and result['plot']:
            result['plot'] = result['plot'][:-20]
            result['plot_truncated'] = True
        return result
    if len(parts) == 3 and parts[0] == 's' and parts[1].isdigit() and parts[2] == 'crew':
        show = Show.objects.get(pk=int(parts[1]))
        groups = {}
        for row in show.showcrew_set.select_related('person__master_person'):
            name = row.normalized_profession or 'Другое'
            groups.setdefault(name, set()).add(row.person.canonical.pk)
        return {
            'title': 'Актёры и команда',
            'groups': [
                {'id': i, 'name': name[:25], 'count': len(ids)}
                for i, (name, ids) in enumerate(sorted(groups.items()))
            ][:12],
        }
    if len(parts) == 4 and parts[0] == 'p' and all(part.isdigit() for part in parts[1:]):
        show = Show.objects.get(pk=int(parts[1]))
        group_index, offset = int(parts[2]), int(parts[3])
        if offset > 10000:
            return {'error': 'Слишком большая страница'}
        groups = {}
        for row in show.showcrew_set.select_related('person__master_person'):
            name = row.normalized_profession or 'Другое'
            person = row.person.canonical
            groups.setdefault(name, {})[person.pk] = person.name
        categories = sorted(groups)
        if group_index >= len(categories):
            return {'error': 'Категория не найдена'}
        title = categories[group_index]
        # Keep the non-scrolling Telegram widget viewport from clipping long
        # crew names. Additional people remain available through pagination.
        people_page_size = 8
        rows = list(groups[title].items())[offset : offset + people_page_size + 1]
        result = {
            'title': title[:80],
            'items': [],
            'offset': offset,
            'more': len(rows) > people_page_size,
        }
        for pk, name in rows[:people_page_size]:
            result['items'].append([pk, name[:80]])
            if len(_serialize(result).encode('utf-8')) > 990:
                result['items'].pop()
                result['more'] = True
                break
        result['next'] = offset + len(result['items'])
        return result
    if len(parts) == 3 and parts[0] == 's' and parts[1].isdigit() and parts[2] == 'seasons':
        show_id = int(parts[1])
        if not Show.objects.filter(pk=show_id).exists():
            return {'error': 'Фильм не найден'}
        seasons = list(
            ShowDuration.objects.filter(show_id=show_id, season_number__gt=0, episode_number__gt=0)
            .values('season_number')
            .annotate(
                duration_seconds=Sum('duration_seconds'),
                episode_count=Count('id'),
            )
            .order_by('season_number')[:30]
        )
        ratings = dict(
            UserRating.objects.filter(user=viewer, show_id=show_id, season_number__gt=0)
            .values('season_number').annotate(score=Avg('rating'))
            .values_list('season_number', 'score')
        )
        return {
            'title': 'Сезоны',
            'seasons': [
                {
                    'number': row['season_number'],
                    'duration_seconds': row['duration_seconds'] or 0,
                    'episode_count': row['episode_count'],
                    'rating': ratings.get(row['season_number']),
                }
                for row in seasons
            ],
        }
    if (
        len(parts) == 4
        and parts[0] == 'e'
        and parts[1].isdigit()
        and re.fullmatch(r'\d+(?:\.0+)?', parts[2])
        and parts[3].isdigit()
    ):
        show_id, offset = int(parts[1]), int(parts[3])
        season = int(parts[2].split('.')[0])
        if offset > 10000 or season < 1:
            return {'error': 'Некорректный запрос'}
        episode_page_size = 12
        episodes = list(
            ShowDuration.objects.filter(show_id=show_id, season_number=season, episode_number__gt=0)
            .order_by('episode_number')
            .values('episode_number', 'duration_seconds')[offset : offset + episode_page_size + 1]
        )
        episode_numbers = [row['episode_number'] for row in episodes[:episode_page_size]]
        ratings = dict(
            UserRating.objects.filter(
                user=viewer,
                show_id=show_id,
                season_number=season,
                episode_number__in=episode_numbers,
            ).values_list('episode_number', 'rating')
        )
        views_by_episode = {}
        for view in ViewHistory.objects.filter(
                show_id=show_id,
                season_number=season,
                episode_number__in=episode_numbers,
                users=viewer,
            ).order_by('-id').values('id', 'episode_number', 'view_date', 'date_precision'):
            views_by_episode.setdefault(view['episode_number'], {
                'id': view['id'],
                'label': _view_label(view['view_date'], view['date_precision']),
            })
        for row in episodes[:episode_page_size]:
            row['season_number'] = season
            row['rating'] = ratings.get(row['episode_number'])
            row['view'] = views_by_episode.get(row['episode_number'])
            row['watched'] = bool(row['view'])
        return {
            'title': f'Сезон {season}',
            'items': episodes[:episode_page_size],
            'offset': offset,
            'next': offset + min(len(episodes), episode_page_size),
            'more': len(episodes) > episode_page_size,
        }
    if len(parts) == 3 and parts[0] == 'r' and parts[1].isdigit():
        show = Show.objects.select_related('ext_rating').get(pk=int(parts[1]))
        if parts[2] == 'all':
            external = getattr(show, 'ext_rating', None)
            local_value, local_users = show.get_internal_rating_data(current_user=viewer)
            kp_details = []
            if external and external.film_critics is not None:
                kp_details.append(f'Критики: {external.film_critics:g} / 10')
            if external and external.russian_film_critics is not None:
                kp_details.append(f'Российские критики: {external.russian_film_critics:g}%')
            if external and external.await_rating is not None:
                kp_details.append(f'Ожидание: {external.await_rating:g}%')
            if external and external.tmdb is not None:
                kp_details.append(f'TMDb: {external.tmdb:g} / 10')
            personal = UserRating.objects.filter(
                user=viewer, show=show, season_number__isnull=True, episode_number__isnull=True
            ).values_list('rating', flat=True).first()
            movie_view = None
            if normalize_show_type(show.type)[0] == 'Movie':
                row = ViewHistory.objects.filter(
                        show=show, season_number=0, episode_number=0, users=viewer,
                    ).order_by('-id').values('id', 'view_date', 'date_precision').first()
                if row:
                    movie_view = {
                        'id': row['id'],
                        'label': _view_label(row['view_date'], row['date_precision']),
                    }
            return {
                'title': 'Рейтинги',
                'ratings': [
                    [
                        'Кинопоиск', getattr(external, 'kp', None),
                        show.kinopoisk_votes or 0, ' · '.join(kp_details),
                        _safe_external_url(show.kinopoisk_url),
                    ],
                    [
                        'IMDb', show.imdb_rating, show.imdb_votes or 0, '',
                        _safe_external_url(show.imdb_url),
                    ],
                    ['Локальный', round(local_value, 1) if local_value is not None else None, len(local_users), ''],
                ],
                'personal': personal,
                'view': movie_view,
            }
        if parts[2] == 'kp':
            rating = getattr(show, 'ext_rating', None)
            details = []
            if rating and rating.film_critics is not None:
                details.append(f'Критики: {rating.film_critics:g} / 10')
            if rating and rating.russian_film_critics is not None:
                details.append(f'Российские критики: {rating.russian_film_critics:g}%')
            if rating and rating.await_rating is not None:
                details.append(f'Ожидание: {rating.await_rating:g}%')
            if rating and rating.tmdb is not None:
                details.append(f'TMDb: {rating.tmdb:g} / 10')
            return {
                'title': 'Кинопоиск',
                'value': getattr(rating, 'kp', None),
                'votes': show.kinopoisk_votes,
                'details': details,
            }
        if parts[2] == 'imdb':
            return {'title': 'IMDb', 'value': show.imdb_rating, 'votes': show.imdb_votes}
        if parts[2] == 'local':
            value, users = show.get_internal_rating_data(current_user=viewer)
            details = [f'{item["label"][:35]}: {item["rating"]:.1f}' for item in users[:6]]
            return {
                'title': 'Локальный рейтинг',
                'value': round(value, 1) if value is not None else None,
                'votes': len(users),
                'details': details,
            }
        return {'error': 'Неизвестный рейтинг'}
    if len(parts) != 4 or parts[0] != 'c' or not parts[3].isdigit():
        return {'error': 'Некорректный запрос'}
    _, kind, identifier, offset_str = parts
    offset = int(offset_str)
    if offset > 10000:
        return {'error': 'Слишком большая страница'}
    shows = Show.objects.all()
    if kind == 'type' and re.fullmatch(r'[A-Za-z]{1,24}', identifier):
        normalized, _ = normalize_show_type(identifier)
        types = {identifier, normalized}
        types.update(k.value for k, v in SHOW_TYPE_MAPPING.items() if v == normalized)
        shows = shows.filter(type__in=types)
        title = (
            'Фильмы'
            if normalized == 'Movie'
            else 'Сериалы'
            if normalized == 'Series'
            else normalized
        )
    elif kind == 'year' and identifier.isdigit() and 1870 <= int(identifier) <= 2200:
        shows, title = shows.filter(year=int(identifier)), identifier
    elif kind == 'status' and identifier in SHOW_STATUS_DISPLAY_RU:
        shows, title = shows.filter(status=identifier), SHOW_STATUS_DISPLAY_RU[identifier]
    elif kind == 'person' and identifier.isdigit():
        person = Person.objects.select_related('master_person').get(pk=int(identifier)).canonical
        ids = [person.pk, *person.aliases.values_list('id', flat=True)]
        shows, title = shows.filter(showcrew__person_id__in=ids), person.name
    elif kind == 'genre' and identifier.isdigit():
        genre = Genre.objects.get(pk=int(identifier))
        title = RAW_TO_NORMALIZED_GENRE.get(genre.name, genre.name)
        shows = shows.filter(genres__name__in=GENRES_MAPPING.get(title, [genre.name]))
    elif kind == 'country' and identifier.isdigit():
        country = Country.objects.get(pk=int(identifier))
        shows, title = shows.filter(countries=country), country.name
    else:
        return {'error': 'Неизвестный раздел'}
    rows = list(
        shows.order_by('-year', '-id')
        .distinct()
        .values('id', 'title', 'year')[offset : offset + PAGE_SIZE + 1]
    )
    result = {'title': title[:80], 'items': [], 'offset': offset, 'more': len(rows) > PAGE_SIZE}
    for row in rows[:PAGE_SIZE]:
        item = [row['id'], row['title'][:80], row['year']]
        result['items'].append(item)
        if len(_serialize(result).encode('utf-8')) > MAX_ANSWER_BYTES - 34:
            result['items'].pop()
            result['more'] = True
            break
    result['next'] = offset + len(result['items'])
    return result
