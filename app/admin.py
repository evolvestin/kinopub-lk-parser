import json

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from redis import Redis

from app.admin_site import admin_site
from app.models import (
    Code,
    Country,
    Genre,
    LogEntry,
    Person,
    SharedStat,
    Show,
    ShowDuration,
    TelegramLog,
    UserRating,
    ViewHistory,
    ViewUser,
    ViewUserGroup,
)
from app.telegram_bot import TelegramSender
from app.views import sync_user_permissions
from shared.constants import UserRole


def _format_object_list_html(queryset, url_name, count_attr='show_count'):
    """Универсальная функция для форматирования списка ссылок на объекты в админке."""
    if not queryset:
        return 'No items found.'

    html = '<ul>'
    for item in queryset:
        link = reverse(url_name, args=[item.id])
        count = getattr(item, count_attr, 0)
        html += f'<li><a href="{link}">{item.name}</a> ({count} shows)</li>'
    html += '</ul>'
    return format_html(html)


def _get_user_stats_html(queryset_filter_q):
    """Генерирует HTML список статистики просмотров пользователей."""
    stats = (
        ViewUser.objects.filter(queryset_filter_q)
        .distinct()
        .annotate(shows_count=Count('history__show', distinct=True, filter=queryset_filter_q))
        .order_by('-shows_count')
    )

    if not stats:
        return 'No views yet.'

    html = '<ul>'
    for user in stats:
        user_label = user.name or user.username or str(user.telegram_id)
        html += f'<li><strong>{user_label}</strong>: {user.shows_count} shows</li>'
    html += '</ul>'
    return format_html(html)


def _get_related_items_html(model, query_filter, url_name):
    """Генерирует HTML список связанных объектов (актеров, жанров, стран)."""
    # Для Person поле называется acted_in_shows, для остальных - show
    relation_field = 'acted_in_shows' if model == Person else 'show'

    items = (
        model.objects.filter(query_filter)
        .distinct()
        .annotate(show_count=Count(relation_field, filter=query_filter))
        .order_by('-show_count')[:20]
    )
    return _format_object_list_html(items, url_name, count_attr='show_count')


admin_site.register(Group, GroupAdmin)


class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_superuser',
        'get_view_user_link',
    )
    readonly_fields = (
        'last_login',
        'date_joined',
        'is_staff',
        'is_superuser',
        'get_groups_display',
        'get_permissions_display',
    )
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        (
            'Permissions (Managed via ViewUser Role)',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'get_groups_display',
                    'get_permissions_display',
                ),
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    @admin.display(description='Groups')
    def get_groups_display(self, user_instance):
        groups = user_instance.groups.all()
        if not groups:
            return '-'
        return format_html(
            '<ul>{}</ul>', format_html_join('', '<li>{}</li>', ((group.name,) for group in groups))
        )

    @admin.display(description='User permissions')
    def get_permissions_display(self, user_instance):
        permissions = user_instance.user_permissions.all()
        if not permissions:
            return '-'
        return format_html(
            '<div style="max-height: 400px; overflow-y: auto;"><ul>{}</ul></div>',
            format_html_join('', '<li>{}</li>', ((permission,) for permission in permissions)),
        )

    @admin.display(description='ViewUser Profile')
    def get_view_user_link(self, obj):
        if hasattr(obj, 'view_user') and obj.view_user:
            url = reverse('admin:app_viewuser_change', args=[obj.view_user.id])
            return format_html('<a href="{}">{}</a>', url, obj.view_user)
        return '-'


admin_site.register(User, CustomUserAdmin)


