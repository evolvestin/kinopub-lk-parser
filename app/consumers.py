import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps

from app.dashboard import get_scheduled_tasks_info  # Импорт общей функции
from shared.constants import DATETIME_FORMAT


class LogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('logs', self.channel_name)
        await self.accept()
        await self.send_recent_logs()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('logs', self.channel_name)

    async def log_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def task_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def schedule_changed(self, event):
        # Теперь мы не просто пингуем, а собираем и отправляем данные
        dashboard_data = await self.get_dashboard_payload()
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'schedule_data_update',
                    'schedule': dashboard_data['schedule'],
                    'history': dashboard_data['history'],
                }
            )
        )

    @database_sync_to_async
    def get_recent_logs(self):
        LogEntry = apps.get_model('app', 'LogEntry')
        logs = LogEntry.objects.all().order_by('-created_at')[:50]
        return list(reversed(logs))

    @database_sync_to_async
    def get_dashboard_payload(self):
        TaskRun = apps.get_model('app', 'TaskRun')

        # 1. История задач
        recent_tasks = TaskRun.objects.all()[:10]
        history_data = [
            {
                'id': t.id,
                'created_at': t.created_at.strftime(DATETIME_FORMAT),
                'command': t.command,
                'arguments': t.arguments or '-',
                'status': t.status,
                'status_display': t.get_status_display(),
            }
            for t in recent_tasks
        ]

        # 2. Расписание (теперь через общую функцию)
        scheduled_tasks = get_scheduled_tasks_info()

        return {'history': history_data, 'schedule': scheduled_tasks}

    async def send_recent_logs(self):
        recent_logs = await self.get_recent_logs()
        for log in recent_logs:
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'log_message',
                        'created_at': log.created_at.strftime('%H:%M:%S'),
                        'level': log.level,
                        'module': log.module,
                        'message': log.message,
                    }
                )
            )
