import logging
import traceback

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.utils import timezone

from app.telegram_bot import TelegramSender


class DatabaseLogHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_entry_model = None

    @property
    def log_entry_model(self):
        if self._log_entry_model is None:
            self._log_entry_model = apps.get_model('app', 'LogEntry')
        return self._log_entry_model

    def emit(self, record):
        try:
            now = timezone.now()
            msg = record.getMessage()

            tb_str = None
            if record.exc_info:
                # Формируем полный трейсбек в строку
                tb_str = ''.join(traceback.format_exception(*record.exc_info))

            self.log_entry_model.objects.create(
                level=record.levelname[:10],
                module=record.module[:100],
                message=msg,
                traceback=tb_str,
                created_at=now,
                updated_at=now,
            )

            # Отправка в WebSocket
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'logs',
                    {
                        'type': 'log_message',
                        'created_at': now.strftime('%H:%M:%S'),
                        'level': record.levelname,
                        'module': record.module,
                        'message': msg,
                    },
                )

            if record.levelno >= logging.ERROR:
                # Передаем также трейсбек
                TelegramSender().send_dev_log(
                    record.levelname, record.module, msg, traceback_str=tb_str
                )

        except Exception:
            self.handleError(record)
