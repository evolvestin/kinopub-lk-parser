"""Public, indexable pages for discovering the Telegram application."""
import os
import json
import secrets
import uuid
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.cache import cache
from django.db.models import BigIntegerField, Case, Count, ExpressionWrapper, F, IntegerField, Q, Value, When
from django.http import Http404, HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin

from app.models import PublicArticle, PublicVisit, Show
from shared.media import build_poster_url


GUIDES = {
    'favorites': {
        'title': 'Как добавить фильм или сериал в избранное',
        'description': 'Сохраняйте фильмы и сериалы в избранное, чтобы вернуться к ним позже.',
        'steps': ['Откройте бота и запустите приложение.', 'Найдите фильм или сериал через поиск.', 'Откройте карточку и добавьте её в избранное, выбрав папку.'],
    },
    'folders': {
        'title': 'Как организовать избранное по папкам',
        'description': 'Разделите избранное на удобные списки, например «Смотрю» и «Буду смотреть».',
        'steps': ['Откройте раздел «Избранное».', 'Создайте папку и выберите её название, цвет и значок.', 'Добавляйте в неё фильмы и сериалы через карточки или изменяйте порядок элементов.'],
    },
    'notifications': {
        'title': 'Как получать уведомления о новых сериях',
        'description': 'Добавьте сериал в избранное, чтобы получать сообщения о новых эпизодах в Telegram.',
        'steps': ['Откройте карточку сериала и добавьте его в избранное.', 'Убедитесь, что бот запущен и не заблокирован в Telegram.', 'Управляйте уведомлениями для сериала в его карточке.'],
    },
    'statistics': {
        'title': 'Статистика фильмов и сериалов',
        'description': 'История просмотров и графики помогают увидеть, что вы смотрели.',
        'steps': ['Откройте приложение бота.', 'Перейдите в раздел статистики.', 'Изучите историю, графики активности и подборки по вашим просмотрам.'],
    },
    'search': {
        'title': 'Как найти фильм или сериал в боте',
        'description': 'Ищите произведение по названию и открывайте его карточку.',
        'steps': ['Откройте поиск в приложении или отправьте боту название.', 'Выберите подходящий результат.', 'В карточке можно посмотреть сведения и добавить произведение в избранное.'],
    },
    'roulette': {
        'title': 'Как выбрать фильм с помощью рулетки',
        'description': 'Рулетка помогает выбрать, что посмотреть из сохранённых произведений.',
        'steps': ['Добавьте несколько произведений в избранное.', 'Откройте раздел «Избранное» и выберите рулетку.', 'Запустите выбор и откройте предложенную карточку.'],
    },
}

GUIDE_DETAILS = {
    'favorites': [
        ('Где найти сохранённые фильмы и сериалы', 'Откройте раздел «Избранное» в приложении бота. Там находятся ваши папки и добавленные в них произведения. Выберите папку, чтобы увидеть её содержимое.'),
        ('Как вернуться к карточке', 'Нажмите на сохранённый фильм или сериал. В карточке можно посмотреть сведения о произведении и доступные действия.'),
    ],
    'folders': [
        ('Пример организации списков', 'Создайте папку «Смотрю сейчас» для текущих сериалов и отдельную папку «Буду смотреть» для фильмов и сериалов на будущее. Названия и значки выбираете вы.'),
        ('Как изменить порядок и настройки', 'В избранном можно изменить порядок папок и содержимого. Чтобы изменить название, цвет или значок, откройте настройки папки.'),
    ],
    'notifications': [
        ('За какими сериалами следит бот', 'Бот отправляет уведомления активным пользователям, у которых сериал есть в избранном или истории просмотров. Для конкретного сериала уведомления можно отключить в карточке.'),
        ('Почему сообщение может не прийти', 'Проверьте, что бот запущен и не заблокирован, сериал добавлен в избранное или историю, а уведомления для него не отключены. Сообщение отправляется, когда сервис обнаружит новый эпизод.'),
    ],
    'statistics': [
        ('Что можно посмотреть в статистике', 'В приложении доступны история просмотров, графики активности и подборки по вашим данным. Откройте нужную подборку, чтобы изучить записи подробнее.'),
        ('Что показывают данные', 'Статистика строится по сохранённой истории просмотров. Если просмотр отсутствует в истории, он не будет отражён в соответствующих показателях.'),
    ],
    'search': [
        ('Поиск на сайте', 'В каталоге сайта можно искать по русскому и оригинальному названию. Откройте результат, чтобы перейти к его карточке в Telegram.'),
        ('Если результат не найден', 'Попробуйте оригинальное название или другую часть названия. В результатах сравните год и оригинальное название, чтобы выбрать нужное произведение.'),
    ],
    'roulette': [
        ('Что выбирает рулетка', 'Рулетка помогает выбрать произведение из папок избранного. Сначала сохраните несколько фильмов или сериалов, между которыми хотите выбирать.'),
        ('Где открыть рулетку', 'Перейдите в избранное и нажмите значок рулетки в верхней части экрана. Затем запустите выбор в открывшемся окне.'),
    ],
}

