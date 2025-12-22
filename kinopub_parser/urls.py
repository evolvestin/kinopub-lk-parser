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
    path('api/bot/check/<int:telegram_id>/', views.check_bot_user),
    path('api/bot/register/', views.register_bot_user),
    path('api/bot/set_role/', views.set_bot_user_role),
    path('api/bot/update_user/', views.update_bot_user),
    path('api/bot/search/', views.bot_search_shows),
    path('api/bot/show/<int:show_id>/', views.bot_get_show_details),
    path('api/bot/show/<int:show_id>/episodes/', views.bot_get_show_episodes),
    path('api/bot/show/<int:show_id>/ratings/', views.bot_get_show_ratings_details),
    path('api/bot/imdb/<str:imdb_id>/', views.bot_get_by_imdb),
    path('api/bot/assign_view/', views.bot_assign_view),
    path('api/bot/unassign_view/', views.bot_unassign_view),
    path('api/bot/toggle_claim/', views.bot_toggle_claim),
    path('api/bot/toggle_view_user/', views.bot_toggle_view_user),
    path('api/bot/toggle_check/', views.bot_toggle_view_check),
    path('api/bot/rate/', views.bot_rate_show),
]

if not settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
