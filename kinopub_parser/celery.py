import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kinopub_parser.settings')

app = Celery('kinopub_parser')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