# A fixed editorial selection: public catalogue URLs and order do not depend on
# the visitor, current time or changing popularity scores.
FEATURED_IMDB_IDS = (
    'tt0816692', 'tt0111161', 'tt0468569', 'tt0133093',
    'tt0903747', 'tt0944947', 'tt0137523', 'tt1375666',
    'tt0120737', 'tt0110912', 'tt2861424', 'tt1520211',
)


class PublicCatalogPaginator(Paginator):
    def __init__(self, object_list, per_page, *, cached_count=None, **kwargs):
        self.cached_count = cached_count
        self._query_count = None
        super().__init__(object_list, per_page, **kwargs)

    @property
    def count(self):
        if self.cached_count is not None:
            return self.cached_count
        if self._query_count is None:
            self._query_count = super().count
        return self._query_count


def _catalog_stats():
    db_name = settings.DATABASES['default']['NAME']
    return cache.get_or_set(
        f'public_catalog_type_counts:{db_name}',
        lambda: Show.objects.aggregate(
            total=Count('id'),
            movies=Count('id', filter=Q(type='Movie')),
            series=Count('id', filter=Q(type='Series')),
        ),
        3600,
    )


def _context(request, **extra):
    username = os.getenv('PUBLIC_BOT_USERNAME', 'kinopub_observer_bot').strip().lstrip('@')
    articles = PublicArticle.objects.filter(published_at__lte=timezone.now()).order_by('-published_at')
    bot_url = f'https://t.me/{username}' if username else ''
    return {
        'bot_url': bot_url,
        'site_bot_url': f'{bot_url}?start=site' if bot_url else '',
        'guides': GUIDES,
        'articles': articles,
        **extra,
    }


