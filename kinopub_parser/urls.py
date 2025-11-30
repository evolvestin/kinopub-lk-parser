from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from django.views.generic.base import RedirectView

from app import views
from app.admin_site import admin_site

urlpatterns = [
    path('', views.index, name='index'),
    path('admin/', admin_site.urls),
    path(
        'favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico', permanent=True)
    ),
]

if not settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)