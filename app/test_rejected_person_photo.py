import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Person, RejectedPersonPhoto
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
