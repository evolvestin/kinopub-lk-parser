from django.test import SimpleTestCase

from app.management.commands.syncpoiskkinoratings import Command


class PoiskkinoSyncHelperTests(SimpleTestCase):
    def test_object_list_treats_null_and_invalid_values_as_empty(self):
        self.assertEqual(Command._object_list({'genres': None}, 'genres'), [])
        self.assertEqual(Command._object_list({'genres': {'name': 'Drama'}}, 'genres'), [])
        self.assertEqual(
            Command._object_list({'genres': [{'name': 'Drama'}, None]}, 'genres'),
            [{'name': 'Drama'}],
        )
