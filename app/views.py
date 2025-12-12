import json
import logging
import uuid

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from shared.constants import UserRole
from app.dashboard import dashboard_callback
from app.models import Show, ViewHistory, ViewUser, UserRating
from app.telegram_bot import TelegramSender
from shared.formatters import format_se


def index(request):
    context = dashboard_callback(request, {})
    return render(request, 'index.html', context)


def _check_token(request):
    token = request.headers.get('X-Bot-Token')
    return token == settings.BOT_TOKEN


@csrf_exempt
@require_http_methods(['GET'])
def check_bot_user(request, telegram_id):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        user = ViewUser.objects.get(telegram_id=telegram_id)
        return JsonResponse({'exists': True, 'role': user.role})
    except ViewUser.DoesNotExist:
        return JsonResponse({'exists': False, 'role': UserRole.GUEST})


@csrf_exempt
@require_http_methods(['POST'])
def bot_toggle_claim(request):
    """
    Переключает участие пользователя в просмотре (добавляет или удаляет).
    """
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        user = ViewUser.objects.get(telegram_id=telegram_id)
        view_history = ViewHistory.objects.get(id=view_id)

        if user in view_history.users.all():
            view_history.users.remove(user)
            action = 'removed'
        else:
            view_history.users.add(user)
            action = 'added'

        # Обновляем сообщение в канале
        TelegramSender().update_history_message(view_history)

        return JsonResponse({'status': 'ok', 'action': action})
    except (ViewUser.DoesNotExist, ViewHistory.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def register_bot_user(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        username = data.get('username')
        first_name = data.get('first_name', '')

        # Основной идентификатор для логина (если username нет, используем ID)
        login_username = username if username else str(telegram_id)

        # Получаем реальный домен из настроек CSRF, исключая локальные адреса
        host = 'localhost'
        trusted_origins = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
        for origin in trusted_origins:
            if 'localhost' not in origin and '127.0.0.1' not in origin:
                # Убираем протокол и возможные пути, оставляем чистый домен
                host = origin.replace('https://', '').replace('http://', '').split('/')[0]
                break

        email = f'{login_username}@{host}'

        # 1. Создаем или обновляем ViewUser
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

        if not created:
            has_changes = False
            if view_user.username != username:
                view_user.username = username
                has_changes = True
            if view_user.name != first_name:
                view_user.name = first_name
                has_changes = True
            if not view_user.is_bot_active:
                view_user.is_bot_active = True
                has_changes = True

            if has_changes:
                view_user.save()

        # 2. Создаем или получаем Django User
        django_user, user_created = User.objects.get_or_create(
            username=login_username,
            defaults={
                'email': email,
                'is_staff': False,
                'is_superuser': False,
                'first_name': first_name[:30],  # Ограничение Django
            },
        )

        if user_created:
            django_user.set_password(str(uuid.uuid4()))
            django_user.save()

        # Связываем
        if view_user.django_user != django_user:
            view_user.django_user = django_user
            view_user.save()

        # 3. Синхронизация прав на основе роли
        sync_user_permissions(django_user, view_user.role)

        # 4. Отправляем сообщение в админ-канал
        # Если пользователь только создан или сообщения о роли еще нет - создаем новое.
        try:
            if created or not view_user.role_message_id:
                TelegramSender().send_user_role_message(view_user)
            else:
                TelegramSender().update_user_role_message(view_user)
        except Exception as e:
            logging.error(f'Failed to handle role message for {telegram_id}: {e}')

        return JsonResponse(
            {'status': 'ok', 'created': created, 'role': view_user.role, 'user_id': view_user.id}
        )
    except Exception as e:
        logging.error(f'Registration error: {e}')
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def set_bot_user_role(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

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
@require_http_methods(['POST'])
def update_bot_user(request):
    """
    Обновляет персональные данные пользователя (имя, username, язык) и статус активности.
    Вызывается при любом взаимодействии с ботом.
    """
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')

        try:
            view_user = ViewUser.objects.get(telegram_id=telegram_id)
        except ViewUser.DoesNotExist:
            return JsonResponse({'status': 'skipped', 'reason': 'user_not_found'})

        updated_fields = []

        # Обновление основных данных
        new_username = data.get('username')
        new_name = data.get('first_name', '')
        new_language = data.get('language_code', 'en')

        if view_user.username != new_username:
            view_user.username = new_username
            updated_fields.append('username')

        if view_user.name != new_name:
            view_user.name = new_name
            updated_fields.append('name')

        if view_user.language != new_language:
            view_user.language = new_language
            updated_fields.append('language')

        # Обновление статуса активности (если передан)
        is_active = data.get('is_active')
        if is_active is not None:
            if view_user.is_bot_active != is_active:
                view_user.is_bot_active = is_active
                updated_fields.append('is_bot_active')

        if updated_fields:
            view_user.save()

            # Если изменилось имя/юзернейм, обновляем сообщение в админ-канале
            if 'username' in updated_fields or 'name' in updated_fields:
                try:
                    TelegramSender().update_user_role_message(view_user)
                except Exception:
                    pass

        return JsonResponse({'status': 'ok', 'updated': updated_fields})

    except Exception as e:
        logging.error(f'Update user error: {e}')
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['GET'])
def bot_search_shows(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

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
@require_http_methods(['GET'])
def bot_get_show_details(request, show_id):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        show = Show.objects.prefetch_related('countries', 'genres').get(id=show_id)

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
    except Show.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@csrf_exempt
@require_http_methods(['GET'])
def bot_get_by_imdb(request, imdb_id):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

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


@csrf_exempt
@require_http_methods(['POST'])
def bot_assign_view(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        user = ViewUser.objects.get(telegram_id=telegram_id)
        view_history = ViewHistory.objects.get(id=view_id)

        view_history.users.add(user)

        show_title = view_history.show.title or view_history.show.original_title
        if view_history.season_number:
            info = f'{show_title} ({format_se(view_history.season_number, view_history.episode_number)})'
        else:
            info = show_title

        return JsonResponse({'status': 'ok', 'info': info})
    except (ViewUser.DoesNotExist, ViewHistory.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def bot_unassign_view(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        user = ViewUser.objects.get(telegram_id=telegram_id)
        view_history = ViewHistory.objects.get(id=view_id)

        view_history.users.remove(user)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def bot_toggle_view_check(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        view_id = data.get('view_id')
        view = ViewHistory.objects.get(id=view_id)
        sender = TelegramSender()

        # Логика обработки дубликатов:
        # 1. Находим более старые записи того же эпизода/фильма, которые сейчас "учтены"
        older_duplicates = ViewHistory.objects.filter(
            show=view.show,
            season_number=view.season_number,
            episode_number=view.episode_number,
            view_date__lt=view.view_date,
            is_checked=True
        )

        updated = False
        message = ''

        # Если текущая запись включена и есть старые дубликаты -> выключаем старые
        if view.is_checked and older_duplicates.exists():
            count = 0
            for old_view in older_duplicates:
                old_view.is_checked = False
                old_view.save(update_fields=['is_checked'])
                sender.update_history_message(old_view)
                count += 1
            # Текущая запись остается включенной (мы просто подтвердили её приоритет)
            sender.update_history_message(view) 
            message = f'Предыдущие просмотры ({count}) помечены как неучтенные.'
            updated = True
        
        # Иначе просто переключаем статус текущей записи
        else:
            view.is_checked = not view.is_checked
            view.save(update_fields=['is_checked'])
            sender.update_history_message(view)
            status_text = 'учтен' if view.is_checked else 'не учтен'
            message = f'Просмотр теперь {status_text}.'
            updated = True

        return JsonResponse({'status': 'ok', 'message': message, 'is_checked': view.is_checked})

    except ViewHistory.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    

@csrf_exempt
@require_http_methods(['POST'])
def bot_toggle_view_user(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        view_id = data.get('view_id')

        # Используем get_or_create для обработки новых пользователей из канала
        user, _ = ViewUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'name': str(telegram_id),
                'role': UserRole.GUEST,
                'is_bot_active': True,
            }
        )
        
        view_history = ViewHistory.objects.get(id=view_id)
        sender = TelegramSender()

        action = 'added'
        if user in view_history.users.all():
            view_history.users.remove(user)
            action = 'removed'
        else:
            view_history.users.add(user)
            action = 'added'

        sender.update_history_message(view_history)

        return JsonResponse({'status': 'ok', 'action': action})
    except ViewHistory.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def bot_rate_show(request):
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

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
            defaults={'rating': rating}
        )
        return JsonResponse({'status': 'ok', 'rating': rating})

    except (ViewUser.DoesNotExist, Show.DoesNotExist) as e:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)