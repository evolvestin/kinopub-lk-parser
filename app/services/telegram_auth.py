import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from django.conf import settings


def validate_telegram_init_data(init_data: str) -> dict | None:
    if not settings.BOT_TOKEN:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data))
        hash_received = parsed_data.pop('hash', None)

        if not hash_received:
            return None

        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(parsed_data.items()))

        secret_key = hmac.new(
            key=b'WebAppData', msg=settings.BOT_TOKEN.encode('utf-8'), digestmod=hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            key=secret_key, msg=data_check_string.encode('utf-8'), digestmod=hashlib.sha256
        ).hexdigest()

        if calculated_hash != hash_received:
            return None

        user_data = parsed_data.get('user')
        if user_data:
            return json.loads(user_data)
        return None

    except Exception:
        return None
