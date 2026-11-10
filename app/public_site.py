"""Public, indexable pages for discovering the Telegram application."""
import os
import json
import secrets
import uuid
import mimetypes
from xml.sax.saxutils import escape
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import BigIntegerField, Case, ExpressionWrapper, F, IntegerField, Q, Value, When
from django.http import FileResponse, Http404, HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin

from app.models import Person, PublicArticle, PublicVisit, Show, ShowCrew, ShowDuration, UserRating, ViewHistory, ViewUser, WishlistItem
from shared.media import build_poster_url
from shared.constants import (
    PROFESSIONS_PLURAL_MAP_RU,
    RAW_TO_NORMALIZED_COUNTRY,
    RAW_TO_NORMALIZED_GENRE,
    RAW_TO_NORMALIZED_RU,
    SERIES_TYPES,
    SHOW_STATUS_DISPLAY_RU,
    SHOW_TYPE_DISPLAY_RU,
)


LEGACY_GUIDES = {
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
        lambda: {'total': Show.objects.count()},
        3600,
    )


def _context(request, **extra):
    username = os.getenv('PUBLIC_BOT_USERNAME', 'kinopub_observer_bot').strip().lstrip('@')
    articles = PublicArticle.objects.filter(published_at__lte=timezone.now()).order_by('-published_at')
    bot_url = f'https://t.me/{username}' if username else ''
    return {
        'bot_url': bot_url,
        'site_bot_url': f'{bot_url}?start=site' if bot_url else '',
        'offer_url': settings.PUBLIC_OFFER_URL or reverse('public_offer'),
        'privacy_url': reverse('public_privacy'),
        'guides': {},
        'guide_previews': articles[:9],
        'articles': articles,
        **extra,
    }


def legal_page(request, document):
    if document not in ('offer', 'privacy'):
        raise Http404
    return render(request, 'public/legal.html', _context(request, document=document))


def about(request):
    return render(request, 'public/about.html', _context(request))


