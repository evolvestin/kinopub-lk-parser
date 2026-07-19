import functools
import hashlib
import json
import logging
import random
import urllib.parse
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Avg, F, Max, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from redis import Redis
from django.db.models import Sum

from app.admin_site import admin_site
from app.models import (
    CasinoSpin,
    Country,
    ExternalRating,
    Genre,
    LogEntry,
    Person,
    SharedStat,
    Show,
    ShowCrew,
    ShowDuration,
    TelegramLog,
    UserRating,
    ViewHistory,
    ViewUser,
    ViewUserGroup,
    WishlistFolder,
    WishlistItem,
)
from app.services.metrics import (
    get_active_countries_list,
    get_duplicate_photo_urls_list,
    get_global_metrics_history,
    get_missing_country_meta_list,
    get_missing_durations_list,
    get_missing_imdb_list,
    get_missing_kp_list,
    get_missing_plot_list,
    get_missing_status_list,
    get_missing_year_list,
    get_no_countries_list,
    get_no_genres_list,
    get_title_collision_list,
    get_total_genres_list,
    get_unmapped_genres_list,
    get_unused_countries_list,
)
from app.services.stats_calculator import (
    generate_global_stats,
    generate_group_stats,
    generate_user_stats,
)
from app.services.telegram_auth import validate_telegram_init_data
from app.tasks import send_view_confirmation_task
from app.telegram_bot import TelegramSender
from shared.constants import (
    GENRES_MAPPING,
    PROFESSIONS_PLURAL_MAP_RU,
    RAW_TO_NORMALIZED_COUNTRY,
    RAW_TO_NORMALIZED_GENRE,
    RAW_TO_NORMALIZED_RU,
    SHOW_STATUS_DISPLAY_RU,
    SHOW_TYPE_DISPLAY_RU,
    UserRole,
)
from shared.formatters import format_precision_date, format_se
from shared.media import get_poster_url

logger = logging.getLogger('app')


def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def _toggle_user_in_view(user, view_id):
    """Вспомогательная функция для переключения участия пользователя в просмотре."""
    view_history = ViewHistory.objects.get(id=view_id)

    if user in view_history.users.all():
        view_history.users.remove(user)
        action = 'removed'
    else:
        view_history.users.add(user)
        action = 'added'

    TelegramSender().update_history_message(view_history)
    return action


def _get_user_ratings_for_shows(user, show_ids):
    """Возвращает маппинг {show_id: rating} для оценок пользователя (среднее по всем оценкам)."""
    if not user or not show_ids:
        return {}

    ratings = (
        UserRating.objects.filter(user=user, show_id__in=show_ids)
        .values('show_id')
        .annotate(avg_rating=Avg('rating'))
    )

    return {r['show_id']: round(r['avg_rating'], 1) for r in ratings}


def _serialize_show_details(show, user=None):
    """Собирает словарь с данными о шоу и рейтингами."""
    internal_rating, user_ratings = show.get_internal_rating_data()
    personal_rating = None
    personal_episodes_count = 0

    # Определяем ID пользователей, которых текущий пользователь имеет право видеть
    visible_ids = set()
    if user:
        visible_ids.add(user.id)
        if user.role != UserRole.GUEST:
            # Получаем ID всех сокомандников (участников тех же групп)
            mate_ids = ViewUser.objects.filter(groups__users=user).values_list('id', flat=True)
            visible_ids.update(mate_ids)

        personal_rating = UserRating.objects.filter(user=user, show=show).aggregate(
            avg=Avg('rating')
        )['avg']

        if personal_rating is not None:
            personal_rating = round(personal_rating, 1)

        personal_episodes_count = UserRating.objects.filter(
            user=user, show=show, season_number__isnull=False
        ).count()

    history_qs = (
        ViewHistory.objects.filter(show=show)
        .prefetch_related('users')
        .order_by(F('view_date').desc(nulls_last=True), '-id')
    )

    view_history_list = []
    last_message_id = None

    for h in history_qs:
        if not last_message_id and h.telegram_message_id:
            last_message_id = h.telegram_message_id

        # Фильтруем пользователей в записи истории согласно области видимости
        # Если запрашивает аноним (нет user), он не видит никого (или можно оставить базовую логику)
        if user:
            h_users = [u for u in h.users.all() if u.id in visible_ids]
        else:
            h_users = []

        if not h_users:
            continue

        view_history_list.append(
            {
                'id': h.id,
                'date': format_precision_date(h.view_date, h.date_precision),
                'season': h.season_number,
                'episode': h.episode_number,
                'users': [
                    f'@{u.username}' if u.username else u.name or str(u.telegram_id)
                    for u in h_users
                ],
                'message_id': h.telegram_message_id,
                'is_viewer': user in h.users.all() if user else False,
            }
        )

    normalized_countries = []
    for country in show.countries.all():
        norm_name = RAW_TO_NORMALIZED_COUNTRY.get(country.name, country.name)
        if norm_name != country.name:
            target = Country.objects.filter(name=norm_name).first()
            if target:
                normalized_countries.append(str(target))
                continue
        normalized_countries.append(str(country))
    normalized_countries = sorted(list(set(normalized_countries)))

    return {
        'id': show.id,
        'title': show.title,
        'original_title': show.original_title,
        'type': show.type,
        'year': show.year,
        'status': show.status,
        'kinopoisk_rating': show.kinopoisk_rating,
        'imdb_rating': show.imdb_rating,
        'countries': normalized_countries,
        'genres': show.display_genres,
        'kinopoisk_url': show.kinopoisk_url,
        'imdb_url': show.imdb_url,
        'internal_rating': internal_rating,
        'user_ratings': user_ratings,
        'personal_rating': personal_rating,
        'personal_episodes_count': personal_episodes_count,
        'channel_message_id': last_message_id,
        'view_history': view_history_list,
    }


def index(request):
    metrics_history = get_global_metrics_history()

    def _get_latest_date(qs, field):
        dt = qs.order_by(f'-{field}').values_list(field, flat=True).first()
        if dt:
            return timezone.localtime(dt).strftime('%d.%m.%Y %H:%M')
        return 'Никогда'

    last_parser_log = (
        LogEntry.objects.filter(message__contains='Parser session finished')
        .order_by('-created_at')
        .first()
    )

    last_actions = {
        'history': _get_latest_date(ViewHistory.objects.all(), 'created_at'),
        'parser_run': timezone.localtime(last_parser_log.created_at).strftime('%d.%m.%Y %H:%M')
        if last_parser_log
        else 'Никогда',
        'shows': _get_latest_date(Show.objects.all(), 'created_at'),
        'ratings': _get_latest_date(ExternalRating.objects.all(), 'updated_at'),
        'durations': _get_latest_date(ShowDuration.objects.all(), 'updated_at'),
        'photos': _get_latest_date(Person.objects.filter(is_photo_fetched=True), 'updated_at'),
        'tg': _get_latest_date(TelegramLog.objects.all(), 'created_at'),
    }

    cutoff_24h = timezone.now() - timedelta(days=1)
    errors_24h_count = LogEntry.objects.filter(
        created_at__gte=cutoff_24h, level__in=['ERROR', 'CRITICAL']
    ).count()

    bot_users_active = ViewUser.objects.filter(is_bot_active=True).count()
    bot_users_total = ViewUser.objects.count()

    context = {
        'last_actions': last_actions,
        'errors_24h_count': errors_24h_count,
        'bot_users_active': bot_users_active,
        'bot_users_total': bot_users_total,
        'metrics_json': json.dumps(metrics_history),
    }
    if request.user.is_staff:
        context['app_list'] = admin_site.get_app_list(request)
    return render(request, 'index.html', context)


def _check_token(request):
    """Проверяет наличие и корректность X-Bot-Token в заголовках."""
    expected_token = settings.BOT_TOKEN
    if not expected_token:
        return False
    return request.headers.get('X-Bot-Token') == expected_token


