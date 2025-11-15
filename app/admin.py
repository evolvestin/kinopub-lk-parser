from django.contrib import admin
from django.db.models import Count, Sum, Q
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from app.models import Code, Show, ViewHistory, ShowDuration, LogEntry, Country, Genre, Person


@admin.register(Code)
class CodeAdmin(ModelAdmin):
    list_display = ('code', 'telegram_message_id', 'received_at', 'created_at', 'updated_at')
    list_filter = ('received_at',)
    search_fields = ('code',)
    readonly_fields = ('code', 'telegram_message_id', 'received_at', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ShowDurationInline(admin.TabularInline):
    model = ShowDuration
    extra = 0
    readonly_fields = ('season_number', 'episode_number', 'duration_seconds', 'created_at', 'updated_at')
    can_delete = False


class ViewHistoryInline(admin.TabularInline):
    model = ViewHistory
    extra = 0
    readonly_fields = ('view_date', 'season_number', 'episode_number', 'created_at', 'updated_at')
    can_delete = False


@admin.register(Show)
class ShowAdmin(ModelAdmin):
    list_display = ('title', 'original_title', 'type', 'year', 'view_count', 'total_duration_hours', 'created_at', 'updated_at')
    list_filter = ('type', 'year', 'genres', 'countries')
    search_fields = ('title', 'original_title')
    inlines = [ShowDurationInline, ViewHistoryInline]
    readonly_fields = ('id', 'title', 'original_title', 'type', 'year', 'kinopoisk_url', 'kinopoisk_rating', 'kinopoisk_votes', 'imdb_url', 'imdb_rating', 'imdb_votes', 'created_at', 'updated_at')
    filter_horizontal = ('countries', 'genres', 'directors', 'actors')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _view_count=Count('viewhistory'),
            _total_duration=Sum('showduration__duration_seconds')
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


@admin.register(ViewHistory)
class ViewHistoryAdmin(ModelAdmin):
    list_display = ('show', 'view_date', 'season_number', 'episode_number', 'created_at', 'updated_at')
    list_filter = ('view_date',)
    search_fields = ('show__title', 'show__original_title')
    autocomplete_fields = ('show',)
    readonly_fields = ('show', 'view_date', 'season_number', 'episode_number', 'created_at', 'updated_at')


@admin.register(ShowDuration)
class ShowDurationAdmin(ModelAdmin):
    list_display = ('show', 'season_number', 'episode_number', 'duration_seconds', 'created_at', 'updated_at')
    search_fields = ('show__title', 'show__original_title')
    autocomplete_fields = ('show',)
    readonly_fields = ('show', 'season_number', 'episode_number', 'duration_seconds', 'created_at', 'updated_at')


@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    list_display = ('timestamp', 'colored_level', 'module', 'message', 'updated_at')
    list_filter = ('level', 'module', 'timestamp')
    search_fields = ('module', 'message')
    readonly_fields = ('timestamp', 'level', 'module', 'message', 'created_at', 'updated_at')

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
            '<span style="color: {}; font_weight: bold;">{}</span>',
            color,
            obj.level
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ShowCountryInline(admin.TabularInline):
    model = Show.countries.through
    verbose_name = "Show"
    verbose_name_plural = "Shows from this country"
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowGenreInline(admin.TabularInline):
    model = Show.genres.through
    verbose_name = "Show"
    verbose_name_plural = "Shows in this genre"
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowDirectorInline(admin.TabularInline):
    model = Show.directors.through
    verbose_name = "Directed Show"
    verbose_name_plural = "Directed Shows"
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ShowActorInline(admin.TabularInline):
    model = Show.actors.through
    verbose_name = "Acted In Show"
    verbose_name_plural = "Acted In Shows"
    extra = 0
    autocomplete_fields = ('show',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class BaseNameAdmin(ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Country)
class CountryAdmin(BaseNameAdmin):
    inlines = [ShowCountryInline]
    readonly_fields = BaseNameAdmin.readonly_fields + ('related_actors',)

    fieldsets = (
        (None, {'fields': ('name',)}),
        ('Related Actors (Top 20 with most roles)', {
            'fields': ('related_actors',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Actors')
    def related_actors(self, obj):
        actors = Person.objects.filter(
            acted_in_shows__countries=obj
        ).distinct().annotate(
            show_count=Count('acted_in_shows', filter=Q(acted_in_shows__countries=obj))
        ).order_by('-show_count')[:20]

        if not actors:
            return "No related actors found."

        html = "<ul>"
        for actor in actors:
            link = reverse("admin:app_person_change", args=[actor.id])
            html += f'<li><a href="{link}">{actor.name}</a> ({actor.show_count} shows)</li>'
        html += "</ul>"
        return format_html(html)


@admin.register(Genre)
class GenreAdmin(BaseNameAdmin):
    inlines = [ShowGenreInline]
    readonly_fields = BaseNameAdmin.readonly_fields + ('related_actors',)

    fieldsets = (
        (None, {'fields': ('name',)}),
        ('Related Actors (Top 20 with most roles)', {
            'fields': ('related_actors',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Actors')
    def related_actors(self, obj):
        actors = Person.objects.filter(
            acted_in_shows__genres=obj
        ).distinct().annotate(
            show_count=Count('acted_in_shows', filter=Q(acted_in_shows__genres=obj))
        ).order_by('-show_count')[:20]

        if not actors:
            return "No related actors found."

        html = "<ul>"
        for actor in actors:
            link = reverse("admin:app_person_change", args=[actor.id])
            html += f'<li><a href="{link}">{actor.name}</a> ({actor.show_count} shows)</li>'
        html += "</ul>"
        return format_html(html)


@admin.register(Person)
class PersonAdmin(BaseNameAdmin):
    inlines = [ShowDirectorInline, ShowActorInline]
    readonly_fields = BaseNameAdmin.readonly_fields + ('related_genres', 'related_countries')

    fieldsets = (
        (None, {'fields': ('name',)}),
        ('Related Information (Top 20)', {
            'fields': ('related_genres', 'related_countries'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Genres')
    def related_genres(self, obj):
        genres = Genre.objects.filter(
            Q(show__actors=obj) | Q(show__directors=obj)
        ).distinct().annotate(
            show_count=Count('show', filter=Q(show__actors=obj) | Q(show__directors=obj))
        ).order_by('-show_count')[:20]

        if not genres:
            return "No related genres found."

        html = "<ul>"
        for genre in genres:
            link = reverse("admin:app_genre_change", args=[genre.id])
            html += f'<li><a href="{link}">{genre.name}</a> ({genre.show_count} shows)</li>'
        html += "</ul>"
        return format_html(html)

    @admin.display(description='Countries')
    def related_countries(self, obj):
        countries = Country.objects.filter(
            Q(show__actors=obj) | Q(show__directors=obj)
        ).distinct().annotate(
            show_count=Count('show', filter=Q(show__actors=obj) | Q(show__directors=obj))
        ).order_by('-show_count')[:20]

        if not countries:
            return "No related countries found."

        html = "<ul>"
        for country in countries:
            link = reverse("admin:app_country_change", args=[country.id])
            html += f'<li><a href="{link}">{country.name}</a> ({country.show_count} shows)</li>'
        html += "</ul>"
        return format_html(html)