@admin.register(Code, site=admin_site)
class CodeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'telegram_message_id',
        'received_at',
        'created_at',
        'updated_at',
    )
    list_filter = ('received_at',)
    search_fields = ('code',)
    readonly_fields = (
        'code',
        'telegram_message_id',
        'received_at',
        'created_at',
        'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SeasonEpisodeDisplayMixin:
    """Миксин для отображения номера сезона и эпизода в админке."""

    @admin.display(description='Season', ordering='season_number')
    def get_season(self, obj):
        return obj.season_number if obj.season_number and obj.season_number > 0 else '-'

    @admin.display(description='Episode', ordering='episode_number')
    def get_episode(self, obj):
        return obj.episode_number if obj.episode_number and obj.episode_number > 0 else '-'


class ShowDurationInline(SeasonEpisodeDisplayMixin, admin.TabularInline):
    model = ShowDuration
    extra = 0
    readonly_fields = (
        'get_season',
        'get_episode',
        'duration_seconds',
        'created_at',
        'updated_at',
    )
    can_delete = False


class ViewHistoryInline(SeasonEpisodeDisplayMixin, admin.TabularInline):
    model = ViewHistory
    extra = 0
    readonly_fields = (
        'view_date',
        'get_season',
        'get_episode',
        'created_at',
        'updated_at',
    )
    can_delete = False


class UserRatingInline(admin.TabularInline):
    model = UserRating
    extra = 1
    autocomplete_fields = ('user',)


class AverageRatingFilter(admin.SimpleListFilter):
    title = 'Average Rating'
    parameter_name = 'avg_rating'

    def lookups(self, request, model_admin):
        return [(f'{i}', f'{i}.0 - {i + 1}.0') for i in range(1, 10)] + [('10', '10.0')]

    def queryset(self, request, queryset):
        if self.value():
            try:
                value = int(self.value())
                if '_avg_rating' not in queryset.query.annotations:
                    queryset = queryset.annotate(_avg_rating=Avg('ratings__rating'))

                if value == 10:
                    return queryset.filter(_avg_rating__gte=10)
                return queryset.filter(_avg_rating__gte=value, _avg_rating__lt=value + 1)
            except ValueError:
                pass
        return queryset


@admin.register(Show, site=admin_site)
class ShowAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'original_title',
        'type',
        'status',
        'year',
        'view_count',
        'total_duration_hours',
        'get_avg_rating',
        'created_at',
        'updated_at',
    )
    list_filter = ('type', 'status', AverageRatingFilter, 'year')
    search_fields = ('title', 'original_title', 'plot')
    inlines = [ShowDurationInline, ViewHistoryInline, UserRatingInline]
    readonly_fields = (
        'id',
        'admin_actions',
        'title',
        'original_title',
        'plot',
        'type',
        'status',
        'year',
        'kinopoisk_url',
        'kinopoisk_rating',
        'kinopoisk_votes',
        'imdb_url',
        'imdb_rating',
        'imdb_votes',
        'created_at',
        'updated_at',
    )
    autocomplete_fields = ('directors', 'actors')
    filter_horizontal = ('countries', 'genres')
    actions = ['action_update_details', 'action_update_durations']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        duration_subquery = (
            ShowDuration.objects.filter(show=OuterRef('pk'))
            .values('show')
            .annotate(total=Sum('duration_seconds'))
            .values('total')
        )

        queryset = queryset.annotate(
            _view_count=Count('viewhistory', distinct=True),
            _total_duration=Subquery(duration_subquery),
            _avg_rating=Avg('ratings__rating'),
        )
        return queryset

    @admin.display(description='Views', ordering='_view_count')
    def view_count(self, obj):
        return obj._view_count

    @admin.display(description='Duration', ordering='_total_duration')
    def total_duration_hours(self, obj):
        if obj and obj._total_duration:
            total_minutes = int(obj._total_duration // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60

            if hours > 0:
                return f'{hours}ч {minutes}м'
            return f'{minutes}м'
        return '-'

    @admin.display(description='Avg Rating', ordering='_avg_rating')
    def get_avg_rating(self, obj):
        ratings = obj.ratings.all()
        if not ratings:
            return '-'
        avg = sum(r.rating for r in ratings) / len(ratings)
        return round(avg, 2)

    @admin.display(description='Actions')
    def admin_actions(self, obj):
        if not obj.id:
            return '-'

        url_details = reverse('admin:show_update_details', args=[obj.id])
        url_durations = reverse('admin:show_update_durations', args=[obj.id])

        return format_html(
            '<div style="display: flex; gap: 10px;">'
            '<a class="button" style="background-color: #3498db; color: white;" href="{}">'
            'Queue Update Details'
            '</a>'
            '<a class="button" style="background-color: #9b59b6; color: white;" href="{}">'
            'Queue Update Durations'
            '</a>'
            '</div>',
            url_details,
            url_durations,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/update-details/',
                self.admin_site.admin_view(self.process_update_details),
                name='show_update_details',
            ),
            path(
                '<int:object_id>/update-durations/',
                self.admin_site.admin_view(self.process_update_durations),
                name='show_update_durations',
            ),
        ]
        return custom_urls + urls

    def _add_to_redis_queue(self, queue_name, object_id):
        try:
            r = Redis.from_url(settings.CELERY_BROKER_URL)
            r.sadd(queue_name, object_id)
            return True
        except Exception:
            return False

    def process_update_details(self, request, object_id):
        if self._add_to_redis_queue('queue:update_details', object_id):
            self.message_user(request, f'Show {object_id} added to "Update Details" queue.')
        else:
            self.message_user(request, 'Error connecting to Redis.', level='ERROR')
        return HttpResponseRedirect(reverse('admin:app_show_change', args=[object_id]))

    def process_update_durations(self, request, object_id):
        if self._add_to_redis_queue('queue:update_durations', object_id):
            self.message_user(request, f'Show {object_id} added to "Update Durations" queue.')
        else:
            self.message_user(request, 'Error connecting to Redis.', level='ERROR')
        return HttpResponseRedirect(reverse('admin:app_show_change', args=[object_id]))

    @admin.action(description='Queue Update Details for selected shows')
    def action_update_details(self, request, queryset):
        count = 0
        for show in queryset:
            if self._add_to_redis_queue('queue:update_details', show.id):
                count += 1
        self.message_user(request, f'{count} shows added to "Update Details" queue.')

    @admin.action(description='Queue Update Durations for selected shows')
    def action_update_durations(self, request, queryset):
        count = 0
        for show in queryset:
            if self._add_to_redis_queue('queue:update_durations', show.id):
                count += 1
        self.message_user(request, f'{count} shows added to "Update Durations" queue.')


