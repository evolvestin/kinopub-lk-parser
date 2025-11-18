from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from kinopub_parser.admin import admin_site
from django.contrib import admin

admin.site = admin_site
admin.sites.site = admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
]

if not settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)