import gzip
import tempfile

from django.test import SimpleTestCase, TestCase

from app.management.commands.syncimdbdata import Command
from app.models import Show


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


class ImdbBasicsImportTests(TestCase):
    def test_unrated_series_is_imported_without_episodes(self):
        with tempfile.NamedTemporaryFile(suffix='.tsv.gz') as file:
            with gzip.open(file.name, 'wt', encoding='utf-8') as dataset:
                dataset.write('tconst\ttitleType\tprimaryTitle\toriginalTitle\tstartYear\n')
                dataset.write('tt13918446\ttvSeries\tHarry Potter\tHarry Potter\t2026\n')
            Command()._process_basics(file.name, {'tvSeries': 'Series'}, set(), True, 100)
        self.assertTrue(Show.objects.filter(imdb_id='tt13918446', type='Series').exists())
