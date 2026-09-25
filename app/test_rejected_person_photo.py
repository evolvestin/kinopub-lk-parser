import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command
from django.test import override_settings
from unittest.mock import Mock, patch

from app.models import Person, RejectedPersonPhoto, Show, ShowCrew
from app.services.person_service import fetch_person_photo_from_tmdb
from app.utils import get_original_image_url


class RejectedPersonPhotoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin', password='test-password', is_staff=True)
        self.client.force_login(self.user)
        self.person = Person.objects.create(
            name='John Walker',
            tmdb_photo_url='https://image.tmdb.org/t/p/w200/profile.jpg',
            is_photo_fetched=True,
        )

    def test_original_url_is_extracted_from_image_proxy_url(self):
        self.assertEqual(
            get_original_image_url(
                '/api/image_proxy/?url=https%3A%2F%2Fimage.tmdb.org%2Ft%2Fp%2Fw200%2Fprofile.jpg'
            ),
            'https://image.tmdb.org/t/p/w200/profile.jpg',
        )

    def test_reject_api_persists_source_url_and_clears_active_photo(self):
        proxy_url = (
            '/api/image_proxy/?url='
            'https%3A%2F%2Fimage.tmdb.org%2Ft%2Fp%2Fw200%2Fprofile.jpg'
        )

        response = self.client.post(
            reverse('reject_person_photo_api'),
            data=json.dumps({'person_id': self.person.id, 'photo_url': proxy_url}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RejectedPersonPhoto.objects.filter(
                person=self.person,
                photo_url='https://image.tmdb.org/t/p/w200/profile.jpg',
            ).exists()
        )
        self.person.refresh_from_db()
        self.assertIsNone(self.person.tmdb_photo_url)
        self.assertFalse(self.person.is_photo_fetched)

    def test_reset_command_quarantines_unresolved_photo_owned_by_known_tmdb_person(self):
        known = Person.objects.create(
            name='Known Person',
            tmdb_id=123,
            tmdb_photo_url=self.person.tmdb_photo_url,
        )

        call_command('reset_unverified_duplicate_photos', '--apply')

        self.person.refresh_from_db()
        known.refresh_from_db()
        self.assertIsNone(self.person.tmdb_photo_url)
        self.assertFalse(self.person.is_photo_fetched)
        self.assertTrue(
            RejectedPersonPhoto.objects.filter(
                person=self.person,
                photo_url='https://image.tmdb.org/t/p/w200/profile.jpg',
            ).exists()
        )
        self.assertEqual(known.tmdb_photo_url, 'https://image.tmdb.org/t/p/w200/profile.jpg')

    @override_settings(
        TMDB_API_KEY='test-key',
        TMDB_API_BASE_URL='https://tmdb.test/3',
    )
    @patch('app.services.person_service.sleep', return_value=None)
    @patch('app.services.person_service.get_tmdb_session')
    def test_conflicting_tmdb_candidate_is_rejected_before_retry(
        self, get_session, _sleep
    ):
        known = Person.objects.create(name='Known Person', tmdb_id=123)
        target = Person.objects.create(name='John Walker', en_name='John Walker')
        show = Show.objects.create(
            title='Known Movie', original_title='Known Movie', year=2020, type='Movie'
        )
        ShowCrew.objects.create(show=show, person=target)

        response = Mock(status_code=200)
        response.json.return_value = {
            'results': [
                {
                    'id': 123,
                    'name': 'John Walker',
                    'original_name': 'John Walker',
                    'profile_path': '/profile.jpg',
                    'known_for': [
                        {
                            'title': 'Known Movie',
                            'original_title': 'Known Movie',
                            'release_date': '2020-01-01',
                        }
                    ],
                }
            ]
        }
        session = Mock()
        session.get.return_value = response
        get_session.return_value = session

        self.assertTrue(fetch_person_photo_from_tmdb(target))

        target.refresh_from_db()
        known.refresh_from_db()
        self.assertIsNone(target.tmdb_photo_url)
        self.assertIsNone(target.tmdb_id)
        self.assertTrue(
            RejectedPersonPhoto.objects.filter(
                person=target,
                photo_url='https://image.tmdb.org/t/p/w200/profile.jpg',
            ).exists()
        )
        self.assertIsNone(known.tmdb_photo_url)
