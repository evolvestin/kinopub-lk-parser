import logging

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from app.models import ViewHistory, ViewUser
from app.telegram_bot import TelegramSender

# Определение кастомного сигнала для создания записи просмотра
view_history_created = Signal()


@receiver(post_delete, sender=ViewUser)
def delete_view_user_message(sender, instance, **kwargs):
    """
    Удаляет сообщение в Telegram при удалении ViewUser.
    """
    if instance.role_message_id:
        try:
            if settings.USER_MANAGEMENT_CHANNEL_ID:
                TelegramSender().delete_message(
                    settings.USER_MANAGEMENT_CHANNEL_ID, instance.role_message_id
                )
        except Exception:
            pass


@receiver(view_history_created)
def handle_new_view_history(sender, instance, **kwargs):
    """
    Обработчик нового просмотра.
    Здесь находится логика уведомлений и в будущем будет логика привязки пользователя.
    """
    try:
        # 1. Отправка уведомления в общий канал истории
        TelegramSender().send_history_notification(instance)
        
        # 2. Здесь можно добавить логику определения пользователя:
        # user = determine_user_for_view(instance)
        # if user:
        #     instance.users.add(user)
        #     notify_user_personally(user, instance)
        
    except Exception as e:
        logging.error(f'Failed to handle new view history signal: {e}')