@admin.register(ViewUser, site=admin_site)
class ViewUserAdmin(admin.ModelAdmin):
    list_display = (
        'telegram_id',
        'get_colored_name',
        'get_colored_username',
        'language',
        'get_role_sortable',
        'is_bot_active',
        'get_django_user_link',
        'created_at',
        'updated_at',
    )
    search_fields = ('name', 'username', 'telegram_id')
    list_filter = ('role', 'is_bot_active', 'language')
    readonly_fields = (
        'django_user',
        'role_message_id',
        'telegram_actions',
        'created_at',
        'updated_at',
    )
    actions = ['resend_role_message']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _role_rank=Case(
                When(role=UserRole.GUEST, then=Value(1)),
                When(role=UserRole.VIEWER, then=Value(2)),
                When(role=UserRole.ADMIN, then=Value(3)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

    def _get_role_color(self, role):
        if role == UserRole.ADMIN:
            return '#e74c3c'  # Red/Orange
        elif role == UserRole.VIEWER:
            return '#2ecc71'  # Green
        return None

    @admin.display(description='Name', ordering='name')
    def get_colored_name(self, obj):
        color = self._get_role_color(obj.role)
        name = obj.name or '-'
        if color:
            return format_html('<span style="color: {}; font_weight: bold;">{}</span>', color, name)
        return name

    @admin.display(description='Username', ordering='username')
    def get_colored_username(self, obj):
        color = self._get_role_color(obj.role)
        username = obj.username or '-'
        if color:
            return format_html(
                '<span style="color: {}; font_weight: bold;">{}</span>', color, username
            )
        return username

    @admin.display(description='Role', ordering='_role_rank')
    def get_role_sortable(self, obj):
        return obj.get_role_display()

    @admin.display(description='Bot Active', boolean=True)
    def is_bot_active(self, obj):
        return obj.is_bot_active

    @admin.display(description='Telegram Actions')
    def telegram_actions(self, obj):
        if not obj.id:
            return '-'
        return format_html(
            '<a class="button" style="padding:4px 10px; background:#2ecc71; color:white; '
            'text-decoration:none; border-radius:4px;" href="?_resend_telegram=1">'
            'Отправить новое сообщение о роли</a>'
        )

    @admin.display(description='Django User', ordering='django_user')
    def get_django_user_link(self, obj):
        if obj.django_user:
            url = reverse('admin:auth_user_change', args=[obj.django_user.id])
            return format_html('<a href="{}">{}</a>', url, obj.django_user)
        return '-'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if '_resend_telegram' in request.GET and object_id:
            try:
                obj = self.get_object(request, object_id)
                if obj:
                    TelegramSender().send_user_role_message(obj)
                    self.message_user(request, f'Сообщение для {obj} успешно отправлено в канал.')
            except Exception as e:
                self.message_user(request, f'Ошибка отправки: {e}', level='ERROR')

            return HttpResponseRedirect(request.path)

        return super().change_view(request, object_id, form_url, extra_context)

    @admin.action(description='Resend Role Management Message to Telegram')
    def resend_role_message(self, request, queryset):
        sender = TelegramSender()
        count = 0
        for user in queryset:
            try:
                sender.send_user_role_message(user)
                count += 1
            except Exception as e:
                self.message_user(request, f'Error sending for {user}: {e}', level='ERROR')

        self.message_user(request, f'Messages resent for {count} users.')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.django_user:
            sync_user_permissions(obj.django_user, obj.role)


@admin.register(ViewUserGroup, site=admin_site)
class ViewUserGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    filter_horizontal = ('users',)


@admin.register(ViewHistory, site=admin_site)
class ViewHistoryAdmin(SeasonEpisodeDisplayMixin, admin.ModelAdmin):
    list_display = (
        'show',
        'view_date',
        'get_season',
        'get_episode',
        'get_users',
        'get_is_checked_display',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_checked', 'view_date', 'users')
    search_fields = ('show__title', 'show__original_title')
    autocomplete_fields = ('show',)
    filter_horizontal = ('users',)
    readonly_fields = (
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(_first_user_id=Min('users__id'))
        return qs.order_by('-view_date', '-season_number', '-episode_number')

    @admin.display(description='Users', ordering='_first_user_id')
    def get_users(self, obj):
        return ', '.join([u.name or u.username or str(u.telegram_id) for u in obj.users.all()])

    @admin.display(description='Учтено', boolean=True, ordering='is_checked')
    def get_is_checked_display(self, obj):
        return obj.is_checked


@admin.register(ShowDuration, site=admin_site)
class ShowDurationAdmin(SeasonEpisodeDisplayMixin, admin.ModelAdmin):
    list_display = (
        'show',
        'get_season',
        'get_episode',
        'duration_seconds',
        'created_at',
        'updated_at',
    )
    search_fields = ('show__title', 'show__original_title')
    autocomplete_fields = ('show',)
    readonly_fields = (
        'show',
        'season_number',
        'episode_number',
        'duration_seconds',
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('-updated_at', '-season_number', '-episode_number')


@admin.register(LogEntry, site=admin_site)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('colored_level', 'module', 'message', 'created_at', 'updated_at')
    list_filter = ('level', 'module', 'created_at')
    search_fields = ('module', 'message', 'traceback')
    readonly_fields = ('level', 'module', 'message', 'traceback', 'created_at', 'updated_at')

    @admin.display(description='Level', ordering='level')
    def colored_level(self, obj):
        colors = {
            'DEBUG': 'grey',
            'INFO': 'green',
            'WARNING': 'orange',
            'ERROR': 'red',
            'CRITICAL': 'darkred',
        }
        color = colors.get(obj.level, 'black')
        return format_html(
            '<span style="color: {}; font_weight: bold;">{}</span>', color, obj.level
        )

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ('created_at', 'updated_at')
        return self.readonly_fields

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return True


class BaseReadonlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowCountryInline(BaseReadonlyInline):
    model = Show.countries.through
    verbose_name = 'Show'
    verbose_name_plural = 'Shows from this country'
    autocomplete_fields = ('show',)


class ShowGenreInline(BaseReadonlyInline):
    model = Show.genres.through
    verbose_name = 'Show'
    verbose_name_plural = 'Shows in this genre'
    autocomplete_fields = ('show',)


class ShowDirectorInline(BaseReadonlyInline):
    model = Show.directors.through
    verbose_name = 'Directed Show'
    verbose_name_plural = 'Directed Shows'
    autocomplete_fields = ('show',)


class ShowActorInline(BaseReadonlyInline):
    model = Show.actors.through
    verbose_name = 'Acted In Show'
    verbose_name_plural = 'Acted In Shows'
    autocomplete_fields = ('show',)


class BaseNameAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Country, site=admin_site)
class CountryAdmin(BaseNameAdmin):
    inlines = [ShowCountryInline]
    list_display = ('name', 'iso_code', 'emoji_flag', 'created_at', 'updated_at')
    readonly_fields = BaseNameAdmin.readonly_fields + ('related_actors', 'user_stats')

    fieldsets = (
        (None, {'fields': ('name',)}),
        (
            'ISO & Flag',
            {
                'fields': ('iso_code', 'emoji_flag'),
                'classes': (),
            },
        ),
        (
            'Statistics',
            {
                'fields': ('user_stats', 'related_actors'),
                'classes': (),
            },
        ),
        (
            'Dates',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )

    @admin.display(description='User Stats (Shows watched)')
    def user_stats(self, obj):
        return _get_user_stats_html(Q(history__show__countries=obj))

    @admin.display(description='Actors')
    def related_actors(self, obj):
        return _get_related_items_html(
            Person, Q(acted_in_shows__countries=obj), 'admin:app_person_change'
        )


@admin.register(Genre, site=admin_site)
class GenreAdmin(BaseNameAdmin):
    inlines = [ShowGenreInline]
    readonly_fields = BaseNameAdmin.readonly_fields + ('related_actors', 'user_stats')

    fieldsets = (
        (None, {'fields': ('name',)}),
        (
            'Statistics',
            {
                'fields': ('user_stats', 'related_actors'),
                'classes': ('collapse',),
            },
        ),
        (
            'Timestamps',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )

    @admin.display(description='User Stats (Shows watched)')
    def user_stats(self, obj):
        return _get_user_stats_html(Q(history__show__genres=obj))

    @admin.display(description='Actors')
    def related_actors(self, obj):
        return _get_related_items_html(
            Person, Q(acted_in_shows__genres=obj), 'admin:app_person_change'
        )


@admin.register(Person, site=admin_site)
class PersonAdmin(BaseNameAdmin):
    inlines = [ShowDirectorInline, ShowActorInline]
    search_fields = ('name',)
    readonly_fields = BaseNameAdmin.readonly_fields + (
        'related_genres',
        'related_countries',
        'user_stats',
    )

    fieldsets = (
        (None, {'fields': ('name',)}),
        (
            'Statistics',
            {
                'fields': ('user_stats', 'related_genres', 'related_countries'),
                'classes': ('collapse',),
            },
        ),
        (
            'Timestamps',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )

    @admin.display(description='User Stats (Shows watched with this person)')
    def user_stats(self, obj):
        return _get_user_stats_html(Q(history__show__actors=obj) | Q(history__show__directors=obj))

    @admin.display(description='Genres')
    def related_genres(self, obj):
        return _get_related_items_html(
            Genre, Q(show__actors=obj) | Q(show__directors=obj), 'admin:app_genre_change'
        )

    @admin.display(description='Countries')
    def related_countries(self, obj):
        return _get_related_items_html(
            Country, Q(show__actors=obj) | Q(show__directors=obj), 'admin:app_country_change'
        )


class TelegramLogDirectionFilter(admin.SimpleListFilter):
    title = 'Direction'
    parameter_name = 'direction'

    def lookups(self, request, model_admin):
        return [('IN', 'Incoming'), ('OUT', 'Outgoing')]

    def queryset(self, request, queryset):
        if self.value() == 'IN':
            # Входящие события (Update) всегда имеют update_id
            return queryset.filter(raw_data__has_key='update_id')
        if self.value() == 'OUT':
            # Исходящие (Message) не имеют update_id
            return queryset.filter(raw_data__message_id__isnull=False).exclude(
                raw_data__has_key='update_id'
            )
        return queryset


class TelegramLogChatIdFilter(admin.SimpleListFilter):
    title = 'Chat ID'
    parameter_name = 'chat_id'

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)

        chat_ids = (
            qs.exclude(_chat_id_sort__isnull=True)
            .values_list('_chat_id_sort', flat=True)
            .distinct()
            .order_by('_chat_id_sort')
        )

        result = []

        for chat_id in chat_ids:
            log = qs.filter(_chat_id_sort=chat_id).first()
            display_name = '-'

            if log:
                user = model_admin._get_from_user(log)
                if user:
                    if user.get('username'):
                        display_name = f'@{user["username"]}'
                    else:
                        if first_name := user.get('first_name'):
                            display_name = first_name
                        if title := user.get('title'):
                            display_name = title
            result.append((str(chat_id), f'{display_name} ({chat_id})'))

        return result

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(_chat_id_sort=self.value())
        return queryset


@admin.register(TelegramLog, site=admin_site)
class TelegramLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_direction',
        'get_username',
        'get_chat_id',
        'get_message_id',
        'get_content_info',
        'is_alive',
        'created_at',
    )
    list_filter = ('created_at', 'is_alive', TelegramLogDirectionFilter, TelegramLogChatIdFilter)

    search_fields = (
        'id',
        'raw_data__message__chat__id',
        'raw_data__callback_query__message__chat__id',
        'raw_data__my_chat_member__chat__id',
        'raw_data__chat__id',
        'raw_data__message__text',
        'raw_data__text',
        'raw_data__callback_query__data',
        'raw_data__message__message_id',
        'raw_data__message_id',
        'raw_data__message__from__username',
        'raw_data__callback_query__from__username',
    )

    fields = (
        'message_history',
        'formatted_raw_data',
        'is_alive',
        'delete_message_button',
        'created_at',
        'updated_at',
    )
    readonly_fields = (
        'message_history',
        'created_at',
        'updated_at',
        'formatted_raw_data',
        'is_alive',
        'delete_message_button',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _direction_sort=Case(
                When(raw_data__has_key='update_id', then=Value(1)),
                default=Value(2),
                output_field=CharField(),
            ),
            _chat_id_sort=Coalesce(
                F('raw_data__message__chat__id'),
                F('raw_data__callback_query__message__chat__id'),
                F('raw_data__my_chat_member__chat__id'),
                F('raw_data__chat__id'),
                output_field=CharField(),
            ),
            _message_id_sort=Coalesce(
                F('raw_data__message__message_id'),
                F('raw_data__callback_query__message__message_id'),
                F('raw_data__message_id'),
                output_field=CharField(),
            ),
        )

    def _get_raw_ids(self, obj):
        """Извлекает чистые ID чата и сообщения из raw_data."""
        data = obj.raw_data
        chat_id = None
        message_id = None

        if 'message' in data:
            chat_id = data['message'].get('chat', {}).get('id')
            message_id = data['message'].get('message_id')
        elif 'edited_message' in data:
            chat_id = data['edited_message'].get('chat', {}).get('id')
            message_id = data['edited_message'].get('message_id')
        elif 'callback_query' in data and 'message' in data['callback_query']:
            chat_id = data['callback_query']['message'].get('chat', {}).get('id')
            message_id = data['callback_query']['message'].get('message_id')
        elif 'chat_id' in data and 'message_id' in data:
            chat_id = data.get('chat_id')
            message_id = data.get('message_id')
        # Для исходящих запросов часто chat_id и message_id лежат в корне или payload
        elif (
            'chat' in data and 'id' in data['chat']
        ):  # Структура может отличаться в зависимости от API call
            chat_id = data['chat']['id']
            message_id = data.get('message_id')

        return chat_id, message_id

    @admin.display(description='Message History (Thread)')
    def message_history(self, obj):
        """Отображает хронологию событий, связанных с этим сообщением."""
        chat_id, message_id = self._get_raw_ids(obj)

        if not chat_id or not message_id:
            return 'Could not determine Chat ID or Message ID for grouping.'

        # Ищем все логи, связанные с этой парой chat_id + message_id
        # Учитываем различные варианты расположения ID в JSON
        related_logs = TelegramLog.objects.filter(
            Q(raw_data__message__chat__id=chat_id, raw_data__message__message_id=message_id)
            | Q(
                raw_data__edited_message__chat__id=chat_id,
                raw_data__edited_message__message_id=message_id,
            )
            | Q(
                raw_data__callback_query__message__chat__id=chat_id,
                raw_data__callback_query__message__message_id=message_id,
            )
            | Q(raw_data__chat_id=chat_id, raw_data__message_id=message_id)
        ).order_by('created_at')

        if not related_logs.exists():
            return 'No related history found.'

        html = """
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <thead>
                <tr style="background-color: #f5f5f5; text-align: left;">
                    <th style="padding: 8px; border: 1px solid #ddd;">Time</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Type</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">User</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Content</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Link</th>
                </tr>
            </thead>
            <tbody>
        """

        for log in related_logs:
            data = log.raw_data
            event_type = 'Unknown'
            if 'message' in data:
                event_type = 'Message'
            elif 'edited_message' in data:
                event_type = 'Edit'
            elif 'callback_query' in data:
                event_type = 'Callback'
            elif 'deleted_business_messages' in data:
                event_type = 'Delete'
            elif 'chat_id' in data:
                event_type = 'Outgoing'  # Предположение для исходящих

            bg_style = 'background-color: #e8f5e9;' if log.id == obj.id else ''

            link = reverse('admin:app_telegramlog_change', args=[log.id])
            content_info = self.get_content_info(log)
            username = self.get_username(log)

            html += f"""
                <tr style="{bg_style}">
                    <td style="padding: 8px; border: 1px solid #ddd;">
                        {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{event_type}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{username}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{content_info}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">
                        <a href="{link}">View Log #{log.id}</a>
                    </td>
                </tr>
            """

        html += '</tbody></table>'
        return format_html(html)

    def _get_from_user(self, obj):
        data = obj.raw_data
        if 'from_user' in data:
            return data['from_user']
        if 'message' in data:
            return data['message'].get('from_user')
        if 'edited_message' in data:
            return data['edited_message'].get('from_user')
        if 'callback_query' in data:
            return data['callback_query'].get('from_user')
        if 'my_chat_member' in data:
            return data['my_chat_member'].get('from_user')
        if 'chat' in data:
            return data['chat']
        return None

    @admin.display(description='Sender Username')
    def get_username(self, obj):
        user = self._get_from_user(obj)
        if not user:
            return '-'
        username = user.get('username')
        if not username:
            return '-'
        return f'@{username}'

    @admin.display(description='Direction', ordering='_direction_sort')
    def get_direction(self, obj):
        if obj.raw_data.get('update_id'):
            return format_html('<span style="color: green;">IN</span>')
        return format_html('<span style="color: grey;">OUT</span>')

    @admin.display(description='Chat ID', ordering='_chat_id_sort')
    def get_chat_id(self, obj):
        chat_id, _ = self._get_raw_ids(obj)
        return chat_id if chat_id else '-'

    @admin.display(description='Message ID', ordering='_message_id_sort')
    def get_message_id(self, obj):
        _, message_id = self._get_raw_ids(obj)
        return message_id if message_id else '-'

    @admin.display(description='Content')
    def get_content_info(self, obj):
        data = obj.raw_data
        text = ''
        prefix = ''

        if 'message' in data:
            msg = data['message']
            text = msg.get('text') or msg.get('caption') or ''
        elif 'edited_message' in data:
            prefix = '[EDIT] '
            msg = data['edited_message']
            text = msg.get('text') or msg.get('caption') or ''
        elif 'deleted_business_messages' in data:
            prefix = '[DEL] '
            ids = data['deleted_business_messages'].get('message_ids', [])
            text = f'IDs: {ids}'
        elif 'callback_query' in data:
            prefix = '[CB] '
            text = data['callback_query'].get('data', '')
        elif 'my_chat_member' in data:
            prefix = '[Status] '
            text = data['my_chat_member'].get('new_chat_member', {}).get('status', '')
        elif 'text' in data:
            text = data['text']

        if not text:
            content = '-'
        else:
            if len(text) > 50:
                text = text[:50] + '...'
            content = f'{prefix}{text}'

        if not obj.is_alive:
            return format_html(
                '<span style="opacity: 0.5; text-decoration: line-through;">{}</span>', content
            )
        return content

    @admin.display(description='Delete')
    def delete_message_button(self, obj):
        if not obj.is_alive:
            return '-'

        url = reverse('admin:app_telegramlog_change', args=[obj.id]) + '?_delete_api=1'
        return format_html(
            '<a class="button" style="background-color: #c0392b; color: white; '
            'padding: 4px 8px; border-radius: 4px;" href="{}">Delete</a>',
            url,
        )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if '_delete_api' in request.GET and object_id:
            try:
                obj = self.get_object(request, object_id)
                if obj and obj.is_alive:
                    chat_id, message_id = self._get_raw_ids(obj)

                    if chat_id and message_id:
                        TelegramSender().delete_message(chat_id, message_id)
                        obj.is_alive = False
                        obj.save(update_fields=['is_alive'])
                        self.message_user(request, 'Сообщение успешно удалено в Telegram.')
                    else:
                        self.message_user(
                            request, 'Не удалось определить Chat ID или Message ID.', level='ERROR'
                        )
                else:
                    self.message_user(
                        request, 'Сообщение уже удалено или не найдено.', level='WARNING'
                    )
            except Exception as e:
                self.message_user(request, f'Ошибка удаления: {e}', level='ERROR')

            return HttpResponseRedirect(request.path.split('?')[0])

        return super().change_view(request, object_id, form_url, extra_context)

    @admin.display(description='Data')
    def formatted_raw_data(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.raw_data, indent=2, ensure_ascii=False))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True


@admin.register(SharedStat, site=admin_site)
class SharedStatAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    readonly_fields = ('id', 'created_at', 'updated_at', 'formatted_data')

    @admin.display(description='Data')
    def formatted_data(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.data, indent=2, ensure_ascii=False))
