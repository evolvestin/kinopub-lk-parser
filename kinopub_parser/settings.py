import logging
import os
import socket
import sys
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
from whitenoise.storage import CompressedManifestStaticFilesStorage

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
if os.path.isdir('/data'):
    data_dir = Path('/data')
else:
    data_dir = BASE_DIR / 'data'
os.makedirs(data_dir, exist_ok=True)

COOKIES_FILE_PATH_MAIN = data_dir / 'cookies_main.json'
COOKIES_FILE_PATH_AUX = data_dir / 'cookies_aux.json'

GOOGLE_DRIVE_CREDENTIALS_JSON = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON')
GOOGLE_DRIVE_FOLDER_ID = '1mpco3I0v22hTklleYJkZZh0VNlhol9L3'
DB_BACKUP_FILENAME = os.getenv('DB_BACKUP_FILENAME', 'data.json')
COOKIES_BACKUP_FILENAME_MAIN = os.getenv('COOKIES_BACKUP_FILENAME_MAIN', 'cookies_main.json')
COOKIES_BACKUP_FILENAME_AUX = os.getenv('COOKIES_BACKUP_FILENAME_AUX', 'cookies_aux.json')

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760

LOCAL_RUN = False
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-for-dev')
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = ['*']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

_web_port = os.getenv('WEB_PORT', '8012')
CSRF_TRUSTED_ORIGINS = [
    f'http://localhost:{_web_port}',
    f'http://127.0.0.1:{_web_port}',
    'https://*.trycloudflare.com',
    'https://*.lhr.life',
    'https://*.tuns.sh',
    'https://*.tunnelmole.net',
    'https://*.serveousercontent.com',
]

if WEBAPP_PUBLIC_URL := os.getenv('WEBAPP_PUBLIC_URL'):
    clean_url = WEBAPP_PUBLIC_URL.rstrip('/')
    if clean_url not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(clean_url)

if WEBAPP_PUBLIC_URL := os.getenv('WEBAPP_PUBLIC_URL'):
    clean_url = WEBAPP_PUBLIC_URL.rstrip('/')
    if clean_url not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(clean_url)

TIME_ZONE = 'UTC'
USE_TZ = True
USE_I18N = True
FORMAT_MODULE_PATH = ['kinopub_parser.formats']
LANGUAGE_CODE = 'en'

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_vite',
    'app',
    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'app.middleware.NoIndexMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DEBUG:
    # Middleware для исправления хоста Vite должен идти после CommonMiddleware
    MIDDLEWARE.insert(4, 'app.middleware.ViteHostMiddleware')

if not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'kinopub_parser.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.version_processor',
            ],
        },
    },
]

