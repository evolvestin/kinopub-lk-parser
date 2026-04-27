import os
import shutil
import time
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from redis import Redis

from app.models import (
    ExternalRating,
    LogEntry,
    Person,
    Show,
    ShowDuration,
    TelegramLog,
    ViewHistory,
)
from app.services.metrics import (
    calculate_duplicate_photo_urls_metric,
    calculate_missing_durations_metric,
    calculate_missing_imdb_metric,
    calculate_missing_kp_metric,
    calculate_no_genres_metric,
    calculate_title_collision_metric,
    calculate_unused_persons_metric,
)
from kinopub_parser import celery_app


class Command(BaseCommand):
    help = 'Gathers live critical metrics and container statuses, and sends a report to Telegram.'

    def handle(self, *args, **options):
        bot_token = settings.BOT_TOKEN
        chat_id = settings.DEV_CHANNEL_ID

        if not bot_token or not chat_id:
            self.stdout.write(self.style.ERROR('BOT_TOKEN or DEV_CHANNEL_ID is not configured.'))
            return

        now = timezone.now()
        is_critical = False
        has_warnings = False
        metrics_lines = []

        def _get_latest_dt(qs, field):
            res = qs.order_by(f'-{field}').values_list(field, flat=True).first()
            if res:
                if isinstance(res, datetime):
                    return res
                return timezone.make_aware(datetime.combine(res, datetime.min.time()))
            return None

        def _check_delay(dt, limit_hours, label, critical=True):
            nonlocal is_critical, has_warnings
            if not dt:
                if critical:
                    is_critical = True
                    metrics_lines.append(f'🔴 {label}: <b>Нет данных</b>')
                else:
                    has_warnings = True
                    metrics_lines.append(f'🟡 {label}: <b>Нет данных</b>')
                return

            diff = now - dt
            if diff > timedelta(hours=limit_hours):
                dt_str = timezone.localtime(dt).strftime('%d.%m.%Y %H:%M')
                if critical:
                    is_critical = True
                    metrics_lines.append(f'🔴 {label}: <b>{dt_str}</b>')
                else:
                    has_warnings = True
                    metrics_lines.append(f'🟡 {label}: <b>{dt_str}</b>')

        _check_delay(
            _get_latest_dt(ViewHistory.objects.all(), 'view_date'), 168, 'Последний просмотр'
        )

        parser_log = (
            LogEntry.objects.filter(message__contains='Parser session finished')
            .order_by('-created_at')
            .first()
        )
        _check_delay(parser_log.created_at if parser_log else None, 10, 'Запуск парсера')

        _check_delay(_get_latest_dt(Show.objects.all(), 'created_at'), 168, 'Новые релизы')
        _check_delay(
            _get_latest_dt(ExternalRating.objects.all(), 'updated_at'),
            24,
            'Рейтинги (KP/IMDb)',
            False,
        )
        _check_delay(
            _get_latest_dt(ShowDuration.objects.all(), 'updated_at'), 24, 'Хронометраж', False
        )
        _check_delay(
            _get_latest_dt(Person.objects.filter(is_photo_fetched=True), 'updated_at'),
            24,
            'Фото персон',
            False,
        )
        _check_delay(
            _get_latest_dt(TelegramLog.objects.all(), 'created_at'),
            24,
            'Активность Telegram',
            False,
        )

        err_24 = LogEntry.objects.filter(
            created_at__gte=now - timedelta(days=1), level__in=['ERROR', 'CRITICAL']
        ).count()
        if err_24 > 0:
            has_warnings = True
            metrics_lines.append(f'• Ошибки (24ч): <b>{err_24}</b>')

        try:
            data_checks = [
                ('Нет рейтинга KP', calculate_missing_kp_metric, 'value'),
                ('Нет рейтинга IMDb', calculate_missing_imdb_metric, 'value'),
                ('Коллизии названий', calculate_title_collision_metric, 'collisions'),
                ('Длительность не указана', calculate_missing_durations_metric, 'value'),
                ('Нет жанров', calculate_no_genres_metric, 'value'),
                ('Одинаковые фото (дубли)', calculate_duplicate_photo_urls_metric, 'value'),
                ('Балласт', calculate_unused_persons_metric, 'value'),
            ]
            for label, func, sum_key in data_checks:
                total = sum(item.get(sum_key, 0) for item in func())
                if total > 0:
                    metrics_lines.append(f'• {label}: <b>{total}</b>')
                    has_warnings = True
        except Exception as e:
            metrics_lines.append(f'⚠️ Ошибка сбора метрик: {e}')

        components_lines = ['\n<b>Статусы:</b>']
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT pg_size_pretty(pg_database_size(current_database())), '
                    '(SELECT count(*) FROM pg_stat_activity);'
                )
                db_size, conn_count = cursor.fetchone()
            components_lines.append(f'✅ Database: <b>OK</b> ({db_size}, {conn_count} conn)')
        except Exception as e:
            is_critical = True
            components_lines.append(f'❌ Database: <b>Error</b> ({str(e)[:30]})')

        r = None
        try:
            r = Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=3)
            q_det = r.scard('queue:update_details')
            q_dur = r.scard('queue:update_durations')
            q_def = r.llen('celery')
            components_lines.append(f'✅ Redis/Queue: <b>OK</b> (Q: {q_det}/{q_dur}/{q_def})')
        except Exception as e:
            is_critical = True
            components_lines.append(f'❌ Redis/Queue: <b>Error</b> ({str(e)[:30]})')

        try:
            inspect = celery_app.control.inspect(timeout=5)
            ping = inspect.ping()
            worker_count = len(ping) if ping else 0
            if worker_count > 0:
                components_lines.append(f'✅ Celery: <b>OK</b> ({worker_count} active)')
            else:
                is_critical = True
                components_lines.append('❌ Celery: <b>No workers</b>')
        except Exception:
            is_critical = True
            components_lines.append('❌ Celery: <b>Inaccessible</b>')

        try:
            heartbeat_dir = settings.HEARTBEAT_DIR
            hb_files = list(heartbeat_dir.glob('heartbeat_*'))

            if not hb_files:
                has_warnings = True
                components_lines.append('⚠️ Heartbeat: <b>No services detected</b>')
            else:
                stale_services = []
                active_count = 0
                for hb_file in hb_files:
                    age = time.time() - os.path.getmtime(hb_file)
                    service_name = hb_file.name.replace('heartbeat_', '')
                    if age > 600:
                        stale_services.append(service_name)
                    else:
                        active_count += 1

                if stale_services:
                    has_warnings = True
                    list_str = ', '.join(stale_services)
                    components_lines.append(
                        f'⚠️ Heartbeat: <b>{active_count} OK, '
                        f'{len(stale_services)} STALE</b> ({list_str})'
                    )
                else:
                    components_lines.append(
                        f'✅ Heartbeat: <b>OK</b> ({active_count} services active)'
                    )
        except Exception as e:
            components_lines.append(f'⚠️ Heartbeat: <b>Error scanning dir</b> ({str(e)[:20]})')

        try:
            total, used, free = shutil.disk_usage('/data')
            percent = (used / total) * 100
            components_lines.append(
                f'✅ Storage: <b>OK</b> ({free // (2**30)}GB free, {percent:.1f}% used)'
            )
        except Exception:
            is_critical = True
            components_lines.append('❌ Storage: <b>Access Error</b>')

        if is_critical:
            main_status = '🔴'
        elif has_warnings:
            main_status = '🟡'
        else:
            main_status = '🟢'

        report_parts = []
        if metrics_lines:
            report_parts.append(f'{main_status} <b>Метрики:</b>')
            report_parts.extend(metrics_lines)
        else:
            report_parts.append('✨ Все показатели в норме')

        report_parts.extend(components_lines)
        message_text = '\n'.join(report_parts)

        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        try:
            resp = requests.post(
                url,
                json={'chat_id': chat_id, 'text': message_text, 'parse_mode': 'HTML'},
                timeout=15,
            )
            resp.raise_for_status()
            self.stdout.write(self.style.SUCCESS('Health report sent successfully.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to send report: {e}'))
