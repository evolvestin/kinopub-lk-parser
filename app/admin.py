from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils.html import format_html

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
    UserRating,
    ViewHistory,
    ViewUser,
    ViewUserGroup,
)
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User


admin_site.register(Group, GroupAdmin)
admin_site.register(User, UserAdmin)


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


class ShowDurationInline(admin.TabularInline):
    model = ShowDuration
    extra = 0
    readonly_fields = (
        'season_number',
        'episode_number',
        'duration_seconds',
        'created_at',
        'updated_at',
    )
    can_delete = False


class ViewHistoryInline(admin.TabularInline):
    model = ViewHistory
    extra = 0
    readonly_fields = (
        'view_date',
        'season_number',
        'episode_number',
        'created_at',
        'updated_at',
    )
    can_delete = False


class UserRatingInline(admin.TabularInline):
    model = UserRating
    extra = 1
    autocomplete_fields = ('user',)


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
    list_filter = ('type', 'status', 'year')
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
        queryset = queryset.annotate(
            _view_count=Count('viewhistory'),
            _total_duration=Sum('showduration__duration_seconds'),
        )
        return queryset

    @admin.display(description='Views', ordering='_view_count')
    def view_count(self, obj):
        return obj._view_count

    @admin.display(description='Duration (h)')
    def total_duration_hours(self, obj):
        if obj and obj._total_duration:
            return round(obj._total_duration / 3600, 1)
        return 0

    @admin.display(description='Avg Rating')
    def get_avg_rating(self, obj):
        ratings = obj.ratings.all()
        if not ratings:
            return '-'
        avg = sum(r.rating for r in ratings) / len(ratings)
        return round(avg, 2)


@admin.register(ViewUser, site=admin_site)
class ViewUserAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'username',
        'telegram_id',
        'language',
        'created_at',
        'updated_at',
    )
    search_fields = ('name', 'username', 'telegram_id')
    list_filter = ('language',)


@admin.register(ViewUserGroup, site=admin_site)
class ViewUserGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    filter_horizontal = ('users',)


@admin.register(ViewHistory, site=admin_site)
class ViewHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'show',
        'view_date',
        'season_number',
        'episode_number',
        'get_users',
        'created_at',
        'updated_at',
    )
    list_filter = ('view_date', 'users')
    search_fields = ('show__title', 'show__original_title')
    autocomplete_fields = ('show',)
    filter_horizontal = ('users',)
    readonly_fields = (
        'created_at',
        'updated_at',
    )

    @admin.display(description='Users')
    def get_users(self, obj):
        return ', '.join([u.name or u.username or str(u.telegram_id) for u in obj.users.all()])


@admin.register(ShowDuration, site=admin_site)
class ShowDurationAdmin(admin.ModelAdmin):
    list_display = (
        'show',
        'season_number',
        'episode_number',
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
        return False


class ShowCountryInline(admin.TabularInline):
    model = Show.countries.through
    verbose_name = 'Show'
    verbose_name_plural = 'Shows from this country'
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowGenreInline(admin.TabularInline):
    model = Show.genres.through
    verbose_name = 'Show'
    verbose_name_plural = 'Shows in this genre'
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowDirectorInline(admin.TabularInline):
    model = Show.directors.through
    verbose_name = 'Directed Show'
    verbose_name_plural = 'Directed Shows'
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowActorInline(admin.TabularInline):
    model = Show.actors.through
    verbose_name = 'Acted In Show'
    verbose_name_plural = 'Acted In Shows'
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class BaseNameAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Country, site=admin_site)
class CountryAdmin(BaseNameAdmin):
    inlines = [ShowCountryInline]
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
            'Dates',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )

    @admin.display(description='User Stats (Shows watched)')
    def user_stats(self, obj):
        # Считаем количество уникальных шоу этой страны, которые посмотрел каждый пользователь
        stats = (
            ViewUser.objects.filter(history__show__countries=obj)
            .distinct()
            .annotate(
                shows_count=Count(
                    'history__show', distinct=True, filter=Q(history__show__countries=obj)
                )
            )
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

    @admin.display(description='Actors')
    def related_actors(self, obj):
        actors = (
            Person.objects.filter(acted_in_shows__countries=obj)
            .distinct()
            .annotate(show_count=Count('acted_in_shows', filter=Q(acted_in_shows__countries=obj)))
            .order_by('-show_count')[:20]
        )

        if not actors:
            return 'No related actors found.'

        html = '<ul>'
        for actor in actors:
            link = reverse('admin:app_person_change', args=[actor.id])
            html += f'<li><a href="{link}">{actor.name}</a> ({actor.show_count} shows)</li>'
        html += '</ul>'
        return format_html(html)


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
        stats = (
            ViewUser.objects.filter(history__show__genres=obj)
            .distinct()
            .annotate(
                shows_count=Count(
                    'history__show', distinct=True, filter=Q(history__show__genres=obj)
                )
            )
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

    @admin.display(description='Actors')
    def related_actors(self, obj):
        actors = (
            Person.objects.filter(acted_in_shows__genres=obj)
            .distinct()
            .annotate(show_count=Count('acted_in_shows', filter=Q(acted_in_shows__genres=obj)))
            .order_by('-show_count')[:20]
        )

        if not actors:
            return 'No related actors found.'

        html = '<ul>'
        for actor in actors:
            link = reverse('admin:app_person_change', args=[actor.id])
            html += f'<li><a href="{link}">{actor.name}</a> ({actor.show_count} shows)</li>'
        html += '</ul>'
        return format_html(html)


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
        # Пользователи, смотревшие фильмы/сериалы с этим актером или режиссером
        stats = (
            ViewUser.objects.filter(Q(history__show__actors=obj) | Q(history__show__directors=obj))
            .distinct()
            .annotate(
                shows_count=Count(
                    'history__show',
                    distinct=True,
                    filter=Q(history__show__actors=obj) | Q(history__show__directors=obj),
                )
            )
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

    @admin.display(description='Genres')
    def related_genres(self, obj):
        genres = (
            Genre.objects.filter(Q(show__actors=obj) | Q(show__directors=obj))
            .distinct()
            .annotate(show_count=Count('show', filter=Q(show__actors=obj) | Q(show__directors=obj)))
            .order_by('-show_count')[:20]
        )

        if not genres:
            return 'No related genres found.'

        html = '<ul>'
        for genre in genres:
            link = reverse('admin:app_genre_change', args=[genre.id])
            html += f'<li><a href="{link}">{genre.name}</a> ({genre.show_count} shows)</li>'
        html += '</ul>'
        return format_html(html)

    @admin.display(description='Countries')
    def related_countries(self, obj):
        countries = (
            Country.objects.filter(Q(show__actors=obj) | Q(show__directors=obj))
            .distinct()
            .annotate(show_count=Count('show', filter=Q(show__actors=obj) | Q(show__directors=obj)))
            .order_by('-show_count')[:20]
        )

        if not countries:
            return 'No related countries found.'

        html = '<ul>'
        for country in countries:
            link = reverse('admin:app_country_change', args=[country.id])
            html += f'<li><a href="{link}">{country.name}</a> ({country.show_count} shows)</li>'
        html += '</ul>'
        return format_html(html)
