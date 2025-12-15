import logging

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from app.models import ViewUser
from app.telegram_bot import TelegramSender
from datetime import timedelta

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
    try:
        sender_service = TelegramSender()

        if not instance.users.exists():
            last_view = sender.objects.filter(
                show=instance.show,
                users__isnull=False
            ).exclude(id=instance.id).order_by('-view_date', '-season_number', '-episode_number').first()

            if last_view:
                instance.users.set(last_view.users.all())

        for user in instance.users.all():
            if user.telegram_id:
                sender_service.send_private_history_notification(user.telegram_id, instance)

        six_months_ago = instance.view_date - timedelta(days=180)

        older_duplicates = sender.objects.filter(
            show=instance.show,
            season_number=instance.season_number,
            episode_number=instance.episode_number,
            view_date__lt=instance.view_date,
            view_date__gte=six_months_ago,
            is_checked=True,
        )

        current_users_set = set(instance.users.values_list('id', flat=True))

        for old_view in older_duplicates:
            old_users_set = set(old_view.users.values_list('id', flat=True))
            
            if current_users_set == old_users_set:
                old_view.is_checked = False
                old_view.save(update_fields=['is_checked'])
                sender_service.update_history_message(old_view)

        sender_service.send_history_notification(instance)

    except Exception as e:
        logging.error(f'Failed to handle new view history signal: {e}')