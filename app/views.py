import json
import uuid
from django.conf import settings
from django.contrib.auth.models import User, Group, Permission
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.constants import UserRole
from app.dashboard import dashboard_callback
from app.models import ViewUser


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

    exists = ViewUser.objects.filter(telegram_id=telegram_id).exists()
    return JsonResponse({'exists': exists})


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

        email = f"{login_username}@{host}"

        # 1. Создаем или обновляем ViewUser
        view_user, created = ViewUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'username': username,
                'name': first_name,
                'language': data.get('language_code', 'ru'),
                'role': UserRole.GUEST  # По умолчанию гость
            },
        )

        if not created:
            view_user.username = username
            view_user.name = first_name
            view_user.save()

        # 2. Создаем или получаем Django User
        django_user, user_created = User.objects.get_or_create(
            username=login_username,
            defaults={
                'email': email,
                'is_staff': False,
                'is_superuser': False,
                'first_name': first_name[:30]  # Ограничение Django
            }
        )

        if user_created:
            # Устанавливаем случайный пароль, так как вход предполагается через другие механизмы или админом
            django_user.set_password(str(uuid.uuid4()))
            django_user.save()

        # Связываем
        if view_user.django_user != django_user:
            view_user.django_user = django_user
            view_user.save()

        # 3. Синхронизация прав на основе роли
        _sync_user_permissions(django_user, view_user.role)

        # 4. Отправляем сообщение в админ-канал для управления ролями
        # Вызываем это асинхронно или просто здесь, так как requests достаточно быстр,
        # но лучше обернуть в try/except чтобы не ломать регистрацию если телеграм лежит
        try:
            from app.telegram_bot import TelegramSender
            TelegramSender().send_user_role_message(view_user)
        except Exception as e:
            print(f"Failed to send role message: {e}")

        return JsonResponse({
            'status': 'ok',
            'created': created,
            'role': view_user.role,
            'user_id': view_user.id
        })
    except Exception as e:
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
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Message outdated. Please refresh or resend.'
                }, status=409)

        if new_role not in [r.value for r in UserRole]:
            return JsonResponse({'error': 'Invalid role'}, status=400)

        view_user.role = new_role
        view_user.save()

        if view_user.django_user:
            _sync_user_permissions(view_user.django_user, new_role)

        # Обновляем галочки в сообщении (бекенд сам обновляет Telegram)
        try:
            from app.telegram_bot import TelegramSender
            TelegramSender().update_user_role_message(view_user)
        except Exception:
            pass

        return JsonResponse({'status': 'ok', 'new_role': new_role})
    except ViewUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def _sync_user_permissions(user, role):
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
            content_type__app_label='app',
            codename__startswith='view_'
        )
        # Назначаем права напрямую, чтобы они отображались в окне "User permissions"
        user.user_permissions.set(permissions)
    else:
        # GUEST
        user.is_staff = False
        user.is_superuser = False

    user.save()