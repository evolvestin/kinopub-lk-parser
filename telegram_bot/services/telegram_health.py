import asyncio
import logging
import time
from dataclasses import dataclass

import client


@dataclass(frozen=True)
class TelegramIncidentEvent:
    handled: bool
    level: str | None = None
    message: str | None = None


class TelegramPollingIncident:
    """Collapse a burst of Telegram polling failures into one tracked incident."""

    FAILURE_PREFIX = 'Failed to fetch updates - '
    RECOVERY_PREFIX = 'Connection established '

    def __init__(self, clock=None, report_interval=600):
        self.clock = clock or time.monotonic
        self.report_interval = report_interval
        self.started_at = None
        self.last_report_at = None
        self.failure_count = 0
        self.last_error = None

    def observe(self, message: str) -> TelegramIncidentEvent | None:
        now = self.clock()

        if message.startswith(self.FAILURE_PREFIX):
            self.last_error = message.removeprefix(self.FAILURE_PREFIX)

            if self.started_at is None:
                self.started_at = now
                self.last_report_at = now
                self.failure_count = 1
                return TelegramIncidentEvent(
                    handled=True,
                    level='ERROR',
                    message=f'Telegram polling unavailable: {self.last_error}',
                )

            self.failure_count += 1
            if now - self.last_report_at >= self.report_interval:
                self.last_report_at = now
                duration = _format_duration(now - self.started_at)
                return TelegramIncidentEvent(
                    handled=True,
                    level='WARNING',
                    message=(
                        f'Telegram polling is still unavailable for {duration}; '
                        f'failed attempts: {self.failure_count}; last error: {self.last_error}'
                    ),
                )

            return TelegramIncidentEvent(handled=True)

        if message.startswith(self.RECOVERY_PREFIX) and self.started_at is not None:
            duration = _format_duration(now - self.started_at)
            event = TelegramIncidentEvent(
                handled=True,
                level='WARNING',
                message=(
                    f'Telegram polling recovered after {duration}; '
                    f'failed attempts: {self.failure_count}'
                ),
            )
            self.started_at = None
            self.last_report_at = None
            self.failure_count = 0
            self.last_error = None
            return event

        return None


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, seconds = divmod(total_seconds, 60)
    if minutes:
        return f'{minutes}m {seconds}s'
    return f'{seconds}s'


class TelegramPollingIncidentHandler(logging.Handler):
    """Report polling state changes through the backend error aggregator."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.incident = TelegramPollingIncident()

    def emit(self, record):
        try:
            event = self.incident.observe(record.getMessage())
            if event is None:
                return

            # Prevent the root RemoteLogHandler from sending every raw retry
            # while the tracker emits the first/summary/recovery event itself.
            record._telegram_incident_handled = True
            if not event.message:
                return

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    client.send_log_entry(
                        level=event.level,
                        module='bot.telegram_health',
                        message=event.message,
                        notify=True,
                    )
                )
            except RuntimeError:
                logging.getLogger(__name__).warning(
                    'Could not schedule Telegram incident report outside an event loop.'
                )
        except Exception:
            self.handleError(record)
