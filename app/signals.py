import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import Signal, receiver
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from celery.signals import task_postrun, task_prerun

from app.models import ViewUser, ViewHistory, TaskRun
from app.telegram_bot import TelegramSender
from shared.constants import DATETIME_FORMAT

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
            last_view = (
                sender.objects.filter(show=instance.show, users__isnull=False)
                .exclude(id=instance.id)
                .order_by('-view_date', '-season_number', '-episode_number')
                .first()
            )

            if last_view:
                instance.users.set(last_view.users.all())

        sender_service.send_history_notification(instance)

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

    except Exception as e:
        logging.error(f'Failed to handle new view history signal: {e}')


@receiver(post_save, sender=TaskRun)
def task_run_update(sender, instance, created, **kwargs):
    """Отправляет обновление статуса задачи через WebSocket."""
    channel_layer = get_channel_layer()
    if channel_layer:
        # Для форматирования времени используем ту же логику, что и везде
        created_str = instance.created_at.strftime(DATETIME_FORMAT)
        
        async_to_sync(channel_layer.group_send)(
            "logs",
            {
                "type": "task_update",
                "id": instance.id,
                "command": instance.command,
                "arguments": instance.arguments or '-',
                "status": instance.status,
                "status_display": instance.get_status_display(),
                "created_at": created_str,
            }
        )


@receiver(task_postrun)
def notify_schedule_update(sender, **kwargs):
    """
    Отправляет уведомление в WebSocket при завершении любой задачи Celery.
    Это заставляет фронтенд обновить таблицу расписания.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "logs",
                {"type": "schedule_changed"}
            )
    except Exception as e:
        logging.warning(f"Failed to send schedule update signal: {e}")


@receiver(task_prerun)
def record_task_start(sender, **kwargs):
    """Запоминаем точное время ЗАПУСКА задачи."""
    try:
        if hasattr(sender, 'name') and sender.name:
            # Сохраняем время старта с ключом, равным имени задачи (напр. app.tasks.expire_codes_task)
            cache.set(f'last_run_{sender.name}', timezone.now(), timeout=None)
            
            # Сразу обновляем интерфейс, чтобы таймер сбросился в начале выполнения
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "logs",
                    {"type": "schedule_changed"}
                )
    except Exception:
        pass

@receiver(task_postrun)
def notify_schedule_update(sender, **kwargs):
    # Оставляем уведомление по завершении для обновления статусов
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "logs",
                {"type": "schedule_changed"}
            )
    except Exception:
        pass