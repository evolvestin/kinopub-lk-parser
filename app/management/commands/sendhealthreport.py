import logging
import os
import re
import shutil
import time
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.db import connection
from django.utils import timezone
from redis import Redis

from app.management.base import LoggableBaseCommand
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
    calculate_missing_country_meta_metric,
    calculate_missing_durations_metric,
    calculate_missing_imdb_metric,
    calculate_missing_kp_metric,
    calculate_missing_status_metric,
    calculate_missing_year_metric,
    calculate_no_countries_metric,
    calculate_no_genres_metric,
    calculate_title_collision_metric,
    calculate_unmapped_genres_metric,
    calculate_unused_persons_metric,
)
from kinopub_parser import celery_app
from shared.constants import RedisQueue
from shared.html_helper import html_secure

logger = logging.getLogger(__name__)


def _send_telegram_report(bot_token: str, chat_id: str, message_text: str) -> bool:
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    max_retries = 5

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                json={'chat_id': chat_id, 'text': message_text, 'parse_mode': 'HTML'},
                timeout=15,
            )
            if response.status_code == 200:
                return True

            if response.status_code == 400 and 'parse' in response.text.lower():
                plain_text = re.sub(r'<[^>]*>', '', message_text)
                fallback_resp = requests.post(
                    url,
                    json={'chat_id': chat_id, 'text': plain_text},
                    timeout=15,
                )
                if fallback_resp.status_code == 200:
                    return True

            logger.warning(
                f'Attempt {attempt}/{max_retries} to send report failed. '
                f'Status: {response.status_code}, Response: {response.text}'
            )
        except Exception as e:
            logger.warning(f'Attempt {attempt}/{max_retries} network error sending report: {e}')

        if attempt < max_retries:
            time.sleep(2 * attempt)

    return False


