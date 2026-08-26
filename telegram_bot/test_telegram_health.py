import unittest

from services.telegram_health import TelegramPollingIncident


class TelegramPollingIncidentTests(unittest.TestCase):
    def test_reports_start_summary_and_recovery(self):
        current_time = [0.0]
        incident = TelegramPollingIncident(
            clock=lambda: current_time[0],
            report_interval=600,
        )

        first = incident.observe('Failed to fetch updates - Bad Gateway')
        self.assertEqual(first.level, 'ERROR')
        self.assertIn('Bad Gateway', first.message)

        current_time[0] = 30
        repeated = incident.observe('Failed to fetch updates - Request timeout')
        self.assertTrue(repeated.handled)
        self.assertIsNone(repeated.message)

        current_time[0] = 600
        summary = incident.observe('Failed to fetch updates - Request timeout')
        self.assertEqual(summary.level, 'WARNING')
        self.assertIn('failed attempts: 3', summary.message)

        current_time[0] = 605
        recovered = incident.observe('Connection established (tryings = 3, bot id = 1)')
        self.assertEqual(recovered.level, 'WARNING')
        self.assertIn('recovered', recovered.message)
        self.assertIsNone(incident.started_at)

    def test_unrelated_messages_are_not_intercepted(self):
        incident = TelegramPollingIncident(clock=lambda: 0)

        self.assertIsNone(incident.observe('Run polling for bot @example id=1'))


if __name__ == '__main__':
    unittest.main()
