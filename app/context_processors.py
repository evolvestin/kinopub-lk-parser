import time

from django.conf import settings


def version_processor(request):
    return {
        'APP_VERSION': time.time() if settings.DEBUG else getattr(settings, 'STATIC_VERSION', '1.0')
    }
