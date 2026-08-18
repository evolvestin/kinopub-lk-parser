from django.test import SimpleTestCase

from app.management.commands.syncimdbdata import Command


class ImdbSyncHelperTests(SimpleTestCase):
    def test_extract_imdb_id_from_http_url(self):
        self.assertEqual(
            Command._extract_imdb_id('http://www.imdb.com/title/tt0077806'),
            'tt0077806',
        )

    def test_extract_imdb_id_from_https_url_with_trailing_slash(self):
        self.assertEqual(
            Command._extract_imdb_id('https://www.imdb.com/title/tt5463162/'),
            'tt5463162',
        )

    def test_extract_imdb_id_returns_none_for_missing_url(self):
        self.assertIsNone(Command._extract_imdb_id(None))
