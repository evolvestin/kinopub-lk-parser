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

from app.models import Person, PublicArticle, PublicVisit, Show, ShowCrew, ShowDuration, UserRating, ViewHistory, ViewUser, WishlistFolder, WishlistItem
from kinopub_parser.settings import SafeCompressedManifestStaticFilesStorage


class PublicSiteTests(TestCase):
    def setUp(self):
        cache.delete(f'public_sitemap_ranges:{settings.DATABASES["default"]["NAME"]}')
        cache.delete(f'public_catalog_type_counts:{settings.DATABASES["default"]["NAME"]}')
        cache.delete('public_usage_counts_v4')
        self.show = Show.objects.create(title='Тестовый сериал', original_title='Test Series', year=2024)

    def test_catalog_and_show_link_to_bot(self):
        response = self.client.get(reverse('public_catalog'), {'q': 'Тестовый'})
        self.assertContains(response, self.show.title)
        self.assertContains(response, reverse('public_show', args=[self.show.pk]))
        response = self.client.get(reverse('public_show', args=[self.show.pk]))
        self.assertContains(response, f'https://t.me/kinopub_observer_bot?start=site_show_{self.show.pk}')

    @override_settings(PUBLIC_SITE_URL='https://kinopub.webredirect.org')
    def test_public_ip_redirects_to_canonical_domain_but_services_do_not(self):
        response = self.client.get('/catalog/', {'page': 2}, HTTP_HOST='157.173.101.93:8012')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://kinopub.webredirect.org/catalog/?page=2')
        self.assertNotIn('noindex', response.get('X-Robots-Tag', ''))
        self.assertEqual(self.client.get('/metrics/', HTTP_HOST='157.173.101.93:8012').status_code, 200)
        self.assertEqual(self.client.get('/', HTTP_HOST='localhost:8022').status_code, 200)

    @override_settings(STATIC_URL='/static/')
    def test_vite_fingerprinted_assets_keep_original_urls(self):
        storage = SafeCompressedManifestStaticFilesStorage()
        self.assertEqual(storage.url('assets/main-CerCkXVE.js'), '/static/assets/main-CerCkXVE.js')
        self.assertEqual(storage.url('assets/main-CMqabRWI.css'), '/static/assets/main-CMqabRWI.css')

    def test_missing_metadata_does_not_claim_seasons_or_cast(self):
        movie = Show.objects.create(title='Новый фильм', type='Movie', imdb_id='tt13918446')
        response = self.client.get(reverse('public_show', args=[movie.pk]))
        self.assertContains(response, 'https://www.imdb.com/title/tt13918446/')
        self.assertNotContains(response, 'Сезоны, эпизоды и участники съёмочной группы')
        self.assertContains(response, 'property="og:type"', count=1)
        concert = Show.objects.create(title='Концерт', type='Concert')
        self.assertContains(self.client.get(reverse('public_show', args=[concert.pk])), '"@type": "CreativeWork"')

    @patch('app.views._get_image_proxy_session')
    @patch('app.views.cache')
    def test_public_poster_proxy_allows_indexing_and_rejects_spoofed_hosts(self, proxy_cache, session_factory):
        proxy_cache.get.return_value = None
        result = session_factory.return_value.get.return_value
        result.status_code = 200
        result.content = b'image data'
        result.headers = {'Content-Type': 'image/jpeg'}
        response = self.client.get('/api/image_proxy/', {'url': 'https://image.tmdb.org/t/p/w200/test.jpg'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('noindex', response.get('X-Robots-Tag', ''))
        response = self.client.get('/api/image_proxy/', {'url': 'https://image.tmdb.org.evil.example/poster.jpg'})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(session_factory.return_value.get.call_count, 1)

    def test_catalog_and_detail_show_webapp_local_rating(self):
        user = ViewUser.objects.create(telegram_id=12345)
        UserRating.objects.create(user=user, show=self.show, rating=8)
        self.assertContains(self.client.get(reverse('public_catalog'), {'q': 'Тестовый'}), '★ 8.0')
        self.assertContains(self.client.get(reverse('public_show', args=[self.show.pk])), '<b>LR</b> 8.0', html=True)

    def test_home_preview_uses_actual_local_ratings(self):
        cache.delete('public_demo_ratings_v1')
        featured = Show.objects.create(pk=74959, title='Дюна')
        user = ViewUser.objects.create(telegram_id=23456)
        UserRating.objects.create(user=user, show=featured, rating=9)
        response = self.client.get('/preview/wishlist/')
        self.assertEqual(response.context['demo_ratings'], {74959: 9.0})

    def test_guide_link_is_rendered_as_a_crawlable_relative_link(self):
        article = PublicArticle.objects.create(
            slug='first-guide', title='Руководство', description='Описание',
            content_blocks=[{'type': 'guide_link', 'slug': 'add-show-to-favorites', 'text': 'Добавить в избранное'}],
            published_at=timezone.now(),
        )
        self.assertContains(self.client.get(reverse('public_guide', args=[article.slug])),
                            'href="/guide/add-show-to-favorites/"')

    def test_status_and_episode_hint_only_for_series(self):
        movie = Show.objects.create(title='Фильм', type='Movie', status='Finished')
        series = Show.objects.create(title='Сериал', type='Series', status='Finished')
        movie_page = self.client.get(reverse('public_show', args=[movie.pk]))
        series_page = self.client.get(reverse('public_show', args=[series.pk]))
        self.assertNotContains(movie_page, 'show-tag">Завершен')
        self.assertNotContains(movie_page, 'и следить за новыми сериями')
        self.assertContains(series_page, 'show-tag">Завершен')
        self.assertContains(series_page, 'и следить за новыми сериями')

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

    def test_home_explains_statistics_and_links_to_guide(self):
        page = self.client.get('/')
        self.assertContains(page, 'href="/guide/how-statistics-works/"')
        self.assertContains(page, 'Откуда берётся статистика просмотров?')
        self.assertContains(page, 'Почему просмотр не появился на карте активности?')

    @override_settings(PUBLIC_OFFER_URL='https://example.org/offer')
    def test_offer_link_in_public_navigation(self):
        response = self.client.get('/guide/')
        self.assertContains(response, 'href="https://example.org/offer"', count=3)

    def test_legal_pages_and_default_navigation(self):
        page = self.client.get('/guide/')
        self.assertContains(page, 'href="/offer/"')
        self.assertContains(page, 'href="/privacy/"')
        self.assertContains(self.client.get('/offer/'), '@evolvestin')
        self.assertContains(self.client.get('/privacy/'), 'sessionStorage')

    def test_about_page_is_linked_and_indexable(self):
        self.assertContains(self.client.get('/guide/'), 'href="/about/"')
        self.assertNotContains(self.client.get('/'), 'id="about"')
        response = self.client.get('/about/')
        self.assertContains(response, 'kino.pub')
        self.assertContains(response, 'kino.watch')
        self.assertNotIn('noindex', response.get('X-Robots-Tag', ''))
        self.assertContains(self.client.get('/sitemap-shows-0.xml'), '/about/')

    def test_robots_and_sitemap(self):
        response = self.client.get('/robots.txt')
        self.assertNotContains(response, 'Disallow: /\n')
        self.assertNotContains(response, 'Disallow: /metrics/')
        self.assertContains(self.client.get('/sitemap.xml'), '/sitemap-shows-1.xml')
        self.assertContains(self.client.get('/sitemap-shows-1.xml'), reverse('public_show', args=[self.show.pk]))
        parser = RobotFileParser()
        parser.parse(response.content.decode().splitlines())
        self.assertTrue(parser.can_fetch('OAI-SearchBot', '/guide/notifications/'))
        self.assertTrue(parser.can_fetch('OAI-SearchBot', '/api/image_proxy/?url=test'))
        self.assertTrue(parser.can_fetch('Googlebot', '/metrics/'))
        self.assertFalse(parser.can_fetch('OAI-SearchBot', '/api/internal/articles/example/'))

    def test_public_pages_allow_indexing_but_internal_pages_do_not(self):
        article = PublicArticle.objects.create(
            slug='indexed-guide', title='Индексируемая статья', description='Описание',
            body='Короткий текст', published_at=timezone.now(),
        )
        for path in ['/', '/catalog/', '/catalog/1/', '/guide/', '/about/', '/offer/', '/privacy/', f'/guide/{article.slug}/']:
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
    def test_home_shows_rounded_catalog_and_actual_usage_counts(self, cached_counts):
        cached_counts.side_effect = lambda key, fallback, timeout: ({'total': 1514860, 'movies': 1316939, 'series': 186263} if key.startswith('public_catalog') else fallback())
        user = ViewUser.objects.create(telegram_id=12345)
        ViewUser.objects.create(telegram_id=None)
        ViewHistory.objects.create(show=self.show, is_checked=True)
        folder = WishlistFolder.objects.create(user=user, name='Избранное')
        WishlistItem.objects.create(user=user, folder=folder, show=self.show, is_active=True)
        UserRating.objects.create(user=user, show=self.show, rating=8)
        response = self.client.get('/')
        self.assertContains(response, '1,5')
        self.assertContains(response, 'пользователей')
        self.assertEqual(response.context['users_count'], 1)
        self.assertEqual(response.context['recorded_views'], 1)
        self.assertEqual(response.context['favorites_count'], 1)
        self.assertEqual(response.context['ratings_count'], 1)
        self.assertNotContains(response, 'фильмов в каталоге')
        self.assertContains(response, 'data-decimals="1"')

    def test_demo_uses_vue_entry_and_blocks_indexing(self):
        response = self.client.get('/preview/wishlist/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'public-wishlist-demo')
        self.assertIn('noindex', response['X-Robots-Tag'])

    def test_statistics_example_includes_catalog_person_photo(self):
        Person.objects.create(id=68732, name='Педро Паскаль', tmdb_photo_url='https://image.tmdb.org/t/p/w185/example.jpg')
        response = self.client.get('/preview/wishlist/', {'stats-example': '1'})
        self.assertContains(response, 'stats-example-people')
        self.assertContains(response, '/api/image_proxy/?url=')
        self.assertIn('Педро Паскаль', response.context['stats_example_people'])
        self.assertNotContains(self.client.get('/preview/wishlist/'), 'stats-example-people')

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
            {'type': 'step', 'title': 'Откройте избранное', 'text': 'Выберите раздел «Избранное».', 'result': 'Появятся сохранённые папки.', 'image': {'src': '/articles/assets/example/abcdef0123456789abcdef0123456789.jpg', 'alt': 'Открыт раздел избранного', 'caption': 'Шаг 1. Откройте избранное.'}},
            {'type': 'steps', 'items': ['Шаг первый', 'Шаг второй']},
        ]
        payload = json.dumps({'title': 'Статья с блоками', 'description': 'Ответ на вопрос', 'body': '', 'content_blocks': blocks, 'published_at': published})
        response = self.client.put('/api/internal/articles/rich-example/', payload, content_type='application/json', HTTP_AUTHORIZATION='Bearer example-test-token')
        self.assertEqual(response.status_code, 201)
        page = self.client.get('/guide/rich-example/')
        self.assertContains(page, '&lt;script&gt;not markup&lt;/script&gt;')
        self.assertContains(page, 'Фото карточки')
        self.assertContains(page, 'Подпись фото')
        self.assertContains(page, 'Откройте избранное')
        self.assertContains(page, 'Шаг 1. Откройте избранное.')
        self.assertContains(page, 'Появятся сохранённые папки.')
        self.assertContains(page, 'Шаг первый')

    def test_visit_events_count_pageviews_and_time(self):
        session = str(uuid.uuid4())
        for event, seconds in [('pageview', 0), ('tick', 15), ('pageview', 0)]:
            response = self.client.post(
                '/api/public/visit/',
                json.dumps({'session_id': session, 'event': event, 'seconds': seconds, 'page': '/catalog/example/', 'referrer': 'https://search.example/query?private=value'}),
                content_type='application/json',
                HTTP_X_REAL_IP='198.51.100.7',
                HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36',
                HTTP_ACCEPT_LANGUAGE='ru-RU,ru;q=0.9',
            )
            self.assertEqual(response.status_code, 204)
        visit = PublicVisit.objects.get(session_id=session)
        self.assertEqual((visit.pageviews, visit.active_seconds), (2, 15))
        self.assertEqual(visit.pages, ['/catalog/example/', '/catalog/example/'])
        self.assertEqual(visit.referrer_host, 'search.example')
        self.assertEqual((visit.browser, visit.operating_system, visit.device_type), ('Chrome', 'Windows', 'desktop'))
        self.assertEqual(visit.accept_language, 'ru-RU')
        self.assertEqual(visit.ip_address, '198.51.100.7')
        self.assertTrue(visit.visitor_fingerprint)
        self.assertNotIn('198.51.100.7', visit.visitor_fingerprint)