def home(request):
    stats = _catalog_stats()
    total = stats['total']
    rounded_total = (total // 100000) / 10
    movies = (stats['movies'] // 100000) / 10
    series = stats['series'] // 1000
    return render(request, 'public/home.html', _context(request, catalog_millions=f'{rounded_total:.1f}'.replace('.', ',') if total >= 1000000 else None, movie_millions=f'{movies:.1f}'.replace('.', ',') if stats['movies'] >= 1000000 else None, series_thousands=series if series else None))


@xframe_options_sameorigin
def wishlist_demo(request):
    response = render(request, 'public/wishlist_demo.html')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def catalog(request):
    query = request.GET.get('q', '').strip()[:120]
    featured = []
    if query:
        shows = Show.objects.exclude(title='').filter(Q(title__icontains=query) | Q(original_title__icontains=query)).order_by('-year', '-id')
    else:
        ordering = Case(*[When(imdb_id=imdb_id, then=Value(index)) for index, imdb_id in enumerate(FEATURED_IMDB_IDS)], output_field=IntegerField())
        if request.GET.get('page', '1') == '1':
            featured = list(Show.objects.filter(imdb_id__in=FEATURED_IMDB_IDS).order_by(ordering, 'id'))
        shows = Show.objects.exclude(title='').order_by('id')
    page = PublicCatalogPaginator(
        shows.only('id', 'title', 'original_title', 'year', 'type', 'kinopub_id', 'tmdb_poster_path'),
        48,
        cached_count=None if query else _catalog_stats()['total'],
    ).get_page(request.GET.get('page'))
    for show in [*featured, *page.object_list]:
        show.public_poster = build_poster_url(show.kinopub_id, show.tmdb_poster_path, 'medium')
    count_display = f'{page.paginator.count:,}'.replace(',', '\u00a0')
    return render(request, 'public/catalog.html', _context(request, page=page, query=query, featured=featured, count_display=count_display))


def show_detail(request, show_id):
    show = get_object_or_404(Show.objects.select_related('ext_rating').prefetch_related('genres', 'countries'), pk=show_id)
    show.public_poster = build_poster_url(show.kinopub_id, show.tmdb_poster_path, 'big')
    return render(request, 'public/show.html', _context(request, show=show))


def guide_index(request):
    return render(request, 'public/guides.html', _context(request))


def guide_detail(request, slug):
    guide = GUIDES.get(slug)
    if not guide:
        article = get_object_or_404(PublicArticle, slug=slug, published_at__lte=timezone.now())
        structured = {'@context': 'https://schema.org', '@type': 'Article', 'headline': article.title, 'description': article.description, 'datePublished': article.published_at.isoformat(), 'mainEntityOfPage': request.build_absolute_uri(request.path)}
        if article.updated_at >= article.published_at:
            structured['dateModified'] = article.updated_at.isoformat()
        structured_json = json.dumps(structured, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        return render(request, 'public/article.html', _context(request, article=article, structured_json=structured_json))
    related = [(key, item) for key, item in GUIDES.items() if key != slug][:3]
    return render(request, 'public/guide.html', _context(request, guide=guide, sections=GUIDE_DETAILS.get(slug, []), related=related))


def sitemap(request):
    bucket = ExpressionWrapper((F('id') - Value(1)) / Value(10000) + Value(1), output_field=BigIntegerField())
    db_name = settings.DATABASES['default']['NAME']
    pages = cache.get_or_set(
        f'public_sitemap_ranges:{db_name}',
        lambda: list(Show.objects.order_by().annotate(bucket=bucket).values_list('bucket', flat=True).distinct().order_by('bucket')),
        300,
    )
    urls = [reverse('public_sitemap_shows', args=[page]) for page in pages]
    entries = ''.join(f'<sitemap><loc>{escape(request.build_absolute_uri(url))}</loc></sitemap>' for url in urls)
    entries = f'<sitemap><loc>{escape(request.build_absolute_uri(reverse("public_sitemap_shows", args=[0])))}</loc></sitemap>' + entries
    return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</sitemapindex>', content_type='application/xml')


def sitemap_shows(request, page):
    dates = {}
    if page == 0:
        urls = [reverse('index'), reverse('public_catalog'), reverse('public_guides')]
        urls += [reverse('public_guide', args=[slug]) for slug in GUIDES]
        for slug, updated_at in PublicArticle.objects.filter(published_at__lte=timezone.now()).values_list('slug', 'updated_at'):
            url = reverse('public_guide', args=[slug])
            urls.append(url)
            dates[url] = updated_at.isoformat()
    else:
        ids = Show.objects.filter(id__gt=(page - 1) * 10000, id__lte=page * 10000).order_by('id').values_list('id', flat=True)
        urls = [reverse('public_show', args=[pk]) for pk in ids]
        if not urls:
            raise Http404
    entries = ''.join(f'<url><loc>{escape(request.build_absolute_uri(url))}</loc>' + (f'<lastmod>{escape(dates[url])}</lastmod>' if url in dates else '') + '</url>' for url in urls)
    return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>', content_type='application/xml')


@csrf_exempt
@require_http_methods(['GET', 'PUT'])
def article_api(request, slug):
    token = getattr(settings, 'PUBLIC_ARTICLE_API_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    if not token or not secrets.compare_digest(supplied, 'Bearer ' + token):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if slug in GUIDES:
        return JsonResponse({'error': 'Reserved slug'}, status=400)
    if request.method == 'GET':
        article = get_object_or_404(PublicArticle, slug=slug)
        return JsonResponse({'slug': article.slug, 'title': article.title, 'description': article.description, 'body': article.body, 'published_at': article.published_at, 'updated_at': article.updated_at})
    try:
        if len(request.body) > 200000:
            raise ValueError('Request too large')
        data = json.loads(request.body)
        title, description, body = (data[k].strip() for k in ('title', 'description', 'body'))
        if not title or len(title) > 255 or not description or len(description) > 300 or not body:
            raise ValueError('Invalid article fields')
        published = data.get('published_at')
        published_at = parse_datetime(published) if published else None
        if published and (published_at is None or timezone.is_naive(published_at)):
            raise ValueError('published_at requires an ISO 8601 timestamp with timezone')
    except (KeyError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    article, created = PublicArticle.objects.update_or_create(slug=slug, defaults={'title': title, 'description': description, 'body': body, 'published_at': published_at})
    return JsonResponse({'slug': article.slug, 'published_at': article.published_at, 'updated_at': article.updated_at}, status=201 if created else 200)


@csrf_exempt
@require_http_methods(['POST'])
def visit_event(request):
    try:
        if len(request.body) > 1024:
            raise ValueError
        data = json.loads(request.body)
        session_id = uuid.UUID(data['session_id'])
        event = data['event']
        if event not in ('pageview', 'tick'):
            raise ValueError
        seconds = max(0, min(int(data.get('seconds', 0)), 30))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid event'}, status=400)
    visit, created = PublicVisit.objects.get_or_create(session_id=session_id)
    PublicVisit.objects.filter(pk=visit.pk).update(last_seen_at=timezone.now(), active_seconds=F('active_seconds') + seconds, pageviews=F('pageviews') + (1 if event == 'pageview' and not created else 0))
    return HttpResponse(status=204)
