import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.dashboard import dashboard_callback
from app.models import ViewUser


def index(request):
    context = dashboard_callback(request, {})
    return render(request, 'index.html', context)


def _check_token(request):
    token = request.headers.get('X-Bot-Token')
    return token == settings.BOT_INTERNAL_TOKEN


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

        user, created = ViewUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'username': username,
                'name': first_name,
                'language': data.get('language_code', 'ru'),
            },
        )

        if not created:
            # Обновляем данные, если пользователь уже был
            user.username = username
            user.name = first_name
            user.save()

        return JsonResponse({'status': 'ok', 'created': created, 'user_id': user.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