DB_PATH = data_dir / DB_BACKUP_FILENAME
if 'runparserlocal' in sys.argv:
    LOCAL_RUN = True
    logging.info(
        '"runparserlocal" command detected. Database will be handled via temporary container.'
    )
    # Устанавливаем параметры по умолчанию для локального запуска
    # Реальные параметры подключения будут установлены динамически внутри команды runparserlocal
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'postgres',
            'USER': 'postgres',
            'PASSWORD': 'temporary_secret',
            'HOST': '127.0.0.1',
            'PORT': '54320',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB'),
            'USER': os.getenv('POSTGRES_USER'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
            'HOST': os.getenv('POSTGRES_HOST', 'db'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
X_FRAME_OPTIONS = 'SAMEORIGIN'
SILENCED_SYSTEM_CHECKS = ['security.W019']

STATIC_URL = 'static/'
STATIC_ROOT = data_dir / 'staticfiles'

DJANGO_VITE = {
    'default': {
        'dev_mode': DEBUG and os.getenv('VITE_DEV_MODE', 'True').lower() == 'true',
        'manifest_path': str(STATIC_ROOT / 'manifest.json'),
        'dev_server_host': 'dynamic-vite-host.internal' if DEBUG else None,
        'dev_server_port': 5173 if DEBUG else None,
    }
}


class SafeCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name


if DEBUG:
    WHITENOISE_MAX_AGE = 0
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_USE_FINDERS = True
    STORAGES = {
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
else:
    WHITENOISE_MAX_AGE = 31536000
    WHITENOISE_AUTOREFRESH = False
    WHITENOISE_USE_FINDERS = False
    STORAGES = {
        'staticfiles': {
            'BACKEND': 'kinopub_parser.settings.SafeCompressedManifestStaticFilesStorage',
        },
    }

WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

STATICFILES_DIRS = []
static_src = BASE_DIR / 'kinopub_parser' / 'static'
if static_src.exists():
    STATICFILES_DIRS.append(static_src)

DJANGO_VITE_ASSETS_PATH = Path('/home/app/frontend_dist_backup')

if not DJANGO_VITE_ASSETS_PATH.exists():
    DJANGO_VITE_ASSETS_PATH = BASE_DIR / 'frontend_webapp' / 'dist'

if DJANGO_VITE_ASSETS_PATH.exists():
    STATICFILES_DIRS.append(DJANGO_VITE_ASSETS_PATH)

_public_url = os.getenv('WEBAPP_PUBLIC_URL', '')
IS_TUNNEL = 'trycloudflare.com' in _public_url

ASGI_APPLICATION = 'kinopub_parser.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
    }
}


if DEBUG:
    WEBSOCKET_URL = '/ws/logs/'
    WEBSOCKET_PORT = ''
else:
    WEBSOCKET_URL = '/ws/logs/'
    WEBSOCKET_PORT = ''

CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False

GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
ALLOWED_SENDER = os.getenv('ALLOWED_SENDER')
IMAP_HOST = 'imap.gmail.com'
IMAP_FOLDER = 'INBOX'
MARK_AS_SEEN = True

# --- Environment Config ---
ENVIRONMENT = os.getenv('ENVIRONMENT')

# --- Bot Integration Config ---
BOT_API_HOST = os.getenv('BOT_API_HOST', 'telegram-bot')
BOT_API_PORT = int(os.getenv('BOT_API_PORT', 8081))
BOT_TOKEN = os.getenv('BOT_TOKEN')
CODES_CHANNEL_ID = os.getenv('CODES_CHANNEL_ID')
USER_MANAGEMENT_CHANNEL_ID = os.getenv('USER_MANAGEMENT_CHANNEL_ID')
HISTORY_CHANNEL_ID = os.getenv('HISTORY_CHANNEL_ID')
DEV_CHANNEL_ID = os.getenv('DEV_CHANNEL_ID')

LOG_IGNORE_PATTERNS = [
    'Connection reset by peer',
    'RemoteDisconnected',
    'over capacity',
    'Application instance',
    'took too long to shut down',
]

# --- History Parser Config (Main Account) ---
KINOPUB_LOGIN = os.getenv('KINOPUB_LOGIN')
KINOPUB_PASSWORD = os.getenv('KINOPUB_PASSWORD')
SITE_URL = os.getenv('SITE_URL')

# --- Auxiliary Account Config (For aggressive tasks) ---
KINOPUB_AUX_LOGIN = os.getenv('KINOPUB_AUX_LOGIN')
KINOPUB_AUX_PASSWORD = os.getenv('KINOPUB_AUX_PASSWORD')
SITE_AUX_URL = os.getenv('SITE_AUX_URL')

POSTER_BASE_URL = os.getenv('POSTER_BASE_URL', 'https://google.com/')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
POISKKINO_API_KEY = os.getenv('POISKKINO_API_KEY')

# --- App Core Config ---
_hostname = socket.gethostname()

REGEX_CODE = r'\d{6}'
CODE_LIFETIME_MINUTES = 15
_heartbeat_base = os.getenv('HEARTBEAT_FILE', str(data_dir / 'heartbeat'))
HEARTBEAT_FILE = f'{_heartbeat_base}_{_hostname}'
HEARTBEAT_DIR = Path(_heartbeat_base).parent
REQUEST_TIMEOUT = 10
IMAP_TIMEOUT = 30
IDLE_TIMEOUT = 25
MAX_RETRIES = 5
RECONNECT_DELAY = 15
EXPIRATION_CHECK_INTERVAL_SECONDS = 20
LOG_RETENTION_DAYS = 90
LOG_DELETION_INTERVAL_HOURS = 24

# --- Full Catalog Scan Config ---
FULL_SCAN_PAGE_DELAY_SECONDS = 1
FULL_SCAN_RESUME_WINDOW_HOURS = 24

# --- Logging ---
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] %(module)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'database': {
            'class': 'app.log_handler.DatabaseLogHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'database'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'database'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'database'],
            'level': 'WARNING',
            'propagate': False,
        },
        'app': {
            'handlers': ['console', 'database'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}


class MultiSchedule:
    def __init__(self, *schedules):
        self.schedules = schedules

    def is_due(self, last_run_at):
        due_results = []
        delays = []
        for s in self.schedules:
            if s is None:
                continue
            is_due, delay = s.is_due(last_run_at)
            due_results.append(is_due)
            delays.append(delay)
        return any(due_results), min(delays)

    def remaining_estimate(self, last_run_at):
        return min(s.remaining_estimate(last_run_at) for s in self.schedules if s is not None)

    def now(self):
        return self.schedules[0].now()

    def __repr__(self):
        return ' | '.join(repr(s) for s in self.schedules)


CELERY_TASK_ROUTES = {
    'app.tasks.update_site_metrics_task': {'queue': 'metrics'},
    'app.tasks.fetch_person_photos_task': {'queue': 'metrics'},
}

CELERY_BEAT_SCHEDULE = {
    'expire_codes': {
        'task': 'app.tasks.expire_codes_task',
        'schedule': crontab(),  # Каждую минуту
    },
    'cleanup_old_data': {
        'task': 'app.tasks.cleanup_old_data_task',
        'schedule': crontab(minute=0, hour=0),  # every 24 hours
    },
    'process_queues': {
        'task': 'app.tasks.process_queues_task',
        'schedule': crontab(minute='*/15'),  # Каждые 15 минут
    },
    'process_errors': {
        'task': 'app.tasks.process_errors_task',
        'schedule': crontab(minute='*/1'),  # Проверяем каждую минуту (отправка раз в 10 мин)
    },
    'update_site_metrics': {
        'task': 'app.tasks.update_site_metrics_task',
        'schedule': crontab(minute=0, hour=0),  # every 24 hours
        'options': {'queue': 'metrics'},
    },
    'auto_enqueue_missing_metadata': {
        'task': 'app.tasks.auto_enqueue_missing_metadata_task',
        'schedule': crontab(minute=0, hour=9),  # every 24 hours
    },
}

if ENVIRONMENT == 'PROD':
    CELERY_BEAT_SCHEDULE.update(
        {
            'run_history_parser': {
                'task': 'app.tasks.run_history_parser_task',
                'schedule': MultiSchedule(
                    crontab(minute=0, hour='0,5,7,11,14-23'), crontab(minute=30, hour='20-22')
                ),
            },
            'run_daily_sync': {
                'task': 'app.tasks.run_daily_sync_task',
                'schedule': crontab(minute=0, hour=4),
            },
            'run_gap_scanner': {
                'task': 'app.tasks.run_gap_scanner_task',
                'schedule': crontab(minute=0, hour=3, day_of_month='1'),
            },
            'fetch_person_photos': {
                'task': 'app.tasks.fetch_person_photos_task',
                'schedule': crontab(minute=15),
            },
            'sync_poiskkino_ratings': {
                'task': 'app.tasks.sync_poiskkino_ratings_task',
                'schedule': crontab(minute=0, hour=5),
            },
            'run_new_episodes': {
                'task': 'app.tasks.run_new_episodes_task',
                'schedule': crontab(minute=20, hour='8-21'),
            },
        }
    )


# --- Config Validation ---
REQUIRED_SETTINGS = (
    'GMAIL_EMAIL',
    'GMAIL_PASSWORD',
    'BOT_TOKEN',
    'CODES_CHANNEL_ID',
    'ALLOWED_SENDER',
    'GOOGLE_DRIVE_CREDENTIALS_JSON',
    'KINOPUB_LOGIN',
    'KINOPUB_PASSWORD',
)

missing_settings = [key for key in REQUIRED_SETTINGS if not globals().get(key)]
if missing_settings:
    raise ImproperlyConfigured(
        f'Missing required environment variables: {", ".join(missing_settings)}'
    )

logging.info('Configuration validated successfully.')
