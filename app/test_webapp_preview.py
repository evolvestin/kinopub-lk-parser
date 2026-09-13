from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings

from app.models import ViewUser
from app.views import get_webapp_user


class WebAppPreviewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username='staff-preview', password='password', is_staff=True
        )
        self.regular_user = user_model.objects.create_user(
            username='regular-preview', password='password'
        )
        self.view_user = ViewUser.objects.create(
            telegram_id=123456,
            name='Preview User',
            screen_width=390,
            screen_height=844,
        )

    @override_settings(DEBUG=False)
    def test_staff_preview_header_selects_requested_user(self):
        request = RequestFactory().post(
            '/api/webapp/detailed_stats/',
            HTTP_X_WEBAPP_PREVIEW_TELEGRAM_ID=str(self.view_user.telegram_id),
        )
        request.user = self.staff

        self.assertEqual(get_webapp_user(request), self.view_user)

    @override_settings(DEBUG=False)
    def test_non_staff_cannot_impersonate_user(self):
        request = RequestFactory().post(
            '/api/webapp/detailed_stats/',
            HTTP_X_WEBAPP_PREVIEW_TELEGRAM_ID=str(self.view_user.telegram_id),
        )
        request.user = self.regular_user

        self.assertIsNone(get_webapp_user(request))

    def test_preview_shell_contains_iframe_and_saved_viewport(self):
        client = Client()
        client.force_login(self.staff)

        response = client.get(f'/webapp-preview/{self.view_user.telegram_id}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'/webapp-preview-app/{self.view_user.telegram_id}/?webapp_preview={self.view_user.telegram_id}',
        )
        self.assertContains(response, 'width: 390px')
        self.assertContains(response, 'height: 844px')

    def test_preview_app_is_frameable_only_from_same_origin(self):
        client = Client()
        client.force_login(self.staff)

        response = client.get(f'/webapp-preview-app/{self.view_user.telegram_id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