def protected_bot_api(func):
    """Декоратор для проверки токена и стандартной обработки ошибок."""

    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not _check_token(request):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        try:
            return func(request, *args, **kwargs)
        except ObjectDoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            logging.error(f'API Error in {func.__name__}: {e}')
            return JsonResponse({'error': str(e)}, status=400)

    return wrapper


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def check_bot_user(request, telegram_id):
    try:
        user = ViewUser.objects.get(telegram_id=telegram_id)
        return JsonResponse({'exists': True, 'role': user.role})
    except ViewUser.DoesNotExist:
        return JsonResponse({'exists': False, 'role': UserRole.GUEST})


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_toggle_claim(request):
    """
    Переключает участие пользователя в просмотре (добавляет или удаляет).
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        user = ViewUser.objects.get(telegram_id=telegram_id)
        action = _toggle_user_in_view(user, view_id)

        return JsonResponse({'status': 'ok', 'action': action})
    except (ViewUser.DoesNotExist, ViewHistory.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
@protected_bot_api
def register_bot_user(request):
    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')
    username = data.get('username')
    first_name = data.get('first_name', '')
    login_username = username if username else str(telegram_id)

    host = 'localhost'
    for origin in getattr(settings, 'CSRF_TRUSTED_ORIGINS', []):
        if 'localhost' not in origin and '127.0.0.1' not in origin:
            host = origin.replace('https://', '').replace('http://', '').split('/')[0]
            break
    email = f'{login_username}@{host}'

    view_user, created = ViewUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'username': username,
            'name': first_name,
            'language': data.get('language_code', 'ru'),
            'role': UserRole.GUEST,
            'is_bot_active': True,
        },
    )

    # Используем метод модели для обновления данных (DRY) и запоминаем изменения
    updated_fields = []
    if not created:
        updated_fields = view_user.update_personal_details(
            username=username,
            name=first_name,
            language=data.get('language_code', 'ru'),
            is_active=True,
        )

    django_user, user_created = User.objects.get_or_create(
        username=login_username,
        defaults={
            'email': email,
            'is_staff': False,
            'is_superuser': False,
            'first_name': first_name[:30],
        },
    )
    if user_created:
        django_user.set_password(str(uuid.uuid4()))
        django_user.save()

    if view_user.django_user != django_user:
        view_user.django_user = django_user
        view_user.save()

    sync_user_permissions(django_user, view_user.role)

    try:
        if created or not view_user.role_message_id:
            TelegramSender().send_user_role_message(view_user)
        elif updated_fields and ('username' in updated_fields or 'name' in updated_fields):
            TelegramSender().update_user_role_message(view_user)
    except Exception as e:
        logging.error(f'Role msg error for {telegram_id}: {e}')

    return JsonResponse(
        {'status': 'ok', 'created': created, 'role': view_user.role, 'user_id': view_user.id}
    )


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def set_bot_user_role(request):
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        new_role = data.get('role')
        message_id = data.get('message_id')

        view_user = ViewUser.objects.get(telegram_id=telegram_id)

        # Проверка актуальности сообщения (защита от нажатий на старые кнопки)
        if view_user.role_message_id and message_id:
            if int(view_user.role_message_id) != int(message_id):
                return JsonResponse(
                    {'status': 'error', 'message': 'Message outdated. Please refresh or resend.'},
                    status=409,
                )

        if new_role not in [r.value for r in UserRole]:
            return JsonResponse({'error': 'Invalid role'}, status=400)

        view_user.role = new_role
        view_user.save()

        if view_user.django_user:
            sync_user_permissions(view_user.django_user, new_role)

        try:
            TelegramSender().update_user_role_message(view_user)
        except Exception:
            pass

        if new_role != UserRole.GUEST:
            try:
                TelegramSender().send_role_upgrade_notification(view_user.telegram_id, new_role)
            except Exception as e:
                logging.error(f'Failed to send upgrade notification to {telegram_id}: {e}')

        return JsonResponse({'status': 'ok', 'new_role': new_role})
    except ViewUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def sync_user_permissions(user, role):
    """Назначает права Django пользователю на основе роли ViewUser."""
    # Очищаем группы и индивидуальные права перед назначением новых
    user.groups.clear()
    user.user_permissions.clear()

    if role == UserRole.ADMIN:
        user.is_staff = True
        user.is_superuser = True
    elif role == UserRole.VIEWER:
        user.is_staff = True
        user.is_superuser = False

        # Получаем права на просмотр (view_) для всех моделей приложения app
        permissions = Permission.objects.filter(
            content_type__app_label='app', codename__startswith='view_'
        )
        # Назначаем права напрямую, чтобы они отображались в окне "User permissions"
        user.user_permissions.set(permissions)
    else:
        # GUEST
        user.is_staff = False
        user.is_superuser = False

    user.save()


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def update_bot_user(request):
    """
    Обновляет персональные данные пользователя (имя, username, язык) и статус активности.
    Вызывается при любом взаимодействии с ботом.
    """
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')

        try:
            view_user = ViewUser.objects.get(telegram_id=telegram_id)
        except ViewUser.DoesNotExist:
            return JsonResponse({'status': 'skipped', 'reason': 'user_not_found'})

        # Используем метод модели для обновления данных (DRY)
        updated_fields = view_user.update_personal_details(
            username=data.get('username'),
            name=data.get('first_name', ''),
            language=data.get('language_code', 'en'),
            is_active=data.get('is_active'),
        )

        # Если изменилось имя/юзернейм, обновляем сообщение в админ-канале
        if updated_fields and ('username' in updated_fields or 'name' in updated_fields):
            try:
                TelegramSender().update_user_role_message(view_user)
            except Exception:
                pass

        return JsonResponse({'status': 'ok', 'updated': updated_fields})

    except Exception as e:
        logging.error(f'Update user error: {e}')
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def bot_search_shows(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    shows = (
        Show.objects.filter(Q(title__icontains=query) | Q(original_title__icontains=query))
        .prefetch_related('countries', 'genres', 'ratings__user')
        .distinct()[:20]
    )

    user = None
    if telegram_id := request.GET.get('telegram_id'):
        user = ViewUser.objects.filter(telegram_id=telegram_id).first()

    show_ids = [s.id for s in shows]
    user_ratings = _get_user_ratings_for_shows(user, show_ids)

    results = []
    for show in shows:
        poster_url = get_poster_url(show.id)
        internal_rating, user_ratings_list = show.get_internal_rating_data()

        results.append(
            {
                'id': show.id,
                'title': show.title,
                'original_title': show.original_title,
                'year': show.year,
                'type': show.type,
                'status': show.status,
                'poster_url': poster_url,
                'imdb_rating': show.imdb_rating,
                'kinopoisk_rating': show.kinopoisk_rating,
                'imdb_url': show.imdb_url,
                'kinopoisk_url': show.kinopoisk_url,
                'countries': [str(c) for c in show.countries.all()[:3]],
                'genres': show.display_genres[:3],
                'internal_rating': internal_rating,
                'user_ratings': user_ratings_list,
                'user_rating': user_ratings.get(show.id),
            }
        )

    return JsonResponse({'results': results})


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def bot_get_show_details(request, show_id):
    try:
        show = Show.objects.prefetch_related('countries', 'genres').get(id=show_id)
        user = None
        if telegram_id := request.GET.get('telegram_id'):
            try:
                user = ViewUser.objects.get(telegram_id=telegram_id)
            except ViewUser.DoesNotExist:
                pass

        data = _serialize_show_details(show, user)
        return JsonResponse(data)
    except Show.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def bot_get_by_imdb(request, imdb_id):
    try:
        show = (
            Show.objects.filter(imdb_url__icontains=f'tt{imdb_id}')
            .prefetch_related('countries', 'genres')
            .first()
        )

        if not show:
            return JsonResponse({'error': 'Not found'}, status=404)

        data = {
            'id': show.id,
            'title': show.title,
            'original_title': show.original_title,
            'type': show.type,
            'year': show.year,
            'status': show.status,
            'kinopoisk_rating': show.kinopoisk_rating,
            'imdb_rating': show.imdb_rating,
            'countries': [str(c) for c in show.countries.all()],
            'genres': [g.name for g in show.genres.all()],
            'kinopoisk_url': show.kinopoisk_url,
            'imdb_url': show.imdb_url,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def _manage_view_assignment(request, action):
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        user = ViewUser.objects.get(telegram_id=telegram_id)
        view_history = ViewHistory.objects.get(id=view_id)

        if action == 'add':
            view_history.users.add(user)
            TelegramSender().update_history_message(view_history)

            show_title = view_history.show.title or view_history.show.original_title
            info = show_title
            if view_history.season_number:
                info += f' ({format_se(view_history.season_number, view_history.episode_number)})'
            return JsonResponse({'status': 'ok', 'info': info})
        elif action == 'remove':
            view_history.users.remove(user)
            TelegramSender().update_history_message(view_history)

            return JsonResponse({'status': 'ok'})

    except (ViewUser.DoesNotExist, ViewHistory.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        logging.error(f'Error in _manage_view_assignment ({action}): {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_assign_view(request):
    return _manage_view_assignment(request, 'add')


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_unassign_view(request):
    return _manage_view_assignment(request, 'remove')


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_toggle_view_check(request):
    try:
        data = json.loads(request.body)
        view_id = data.get('view_id')
        telegram_id = data.get('telegram_id')

        view = ViewHistory.objects.get(id=view_id)

        if telegram_id:
            try:
                user = ViewUser.objects.get(telegram_id=telegram_id)
                if user.role == UserRole.VIEWER:
                    if not view.users.filter(id=user.id).exists():
                        return JsonResponse(
                            {
                                'status': 'error',
                                'error': 'Вы должны быть в списке зрителей, чтобы менять статус.',
                            }
                        )
                elif user.role != UserRole.ADMIN:
                    return JsonResponse({'status': 'error', 'error': 'Недостаточно прав.'})
            except ViewUser.DoesNotExist:
                return JsonResponse({'status': 'error', 'error': 'Пользователь не найден.'})

        view.is_checked = not view.is_checked
        view.save(update_fields=['is_checked'])

        TelegramSender().update_history_message(view)

        status_text = 'учтен' if view.is_checked else 'не учтен'
        message = f'Просмотр теперь {status_text}.'

        if not view.is_checked:
            current_user_ids = set(view.users.values_list('id', flat=True))

            candidates = (
                ViewHistory.objects.filter(
                    show=view.show,
                    season_number=view.season_number,
                    episode_number=view.episode_number,
                    is_checked=False,
                )
                .exclude(id=view.id)
                .order_by(F('view_date').desc(nulls_last=True), '-id')
            )

            for candidate in candidates:
                candidate_user_ids = set(candidate.users.values_list('id', flat=True))
                if candidate_user_ids == current_user_ids:
                    candidate.is_checked = True
                    candidate.save(update_fields=['is_checked'])
                    TelegramSender().update_history_message(candidate)
                    message += ' Восстановлен статус просмотра.'
                    break

        return JsonResponse({'status': 'ok', 'message': message, 'is_checked': view.is_checked})

    except ViewHistory.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_toggle_view_user(request):
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        user, _ = ViewUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'name': str(telegram_id),
                'role': UserRole.GUEST,
                'is_bot_active': True,
            },
        )

        action = _toggle_user_in_view(user, view_id)

        return JsonResponse({'status': 'ok', 'action': action})
    except ViewHistory.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_rate_show(request):
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        show_id = data.get('show_id')
        rating = float(data.get('rating'))
        season = data.get('season')
        episode = data.get('episode')

        user = ViewUser.objects.get(telegram_id=telegram_id)
        show = Show.objects.get(id=show_id)

        UserRating.objects.update_or_create(
            user=user,
            show=show,
            season_number=season,
            episode_number=episode,
            defaults={'rating': rating},
        )

        history_qs = ViewHistory.objects.filter(
            show=show,
            season_number=season or 0,
            episode_number=episode or 0,
            users=user,
            telegram_message_id__isnull=False,
        )

        sender = TelegramSender()
        for history_item in history_qs:
            sender.update_history_message(history_item)

        return JsonResponse({'status': 'ok', 'rating': rating})

    except (ViewUser.DoesNotExist, Show.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def bot_get_show_episodes(request, show_id):
    try:
        telegram_id = request.GET.get('telegram_id')
        user_ratings_map = {}

        if telegram_id:
            try:
                user = ViewUser.objects.get(telegram_id=telegram_id)
                ratings = UserRating.objects.filter(user=user, show_id=show_id)
                for rating_entry in ratings:
                    season_number = rating_entry.season_number
                    episode_number = rating_entry.episode_number
                    if season_number and episode_number:
                        user_ratings_map[(season_number, episode_number)] = rating_entry.rating
            except ViewUser.DoesNotExist:
                pass

        durations = (
            ShowDuration.objects.filter(
                show_id=show_id,
                season_number__isnull=False,
                season_number__gt=0,
                episode_number__isnull=False,
                episode_number__gt=0,
            )
            .values('season_number', 'episode_number')
            .order_by('season_number', 'episode_number')
        )

        result = []
        for duration_data in durations:
            season_number = duration_data['season_number']
            episode_number = duration_data['episode_number']
            item = {'season_number': season_number, 'episode_number': episode_number}

            if (season_number, episode_number) in user_ratings_map:
                item['rating'] = user_ratings_map[(season_number, episode_number)]
            result.append(item)

        return JsonResponse({'episodes': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def bot_get_show_ratings_details(request, show_id):
    try:
        ratings = (
            UserRating.objects.filter(show_id=show_id)
            .select_related('user')
            .order_by('user__name', 'season_number', 'episode_number')
        )

        if not ratings.exists():
            return JsonResponse({'ratings': []})

        grouped_data = {}

        for r in ratings:
            uid = r.user.id
            if uid not in grouped_data:
                user_label = r.user.username if r.user.username else r.user.name
                grouped_data[uid] = {
                    'user': f'@{user_label}' if r.user.username else user_label,
                    'show_rating': None,
                    'episodes': [],
                }

            if r.season_number is None and r.episode_number is None:
                grouped_data[uid]['show_rating'] = r.rating
            else:
                grouped_data[uid]['episodes'].append(
                    {
                        'season': r.season_number,
                        'episode': r.episode_number,
                        'rating': r.rating,
                    }
                )

        result = list(grouped_data.values())
        return JsonResponse({'ratings': result})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_log_message(request):
    try:
        data = json.loads(request.body)
        # Сохраняем весь пришедший JSON (включая direction, chat_id, message_id) в поле raw_data
        TelegramLog.objects.create(raw_data=data)
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_create_log_entry(request):
    try:
        data = json.loads(request.body)
        level = data.get('level', 'INFO')
        module = data.get('module', 'bot')
        message = data.get('message', '')

        traceback_str = data.get('traceback', None)

        if not module.startswith('bot.'):
            module = f'bot.{module}'

        LogEntry.objects.create(
            level=level[:10],
            module=module[:100],
            message=message,
            traceback=traceback_str,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        if level in ('ERROR', 'CRITICAL'):
            TelegramSender().send_dev_log(level, module, message, traceback_str)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['GET'])
def bot_get_user_groups(request):
    telegram_id = request.GET.get('telegram_id')
    try:
        user = ViewUser.objects.get(telegram_id=telegram_id)
        groups = user.groups.all()
        results = [{'id': g.id, 'name': g.name} for g in groups]
        return JsonResponse({'groups': results})
    except ViewUser.DoesNotExist:
        return JsonResponse({'groups': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@protected_bot_api
@require_http_methods(['POST'])
def bot_assign_group_view(request):
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')
        group_id = data.get('group_id')

        # Проверяем права пользователя (должен быть в группе)
        user = ViewUser.objects.get(telegram_id=telegram_id)
        group = ViewUserGroup.objects.get(id=group_id)

        if user not in group.users.all():
            return JsonResponse({'status': 'error', 'error': 'User not in group'}, status=403)

        view_history = ViewHistory.objects.get(id=view_id)

        group_users = group.users.all()
        added_count = 0
        for group_member in group_users:
            if not view_history.users.filter(id=group_member.id).exists():
                view_history.users.add(group_member)
                added_count += 1

        if added_count > 0:
            TelegramSender().update_history_message(view_history)

        return JsonResponse({'status': 'ok', 'added_count': added_count, 'group_name': group.name})

    except (ViewUser.DoesNotExist, ViewUserGroup.DoesNotExist, ViewHistory.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def webapp_index(request):
    view_user = get_webapp_user(request)
    user_role = view_user.role if view_user else 'guest'
    context = {
        'is_debug': settings.ENVIRONMENT == 'DEV',
        'user_role': user_role,
    }
    return render(request, 'webapp/stats.html', context)


def get_webapp_user(request) -> ViewUser | None:
    init_data = None
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            init_data = body.get('init_data')
        except Exception:
            pass
    if not init_data:
        init_data = request.GET.get('init_data')

    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        if token and token != 'null' and token != 'undefined':
            init_data = token

    if init_data:
        tg_user = validate_telegram_init_data(init_data)
        if tg_user:
            user, _ = ViewUser.objects.get_or_create(
                telegram_id=tg_user.get('id'),
                defaults={
                    'username': tg_user.get('username'),
                    'name': tg_user.get('first_name', ''),
                    'language': tg_user.get('language_code', 'ru'),
                    'role': UserRole.GUEST,
                },
            )
            return user

    if settings.DEBUG:
        mock_user = ViewUser.objects.filter(role=UserRole.ADMIN).first()
        if not mock_user:
            mock_user = ViewUser.objects.create(
                telegram_id=999999,
                username='dev_admin',
                name='Dev Admin',
                role=UserRole.ADMIN,
            )
        return mock_user

    return None


@csrf_exempt
@require_http_methods(['POST'])
def webapp_get_stats(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        current_year = timezone.now().year
        stats = generate_user_stats(view_user, year=current_year)
        return JsonResponse(stats)

    except Exception as e:
        logger.error(f'WebApp Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_get_detailed_stats(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        period_value = body.get('period_value') or body.get('year')

        if period_value in (0, '0', 'all', None):
            year = None
        else:
            year = str(period_value).split('-')[0]

        view_user.update_personal_details(
            username=view_user.username,
            name=view_user.name,
            language=view_user.language,
            photo_url=view_user.photo_url,
            screen_width=body.get('screen_width'),
            screen_height=body.get('screen_height'),
        )

        stats = generate_user_stats(view_user, year=year)

        group_stats = generate_group_stats(view_user, year=year)
        if group_stats:
            stats['group'] = group_stats

        return JsonResponse(stats)

    except Exception as e:
        logger.error(f'WebApp Stats Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_bake_stats(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        config = body.get('config', {})
        years = config.get('years', [])
        anon_user = config.get('anon_user', False)
        include_group = config.get('include_group', True)
        anon_group = config.get('anon_group', False)

        if not years:
            years = ['all']

        baked_data = {}
        for yr in years:
            year_val = None if yr == 'all' else yr
            stat = generate_user_stats(view_user, year=year_val)
            stat = json.loads(json.dumps(stat))

            user_info_map = {}
            group_exists = False

            if include_group:
                group_stats = generate_group_stats(view_user, year=year_val)
                if group_stats:
                    group_exists = True
                    group_stats = json.loads(json.dumps(group_stats))

                    if anon_group:
                        group_stats['group_name'] = 'Группа'

                    for idx, member in enumerate(group_stats['members'], 1):
                        mid = member.get('id')
                        is_me = mid == view_user.id

                        should_hide = False
                        if is_me and anon_user:
                            should_hide = True
                        elif not is_me and anon_group:
                            should_hide = True

                        display_name = f'Участник {idx}' if should_hide else member['name']
                        display_photo = None if should_hide else member.get('photo_url')

                        user_info_map[mid] = {
                            'id': idx,
                            'name': display_name,
                            'photo': display_photo,
                        }
                        member['id'] = idx
                        member['name'] = display_name
                        member['photo_url'] = display_photo

                    stat['group'] = group_stats

            if view_user.id not in user_info_map:
                if anon_user:
                    name = 'Аноним'
                    uid = 1 if group_exists else 0
                else:
                    name = view_user.name or view_user.username
                    uid = 1 if group_exists else 0

                user_info_map[view_user.id] = {
                    'id': uid,
                    'name': name,
                    'photo': None if anon_user else view_user.photo_url,
                }

            history_pools = [stat]
            if 'group' in stat:
                history_pools.append(stat['group'])

            for pool in history_pools:
                for h_type in ['history_movies', 'history_episodes']:
                    if h_type not in pool:
                        continue
                    for item in pool[h_type]:
                        mapped_users = []
                        for uid in item.get('user_ids', []):
                            info = user_info_map.get(uid)
                            if info:
                                mapped_users.append(info)
                            else:
                                mapped_users.append({'id': 0, 'name': 'Участник', 'photo': None})
                        mapped_users.sort(key=lambda x: x['id'])
                        item['user_ids'] = [u['id'] for u in mapped_users]
                        item['user_names'] = [u['name'] for u in mapped_users]
                        item['user_photos'] = [u['photo'] for u in mapped_users]

            if anon_user:
                stat['meta']['name'] = 'Аноним'
                stat['meta']['is_anonymous'] = True
                stat['meta']['photo_url'] = None
                stat['meta']['id'] = 1 if group_exists else 0
                stat['meta']['username'] = None
            else:
                stat['meta']['id'] = user_info_map[view_user.id]['id']
                if view_user.photo_url:
                    stat['meta']['photo_url'] = view_user.photo_url

            baked_data[str(yr)] = stat

        final_payload = {'metadata': {'years': years}, 'data': baked_data}
        content_hash = hashlib.sha256(
            json.dumps(final_payload, sort_keys=True).encode()
        ).hexdigest()
        stat_id = content_hash[:16]
        SharedStat.objects.get_or_create(id=stat_id, defaults={'data': final_payload})
        return JsonResponse({'id': stat_id})

    except Exception as e:
        logging.error(f'WebApp Bake Stats Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_http_methods(['GET'])
def webapp_get_shared_stats(request, stat_id):
    try:
        shared_stat = SharedStat.objects.get(id=stat_id)
        return JsonResponse(shared_stat.data)
    except SharedStat.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        logging.error(f'WebApp Shared Stats Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST', 'GET'])
def webapp_get_show_full(request, show_id):
    try:
        show = (
            Show.objects.select_related('ext_rating')
            .prefetch_related('countries', 'genres', 'showcrew_set__person__master_person')
            .get(id=show_id)
        )

        view_user = get_webapp_user(request)

        internal_rating, user_ratings = show.get_internal_rating_data()
        
        duration_qs = ShowDuration.objects.filter(show=show).aggregate(total=Sum('duration_seconds'))
        total_duration = duration_qs['total'] or 0

        personal_rating = None
        personal_episodes_count = 0

        visible_ids = set()
        is_guest = True
        if view_user:
            is_guest = view_user.role == UserRole.GUEST
            visible_ids.add(view_user.id)
            if not is_guest:
                mate_ids = ViewUser.objects.filter(groups__users=view_user).values_list(
                    'id', flat=True
                )
                visible_ids.update(mate_ids)

            rating_obj = UserRating.objects.filter(
                user=view_user, show=show, season_number__isnull=True
            ).first()
            if rating_obj:
                personal_rating = rating_obj.rating

            personal_episodes_count = UserRating.objects.filter(
                user=view_user, show=show, season_number__isnull=False
            ).count()

        last_view = None
        user_show_history = []
        if view_user:
            history_qs = (
                ViewHistory.objects.filter(show=show)
                .prefetch_related('users')
                .order_by(F('view_date').desc(nulls_last=True), '-id')
            )

            for h in history_qs:
                allowed_users = [u for u in h.users.all() if u.id in visible_ids]
                if not allowed_users:
                    continue

                item = {
                    'id': h.id,
                    'show_id': show.id,
                    'show__title': show.title,
                    'show__original_title': show.original_title,
                    'show__year': show.year,
                    'view_date': format_precision_date(h.view_date, h.date_precision),
                    'season_number': h.season_number,
                    'episode_number': h.episode_number,
                    'poster_url': get_poster_url(show.id),
                    'user_names': [
                        u.name or u.username or str(u.telegram_id) for u in allowed_users
                    ],
                    'user_photos': [] if is_guest else [u.photo_url for u in allowed_users],
                    'user_ids': [u.id for u in allowed_users],
                }
                user_show_history.append(item)

            if user_show_history:
                my_last = next(
                    (x for x in user_show_history if view_user.id in x['user_ids']), None
                )
                if my_last:
                    se_suffix = (
                        f' ({format_se(my_last["season_number"], my_last["episode_number"])})'
                        if my_last['season_number'] > 0
                        else ''
                    )
                    last_view = {'display': f'{my_last["view_date"]}{se_suffix}'}

        crew_grouped = defaultdict(list)
        seen_canonical_by_prof = defaultdict(set)

        for crew_member in show.showcrew_set.all():
            person = crew_member.person.canonical
            norm_ru = RAW_TO_NORMALIZED_RU.get(crew_member.profession, crew_member.profession)
            if not norm_ru:
                norm_ru = 'Другое'

            if person.id in seen_canonical_by_prof[norm_ru]:
                continue
            seen_canonical_by_prof[norm_ru].add(person.id)

            crew_grouped[norm_ru].append(
                {
                    'id': person.id,
                    'name': person.name,
                    'photo_url': person.photo_url,
                    'fallback_photo_url': person.kp_photo_url if person.tmdb_photo_url else None,
                }
            )

        preferred_order = [
            'Актёр',
            'Актёр дубляжа',
            'Режиссёр',
            'Сценарист',
            'Продюссер',
            'Оператор',
            'Композитор',
            'Художник',
            'Монтажёр',
        ]

        ordered_crew = []
        for prof in preferred_order:
            if prof in crew_grouped and crew_grouped[prof]:
                persons = crew_grouped[prof]
                label = PROFESSIONS_PLURAL_MAP_RU.get(prof, prof) if len(persons) > 1 else prof
                ordered_crew.append({'profession': label, 'persons': persons})

        for prof, persons in crew_grouped.items():
            if prof not in preferred_order:
                label = PROFESSIONS_PLURAL_MAP_RU.get(prof, prof) if len(persons) > 1 else prof
                ordered_crew.append({'profession': label, 'persons': persons})

        genre_map = {}
        for g in show.genres.all():
            norm_name = RAW_TO_NORMALIZED_GENRE.get(g.name, g.name)
            if norm_name not in genre_map:
                genre_map[norm_name] = g.id

        genres_list = [{'id': gid, 'name': name} for name, gid in sorted(genre_map.items())]

        countries_data = []
        seen_names = set()
        for c in show.countries.all():
            norm_name = RAW_TO_NORMALIZED_COUNTRY.get(c.name, c.name)
            if norm_name in seen_names:
                continue
            seen_names.add(norm_name)
            if norm_name != c.name:
                target = Country.objects.filter(name=norm_name).first()
                if target:
                    countries_data.append(
                        {'id': target.id, 'name': target.name, 'emoji': target.emoji_flag}
                    )
                    continue
            countries_data.append({'id': c.id, 'name': c.name, 'emoji': c.emoji_flag})

        ext_rating_data = None
        try:
            if hasattr(show, 'ext_rating') and show.ext_rating:
                ext_rating_data = {
                    'kp': show.ext_rating.kp,
                    'imdb': show.ext_rating.imdb,
                    'tmdb': show.ext_rating.tmdb,
                    'film_critics': show.ext_rating.film_critics,
                    'russian_film_critics': show.ext_rating.russian_film_critics,
                    'await_rating': show.ext_rating.await_rating,
                    'updated_at': show.ext_rating.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                    if show.ext_rating.updated_at
                    else None,
                }
        except Exception:
            pass

        ratings_qs = UserRating.objects.filter(show=show).select_related('user')
        total_ratings_count = ratings_qs.count()

        grouped_ratings = {}
        for r in ratings_qs:
            uid = r.user.id
            if uid not in grouped_ratings:
                user_label = r.user.username if r.user.username else r.user.name
                user_display = f'@{user_label}' if r.user.username else user_label
                grouped_ratings[uid] = {
                    'user': user_display,
                    'show_rating': None,
                    'episodes': [],
                }
            if r.season_number is None and r.episode_number is None:
                grouped_ratings[uid]['show_rating'] = r.rating
            else:
                grouped_ratings[uid]['episodes'].append(
                    {
                        'season': r.season_number,
                        'episode': r.episode_number,
                        'rating': r.rating,
                    }
                )

        for uid in grouped_ratings:
            grouped_ratings[uid]['episodes'].sort(key=lambda x: (x['season'], x['episode']))

        user_ratings_details = list(grouped_ratings.values())

        data = {
            'id': show.id,
            'title': show.title,
            'original_title': show.original_title,
            'type': show.type,
            'year': show.year,
            'status': show.status,
            'plot': show.plot,
            'poster_large': get_poster_url(show.id, 'big'),
            'poster_medium': get_poster_url(show.id, 'medium'),
            'kinopoisk_rating': show.kinopoisk_rating,
            'kinopoisk_votes': show.kinopoisk_votes,
            'kinopoisk_url': show.kinopoisk_url,
            'imdb_rating': show.imdb_rating,
            'imdb_votes': show.imdb_votes,
            'imdb_url': show.imdb_url,
            'internal_rating': internal_rating,
            'user_ratings': user_ratings,
            'total_duration': total_duration,
            'user_ratings_details': user_ratings_details,
            'total_ratings_count': total_ratings_count,
            'personal_rating': personal_rating,
            'personal_episodes_count': personal_episodes_count,
            'last_view': last_view,
            'view_history': user_show_history,
            'countries': countries_data,
            'genres': genres_list,
            'crew': ordered_crew,
            'ext_rating': ext_rating_data,
            'updated_at': show.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            if show.updated_at
            else None,
        }
        return JsonResponse(data)
    except Show.DoesNotExist:
        return JsonResponse({'error': 'Show not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST', 'GET'])
def webapp_get_collection(request, collection_type, item_id):
    try:
        offset = 0
        limit = 50
        if request.method == 'POST':
            try:
                body = json.loads(request.body)
                offset = int(body.get('offset', 0))
                limit = int(body.get('limit', 50))
            except Exception:
                pass
        else:
            offset = int(request.GET.get('offset', 0))
            limit = int(request.GET.get('limit', 50))

        shows = Show.objects.all()
        title = 'Коллекция'
        person_info = None

        if collection_type == 'person':
            base_person = Person.objects.get(id=int(item_id))
            person = base_person.canonical

            target_ids = [person.id] + list(person.aliases.values_list('id', flat=True))
            shows = shows.filter(showcrew__person__id__in=target_ids)
            title = person.name

            professions = (
                ShowCrew.objects.filter(person_id__in=target_ids)
                .exclude(profession__isnull=True)
                .values_list('profession', flat=True)
                .distinct()
            )
            norm_profs = sorted(list({RAW_TO_NORMALIZED_RU.get(p, p) for p in professions if p}))

            person_info = {
                'photo_url': person.photo_url,
                'fallback_photo_url': person.kp_photo_url if person.tmdb_photo_url else None,
                'professions': norm_profs,
            }
        elif collection_type == 'genre':
            genre = Genre.objects.get(id=int(item_id))
            norm_name = RAW_TO_NORMALIZED_GENRE.get(genre.name, genre.name)
            search_list = GENRES_MAPPING.get(norm_name, [genre.name])
            shows = shows.filter(genres__name__in=search_list)
            title = f'Жанр: {norm_name}'
        elif collection_type == 'country':
            country = Country.objects.get(id=int(item_id))
            shows = shows.filter(countries=country)
            title = country.name
            if country.emoji_flag:
                title = f'{country.emoji_flag} {title}'
        elif collection_type == 'show_type':
            shows = shows.filter(type=item_id)
            title = f'Тип: {SHOW_TYPE_DISPLAY_RU.get(item_id, item_id)}'
        elif collection_type == 'year':
            shows = shows.filter(year=int(item_id))
            title = f'Год: {item_id}'
        elif collection_type == 'status':
            shows = shows.filter(status=item_id)
            title = f'Статус: {SHOW_STATUS_DISPLAY_RU.get(item_id, item_id)}'
        else:
            return JsonResponse({'error': 'Invalid collection type'}, status=400)

        shows = shows.order_by('-year', '-id').distinct()

        sliced_shows = list(shows[offset : offset + limit + 1])
        has_more = len(sliced_shows) > limit
        shows_to_return = sliced_shows[:limit]

        view_user = get_webapp_user(request)
        user_ratings = _get_user_ratings_for_shows(view_user, [s.id for s in shows_to_return])

        results = []
        for show in shows_to_return:
            results.append(
                {
                    'id': show.id,
                    'title': show.title,
                    'original_title': show.original_title,
                    'year': show.year,
                    'type': show.type,
                    'poster_url': get_poster_url(show.id, 'medium'),
                    'user_rating': user_ratings.get(show.id),
                }
            )

        return JsonResponse(
            {'title': title, 'items': results, 'person_info': person_info, 'has_more': has_more}
        )
    except (Person.DoesNotExist, Genre.DoesNotExist, Country.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_search(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        query = body.get('query', '').strip()
        offset = int(body.get('offset', 0))
        limit = int(body.get('limit', 30))

        if len(query) < 2:
            return JsonResponse({'shows': [], 'persons': []})

        shows_qs = Show.objects.filter(
            Q(title__icontains=query) | Q(original_title__icontains=query)
        ).order_by('-year', '-id')

        shows = shows_qs[offset : offset + limit]
        user_ratings = _get_user_ratings_for_shows(view_user, [s.id for s in shows])

        persons = []
        if offset == 0:
            persons = (
                Person.objects.filter(Q(name__icontains=query) | Q(en_name__icontains=query))
                .select_related('master_person')
                .order_by('-updated_at')[:20]
            )

        show_results = []
        for s in shows:
            show_results.append(
                {
                    'id': s.id,
                    'title': s.title,
                    'original_title': s.original_title,
                    'year': s.year,
                    'type': s.type,
                    'poster_url': get_poster_url(s.id, 'medium'),
                    'user_rating': user_ratings.get(s.id),
                }
            )

        person_results = []
        seen_canonical_ids = set()
        for p in persons:
            canonical = p.canonical
            if canonical.id in seen_canonical_ids:
                continue
            seen_canonical_ids.add(canonical.id)
            person_results.append(
                {
                    'id': canonical.id,
                    'name': canonical.name,
                    'en_name': canonical.en_name,
                    'photo_url': canonical.photo_url,
                    'fallback_photo_url': canonical.kp_photo_url
                    if canonical.tmdb_photo_url
                    else None,
                }
            )
            if len(person_results) >= 10:
                break

        return JsonResponse(
            {
                'shows': show_results,
                'persons': person_results,
                'has_more': len(show_results) == limit,
            }
        )
    except Exception as e:
        logger.error(f'WebApp Search Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@staff_member_required
@require_http_methods(['GET'])
def get_metric_details(request, key):
    if not request.user.is_staff:
        return JsonResponse({'is_authenticated': False, 'error': 'Forbidden'}, status=403)

    show_type = request.GET.get('type')
    is_person_metric = any(
        x in key for x in ['person', 'avatar', 'professions', 'duplicate_photo', 'unused_persons']
    )
    is_country_metric = 'country' in key
    is_genre_metric = 'genre' in key

    if is_person_metric:
        admin_base_url = reverse('admin:app_person_changelist')
    elif is_country_metric:
        admin_base_url = reverse('admin:app_country_changelist')
    elif is_genre_metric:
        admin_base_url = reverse('admin:app_genre_changelist')
    else:
        admin_base_url = reverse('admin:app_show_changelist')

    query_params = {}
    is_genre = False
    items, is_summary, is_country, is_person, target_task = [], False, False, False, 'details'

    inverse_map = {v: k for k, v in SHOW_TYPE_DISPLAY_RU.items()}
    db_show_type = inverse_map.get(show_type, show_type)

    if key == 'missing_kp':
        items = list(get_missing_kp_list(db_show_type))
        query_params.update(
            {
                'type': db_show_type,
                'kinopoisk_url__isnull': 'False',
                'ext_rating__kp__isnull': 'True',
            }
        )
        target_task = 'priority_sync'
    elif key == 'missing_imdb':
        items = list(get_missing_imdb_list(db_show_type))
        query_params.update(
            {'type': db_show_type, 'imdb_url__isnull': 'False', 'ext_rating__imdb__isnull': 'True'}
        )
        target_task = 'priority_sync'
    elif key == 'title_collision':
        items = list(get_title_collision_list(db_show_type))
        query_params['type'] = db_show_type
    elif key == 'missing_year':
        items = list(get_missing_year_list(db_show_type))
        query_params.update({'type': db_show_type, 'year__isnull': 'True'})
    elif key == 'missing_status':
        items = list(get_missing_status_list(db_show_type))
        query_params.update({'type': db_show_type, 'status__isnull': 'True'})
    elif key == 'missing_plot':
        items = list(get_missing_plot_list(db_show_type))
        query_params.update({'type': db_show_type, 'plot__isnull': 'True'})
    elif key == 'missing_durations':
        items = list(get_missing_durations_list(db_show_type))
        query_params.update({'type': db_show_type, 'showduration__isnull': 'True'})
        target_task = 'durations'
    elif key == 'no_genres':
        items = list(get_no_genres_list(db_show_type))
        query_params.update({'type': db_show_type, 'genres__isnull': 'True'})
    elif key == 'total_genres':
        is_genre, items = True, list(get_total_genres_list(db_show_type))
    elif key == 'unmapped_genres':
        is_genre, items = True, list(get_unmapped_genres_list())
    elif key == 'no_countries':
        items = list(get_no_countries_list(db_show_type))
        query_params.update({'type': db_show_type, 'countries__isnull': 'True'})
    elif key == 'has_kp':
        is_summary = True
        query_params.update({'type': db_show_type, 'ext_rating__kp__isnull': 'False'})
    elif key == 'has_imdb':
        is_summary = True
        query_params.update({'type': db_show_type, 'ext_rating__imdb__isnull': 'False'})
    elif key == 'total_shows':
        is_summary = True
        if db_show_type:
            query_params['type'] = db_show_type
    elif key == 'missing_country_meta':
        is_country, items = True, list(get_missing_country_meta_list())
    elif key == 'total_countries':
        is_country = True
        if show_type == 'Неиспользуемые':
            items = list(get_unused_countries_list())
        else:
            items = list(get_active_countries_list())
    elif key == 'total_persons_by_show_type':
        is_summary = True
        query_params['showcrew__show__type'] = db_show_type
    elif key == 'persons_avatar_stats':
        is_summary = True
        mapping = {
            'Есть фото (TMDB)': 'has_tmdb',
            'Есть фото (KP)': 'kp',
            'TMDB не найдено': 'tmdb_none',
            'KP не найдено': 'kp_none',
            'В ожидании TMDB': 'tmdb_wait',
            'В ожидании KP': 'kp_wait',
            'Не найдено вообще': 'all_none',
        }
        if show_type in mapping:
            query_params['photo_source'] = mapping[show_type]
    elif key == 'professions_stats':
        is_summary = True
        query_params['profession_norm'] = show_type
    elif key == 'en_professions_stats':
        is_summary = True
        query_params['en_profession_norm'] = show_type
    elif key == 'duplicate_photo_urls':
        is_person, items = True, list(get_duplicate_photo_urls_list(show_type))
        query_params['q'] = show_type
    elif key == 'unused_persons':
        is_summary = True
        query_params['showcrew__isnull'] = 'True'
    else:
        return JsonResponse({'error': 'Invalid key'}, status=400)

    query_string = urllib.parse.urlencode(query_params)
    admin_url = f'{admin_base_url}?{query_string}' if query_string else admin_base_url

    if is_summary:
        return JsonResponse({'is_summary': True, 'admin_url': admin_url, 'items': []})

    try:
        r = Redis.from_url(settings.CELERY_BROKER_URL)
        all_queued = (
            {int(x) for x in r.smembers('queue:update_details')}
            | {int(x) for x in r.smembers('queue:priority_ratings_sync')}
            | {int(x) for x in r.smembers('queue:update_durations')}
        )
    except Exception:
        all_queued = set()

    for item in items:
        if is_genre:
            item['is_genre'] = True
            if not item.get('is_duplicate_group'):
                item['admin_url'] = (
                    f'{reverse("admin:app_genre_changelist")}?q='
                    f'{urllib.parse.quote(item.get("name", item.get("title", "")))}'
                )
        elif is_person:
            if 'persons' in item:
                item.update(
                    {
                        'is_person': True,
                        'is_duplicate_group': True,
                        'poster_url': item.get('tmdb_photo_url') or item.get('kp_photo_url') or '',
                    }
                )
            else:
                item.update(
                    {
                        'is_person': True,
                        'title': item.get('name', item.get('title')),
                        'original_title': item.get('en_name'),
                        'poster_url': item.get('tmdb_photo_url') or item.get('kp_photo_url') or '',
                        'admin_url': (
                            f'{reverse("admin:app_person_changelist")}'
                            f'?q={urllib.parse.quote(item.get("name", item.get("title", "")))}'
                        ),
                    }
                )
        elif is_country:
            item.update(
                {
                    'is_country': True,
                    'admin_url': reverse('admin:app_country_change', args=[item['id']]),
                }
            )
        else:
            item.update(
                {
                    'in_queue': item['id'] in all_queued,
                    'poster_url': get_poster_url(item['id'], 'small'),
                    'kinopub_url': f'{settings.SITE_AUX_URL.rstrip("/")}/item/view/{item["id"]}',
                    'admin_url': reverse('admin:app_show_change', args=[item['id']]),
                }
            )

    return JsonResponse(
        {
            'items': items,
            'admin_url': admin_url,
            'target_task': target_task,
            'is_country': is_country,
            'is_person': is_person,
            'is_genre': is_genre,
            'is_authenticated': True,
        }
    )


@csrf_exempt
@require_http_methods(['POST'])
def queue_update_details(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        target = data.get('target', 'details')

        if not ids:
            return JsonResponse({'status': 'ok', 'added': 0})

        if target == 'priority_sync':
            redis_key = 'queue:priority_ratings_sync'
        elif target == 'durations':
            redis_key = 'queue:update_durations'
        else:
            redis_key = 'queue:update_details'

        r = Redis.from_url(settings.CELERY_BROKER_URL)
        added = r.sadd(redis_key, *ids)
        return JsonResponse({'status': 'ok', 'added': added})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_wishlist_data(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        action = body.get('action')

        if action == 'get':
            if not WishlistFolder.objects.filter(user=view_user, is_deleted=False).exists():
                WishlistFolder.objects.create(
                    user=view_user, name='Избранное', icon='bookmark', color='#f1c40f', sort_order=1
                )

            active_items_qs = WishlistItem.objects.filter(is_active=True).select_related('show')
            folders = WishlistFolder.objects.filter(
                user=view_user, is_deleted=False
            ).prefetch_related(Prefetch('items', queryset=active_items_qs))

            all_show_ids = []
            for f in folders:
                all_show_ids.extend([item.show_id for item in f.items.all()])

            user_ratings = _get_user_ratings_for_shows(view_user, list(set(all_show_ids)))

            data = []
            for folder in folders:
                items = []
                for item in folder.items.all():
                    items.append(
                        {
                            'id': item.id,
                            'show_id': item.show.id,
                            'title': item.show.title,
                            'original_title': item.show.original_title,
                            'year': item.show.year,
                            'type': item.show.type,
                            'poster_url': get_poster_url(item.show.id, 'small'),
                            'added_at': item.created_at.strftime('%Y-%m-%d'),
                            'user_rating': user_ratings.get(item.show_id),
                        }
                    )
                data.append(
                    {
                        'id': folder.id,
                        'name': folder.name,
                        'icon': folder.icon,
                        'color': folder.color,
                        'sort_order': folder.sort_order,
                        'items': items,
                    }
                )
            return JsonResponse({'folders': data})

        elif action == 'create_folder':
            if WishlistFolder.objects.filter(user=view_user, is_deleted=False).count() >= 12:
                return JsonResponse({'error': 'Достигнут лимит в 12 папок'}, status=400)

            name = body.get('name', '').strip()
            if len(name) > 100:
                return JsonResponse(
                    {'error': 'Название папки не должно превышать 100 символов'}, status=400
                )

            icon = body.get('icon', 'folder')
            color = body.get('color', '#60a5fa')
            max_order = (
                WishlistFolder.objects.filter(user=view_user, is_deleted=False).aggregate(
                    m=Max('sort_order')
                )['m']
                or 0
            )
            folder = WishlistFolder.objects.create(
                user=view_user, name=name, icon=icon, color=color, sort_order=max_order + 1
            )
            return JsonResponse({'status': 'ok', 'id': folder.id})

        elif action == 'delete_folder':
            folder_id = body.get('folder_id')

            WishlistItem.objects.filter(folder_id=folder_id, folder__user=view_user).update(
                is_active=False
            )
            WishlistFolder.objects.filter(id=folder_id, user=view_user).update(is_deleted=True)

            if not WishlistFolder.objects.filter(user=view_user, is_deleted=False).exists():
                WishlistFolder.objects.create(
                    user=view_user, name='Избранное', icon='bookmark', color='#f1c40f', sort_order=1
                )

            return JsonResponse({'status': 'ok'})

        elif action == 'edit_folder':
            folder_id = body.get('folder_id')
            name = body.get('name', '').strip()
            if len(name) > 100:
                return JsonResponse(
                    {'error': 'Название папки не должно превышать 100 символов'}, status=400
                )

            icon = body.get('icon')
            color = body.get('color')
            WishlistFolder.objects.filter(id=folder_id, user=view_user, is_deleted=False).update(
                name=name, icon=icon, color=color
            )
            return JsonResponse({'status': 'ok'})

        elif action == 'add_item':
            folder_id = body.get('folder_id')
            show_id = body.get('show_id')
            folder = WishlistFolder.objects.filter(
                id=folder_id, user=view_user, is_deleted=False
            ).first()
            if not folder:
                return JsonResponse({'error': 'Folder not found'}, status=404)
            show = Show.objects.filter(id=show_id).first()
            if not show:
                return JsonResponse({'error': 'Show not found'}, status=404)

            already_in_stats = (
                WishlistItem.objects.filter(
                    user=view_user, show=show, is_active=True, include_in_stats=True
                )
                .exclude(folder=folder)
                .exists()
            )

            should_include = not already_in_stats

            item = WishlistItem.objects.filter(folder=folder, show=show).first()
            if item:
                item.is_active = True
                item.include_in_stats = should_include
                item.user = view_user
                item.created_at = timezone.now()
                item.save(update_fields=['is_active', 'include_in_stats', 'user', 'created_at'])
            else:
                max_order = (
                    WishlistItem.objects.filter(folder=folder).aggregate(m=Max('sort_order'))['m']
                    or 0
                )
                WishlistItem.objects.create(
                    user=view_user,
                    folder=folder,
                    show=show,
                    sort_order=max_order + 1,
                    include_in_stats=should_include,
                )
            return JsonResponse({'status': 'ok'})

        elif action == 'remove_item':
            item_id = body.get('item_id')
            keep_stats = body.get('keep_stats', True)
            is_stat_removal = body.get('is_stat_removal', False)

            queryset = WishlistItem.objects.filter(
                Q(id=item_id) & (Q(user=view_user) | Q(folder__user=view_user))
            )

            if is_stat_removal:
                queryset.update(include_in_stats=False)
            else:
                queryset.update(is_active=False, include_in_stats=keep_stats)

            return JsonResponse({'status': 'ok'})

        elif action == 'reorder_folders':
            order_ids = body.get('order', [])
            for idx, fid in enumerate(order_ids):
                WishlistFolder.objects.filter(id=fid, user=view_user, is_deleted=False).update(
                    sort_order=idx
                )
            return JsonResponse({'status': 'ok'})

        elif action == 'reorder_items':
            folder_id = body.get('folder_id')
            order_ids = body.get('order', [])
            folder = WishlistFolder.objects.filter(
                id=folder_id, user=view_user, is_deleted=False
            ).first()
            if folder:
                total = len(order_ids)
                for idx, item_id in enumerate(order_ids):
                    WishlistItem.objects.filter(id=item_id, folder=folder).update(
                        sort_order=total - idx
                    )
            return JsonResponse({'status': 'ok'})

        return JsonResponse({'error': 'Invalid action'}, status=400)

    except Exception as e:
        logging.error(f'WebApp Wishlist Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_casino(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        action = body.get('action')

        if action == 'status':
            latest_spin = CasinoSpin.objects.filter(user=view_user).order_by('-created_at').first()
            if latest_spin:
                time_passed = (timezone.now() - latest_spin.created_at).total_seconds()
                if time_passed < 86400:
                    show = latest_spin.show
                    expires_ms = int(
                        (latest_spin.created_at + timedelta(hours=24)).timestamp() * 1000
                    )

                    user_rating = UserRating.objects.filter(
                        user=view_user, show=show, season_number__isnull=True
                    ).first()

                    return JsonResponse(
                        {
                            'active_spin': {
                                'show': {
                                    'show_id': show.id,
                                    'title': show.title,
                                    'original_title': show.original_title,
                                    'year': show.year,
                                    'type': show.type,
                                    'poster_url': get_poster_url(show.id, 'small'),
                                    'user_rating': user_rating.rating if user_rating else None,
                                },
                                'expires': expires_ms,
                            }
                        }
                    )
            return JsonResponse({'active_spin': None})

        elif action == 'spin':
            latest_spin = CasinoSpin.objects.filter(user=view_user).order_by('-created_at').first()
            if latest_spin:
                time_passed = (timezone.now() - latest_spin.created_at).total_seconds()
                if time_passed < 86400:
                    return JsonResponse({'error': 'Cooldown active'}, status=400)

            folder_id = body.get('folder_id')
            if folder_id == 'all':
                items = WishlistItem.objects.filter(folder__user=view_user).select_related('show')
            else:
                items = WishlistItem.objects.filter(
                    folder__user=view_user, folder__id=folder_id
                ).select_related('show')

                if not items.exists():
                    return JsonResponse({'error': 'Empty folder'}, status=400)

            winner_item = random.choice(list(items))
            winner_show = winner_item.show

            new_spin = CasinoSpin.objects.create(user=view_user, show=winner_show)
            expires_ms = int((new_spin.created_at + timedelta(hours=24)).timestamp() * 1000)

            user_rating = UserRating.objects.filter(
                user=view_user, show=winner_show, season_number__isnull=True
            ).first()

            return JsonResponse(
                {
                    'show': {
                        'show_id': winner_show.id,
                        'title': winner_show.title,
                        'original_title': winner_show.original_title,
                        'year': winner_show.year,
                        'type': winner_show.type,
                        'poster_url': get_poster_url(winner_show.id, 'small'),
                        'user_rating': user_rating.rating if user_rating else None,
                    },
                    'expires': expires_ms,
                }
            )

        elif action == 'history':
            spins = (
                CasinoSpin.objects.filter(user=view_user, is_deleted=False)
                .order_by('-created_at')
                .select_related('show')
            )
            history = []
            for s in spins:
                history.append(
                    {
                        'id': s.id,
                        'show_id': s.show.id,
                        'show__title': s.show.title,
                        'show__original_title': s.show.original_title,
                        'show__year': s.show.year,
                        'poster_url': get_poster_url(s.show.id, 'small'),
                        'view_date': timezone.localtime(s.created_at).strftime('%Y-%m-%d %H:%M'),
                        'season_number': 0,
                        'episode_number': 0,
                        'user_names': [],
                    }
                )
            return JsonResponse({'history': history})

        elif action == 'delete_spin':
            spin_id = body.get('spin_id')
            CasinoSpin.objects.filter(id=spin_id, user=view_user).update(is_deleted=True)
            return JsonResponse({'status': 'ok'})

        elif action == 'reset':
            now = timezone.now()
            day_ago = now - timedelta(hours=24)
            target_time = now - timedelta(hours=25)

            CasinoSpin.objects.filter(user=view_user, created_at__gte=day_ago).update(
                created_at=target_time
            )

            return JsonResponse({'status': 'ok'})

        return JsonResponse({'error': 'Invalid action'}, status=400)

    except Exception as e:
        logging.error(f'Casino API Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@staff_member_required
@require_http_methods(['GET'])
def admin_get_folder_content(request, folder_id):
    """API для админки: получение содержимого папки без TG-авторизации."""
    try:
        folder = WishlistFolder.objects.get(id=folder_id)
        items_qs = (
            WishlistItem.objects.filter(folder=folder, is_active=True)
            .select_related('show')
            .order_by('-sort_order', '-id')
        )

        show_ids = [item.show_id for item in items_qs]
        user_ratings = _get_user_ratings_for_shows(folder.user, show_ids)

        items_data = []
        for item in items_qs:
            items_data.append(
                {
                    'id': item.id,
                    'show_id': item.show.id,
                    'title': item.show.title,
                    'original_title': item.show.original_title,
                    'year': item.show.year,
                    'type': item.show.type,
                    'poster_url': get_poster_url(item.show.id, 'small'),
                    'added_at': item.created_at.strftime('%Y-%m-%d'),
                    'user_rating': user_ratings.get(item.show_id),
                }
            )

        return JsonResponse(
            {
                'id': folder.id,
                'name': folder.name,
                'icon': folder.icon,
                'color': folder.color,
                'items': items_data,
            }
        )
    except WishlistFolder.DoesNotExist:
        return JsonResponse({'error': 'Folder not found'}, status=404)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_add_view(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        show_id = body.get('show_id')
        season = int(body.get('season') or 0)
        episode = int(body.get('episode') or 0)
        date_mode = body.get('date_mode', 'exact')
        date_val = body.get('date_val')

        view_date = None
        if date_mode == 'exact' and date_val:
            view_date = datetime.strptime(str(date_val), '%Y-%m-%d').date()
        elif date_mode == 'month' and date_val:
            view_date = datetime.strptime(str(date_val), '%Y-%m').date()
        elif date_mode == 'year' and date_val:
            view_date = datetime.strptime(str(date_val), '%Y').date()

        vh = ViewHistory.objects.filter(
            show_id=show_id,
            season_number=season,
            episode_number=episode,
            view_date=view_date,
            date_precision=date_mode,
        ).first()

        if not vh:
            vh = ViewHistory(
                show_id=show_id,
                view_date=view_date,
                season_number=season,
                episode_number=episode,
                date_precision=date_mode,
                is_checked=True,
                source=ViewHistory.SOURCE_MANUAL,
            )
            vh._skip_broadcast = True
            vh.save()
        else:
            vh._skip_broadcast = True

        if not vh.users.filter(id=view_user.id).exists():
            vh.users.add(view_user)

        show_title = vh.show.title or vh.show.original_title
        send_view_confirmation_task.delay(
            view_user.telegram_id,
            show_title,
            season if season > 0 else None,
            episode if episode > 0 else None,
        )

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logging.error(f'WebApp Add View Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_remove_view(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        history_id = body.get('view_history_id')
        if not history_id:
            show_id = body.get('show_id')
            season = int(body.get('season') or 0)
            episode = int(body.get('episode') or 0)
            date_mode = body.get('date_mode', 'exact')
            date_val = body.get('date_val')

            view_date = None
            if date_mode == 'exact' and date_val:
                view_date = datetime.strptime(str(date_val), '%Y-%m-%d').date()
            elif date_mode == 'month' and date_val:
                view_date = datetime.strptime(str(date_val), '%Y-%m').date()
            elif date_mode == 'year' and date_val:
                view_date = datetime.strptime(str(date_val), '%Y').date()

            vh = ViewHistory.objects.filter(
                show_id=show_id,
                season_number=season,
                episode_number=episode,
                view_date=view_date,
                date_precision=date_mode,
            ).first()
        else:
            vh = ViewHistory.objects.filter(id=history_id).first()

        if vh:
            vh.users.remove(view_user)
            if vh.source == ViewHistory.SOURCE_KINOPUB and vh.telegram_message_id:
                TelegramSender().update_history_message(vh)

            return JsonResponse({'status': 'ok'})

        return JsonResponse({'error': 'View record not found in database'}, status=404)

    except Exception as e:
        logging.error(f'WebApp Remove View Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_get_episodes(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        show_id = body.get('show_id')

        durations = ShowDuration.objects.filter(
            show_id=show_id, season_number__isnull=False, episode_number__isnull=False
        ).order_by('season_number', 'episode_number')

        ratings = UserRating.objects.filter(
            user=view_user, show_id=show_id, season_number__isnull=False
        ).values('season_number', 'episode_number', 'rating')

        ratings_map = {(r['season_number'], r['episode_number']): r['rating'] for r in ratings}

        views = ViewHistory.objects.filter(
            show_id=show_id, users=view_user, season_number__gt=0, episode_number__gt=0
        ).values('id', 'season_number', 'episode_number')

        views_map = {(v['season_number'], v['episode_number']): v['id'] for v in views}

        seasons_dict = defaultdict(list)
        for d in durations:
            seasons_dict[d.season_number].append(
                {
                    'episode_number': d.episode_number,
                    'rating': ratings_map.get((d.season_number, d.episode_number)),
                    'watched': (d.season_number, d.episode_number) in views_map,
                    'view_history_id': views_map.get((d.season_number, d.episode_number)),
                    'duration': d.duration_seconds,
                }
            )

        result = [
            {'season_number': s, 'episodes': episodes}
            for s, episodes in sorted(seasons_dict.items())
        ]

        return JsonResponse({'seasons': result})
    except Exception as e:
        logging.error(f'WebApp Get Episodes Error: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_rate_show(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        show_id = body.get('show_id')
        rating = float(body.get('rating'))

        season = body.get('season')
        episode = body.get('episode')

        if season == 0 or season == '0':
            season = None
        if episode == 0 or episode == '0':
            episode = None

        show = Show.objects.get(id=show_id)

        UserRating.objects.update_or_create(
            user=view_user,
            show=show,
            season_number=season,
            episode_number=episode,
            defaults={'rating': rating},
        )

        history_qs = ViewHistory.objects.filter(
            show=show,
            users=view_user,
            telegram_message_id__isnull=False,
        )

        if season is not None and episode is not None:
            history_qs = history_qs.filter(season_number=season, episode_number=episode)
        else:
            history_qs = history_qs.filter(season_number=0)

        sender = TelegramSender()
        for history_item in history_qs:
            sender.update_history_message(history_item)

        for y in [timezone.now().year, 'all']:
            cache.delete(f'user_stats_v6:{view_user.id}:{y}')
            cache.delete(f'group_stats_v6:{view_user.id}:{y}')

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logging.error(f'WebApp Rate Show Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def webapp_delete_rating(request):
    try:
        view_user = get_webapp_user(request)
        if not view_user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        body = json.loads(request.body)
        show_id = body.get('show_id')

        season = body.get('season')
        episode = body.get('episode')

        if season == 0 or season == '0':
            season = None
        if episode == 0 or episode == '0':
            episode = None

        UserRating.objects.filter(
            user=view_user,
            show_id=show_id,
            season_number=season,
            episode_number=episode,
        ).delete()

        history_qs = ViewHistory.objects.filter(
            show_id=show_id,
            users=view_user,
            telegram_message_id__isnull=False,
        )

        if season is not None and episode is not None:
            history_qs = history_qs.filter(season_number=season, episode_number=episode)
        else:
            history_qs = history_qs.filter(season_number=0)

        sender = TelegramSender()
        for history_item in history_qs:
            sender.update_history_message(history_item)

        for y in [timezone.now().year, 'all']:
            cache.delete(f'user_stats_v6:{view_user.id}:{y}')
            cache.delete(f'group_stats_v6:{view_user.id}:{y}')

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logging.error(f'WebApp Delete Rating Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@staff_member_required
@require_http_methods(['POST'])
def merge_persons_api(request):
    try:
        data = json.loads(request.body)
        master_id = data.get('master_id')
        alias_ids = data.get('alias_ids', [])

        if not master_id or not alias_ids:
            return JsonResponse({'error': 'Master ID and Aliases are required'}, status=400)

        with transaction.atomic():
            master = Person.objects.get(id=master_id)

            if master.master_person:
                master.master_person = None
                master.save(update_fields=['master_person'])

            aliases = Person.objects.filter(id__in=alias_ids).exclude(id=master_id)
            count = aliases.update(master_person=master)

            for aid in alias_ids:
                cache.delete(f'user_stats:person:{aid}')
            cache.delete(f'user_stats:person:{master_id}')

        return JsonResponse({'status': 'ok', 'merged_count': count, 'master_name': master.name})
    except Person.DoesNotExist:
        return JsonResponse({'error': 'Master person not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def vite_proxy_view(request, path=''):
    query_string = request.META.get('QUERY_STRING', '')
    upstream_url = f'http://frontend:5173/__vite__/{path}'

    if query_string:
        upstream_url += f'?{query_string}'

    if cache.get('vite_frontend_alive') is False:
        return HttpResponse(status=502)

    try:
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

        proxy_response = requests.get(
            upstream_url, headers=headers, stream=False, timeout=(0.5, 5.0)
        )

        response = HttpResponse(
            proxy_response.content,
            status=proxy_response.status_code,
            content_type=proxy_response.headers.get('Content-Type'),
        )

        excluded_headers = {
            'content-encoding',
            'transfer-encoding',
            'content-length',
            'connection',
            'keep-alive',
            'proxy-authenticate',
            'proxy-authorization',
        }

        for key, value in proxy_response.headers.items():
            if key.lower() not in excluded_headers:
                response[key] = value

        response['Access-Control-Allow-Origin'] = '*'
        cache.set('vite_frontend_alive', True, timeout=30)
        return response

    except Exception as e:
        logger.error(f'[ViteProxy] FAILED {upstream_url}: {str(e)}')
        cache.set('vite_frontend_alive', False, timeout=10)
        return HttpResponse(status=502)


@csrf_exempt
@require_http_methods(['POST'])
def internal_set_url(request):
    """
    Принимает новый URL от tunnel-monitor и сохраняет его в кэш.
    Используется для генерации корректных ссылок в боте и письмах.
    """
    expected_token = settings.BOT_TOKEN
    if request.headers.get('X-Bot-Token') != expected_token:
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        url = data.get('url')
        if not url:
            return JsonResponse({'ok': False, 'error': 'No URL provided'}, status=400)

        # Сохраняем в кэш Redis на 24 часа
        cache.set('live_webapp_url', url.rstrip('/'), timeout=86400)
        logger.info(f'[System] WebApp URL updated via Monitor: {url}')
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@staff_member_required
@require_http_methods(['GET'])
def admin_get_global_stats(request):
    year = request.GET.get('year')
    if year == 'all' or not year:
        year = None
    stats = generate_global_stats(year=year)
    return JsonResponse(stats)
