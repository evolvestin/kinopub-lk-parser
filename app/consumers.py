import asyncio
import json

import websockets
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from django.core.cache import cache

from app.utils import get_scheduled_tasks_info
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
        logs = list(LogEntry.objects.all().order_by('-created_at')[:50])
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
        await self.send(text_data=json.dumps({'type': 'connected'}))

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


class ViteHMRConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vite_ws = None
        self.proxy_task = None

    async def connect(self):
        requested_protocols = self.scope.get('subprotocols', [])

        if await cache.aget('vite_frontend_alive') is False:
            await self.close()
            return

        try:
            self.vite_ws = await websockets.connect(
                'ws://frontend:5173/__vite__/hmr',
                subprotocols=requested_protocols,
                open_timeout=1.0,
            )

            await self.accept(subprotocol=self.vite_ws.subprotocol)

            self.proxy_task = asyncio.create_task(self._forward_vite_to_client())
        except Exception as e:
            print(f'[ViteHMR] Connection to Vite failed: {e}')
            await cache.aset('vite_frontend_alive', False, timeout=10)
            await self.close()

    async def disconnect(self, close_code):
        if self.proxy_task:
            self.proxy_task.cancel()
        if self.vite_ws:
            await self.vite_ws.close()

    async def receive(self, text_data=None, bytes_data=None):
        if self.vite_ws:
            await self.vite_ws.send(text_data or bytes_data)

    async def _forward_vite_to_client(self):
        try:
            async for message in self.vite_ws:
                await self.send(
                    text_data=message if isinstance(message, str) else None,
                    bytes_data=message if isinstance(message, bytes) else None,
                )
        except Exception:
            await self.close()
