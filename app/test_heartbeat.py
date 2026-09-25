import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase

from app.management.commands.sendhealthreport import collect_heartbeat_status


class HeartbeatStatusTests(TestCase):
    def test_replaced_container_files_are_not_reported_as_stale(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            heartbeat_dir = Path(temp_dir)
            (heartbeat_dir / 'heartbeat_old-container').touch()
            (heartbeat_dir / 'heartbeat_email-listener').touch()
            (heartbeat_dir / 'heartbeat_health-monitor').touch()
            old_timestamp = now - 900
            os.utime(heartbeat_dir / 'heartbeat_old-container', (old_timestamp, old_timestamp))

            active_count, stale_services, deleted_count = collect_heartbeat_status(
                heartbeat_dir,
                ('email-listener', 'health-monitor'),
                now=now,
            )

        self.assertEqual(active_count, 2)
        self.assertEqual(stale_services, [])
        self.assertEqual(deleted_count, 0)

    def test_missing_expected_service_is_reported(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            heartbeat_dir = Path(temp_dir)
            (heartbeat_dir / 'heartbeat_email-listener').touch()

            active_count, stale_services, deleted_count = collect_heartbeat_status(
                heartbeat_dir,
                ('email-listener', 'health-monitor'),
                now=now,
            )

        self.assertEqual(active_count, 1)
        self.assertEqual(stale_services, ['health-monitor missing'])
        self.assertEqual(deleted_count, 0)