def home(request):
    stats = _catalog_stats()
    total = stats['total']
    rounded_total = (total // 100000) / 10
    def usage_counts():
        return {
            'users': ViewUser.objects.filter(telegram_id__isnull=False).count(),
            'views': ViewHistory.objects.filter(is_checked=True).count(),
            'favorites': WishlistItem.objects.filter(is_active=True, folder__is_deleted=False).count(),
            'ratings': UserRating.objects.count(),
        }
    usage = cache.get_or_set('public_usage_counts_v4', usage_counts, 300)
    return render(request, 'public/home.html', _context(request, catalog_millions=f'{rounded_total:.1f}'.replace('.', ',') if total >= 1000000 else None, users_count=usage['users'], recorded_views=usage['views'], favorites_count=usage['favorites'], ratings_count=usage['ratings']))


@xframe_options_sameorigin
def wishlist_demo(request):
    context = {}
    def demo_ratings():
        ratings = UserRating.objects.filter(show_id__in=[74959, 8739]).select_related('user')
        grouped = {}
        for rating in ratings:
            grouped.setdefault(rating.show_id, []).append(rating)
        result = {}
        for show in Show.objects.filter(id__in=grouped):
            show._prefetched_objects_cache = {'ratings': grouped[show.id]}
            value, _ = show.get_internal_rating_data()
            if value is not None:
                result[show.id] = round(value, 1)
        return result
    context['demo_ratings'] = cache.get_or_set('public_demo_ratings_v1', demo_ratings, 300)
    if 'stats-example' in request.GET:
        people = {
            'Педро Паскаль': 68732, 'Брайан Крэнстон': 2013, 'Киллиан Мёрфи': 3170,
            'Мишель Макларен': 111416, 'Дэвид Наттер': 556533, 'Винс Гиллиган': 70616,
            'Крейг Мэйзин': 569070,
        }
        records = Person.objects.select_related('master_person').in_bulk(people.values())
        context['stats_example_people'] = {
            name: {'photo_url': records[pk].photo_url, 'fallback_photo_url': records[pk].canonical.kp_photo_url}
            for name, pk in people.items() if pk in records
        }
    response = render(request, 'public/wishlist_demo.html', context)
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
    visible_shows = [*featured, *page.object_list]
    ratings_by_show = {}
    for rating in UserRating.objects.filter(show_id__in=[show.pk for show in visible_shows]).select_related('user'):
        ratings_by_show.setdefault(rating.show_id, []).append(rating)
    for show in visible_shows:
        show._prefetched_objects_cache = {'ratings': ratings_by_show.get(show.pk, [])}
        show.public_internal_rating, _ = show.get_internal_rating_data()
        show.public_poster = build_poster_url(show.kinopub_id, show.tmdb_poster_path, 'medium')
    count_display = f'{page.paginator.count:,}'.replace(',', '\u00a0')
    return render(request, 'public/catalog.html', _context(request, page=page, query=query, featured=featured, count_display=count_display))


def show_detail(request, show_id):
    show = get_object_or_404(
        Show.objects.select_related('ext_rating').prefetch_related(
            'genres', 'countries',
            # Load credits in one query and resolve aliases without N+1 reads.
            'showcrew_set__person__master_person',
        ),
        pk=show_id,
    )
    show.public_poster = build_poster_url(show.kinopub_id, show.tmdb_poster_path, 'big')
    show.public_poster_absolute = request.build_absolute_uri(show.public_poster) if show.public_poster else None
    show.public_internal_rating, _ = show.get_internal_rating_data()
    show.public_type_label = SHOW_TYPE_DISPLAY_RU.get(show.type, show.type)
    show.public_status_label = SHOW_STATUS_DISPLAY_RU.get(show.status, show.status) if show.type in SERIES_TYPES else ''
    show.public_is_series = show.type in SERIES_TYPES
    show.public_genres = sorted(
        {RAW_TO_NORMALIZED_GENRE.get(genre.name, genre.name) for genre in show.genres.all()}
    )
    show.public_countries = sorted(
        {RAW_TO_NORMALIZED_COUNTRY.get(country.name, country.name) for country in show.countries.all()}
    )

    grouped_crew = {}
    seen_people = set()
    for credit in show.showcrew_set.all():
        person = credit.person.canonical
        profession = credit.normalized_profession
        if not profession or profession == '-':
            profession = 'Другое'
        identity = (profession, person.pk)
        if identity in seen_people:
            continue
        seen_people.add(identity)
        group = grouped_crew.setdefault(profession, [])
        group.append({
            'name': person.name,
            'photo_url': person.photo_url,
            'profession': profession,
        })

    preferred_professions = [
        'Актёр', 'Актёр дубляжа', 'Режиссёр', 'Сценарист', 'Продюссер',
        'Оператор', 'Композитор', 'Художник', 'Монтажёр',
    ]
    crew = []
    added_professions = set()
    for profession in [*preferred_professions, *grouped_crew.keys()]:
        people = grouped_crew.get(profession)
        if not people or profession in added_professions:
            continue
        added_professions.add(profession)
        crew.append({
            'title': PROFESSIONS_PLURAL_MAP_RU.get(profession, profession)
            if len(people) > 1 else profession,
            'people': people,
        })

    seasons_by_number = {}
    if show.type in SERIES_TYPES:
        episode_rows = ShowDuration.objects.filter(
            show_id=show.pk,
            season_number__isnull=False,
            season_number__gt=0,
            episode_number__isnull=False,
            episode_number__gt=0,
        ).values('season_number', 'episode_number').order_by('season_number', 'episode_number')
        for episode in episode_rows:
            season = seasons_by_number.setdefault(
                episode['season_number'],
                {'season_number': episode['season_number'], 'episodes': [], 'episode_count': 0},
            )
            season['episodes'].append(episode)
            season['episode_count'] += 1
    seasons = list(seasons_by_number.values())
    total_episodes = sum(season['episode_count'] for season in seasons)

    structured = {
        '@context': 'https://schema.org',
        '@type': 'TVSeries' if show.public_is_series else 'Movie' if show.type in ('Movie', 'Documentary Movie', '3D Movie') else 'CreativeWork',
        'name': show.title,
        'alternateName': show.original_title if show.original_title != show.title else None,
        'description': show.plot[:500] if show.plot else None,
        'image': request.build_absolute_uri(show.public_poster) if show.public_poster else None,
        'genre': show.public_genres,
        'countryOfOrigin': show.public_countries,
        'datePublished': str(show.year) if show.year else None,
        'actor': [
            {'@type': 'Person', 'name': person['name']}
            for group in crew if group['title'].startswith('Акт')
            for person in group['people']
        ],
    }
    structured_json = json.dumps(
        {key: value for key, value in structured.items() if value}, ensure_ascii=False
    ).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return render(
        request,
        'public/show.html',
        _context(
            request,
            show=show,
            seasons=seasons,
            total_episodes=total_episodes,
            total_season_count=len(seasons),
            crew=crew,
            structured_json=structured_json,
        ),
    )


def guide_index(request):
    articles = PublicArticle.objects.filter(published_at__lte=timezone.now()).order_by('-published_at')
    return render(request, 'public/guides.html', _context(request, articles=articles))


def guide_detail(request, slug):
    legacy_slugs = {
        'favorites': 'add-show-to-favorites',
        'folders': 'organize-favorite-folders',
        'notifications': 'new-episode-notifications',
        'statistics': 'viewing-statistics',
        'search': 'find-movie-in-catalog',
        'roulette': 'choose-from-favorites',
    }
    if slug in legacy_slugs:
        return HttpResponsePermanentRedirect(reverse('public_guide', args=[legacy_slugs[slug]]))
    article = get_object_or_404(PublicArticle, slug=slug, published_at__lte=timezone.now())
    structured = {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': article.title, 'description': article.description,
        'datePublished': article.published_at.isoformat(),
        'dateModified': article.updated_at.isoformat(),
        'inLanguage': 'ru',
        'mainEntityOfPage': request.build_absolute_uri(request.path),
        'author': {'@type': 'Organization', 'name': 'KinoPub Observer'},
        'publisher': {'@type': 'Organization', 'name': 'KinoPub Observer'},
    }
    images = []
    for block in article.content_blocks:
        image = block if block.get('type') == 'image' else block.get('image') if block.get('type') == 'step' else None
        if isinstance(image, dict) and image.get('src', '').startswith('/'):
            images.append(image['src'])
    article_images = [request.build_absolute_uri(src) for src in images[:3]]
    if images:
        structured['image'] = article_images
    structured_json = json.dumps(structured, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    related = PublicArticle.objects.filter(published_at__lte=timezone.now()).exclude(pk=article.pk).order_by('-published_at')[:3]
    return render(request, 'public/article.html', _context(request, article=article, related=related, structured_json=structured_json, article_images=article_images))


def _article_token_valid(request):
    token = getattr(settings, 'PUBLIC_ARTICLE_API_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    return bool(token and secrets.compare_digest(supplied, 'Bearer ' + token))


@csrf_exempt
@require_http_methods(['POST'])
def article_asset_api(request, slug):
    if not _article_token_valid(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    uploaded = request.FILES.get('image')
    if not uploaded or uploaded.size > 12 * 1024 * 1024:
        return JsonResponse({'error': 'Image required; maximum size is 12 MB'}, status=400)
    signature = uploaded.read(12)
    uploaded.seek(0)
    image_types = ((b'\x89PNG\r\n\x1a\n', 'png', 'image/png'), (b'\xff\xd8\xff', 'jpg', 'image/jpeg'))
    image = next(((ext, mime) for magic, ext, mime in image_types if signature.startswith(magic)), None)
    if not image and signature[:4] == b'RIFF' and signature[8:12] == b'WEBP':
        image = ('webp', 'image/webp')
    if not image:
        return JsonResponse({'error': 'Only PNG, JPEG and WebP images are supported'}, status=400)
    filename = f'{uuid.uuid4().hex}.{image[0]}'
    directory = Path(settings.PUBLIC_ARTICLE_MEDIA_ROOT) / slug
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    with target.open('wb') as output:
        for chunk in uploaded.chunks():
            output.write(chunk)
    return JsonResponse({'src': f'/articles/assets/{slug}/{filename}', 'content_type': image[1]}, status=201)


def article_asset(request, slug, filename):
    path = Path(settings.PUBLIC_ARTICLE_MEDIA_ROOT) / slug / filename
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open('rb'), content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _sitemap_ranges():
    if connection.vendor == 'postgresql':
        table = connection.ops.quote_name(Show._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'''
                SELECT bucket FROM generate_series(
                    1::bigint, (SELECT (COALESCE(MAX(id), 0) + 9999) / 10000 FROM {table})
                ) AS bucket
                WHERE EXISTS (SELECT 1 FROM {table} WHERE id > (bucket - 1) * 10000 AND id <= bucket * 10000)
                ORDER BY bucket
            ''')
            return [row[0] for row in cursor.fetchall()]
    bucket = ExpressionWrapper((F('id') - Value(1)) / Value(10000) + Value(1), output_field=BigIntegerField())
    return list(Show.objects.order_by().annotate(bucket=bucket).values_list('bucket', flat=True).distinct().order_by('bucket'))


def sitemap(request):
    db_name = settings.DATABASES['default']['NAME']
    pages = cache.get_or_set(
        f'public_sitemap_ranges:{db_name}',
        _sitemap_ranges,
        300,
    )
    urls = [reverse('public_sitemap_shows', args=[page]) for page in pages]
    entries = ''.join(f'<sitemap><loc>{escape(request.build_absolute_uri(url))}</loc></sitemap>' for url in urls)
    entries = f'<sitemap><loc>{escape(request.build_absolute_uri(reverse("public_sitemap_shows", args=[0])))}</loc></sitemap>' + entries
    return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</sitemapindex>', content_type='application/xml')


def sitemap_shows(request, page):
    dates = {}
    if page == 0:
        urls = [reverse('index'), reverse('public_catalog'), reverse('public_guides'), reverse('public_about'), reverse('public_offer'), reverse('public_privacy')]
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
    if not _article_token_valid(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method == 'GET':
        article = get_object_or_404(PublicArticle, slug=slug)
        return JsonResponse({'slug': article.slug, 'title': article.title, 'description': article.description, 'body': article.body, 'content_blocks': article.content_blocks, 'published_at': article.published_at, 'updated_at': article.updated_at})
    try:
        if len(request.body) > 2_000_000:
            raise ValueError('Request too large')
        data = json.loads(request.body)
        title, description = (data[k].strip() for k in ('title', 'description'))
        blocks = data.get('content_blocks', [])
        body = data.get('body', '')
        if not title or len(title) > 255 or not description or len(description) > 300 or not isinstance(blocks, list) or len(blocks) > 100 or (not body and not blocks):
            raise ValueError('Invalid article fields')
        valid_types = {'lead', 'paragraph', 'heading', 'image', 'step', 'steps', 'list', 'callout', 'quote', 'guide_link'}
        for block in blocks:
            if not isinstance(block, dict) or block.get('type') not in valid_types:
                raise ValueError('Invalid content block')
            if block['type'] == 'guide_link':
                slug_value, label = block.get('slug'), block.get('text')
                if not isinstance(slug_value, str) or not slug_value or len(slug_value) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in slug_value):
                    raise ValueError('Guide link requires a valid slug')
                if not isinstance(label, str) or not label.strip() or len(label) > 200:
                    raise ValueError('Guide link requires a concise label')
            if block['type'] == 'image':
                src, alt, caption = block.get('src'), block.get('alt'), block.get('caption')
                if not isinstance(src, str) or not src.startswith('/articles/assets/') or '..' in src:
                    raise ValueError('Images must use uploaded article assets')
                if not isinstance(alt, str) or not alt.strip() or len(alt) > 300 or not isinstance(caption, str) or not caption.strip() or len(caption) > 500:
                    raise ValueError('Images require a concise alt text and caption')
            if block['type'] == 'step':
                if not isinstance(block.get('title'), str) or not block['title'].strip() or len(block['title']) > 160:
                    raise ValueError('Step blocks require a short title')
                if not isinstance(block.get('text'), str) or not block['text'].strip() or len(block['text']) > 1200:
                    raise ValueError('Step blocks require clear action instructions')
                image = block.get('image')
                if image is not None:
                    if not isinstance(image, dict):
                        raise ValueError('Step images must be an object')
                    src, alt, caption = image.get('src'), image.get('alt'), image.get('caption')
                    if not isinstance(src, str) or not src.startswith('/articles/assets/') or '..' in src:
                        raise ValueError('Step images must use uploaded article assets')
                    if not isinstance(alt, str) or not alt.strip() or len(alt) > 300 or not isinstance(caption, str) or not caption.strip() or len(caption) > 500:
                        raise ValueError('Step images require concise alt text and a caption')
                result = block.get('result')
                if result is not None and (not isinstance(result, str) or len(result) > 500):
                    raise ValueError('Step results must be under 500 characters')
            if block['type'] in {'steps', 'list'} and (not isinstance(block.get('items'), list) or not block['items'] or len(block['items']) > 30 or not all(isinstance(item, str) and item.strip() and len(item) <= 1000 for item in block['items'])):
                raise ValueError('List blocks require text items')
            if block['type'] in {'lead', 'paragraph', 'heading', 'callout', 'quote'} and (not isinstance(block.get('text'), str) or not block['text'].strip() or len(block['text']) > 10000):
                raise ValueError('Text block requires non-empty text under 10000 characters')
        published = data.get('published_at')
        published_at = parse_datetime(published) if published else None
        if published and (published_at is None or timezone.is_naive(published_at)):
            raise ValueError('published_at requires an ISO 8601 timestamp with timezone')
    except (KeyError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    article, created = PublicArticle.objects.update_or_create(slug=slug, defaults={'title': title, 'description': description, 'body': body, 'content_blocks': blocks, 'published_at': published_at})
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
