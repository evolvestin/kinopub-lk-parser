import re

from django.conf import settings


class ViteHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.marker = 'dynamic-vite-host.internal'

    def __call__(self, request):
        response = self.get_response(request)

        if settings.DEBUG and 'text/html' in response.get('Content-Type', ''):
            try:
                content = response.content.decode('utf-8')
                if self.marker in content:
                    # Заменяем абсолютно любой URL к Vite-хосту на наш прокси-путь
                    # Это поймает и /static/ (если django-vite его добавит) и /__vite__/
                    pattern = r'https?://dynamic-vite-host\.internal(?::\d+)?/(?:static/)?'
                    new_content = re.sub(pattern, '/__vite__/', content)
                    response.content = new_content.encode('utf-8')
                    response['Content-Length'] = len(response.content)
            except Exception:
                pass

        return response


class NoIndexMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        public_routes = {'index', 'public_catalog', 'public_show', 'public_guides', 'public_guide', 'public_sitemap', 'public_sitemap_shows'}
        route = getattr(request.resolver_match, 'url_name', None)
        searchable = route in public_routes and response.status_code == 200
        if route == 'public_catalog' and request.GET.get('q', '').strip():
            searchable = False
        if not searchable:
            response.setdefault('X-Robots-Tag', 'noindex, nofollow, noarchive')
        return response
