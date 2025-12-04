import os
from logging.config import dictConfig

from celery import Celery
from celery.signals import setup_logging
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kinopub_parser.settings')


@setup_logging.connect
def config_loggers(*args, **kwargs):
    dictConfig(settings.LOGGING)


celery_app = Celery('kinopub_parser')
celery_app.config_from_object('django.conf:settings', namespace='CELERY')
celery_app.autodiscover_tasks()