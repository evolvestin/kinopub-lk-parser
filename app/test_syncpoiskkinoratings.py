from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase

from app.management.commands.syncpoiskkinoratings import Command
from app.models import ShowCrew
from shared.formatters import format_country_display_names


class PoiskkinoSyncHelperTests(SimpleTestCase):
    def test_object_list_treats_null_and_invalid_values_as_empty(self):
        self.assertEqual(Command._object_list({'genres': None}, 'genres'), [])
        self.assertEqual(Command._object_list({'genres': {'name': 'Drama'}}, 'genres'), [])
        self.assertEqual(
            Command._object_list({'genres': [{'name': 'Drama'}, None]}, 'genres'),
            [{'name': 'Drama'}],
        )

    def test_deadlock_is_detected_by_postgres_sqlstate_or_message(self):
        sqlstate_error = OperationalError('database operation failed')
        cause = OperationalError('postgres deadlock')
        cause.sqlstate = '40P01'
        sqlstate_error.__cause__ = cause

        self.assertTrue(Command._is_deadlock(sqlstate_error))
        self.assertTrue(Command._is_deadlock(OperationalError('deadlock detected')))
        self.assertFalse(Command._is_deadlock(OperationalError('connection lost')))

    def test_deadlocked_write_is_retried(self):
        attempts = 0

        def operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise OperationalError('deadlock detected')
            return 'saved'

        with patch('app.management.commands.syncpoiskkinoratings.time.sleep') as sleep:
            self.assertEqual(Command._with_deadlock_retry(operation, 'test write'), 'saved')

        self.assertEqual(attempts, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_showcrew_professions_are_unbounded_text_fields(self):
        self.assertEqual(ShowCrew._meta.get_field('profession').get_internal_type(), 'TextField')
        self.assertEqual(ShowCrew._meta.get_field('en_profession').get_internal_type(), 'TextField')

    def test_country_display_names_deduplicate_source_aliases(self):
        countries = [
            type('Country', (), {'name': 'США', 'emoji_flag': '🇺🇸'})(),
            type('Country', (), {'name': 'United States of America', 'emoji_flag': None})(),
            type('Country', (), {'name': 'Италия', 'emoji_flag': '🇮🇹'})(),
            type('Country', (), {'name': 'Italy', 'emoji_flag': None})(),
        ]

        self.assertEqual(
            format_country_display_names(
                countries,
                {country.name: country.emoji_flag for country in countries},
            ),
            ['🇮🇹 Италия', '🇺🇸 США'],
        )
