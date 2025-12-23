import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.apps import apps

class LogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("logs", self.channel_name)
        await self.accept()
        # Отправляем последние логи при подключении
        await self.send_recent_logs()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("logs", self.channel_name)

    async def log_message(self, event):
        # Отправка нового лога клиенту
        await self.send(text_data=json.dumps(event))

    async def task_update(self, event):
        # Отправка обновления статуса задачи клиенту
        await self.send(text_data=json.dumps(event))

    async def schedule_changed(self, event):
        # Уведомление об изменении расписания (запуск периодической задачи)
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_recent_logs(self):
        # Используем apps.get_model для получения модели (стандартный механизм Django для lazy loading),
        # чтобы избежать ошибки AppRegistryNotReady при раннем импорте consumers.py
        LogEntry = apps.get_model('app', 'LogEntry')
        
        # Получаем последние 50 записей
        logs = LogEntry.objects.all().order_by('-created_at')[:50]
        return list(reversed(logs))

    async def send_recent_logs(self):
        recent_logs = await self.get_recent_logs()
        for log in recent_logs:
            await self.send(text_data=json.dumps({
                'type': 'log_message',
                'created_at': log.created_at.strftime('%H:%M:%S'),
                'level': log.level,
                'module': log.module,
                'message': log.message
            }))