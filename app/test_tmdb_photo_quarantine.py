from django.test import TestCase

from app.models import Person, RejectedPersonPhoto
from app.services.person_photo_quarantine import quarantine_tmdb_photo_conflicts
from app.services.tmdb_client import _save_tmdb_person


class TmdbPersonPhotoQuarantineTests(TestCase):
    def test_tmdb_credit_write_quarantines_legacy_unresolved_photo(self):
        shared_url = 'https://image.tmdb.org/t/p/w200/shared.jpg'
        legacy = Person.objects.create(
            name='Legacy Person',
            tmdb_photo_url=shared_url,
            is_photo_fetched=True,
        )
        incoming = Person.objects.create(name='New Person')

        saved = _save_tmdb_person(
            incoming,
            {
                'id': 456,
                'name': 'New Person',
                'original_name': 'New Person',
                'profile_path': '/shared.jpg',
            },
        )

        legacy.refresh_from_db()
        saved.refresh_from_db()
        self.assertEqual(saved.tmdb_id, 456)
        self.assertEqual(saved.tmdb_photo_url, shared_url)
        self.assertIsNone(legacy.tmdb_photo_url)
        self.assertFalse(legacy.is_photo_fetched)
        self.assertTrue(
            RejectedPersonPhoto.objects.filter(person=legacy, photo_url=shared_url).exists()
        )

    def test_new_tmdb_identity_quarantines_when_photo_was_already_present(self):
        shared_url = 'https://image.tmdb.org/t/p/w200/shared.jpg'
        legacy = Person.objects.create(
            name='Legacy Person',
            tmdb_photo_url=shared_url,
            is_photo_fetched=True,
        )
        identity_row = Person.objects.create(
            name='New Person',
            tmdb_photo_url=shared_url,
            is_photo_fetched=True,
        )

        saved = _save_tmdb_person(
            identity_row,
            {'id': 789, 'name': 'New Person', 'original_name': 'New Person'},
        )

        legacy.refresh_from_db()
        saved.refresh_from_db()
        self.assertEqual(saved.tmdb_id, 789)
        self.assertEqual(saved.tmdb_photo_url, shared_url)
        self.assertIsNone(legacy.tmdb_photo_url)
        self.assertTrue(
            RejectedPersonPhoto.objects.filter(person=legacy, photo_url=shared_url).exists()
        )

    def test_photo_quarantine_clears_the_unresolved_person_when_it_is_saved_last(self):
        shared_url = 'https://image.tmdb.org/t/p/w200/shared.jpg'
        Person.objects.create(name='Confirmed', tmdb_id=123, tmdb_photo_url=shared_url)
        unresolved = Person.objects.create(
            name='Unresolved', tmdb_photo_url=shared_url, is_photo_fetched=True
        )

        updated = quarantine_tmdb_photo_conflicts(unresolved.id)

        unresolved.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertIsNone(unresolved.tmdb_photo_url)
        self.assertFalse(unresolved.is_photo_fetched)
        self.assertTrue(
            RejectedPersonPhoto.objects.filter(person=unresolved, photo_url=shared_url).exists()
        )

    def test_different_confirmed_tmdb_ids_keep_their_shared_photo(self):
        shared_url = 'https://image.tmdb.org/t/p/w200/shared.jpg'
        first = Person.objects.create(name='Confirmed A', tmdb_id=123, tmdb_photo_url=shared_url)
        second = Person.objects.create(name='Confirmed B', tmdb_id=456, tmdb_photo_url=shared_url)

        self.assertEqual(quarantine_tmdb_photo_conflicts(first.id), 0)
        self.assertEqual(quarantine_tmdb_photo_conflicts(second.id), 0)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.tmdb_photo_url, shared_url)
        self.assertEqual(second.tmdb_photo_url, shared_url)
