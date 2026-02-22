import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery.signals import task_postrun, task_prerun
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import Signal, receiver
from django.utils import timezone

from app.models import TaskRun, ViewHistory, ViewUser
from app.telegram_bot import TelegramSender
from shared.constants import DATETIME_FORMAT

view_history_created = Signal()


@receiver(post_delete, sender=ViewUser)
def delete_view_user_message(sender, instance, **kwargs):
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
    channel_layer = get_channel_layer()
    if channel_layer:
        created_str = instance.created_at.strftime(DATETIME_FORMAT)

        async_to_sync(channel_layer.group_send)(
            'logs',
            {
                'type': 'task_update',
                'id': instance.id,
                'command': instance.command,
                'arguments': instance.arguments or '-',
                'status': instance.status,
                'status_display': instance.get_status_display(),
                'created_at': created_str,
            },
        )


@receiver(task_postrun)
def notify_schedule_update(sender, **kwargs):
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)('logs', {'type': 'schedule_changed'})
    except Exception as e:
        logging.warning(f'Failed to send schedule update signal: {e}')


@receiver(task_prerun)
def record_task_start(sender, **kwargs):
    try:
        # Пытаемся получить имя задачи (с учетом разных способов вызова)
        task_name = getattr(sender, 'name', None)
        if not task_name and hasattr(sender, 'request'):
            task_name = sender.request.task

        if task_name:
            cache.set(f'last_run_{task_name}', timezone.now(), timeout=None)
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)('logs', {'type': 'schedule_changed'})
    except Exception as e:
        # Логируем ошибку, чтобы она была видна в docker logs kinopub-parser-celery
        logging.error(f'Error in task_prerun signal: {e}')


@receiver(m2m_changed, sender=ViewHistory.users.through)
def invalidate_stats_on_user_change(sender, instance, action, pk_set, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        year = instance.view_date.year
        user_ids = set(pk_set) if pk_set else set()
        user_ids.update(instance.users.values_list('id', flat=True))

        for uid in user_ids:
            cache.delete(f'user_stats:{uid}:{year}')
            cache.delete(f'user_stats:{uid}:all')


@receiver(post_save, sender=ViewHistory)
def invalidate_stats_on_history_change(sender, instance, created, **kwargs):
    year = instance.view_date.year
    # Очищаем кэш для всех пользователей, привязанных к этой записи
    for user in instance.users.all():
        cache.delete(f'user_stats:{user.id}:{year}')
        cache.delete(f'user_stats:{user.id}:all')


@receiver(post_delete, sender=ViewHistory)
def invalidate_stats_on_history_delete(sender, instance, **kwargs):
    year = instance.view_date.year
    for user in instance.users.all():
        cache.delete(f'user_stats:{user.id}:{year}')
        cache.delete(f'user_stats:{user.id}:all')
