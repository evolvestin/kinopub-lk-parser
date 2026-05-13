from django.urls import path

from app import consumers

websocket_urlpatterns = [
    path('', consumers.LogConsumer.as_asgi()),
    path('ws/logs/', consumers.LogConsumer.as_asgi()),
    # Используем явные пути без регулярных выражений для исключения ошибок сопоставления
    path('__vite__/hmr', consumers.ViteHMRConsumer.as_asgi()),
    path('vite/hmr', consumers.ViteHMRConsumer.as_asgi()),
]
