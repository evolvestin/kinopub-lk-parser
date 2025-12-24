import json

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    F,
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
from django.urls import reverse
from django.utils.html import format_html, format_html_join

# Импортируем нашу кастомную админку
from app.admin_site import admin_site
from app.models import (
    Code,
    Country,
    Genre,
    LogEntry,
    Person,
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
    search_fields = ('title', 'original_title')
    inlines = [ShowDurationInline, ViewHistoryInline, UserRatingInline]
    readonly_fields = (
        'id',
        'title',
        'original_title',
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # Используем подзапрос для подсчета длительности,
        # чтобы избежать умножения суммы на количество просмотров (проблема JOIN)
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


@admin.register(ViewUser, site=admin_site)
class ViewUserAdmin(admin.ModelAdmin):
    list_display = (
        'telegram_id',
        'name',
        'username',
        'language',
        'role',
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
    search_fields = ('module', 'message')
    readonly_fields = ('level', 'module', 'message', 'created_at', 'updated_at')

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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

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
        'get_view_user_link',
        'get_django_user_link',
        'created_at',
    )
    list_filter = ('created_at', TelegramLogDirectionFilter, TelegramLogChatIdFilter)

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
        'formatted_raw_data',
        'created_at',
        'updated_at',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'formatted_raw_data',
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

    def _get_from_user(self, obj):
        data = obj.raw_data
        if 'from_user' in data:
            return data['from_user']
        if 'message' in data:
            return data['message'].get('from_user')
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

    @admin.display(description='View User')
    def get_view_user_link(self, obj):
        user = self._get_from_user(obj)
        if not user:
            return '-'
        tg_id = user.get('id')
        view_user = ViewUser.objects.filter(telegram_id=tg_id).first()
        if view_user:
            url = reverse('admin:app_viewuser_change', args=[view_user.id])
            return format_html('<a href="{}">{}</a>', url, view_user)
        return '-'

    @admin.display(description='Django User')
    def get_django_user_link(self, obj):
        user = self._get_from_user(obj)
        if not user:
            return '-'
        tg_id = user.get('id')
        view_user = ViewUser.objects.filter(telegram_id=tg_id).select_related('django_user').first()
        if view_user and view_user.django_user:
            url = reverse('admin:auth_user_change', args=[view_user.django_user.id])
            return format_html('<a href="{}">{}</a>', url, 'Link')
        return '-'

    @admin.display(description='Direction', ordering='_direction_sort')
    def get_direction(self, obj):
        if obj.raw_data.get('update_id'):
            return format_html('<span style="color: green;">IN</span>')
        return format_html('<span style="color: grey;">OUT</span>')

    @admin.display(description='Chat ID', ordering='_chat_id_sort')
    def get_chat_id(self, obj):
        data = obj.raw_data
        if 'message' in data and 'chat' in data['message']:
            return data['message']['chat'].get('id')
        if 'callback_query' in data and 'message' in data['callback_query']:
            return data['callback_query']['message']['chat'].get('id')
        if 'my_chat_member' in data:
            return data['my_chat_member']['chat'].get('id')
        if 'chat' in data:
            return data['chat'].get('id')
        return '-'

    @admin.display(description='Message ID', ordering='_message_id_sort')
    def get_message_id(self, obj):
        data = obj.raw_data
        if 'message' in data:
            return data['message'].get('message_id')
        if 'callback_query' in data and 'message' in data['callback_query']:
            return data['callback_query']['message'].get('message_id')
        if 'message_id' in data:
            return data['message_id']
        return '-'

    @admin.display(description='Content')
    def get_content_info(self, obj):
        data = obj.raw_data
        text = ''
        prefix = ''

        if 'message' in data:
            msg = data['message']
            text = msg.get('text') or msg.get('caption') or ''
        elif 'callback_query' in data:
            prefix = '[CB] '
            text = data['callback_query'].get('data', '')
        elif 'my_chat_member' in data:
            prefix = '[Status] '
            text = data['my_chat_member'].get('new_chat_member', {}).get('status', '')
        elif 'text' in data:
            text = data['text']

        if not text:
            return '-'

        if len(text) > 50:
            text = text[:50] + '...'
        return f'{prefix}{text}'

    @admin.display(description='Data')
    def formatted_raw_data(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.raw_data, indent=2, ensure_ascii=False))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
