import os
import logging

GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
ALLOWED_SENDER = os.getenv('ALLOWED_SENDER')
IMAP_HOST = 'imap.gmail.com'
IMAP_FOLDER = 'INBOX'
MARK_AS_SEEN = False

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

REGEX_CODE = r'\d{6}'
CODE_LIFETIME_MINUTES = 15
HEARTBEAT_FILE = '/tmp/kinopub-parser_heartbeat'
DB_PATH = '/data/codes.db'

REQUEST_TIMEOUT = 10
IMAP_TIMEOUT = 30
IDLE_TIMEOUT = 25
MAX_RETRIES = 5
RECONNECT_DELAY = 15
EXPIRATION_CHECK_INTERVAL_SECONDS = 10


LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


def validate_config():
    """Validates the presence of all required environment variables."""
    missing = [key for key in ('GMAIL_EMAIL', 'GMAIL_PASSWORD', 'BOT_TOKEN', 'CHAT_ID', 'ALLOWED_SENDER') if
               not globals()[key]]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    logging.info("Configuration validated successfully.")
