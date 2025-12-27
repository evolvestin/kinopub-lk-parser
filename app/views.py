import functools
import json
import logging
import uuid

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.dashboard import dashboard_callback
from app.models import LogEntry, Show, ShowDuration, TelegramLog, UserRating, ViewHistory, ViewUser
from app.telegram_bot import TelegramSender
from shared.constants import UserRole
from shared.formatters import format_se


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


def _serialize_show_details(show, user=None):
    """Собирает словарь с данными о шоу и рейтингами."""
    internal_rating, user_ratings = show.get_internal_rating_data()
    personal_rating = None
    personal_episodes_count = 0

    if user:
        user_rating_obj = UserRating.objects.filter(
            user=user, show=show, season_number__isnull=True
        ).first()
        if user_rating_obj:
            personal_rating = user_rating_obj.rating

        personal_episodes_count = UserRating.objects.filter(
            user=user, show=show, season_number__isnull=False
        ).count()

    # Сбор истории просмотров
    history_qs = (
        ViewHistory.objects.filter(show=show)
        .prefetch_related('users')
        .order_by('-view_date', '-id')
    )

    view_history_list = []
    last_message_id = None

    for h in history_qs:
        if not last_message_id and h.telegram_message_id:
            last_message_id = h.telegram_message_id

        view_history_list.append(
            {
                'id': h.id,
                'date': h.view_date.strftime('%Y-%m-%d'),
                'users': [
                    f'@{u.username}' if u.username else u.name or str(u.telegram_id)
                    for u in h.users.all()
                ],
                'message_id': h.telegram_message_id,
                'is_viewer': user in h.users.all() if user else False,
            }
        )

    return {
        'id': show.id,
        'title': show.title,
        'original_title': show.original_title,
        'type': show.type,
        'year': show.year,
        'status': show.status,
        'kinopoisk_rating': show.kinopoisk_rating,
        'imdb_rating': show.imdb_rating,
        'countries': [str(country) for country in show.countries.all()],
        'genres': [genre.name for genre in show.genres.all()],
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
    context = dashboard_callback({})
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

    # Поиск по названию или оригинальному названию (макс 10 результатов)
    shows = Show.objects.filter(
        Q(title__icontains=query) | Q(original_title__icontains=query)
    ).distinct()[:10]

    results = []
    for show in shows:
        results.append(
            {
                'id': show.id,
                'title': show.title,
                'original_title': show.original_title,
                'year': show.year,
                'type': show.type,
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

        # Проверка прав доступа
        if telegram_id:
            try:
                user = ViewUser.objects.get(telegram_id=telegram_id)
                if user.role == UserRole.VIEWER:
                    # VIEWER может менять статус только если он сам есть в списке зрителей
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

        # Добавляем префикс bot. к модулю для ясности в общей таблице
        if not module.startswith('bot.'):
            module = f'bot.{module}'

        LogEntry.objects.create(
            level=level[:10],
            module=module[:100],
            message=message,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        # Если это ошибка от бота, тоже отправляем в DEV канал
        if level in ('ERROR', 'CRITICAL'):
            TelegramSender().send_dev_log(level, module, message)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
