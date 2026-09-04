from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from app.models import Code


@override_settings(KINOPUB_CODE_API_TOKEN='test-code-token')
class KinopubCodeEndpointTests(TestCase):
    url = '/api/internal/kinopub-code/'

    def test_endpoint_requires_dedicated_token(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)
        self.assertNotIn('code', response.json())

    def test_endpoint_returns_latest_unexpired_code(self):
        now = timezone.now()
        Code.objects.create(
            code='111111',
            telegram_message_id=-1,
            received_at=now - timedelta(minutes=2),
        )
        Code.objects.create(
            code='222222',
            telegram_message_id=-1,
            received_at=now - timedelta(minutes=1),
        )

        response = self.client.get(self.url, HTTP_X_KINOPUB_CODE_TOKEN='test-code-token')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], '222222')
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')

    def test_endpoint_does_not_return_expired_codes(self):
        Code.objects.create(
            code='333333',
            telegram_message_id=-1,
            received_at=timezone.now() - timedelta(minutes=16),
        )

        response = self.client.get(self.url, HTTP_X_KINOPUB_CODE_TOKEN='test-code-token')

        self.assertEqual(response.status_code, 404)
        self.assertNotIn('code', response.json())
