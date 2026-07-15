import logging
import threading
import time

from django.core.management import call_command
from django.utils import timezone

from app.management.base import LoggableBaseCommand
from app.utils import update_heartbeat

logger = logging.getLogger(__name__)


class Command(LoggableBaseCommand):
    help = 'Runs a lightweight background loop to send health reports at a specific time.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Health monitor daemon started.'))
        last_run_date = None

        while True:
            try:
                update_heartbeat()
                now = timezone.now()

                if now.hour == 15 and now.date() != last_run_date:
                    self.stdout.write(
                        f'[{now.strftime("%Y-%m-%d %H:%M:%S")}] Triggering health report...'
                    )
                    threading.Thread(
                        target=call_command, args=('sendhealthreport',), daemon=True
                    ).start()
                    last_run_date = now.date()

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error in health daemon loop: {e}'))
                logger.error(f'Error in health daemon loop: {e}', exc_info=True)

            time.sleep(30)
