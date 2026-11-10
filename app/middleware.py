import re
import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin


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
        public_routes = {'index', 'public_catalog', 'public_show', 'public_guides', 'public_guide', 'public_sitemap', 'public_sitemap_shows', 'public_about', 'public_offer', 'public_privacy'}
        route = getattr(request.resolver_match, 'url_name', None)
        if route in public_routes | {'robots_txt'} and response.status_code in (301, 302, 307, 308):
            return response
        searchable = route in public_routes and response.status_code == 200
        if route == 'proxy_image_view' and response.status_code == 200 and response.get('Content-Type', '').startswith('image/'):
            searchable = True
        if route == 'public_catalog' and request.GET.get('q', '').strip():
            response.setdefault('X-Robots-Tag', 'noindex, follow')
            return response
        if not searchable:
            response.setdefault('X-Robots-Tag', 'noindex, nofollow, noarchive')
        return response


class PublicCanonicalHostMiddleware(MiddlewareMixin):
    """Redirect only public pages from a public IP, leaving service APIs alone."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        base = getattr(settings, 'PUBLIC_SITE_URL', '').rstrip('/')
        parsed = urlsplit(base)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            return None
        route = getattr(request.resolver_match, 'url_name', None)
        if route not in {'index', 'public_catalog', 'public_show', 'public_guides', 'public_guide', 'public_sitemap', 'public_sitemap_shows', 'public_about', 'public_offer', 'public_privacy', 'robots_txt'}:
            return None
        try:
            host = urlsplit('//' + request.get_host()).hostname
            is_public_ip = ipaddress.ip_address(host).is_global
        except (ValueError, TypeError):
            return None
        if is_public_ip:
            return HttpResponsePermanentRedirect(base + request.get_full_path())
        return None
