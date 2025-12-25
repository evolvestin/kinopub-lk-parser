import logging
import os
import sys
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

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

LOCAL_RUN = False
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-for-dev')
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8012',
    'http://127.0.0.1:8012',
    'https://kinopub.webredirect.org',
]

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
    'app',
    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kinopub_parser.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
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

STATICFILES_DIRS = []
static_src = BASE_DIR / 'kinopub_parser' / 'static'
if static_src.exists():
    STATICFILES_DIRS.append(static_src)

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
    WEBSOCKET_URL = 'ws://127.0.0.1:8013/ws/logs/'
    WEBSOCKET_PORT = 8013
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
BOT_TOKEN = os.getenv('BOT_TOKEN')
CODES_CHANNEL_ID = os.getenv('CODES_CHANNEL_ID')
USER_MANAGEMENT_CHANNEL_ID = os.getenv('USER_MANAGEMENT_CHANNEL_ID')
HISTORY_CHANNEL_ID = os.getenv('HISTORY_CHANNEL_ID')

# --- History Parser Config (Main Account) ---
KINOPUB_LOGIN = os.getenv('KINOPUB_LOGIN')
KINOPUB_PASSWORD = os.getenv('KINOPUB_PASSWORD')
SITE_URL = os.getenv('SITE_URL')

# --- Auxiliary Account Config (For aggressive tasks) ---
KINOPUB_AUX_LOGIN = os.getenv('KINOPUB_AUX_LOGIN')
KINOPUB_AUX_PASSWORD = os.getenv('KINOPUB_AUX_PASSWORD')
SITE_AUX_URL = os.getenv('SITE_AUX_URL')
HISTORY_PARSER_INTERVAL_HOURS = int(os.getenv('HISTORY_PARSER_INTERVAL_HOURS', 6))

# --- App Core Config ---
REGEX_CODE = r'\d{6}'
CODE_LIFETIME_MINUTES = 15
HEARTBEAT_FILE = '/tmp/kinopub-parser_heartbeat'
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

CELERY_BEAT_SCHEDULE = {
    'expire_codes': {
        'task': 'app.tasks.expire_codes_task',
        'schedule': crontab(),  # Каждую минуту в :00 секунд
    },
    'delete_old_logs': {
        'task': 'app.tasks.delete_old_logs_task',
        'schedule': crontab(minute=0, hour=0),  # every 24 hours
    },
}

if ENVIRONMENT == 'PROD':
    CELERY_BEAT_SCHEDULE.update(
        {
            'run_history_parser': {
                'task': 'app.tasks.run_history_parser_task',
                'schedule': crontab(minute=0, hour=f'*/{HISTORY_PARSER_INTERVAL_HOURS}'),
            },
            'run_daily_sync': {
                'task': 'app.tasks.run_daily_sync_task',
                'schedule': crontab(minute=0, hour=4),  # every 24 hours
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
