from unittest.mock import Mock, patch

from django.test import TestCase

from app import tasks
from app.models import Show
from shared.constants import ParserSessionType, RedisQueue


class FakeQueueRedis:
    def __init__(self, show_id):
        self.show_id = show_id
        self.requeued = []
        self.retry_attempts = 0
        self.cleared_keys = []

    def scard(self, _queue_name):
        return 1

    def spop(self, _queue_name, count):
        assert count == 50
        return [str(self.show_id).encode()]

    def sadd(self, _queue_name, *show_ids):
        self.requeued.extend(show_ids)

    def incr(self, _retry_key):
        self.retry_attempts += 1
        return self.retry_attempts

    def expire(self, _retry_key, _ttl):
        return True

    def delete(self, retry_key):
        self.cleared_keys.append(retry_key)


class QueueRetryTests(TestCase):
    def test_missing_details_result_is_put_back_into_queue(self):
        show = Show.objects.create(
            kinopub_id=12345,
            title='Queued show',
            original_title='Queued show',
            type='Series',
        )
        redis_client = FakeQueueRedis(show.id)
        driver = Mock()
        process_func = Mock(return_value=None)

        with (
            patch('app.tasks.Redis.from_url', return_value=redis_client),
            patch('app.tasks.history_parser.initialize_driver_session', return_value=driver),
            patch('app.tasks.history_parser.close_driver'),
        ):
            tasks._process_batch_from_queue(
                RedisQueue.UPDATE_DETAILS,
                ParserSessionType.AUX,
                process_func,
            )

        process_func.assert_called_once_with(
            driver,
            show.kinopub_id,
            force=True,
            session_type=ParserSessionType.AUX,
        )
        self.assertEqual(redis_client.requeued, [show.id])
        self.assertEqual(redis_client.retry_attempts, 1)

    def test_successful_duration_result_clears_retry_state(self):
        show = Show.objects.create(
            kinopub_id=12346,
            title='Queued movie',
            original_title='Queued movie',
            type='Movie',
        )
        redis_client = FakeQueueRedis(show.id)
        driver = Mock()
        process_func = Mock(return_value=True)

        with (
            patch('app.tasks.Redis.from_url', return_value=redis_client),
            patch('app.tasks.history_parser.initialize_driver_session', return_value=driver),
            patch('app.tasks.history_parser.close_driver'),
            patch('app.tasks.BackupManager.schedule_backup'),
        ):
            tasks._process_batch_from_queue(
                RedisQueue.UPDATE_DURATIONS,
                ParserSessionType.MAIN,
                process_func,
            )

        self.assertEqual(redis_client.requeued, [])
        self.assertEqual(redis_client.cleared_keys, [
            tasks._queue_item_retry_key(RedisQueue.UPDATE_DURATIONS, show.id),
        ])
