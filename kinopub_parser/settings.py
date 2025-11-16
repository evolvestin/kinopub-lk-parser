import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
if os.path.isdir('/data'):
    data_dir = Path('/data')
else:
    data_dir = BASE_DIR / 'data'
os.makedirs(data_dir, exist_ok=True)

COOKIES_FILE_PATH = data_dir / 'cookies.json'

# --- Google Drive Backup Config ---
GOOGLE_DRIVE_CREDENTIALS_JSON = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON')
GOOGLE_DRIVE_FOLDER_ID = '1mpco3I0v22hTklleYJkZZh0VNlhol9L3'
DB_BACKUP_FILENAME = os.getenv('DB_BACKUP_FILENAME', 'data.db')
COOKIES_BACKUP_FILENAME = os.getenv('COOKIES_BACKUP_FILENAME', 'cookies.json')

# --- Django Core Settings ---
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-for-dev')
DEBUG = False
ALLOWED_HOSTS = ['*']

TIME_ZONE = 'UTC'
USE_TZ = True
USE_I18N = True
FORMAT_MODULE_PATH = ['kinopub_parser.formats']
LANGUAGE_CODE = 'en'

# Application definition
INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
    'app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_PATH,
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# --- Celery Configuration ---
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# --- Email Processor & Telegram Bot Config ---
GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
ALLOWED_SENDER = os.getenv('ALLOWED_SENDER')
IMAP_HOST = 'imap.gmail.com'
IMAP_FOLDER = 'INBOX'
MARK_AS_SEEN = True
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# --- History Parser Config ---
KINOPUB_LOGIN = os.getenv('KINOPUB_LOGIN')
KINOPUB_PASSWORD = os.getenv('KINOPUB_PASSWORD')
SITE_URL = 'https://y52x.ddm.ovh/'
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
FULL_SCAN_PAGE_DELAY_SECONDS = 60
FULL_SCAN_RESUME_WINDOW_HOURS = 24

# --- Unfold ---
UNFOLD = {
    "SITE_TITLE": "KinoPub Parser",
    "SITE_HEADER": "KinoPub Parser",
    "SITE_BRAND": "KinoPub Parser",
    "WELCOME_SIGN": "Добро пожаловать в панель управления",
    "DASHBOARD_CALLBACK": "app.dashboard.dashboard_callback",
    "THEME": "dark",
}

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
}


# --- Config Validation ---
REQUIRED_SETTINGS = (
    'GMAIL_EMAIL',
    'GMAIL_PASSWORD',
    'BOT_TOKEN',
    'CHAT_ID',
    'ALLOWED_SENDER',
    'GOOGLE_DRIVE_CREDENTIALS_JSON',
    'KINOPUB_LOGIN',
    'KINOPUB_PASSWORD',
)

missing_settings = [key for key in REQUIRED_SETTINGS if not globals().get(key)]
if missing_settings:
    raise ImproperlyConfigured(
        f"Missing required environment variables: {', '.join(missing_settings)}"
    )

logging.info('Configuration validated successfully.')