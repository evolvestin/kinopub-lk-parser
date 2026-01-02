import hashlib
import json
import logging
import time

from django.conf import settings
from redis import Redis


class ErrorAggregator:
    REDIS_KEY_QUEUE = 'queue:errors'
    REDIS_KEY_LAST_SENT = 'errors:last_sent'
    REDIS_PREFIX_DEDUP = 'dedup:error:'

    # Конфигурация
    DEDUP_TTL = 3 * 60 * 60  # 3 часа
    BATCH_INTERVAL = 10 * 60  # 10 минут
    BATCH_SIZE = 50

    def __init__(self):
        self.redis = Redis.from_url(settings.CELERY_BROKER_URL)

    def _get_hash(self, message: str, traceback: str | None) -> str:
        content = f'{message}:{traceback or ""}'
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def push_error(self, level: str, module: str, message: str, traceback: str | None = None):
        """
        Добавляет ошибку в очередь, если она не была залогирована в последние 3 часа.
        """
        error_hash = self._get_hash(message, traceback)
        dedup_key = f'{self.REDIS_PREFIX_DEDUP}{error_hash}'

        if self.redis.get(dedup_key):
            return

        # Блокируем этот хэш на 3 часа
        self.redis.setex(dedup_key, self.DEDUP_TTL, 1)

        payload = {
            'level': level,
            'module': module,
            'message': message,
            'traceback': traceback,
            'timestamp': time.time(),
        }

        try:
            self.redis.rpush(self.REDIS_KEY_QUEUE, json.dumps(payload))
        except Exception as e:
            logging.error(f'Failed to push error to Redis: {e}')

    def get_batch_to_send(self) -> list[dict] | None:
        """
        Возвращает список ошибок для отправки, если прошел интервал отправки.
        """
        now = time.time()
        last_sent = self.redis.get(self.REDIS_KEY_LAST_SENT)

        if last_sent:
            time_passed = now - float(last_sent)
            if time_passed < self.BATCH_INTERVAL:
                return None

        # Проверяем наличие элементов
        queue_len = self.redis.llen(self.REDIS_KEY_QUEUE)
        if queue_len == 0:
            return None

        # Забираем пачку
        # lpop удаляет элементы, transaction здесь не критична (потеря логов допустима при краше)
        raw_items = self.redis.lpop(self.REDIS_KEY_QUEUE, count=self.BATCH_SIZE)

        if not raw_items:
            return None

        items = []
        for raw in raw_items:
            try:
                items.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

        # Обновляем время отправки
        self.redis.set(self.REDIS_KEY_LAST_SENT, now)

        return items
