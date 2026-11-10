import json
import uuid
from unittest.mock import patch
from urllib.robotparser import RobotFileParser

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.urls import reverse
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app.models import Person, PublicArticle, PublicVisit, Show, ShowCrew, ShowDuration


class PublicSiteTests(TestCase):
    def setUp(self):
        cache.delete(f'public_sitemap_ranges:{settings.DATABASES["default"]["NAME"]}')
        cache.delete(f'public_catalog_type_counts:{settings.DATABASES["default"]["NAME"]}')
        self.show = Show.objects.create(title='Тестовый сериал', original_title='Test Series', year=2024)

    def test_catalog_and_show_link_to_bot(self):
        response = self.client.get(reverse('public_catalog'), {'q': 'Тестовый'})
        self.assertContains(response, self.show.title)
        self.assertContains(response, reverse('public_show', args=[self.show.pk]))
        response = self.client.get(reverse('public_show', args=[self.show.pk]))
        self.assertContains(response, f'https://t.me/kinopub_observer_bot?start=site_show_{self.show.pk}')

    def test_show_detail_renders_seasons_and_crew(self):
        person = Person.objects.create(name='Тестовый актёр')
        ShowCrew.objects.create(show=self.show, person=person, profession='Актер')
        ShowDuration.objects.create(
            show=self.show,
            season_number=1,
            episode_number=1,
            duration_seconds=1800,
        )

        response = self.client.get(reverse('public_show', args=[self.show.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Сезоны и эпизоды')
        self.assertContains(response, 'Сезон 1')
        self.assertContains(response, 'E01')
        self.assertContains(response, 'Актёр')
        self.assertContains(response, 'Тестовый актёр')
        self.assertContains(response, '"@type": "TVSeries"')

    def test_public_ctas_mark_site_traffic(self):
        for path in ['/', '/catalog/', '/guide/']:
            self.assertContains(self.client.get(path), 'https://t.me/kinopub_observer_bot?start=site')

    def test_robots_and_sitemap(self):
        response = self.client.get('/robots.txt')
        self.assertNotContains(response, 'Disallow: /\n')
        self.assertContains(response, 'Disallow: /metrics/')
        self.assertContains(self.client.get('/sitemap.xml'), '/sitemap-shows-1.xml')
        self.assertContains(self.client.get('/sitemap-shows-1.xml'), reverse('public_show', args=[self.show.pk]))
        parser = RobotFileParser()
        parser.parse(response.content.decode().splitlines())
        self.assertTrue(parser.can_fetch('OAI-SearchBot', '/guide/notifications/'))
        self.assertFalse(parser.can_fetch('OAI-SearchBot', '/api/internal/articles/example/'))

    def test_public_pages_allow_indexing_but_internal_pages_do_not(self):
        article = PublicArticle.objects.create(
            slug='indexed-guide', title='Индексируемая статья', description='Описание',
            body='Короткий текст', published_at=timezone.now(),
        )
        for path in ['/', '/catalog/', '/catalog/1/', '/guide/', f'/guide/{article.slug}/']:
            if path == '/catalog/1/':
                path = reverse('public_show', args=[self.show.pk])
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('noindex', response.get('X-Robots-Tag', ''))
        for path in ['/metrics/', '/preview/wishlist/', '/api/internal/articles/example/']:
            response = self.client.get(path)
            self.assertIn('noindex', response.get('X-Robots-Tag', ''))
        self.assertIn('noindex', self.client.get('/catalog/', {'q': 'Test'}).get('X-Robots-Tag', ''))

    def test_sitemap_uses_stable_id_ranges(self):
        show = Show.objects.create(id=20001, title='Другая запись', original_title='Other')
        self.assertContains(self.client.get('/sitemap.xml'), '/sitemap-shows-3.xml')
        self.assertContains(self.client.get('/sitemap-shows-3.xml'), reverse('public_show', args=[show.id]))
        self.assertNotContains(self.client.get('/sitemap-shows-1.xml'), reverse('public_show', args=[show.id]))

    def test_legacy_guide_urls_redirect_to_editorial_articles(self):
        response = self.client.get('/guide/notifications/')
        self.assertRedirects(response, '/guide/new-episode-notifications/', status_code=301, fetch_redirect_response=False)

    @patch('app.public_site.cache.get_or_set')
    def test_home_shows_rounded_real_catalog_counts(self, cached_counts):
        cached_counts.return_value = {'total': 1514860, 'movies': 1316939, 'series': 186263}
        response = self.client.get('/')
        self.assertContains(response, '1,5')
        self.assertContains(response, '1,3')
        self.assertContains(response, '186')
        self.assertContains(response, 'data-decimals="1"')

    def test_demo_uses_vue_entry_and_blocks_indexing(self):
        response = self.client.get('/preview/wishlist/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'public-wishlist-demo')
        self.assertIn('noindex', response['X-Robots-Tag'])

    def test_public_pages_do_not_link_metrics(self):
        for path in ['/', '/catalog/', '/guide/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, '/metrics/')

    def test_search_original_and_local_title(self):
        show = Show.objects.create(title='Интерстеллар', original_title='Interstellar', year=2014)
        for query in ('интерстеллар', 'interstellar'):
            self.assertContains(self.client.get('/catalog/', {'q': query}), show.title)

    def test_catalog_has_fixed_selection(self):
        featured = Show.objects.create(title='Интерстеллар', original_title='Interstellar', imdb_id='tt0816692')
        Show.objects.create(title='Неизвестная новинка', original_title='New title', year=2099)
        response = self.client.get('/catalog/')
        self.assertContains(response, featured.title)
        self.assertContains(response, 'Неизвестная новинка')
        self.assertLess(response.content.find(featured.title.encode()), response.content.find('Неизвестная новинка'.encode()))

    @patch('app.public_site.cache.get_or_set', return_value={'total': 100, 'movies': 90, 'series': 10})
    def test_default_catalog_uses_cached_count(self, _cached_counts):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get('/catalog/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any('COUNT(' in query['sql'].upper() for query in captured.captured_queries))

    @override_settings(PUBLIC_ARTICLE_API_TOKEN='example-test-token')
    def test_article_api_requires_token_and_publishes(self):
        url = '/api/internal/articles/example/'
        body = json.dumps({'title': 'Тест', 'description': 'Описание', 'body': '<script>alert(1)</script>', 'published_at': '2020-01-01T12:00:00+03:00'})
        self.assertEqual(self.client.put(url, body, content_type='application/json').status_code, 401)
        response = self.client.put(url, body, content_type='application/json', HTTP_AUTHORIZATION='Bearer example-test-token')
        self.assertEqual(response.status_code, 201)
        page = self.client.get('/guide/example/')
        self.assertContains(page, '&lt;script&gt;')
        self.assertContains(page, 'application/ld+json')
        self.assertContains(page, 'datePublished')
        self.assertContains(self.client.get('/sitemap-shows-0.xml'), '/guide/example/')

    @override_settings(PUBLIC_ARTICLE_API_TOKEN='example-test-token')
    def test_article_renders_typed_content_and_photo(self):
        published = timezone.now().isoformat()
        blocks = [
            {'type': 'lead', 'text': '<script>not markup</script>'},
            {'type': 'image', 'src': '/articles/assets/example/0123456789abcdef0123456789abcdef.jpg', 'alt': 'Фото карточки', 'caption': 'Подпись фото'},
            {'type': 'steps', 'items': ['Шаг первый', 'Шаг второй']},
        ]
        payload = json.dumps({'title': 'Статья с блоками', 'description': 'Ответ на вопрос', 'body': '', 'content_blocks': blocks, 'published_at': published})
        response = self.client.put('/api/internal/articles/rich-example/', payload, content_type='application/json', HTTP_AUTHORIZATION='Bearer example-test-token')
        self.assertEqual(response.status_code, 201)
        page = self.client.get('/guide/rich-example/')
        self.assertContains(page, '&lt;script&gt;not markup&lt;/script&gt;')
        self.assertContains(page, 'Фото карточки')
        self.assertContains(page, 'Подпись фото')
        self.assertContains(page, 'Шаг первый')

    def test_visit_events_count_pageviews_and_time(self):
        session = str(uuid.uuid4())
        for event, seconds in [('pageview', 0), ('tick', 15), ('pageview', 0)]:
            response = self.client.post('/api/public/visit/', json.dumps({'session_id': session, 'event': event, 'seconds': seconds}), content_type='application/json')
            self.assertEqual(response.status_code, 204)
        visit = PublicVisit.objects.get(session_id=session)
        self.assertEqual((visit.pageviews, visit.active_seconds), (2, 15))