class Command(LoggableBaseCommand):
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
            try:
                res = qs.order_by(f'-{field}').values_list(field, flat=True).first()
                if res:
                    if isinstance(res, datetime):
                        return res
                    return timezone.make_aware(datetime.combine(res, datetime.min.time()))
            except Exception as e:
                logger.error(f'Error getting latest date for {field}: {e}')
            return None

        def _check_delay(dt, limit_hours, label, critical=True):
            nonlocal is_critical, has_warnings
            safe_label = html_secure(label)
            if not dt:
                if critical:
                    is_critical = True
                    metrics_lines.append(f'🔴 {safe_label}: <b>Нет данных</b>')
                else:
                    has_warnings = True
                    metrics_lines.append(f'🟡 {safe_label}: <b>Нет данных</b>')
                return

            diff = now - dt
            if diff > timedelta(hours=limit_hours):
                dt_str = timezone.localtime(dt).strftime('%d.%m.%Y %H:%M')
                if critical:
                    is_critical = True
                    metrics_lines.append(f'🔴 {safe_label}: <b>{dt_str}</b>')
                else:
                    has_warnings = True
                    metrics_lines.append(f'🟡 {safe_label}: <b>{dt_str}</b>')

        _check_delay(
            _get_latest_dt(ViewHistory.objects.all(), 'view_date'), 168, 'Последний просмотр'
        )

        try:
            parser_log = (
                LogEntry.objects.filter(message__contains='Parser session finished')
                .order_by('-created_at')
                .first()
            )
            _check_delay(parser_log.created_at if parser_log else None, 10, 'Запуск парсера')
        except Exception as e:
            metrics_lines.append(f'⚠️ Ошибка получения логов парсера: {html_secure(e)}')

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

        try:
            err_24 = LogEntry.objects.filter(
                created_at__gte=now - timedelta(days=1), level__in=['ERROR', 'CRITICAL']
            ).count()
            if err_24 > 0:
                has_warnings = True
                metrics_lines.append(f'• Ошибки (24ч): <b>{err_24}</b>')
        except Exception as e:
            metrics_lines.append(f'⚠️ Ошибка подсчета ошибок: {html_secure(e)}')

        data_checks = [
            ('Нет рейтинга KP', calculate_missing_kp_metric, 'value'),
            ('Нет рейтинга IMDb', calculate_missing_imdb_metric, 'value'),
            ('Коллизии названий', calculate_title_collision_metric, 'collisions'),
            ('KinoPub без года', calculate_missing_year_metric, 'value'),
            ('KinoPub без статуса', calculate_missing_status_metric, 'value'),
            ('KinoPub без хронометража', calculate_missing_durations_metric, 'value'),
            ('KinoPub без жанров', calculate_no_genres_metric, 'value'),
            ('Нераспознанные жанры', calculate_unmapped_genres_metric, 'value'),
            ('KinoPub без стран', calculate_no_countries_metric, 'value'),
            ('Страны без ISO', calculate_missing_country_meta_metric, 'value'),
            ('Одинаковые фото (дубли)', calculate_duplicate_photo_urls_metric, 'value'),
            ('Персоны без ролей', calculate_unused_persons_metric, 'value'),
        ]

        for label, func, sum_key in data_checks:
            try:
                total = sum(item.get(sum_key, 0) for item in func())
                if total > 0:
                    metrics_lines.append(f'• {html_secure(label)}: <b>{total}</b>')
                    has_warnings = True
            except Exception as e:
                metrics_lines.append(f'⚠️ Ошибка метрики {html_secure(label)}: {html_secure(e)}')

        components_lines = ['\n<b>Статусы:</b>']

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT pg_size_pretty(pg_database_size(current_database())), '
                    '(SELECT count(*) FROM pg_stat_activity);'
                )
                db_size, conn_count = cursor.fetchone()
            components_lines.append(
                f'✅ Database: <b>OK</b> ({html_secure(db_size)}, {conn_count} conn)'
            )
        except Exception as e:
            is_critical = True
            components_lines.append(f'❌ Database: <b>Error</b> ({html_secure(str(e)[:30])})')

        try:
            r = Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=3)
            q_det = r.scard(RedisQueue.UPDATE_DETAILS)
            q_dur = r.scard(RedisQueue.UPDATE_DURATIONS)
            q_def = r.llen('celery')
            components_lines.append(f'✅ Redis/Queue: <b>OK</b> (Q: {q_det}/{q_dur}/{q_def})')
        except Exception as e:
            is_critical = True
            components_lines.append(f'❌ Redis/Queue: <b>Error</b> ({html_secure(str(e)[:30])})')

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
                deleted_count = 0

                for hb_file in hb_files:
                    age = time.time() - os.path.getmtime(hb_file)
                    service_name = hb_file.name.replace('heartbeat_', '')

                    if age > 3600:
                        try:
                            hb_file.unlink(missing_ok=True)
                            deleted_count += 1
                        except Exception:
                            pass
                        continue

                    if age > 600:
                        stale_services.append(service_name)
                    else:
                        active_count += 1

                if stale_services:
                    has_warnings = True
                    list_str = ', '.join(stale_services)
                    components_lines.append(
                        f'⚠️ Heartbeat: <b>{active_count} OK, '
                        f'{len(stale_services)} STALE</b> ({html_secure(list_str)})'
                    )
                else:
                    msg = f'✅ Heartbeat: <b>OK</b> ({active_count} services active)'
                    if deleted_count > 0:
                        msg += f' <small>(cleaned {deleted_count} ghost files)</small>'
                    components_lines.append(msg)
        except Exception as e:
            components_lines.append(
                f'⚠️ Heartbeat: <b>Error scanning dir</b> ({html_secure(str(e)[:20])})'
            )

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

        success = _send_telegram_report(bot_token, chat_id, message_text)
        if success:
            self.stdout.write(self.style.SUCCESS('Health report sent successfully.'))
        else:
            self.stdout.write(self.style.ERROR('Failed to send health report after retries.'))
