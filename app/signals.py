from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

from app.models import ViewUser
from app.telegram_bot import TelegramSender


@receiver(post_delete, sender=ViewUser)
def delete_view_user_message(sender, instance, **kwargs):
    """
    Удаляет сообщение в Telegram при удалении ViewUser.
    Срабатывает при:
    1. ViewUser.delete()
    2. User.delete() -> CASCADE -> ViewUser delete
    """
    if instance.role_message_id:
        try:
            if settings.USER_MANAGEMENT_CHANNEL_ID:
                TelegramSender().delete_message(
                    settings.USER_MANAGEMENT_CHANNEL_ID,
                    instance.role_message_id
                )
        except Exception:
            pass