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
    # WebApp Endpoints
    path('webapp/', views.webapp_index, name='webapp_index'),
    path('api/webapp/stats/', views.webapp_get_stats, name='webapp_get_stats'),
    # Bot API Endpoints
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
    path('api/bot/assign_group_view/', views.bot_assign_group_view),
    path('api/bot/get_user_groups/', views.bot_get_user_groups),
    path('api/bot/toggle_view_user/', views.bot_toggle_view_user),
    path('api/bot/toggle_check/', views.bot_toggle_view_check),
    path('api/bot/rate/', views.bot_rate_show),
    path('api/bot/log/', views.bot_log_message),
    path('api/bot/log_entry/', views.bot_create_log_entry),
]

if not settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
