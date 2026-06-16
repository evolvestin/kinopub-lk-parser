from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path
from django.views.generic.base import RedirectView

from app import views
from app.admin_site import admin_site
from app.views import vite_proxy_view

if settings.DEBUG:
    proxy_patterns = [
        # Убеждаемся, что захватываем всё, что начинается с __vite__
        re_path(r'^__vite__/(?P<path>.*)$', vite_proxy_view),
        path('__vite__/', vite_proxy_view, {'path': ''}),
    ]
else:
    proxy_patterns = []

urlpatterns = proxy_patterns + [
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('', views.index, name='index'),
    path('admin/', admin_site.urls),
    path('api/internal/set_url', views.internal_set_url, name='internal_set_url'),
    path(
        'api/admin/wishlist/folder/<int:folder_id>/',
        views.admin_get_folder_content,
        name='admin_get_folder_content',
    ),
    path('api/admin/global_stats/', views.admin_get_global_stats, name='admin_get_global_stats'),
    path(
        'favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico', permanent=True)
    ),
    path('api/metrics/details/<str:key>/', views.get_metric_details, name='get_metric_details'),
    path('api/metrics/queue_update/', views.queue_update_details, name='queue_update_details'),
    path('api/metrics/merge_persons/', views.merge_persons_api, name='merge_persons_api'),
    # WebApp Endpoints
    path('webapp/', views.webapp_index, name='webapp_index'),
    path(
        'api/webapp/collection/<str:collection_type>/<int:item_id>/',
        views.webapp_get_collection,
        name='webapp_get_collection',
    ),
    path('api/webapp/search/', views.webapp_search, name='webapp_search'),
    path('api/webapp/stats/', views.webapp_get_stats, name='webapp_get_stats'),
    path(
        'api/webapp/detailed_stats/',
        views.webapp_get_detailed_stats,
        name='webapp_get_detailed_stats',
    ),
    path('api/webapp/bake_stats/', views.webapp_bake_stats, name='webapp_bake_stats'),
    path(
        'api/webapp/shared_stats/<str:stat_id>/',
        views.webapp_get_shared_stats,
        name='webapp_get_shared_stats',
    ),
    path('api/webapp/rate/', views.webapp_rate_show, name='webapp_rate_show'),
    path('api/webapp/delete_rating/', views.webapp_delete_rating, name='webapp_delete_rating'),
    path('api/webapp/get_episodes/', views.webapp_get_episodes, name='webapp_get_episodes'),
    path('api/webapp/show/<int:show_id>/', views.webapp_get_show_full, name='webapp_get_show_full'),
    path('api/webapp/wishlist/', views.webapp_wishlist_data, name='webapp_wishlist_data'),
    path('api/webapp/casino/', views.webapp_casino, name='webapp_casino'),
    path('api/webapp/add_view/', views.webapp_add_view, name='webapp_add_view'),
    path('api/webapp/remove_view/', views.webapp_remove_view, name='webapp_remove_view'),
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
