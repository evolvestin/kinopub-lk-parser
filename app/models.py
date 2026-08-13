import statistics
import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models import JSONField, Q
from django.db.models.functions import Trim, Upper

from app.utils import format_user_for_rating, get_proxied_image_url, normalize_country_name
from shared.constants import (
    DATETIME_FORMAT,
    PROFESSION_TRANS_MAP,
    RATING_VALUES,
    RAW_TO_NORMALIZED_EN,
    RAW_TO_NORMALIZED_GENRE,
    RAW_TO_NORMALIZED_RU,
    TaskRunStatus,
    UserRole,
)
from shared.formatters import format_se


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        verbose_name = 'Base model'
        verbose_name_plural = 'Base models'


class Code(BaseModel):
    code = models.CharField(max_length=255)
    telegram_message_id = models.IntegerField()
    received_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Code'
        verbose_name_plural = 'Codes'


class Country(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    iso_code = models.CharField(
        max_length=2, null=True, blank=True, help_text='ISO 3166-1 alpha-2 code'
    )
    emoji_flag = models.CharField(max_length=20, null=True, blank=True, help_text='Emoji flag')

    def save(self, *args, **kwargs):
        self.name = normalize_country_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.emoji_flag:
            return f'{self.emoji_flag} {self.name}'
        return self.name

    class Meta:
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name=Trim('name')),
                name='country_name_no_outer_whitespace',
            )
        ]


class Genre(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'


class Person(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    en_name = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    tmdb_id = models.IntegerField(
        null=True, blank=True, unique=True, db_index=True, verbose_name='TMDB ID'
    )
    tmdb_photo_url = models.URLField(max_length=500, null=True, blank=True, db_index=True)
    kp_photo_url = models.URLField(max_length=500, null=True, blank=True, db_index=True)
    is_photo_fetched = models.BooleanField(default=False, db_index=True)
    master_person = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='aliases'
    )

    @property
    def canonical(self):
        if self.master_person_id and self.master_person_id != self.id:
            return self.master_person
        return self

    @property
    def photo_url(self):
        target = self.canonical
        return get_proxied_image_url(target.tmdb_photo_url or target.kp_photo_url)

    def auto_resolve_kp_duplicate(self):
        if not self.kp_photo_url:
            return

        def clean(s):
            if not s:
                return ''
            return (
                ' '.join(s.replace('\xa0', ' ').split()).lower().replace('ё', 'е').replace('э', 'е')
            )

        cleaned_name = clean(self.name)
        if not cleaned_name:
            return

        cleaned_en_name = clean(self.en_name)

        candidates = Person.objects.filter(
            kp_photo_url=self.kp_photo_url, master_person__isnull=True
        ).exclude(id=self.id)

        for candidate in candidates:
            cand_name = clean(candidate.name)

            if cand_name == cleaned_name:
                cand_en_name = clean(candidate.en_name)

                is_exact_match = bool(
                    cleaned_en_name and cand_en_name and cleaned_en_name == cand_en_name
                )

                is_both_empty = not cleaned_en_name and not cand_en_name

                is_special_match = (cleaned_en_name == cleaned_name and not cand_en_name) or (
                    cand_en_name == cleaned_name and not cleaned_en_name
                )

                # Допускаем слияние при совпадении RU-имен:
                # 1. Точное совпадение EN-имен.
                # 2. EN отсутствует у обеих записей.
                # 3. EN отсутствует у одной записи, а у другой дублирует RU-имя.
                if is_exact_match or is_both_empty or is_special_match:
                    self.master_person = candidate.canonical
                    break

    def save(self, *args, **kwargs):
        if not self.master_person_id and self.kp_photo_url:
            self.auto_resolve_kp_duplicate()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.master_person_id and self.master_person_id != self.id:
            return f'{self.name} -> [{self.master_person.name}]'
        return self.name

    class Meta:
        verbose_name = 'Person'
        verbose_name_plural = 'Persons'
        indexes = [
            models.Index(
                fields=['tmdb_photo_url'],
                name='idx_person_tmdb_dupe_source',
                condition=Q(master_person__isnull=True)
                & Q(tmdb_photo_url__isnull=False)
                & ~Q(tmdb_photo_url=''),
            ),
            models.Index(
                fields=['kp_photo_url'],
                name='idx_person_kp_dupe_source',
                condition=Q(master_person__isnull=True)
                & Q(kp_photo_url__isnull=False)
                & ~Q(kp_photo_url=''),
            ),
            GinIndex(
                OpClass(Upper('name'), name='gin_trgm_ops'),
                name='idx_person_name_upper_trgm',
            ),
            GinIndex(
                OpClass(Upper('en_name'), name='gin_trgm_ops'),
                name='idx_person_en_name_upper_trgm',
            ),
        ]


class ShowCrew(BaseModel):
    show = models.ForeignKey('Show', on_delete=models.CASCADE)
    person = models.ForeignKey('Person', on_delete=models.CASCADE)
    canonical_person = models.ForeignKey(
        'Person',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='canonical_crew_rows',
    )
    profession = models.CharField(max_length=500, null=True, blank=True, db_index=True)
    en_profession = models.CharField(max_length=500, null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Show Crew Member'
        verbose_name_plural = 'Show Crew Members'
        unique_together = ('show', 'person', 'profession')
        indexes = [
            models.Index(fields=['profession', 'show'], name='idx_crew_prof_show'),
            models.Index(fields=['en_profession', 'show'], name='idx_crew_enprof_show'),
            models.Index(fields=['profession', 'canonical_person'], name='idx_crew_prof_canonical'),
            models.Index(
                fields=['en_profession', 'canonical_person'], name='idx_crew_enprof_canonical'
            ),
            models.Index(fields=['show', 'canonical_person'], name='idx_crew_show_canonical'),
            models.Index(fields=['person', 'profession'], name='idx_crew_person_prof'),
            models.Index(fields=['person', 'en_profession'], name='idx_crew_person_enprof'),
        ]

    @property
    def normalized_profession(self):
        if self.profession and self.profession in RAW_TO_NORMALIZED_RU:
            return RAW_TO_NORMALIZED_RU[self.profession]
        if self.en_profession and self.en_profession in RAW_TO_NORMALIZED_EN:
            norm_en = RAW_TO_NORMALIZED_EN[self.en_profession]
            for ru_role, en_role in PROFESSION_TRANS_MAP.items():
                if en_role == norm_en:
                    return ru_role
        return self.profession if self.profession else '-'

    @property
    def normalized_en_profession(self):
        if self.en_profession and self.en_profession in RAW_TO_NORMALIZED_EN:
            return RAW_TO_NORMALIZED_EN[self.en_profession]
        if self.profession and self.profession in RAW_TO_NORMALIZED_RU:
            norm_ru = RAW_TO_NORMALIZED_RU[self.profession]
            return PROFESSION_TRANS_MAP.get(norm_ru, norm_ru)
        return self.en_profession if self.en_profession else '-'

    def __str__(self):
        return f'{self.person.name} - {self.normalized_profession}'


class ViewUser(BaseModel):
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, default='')
    language = models.CharField(max_length=10, default='en')
    photo_url = models.URLField(max_length=500, null=True, blank=True)
    is_bot_active = models.BooleanField(default=True, verbose_name='Bot Active')

    screen_width = models.IntegerField(null=True, blank=True)
    screen_height = models.IntegerField(null=True, blank=True)

    role = models.CharField(
        max_length=20, choices=[(r.value, r.name) for r in UserRole], default=UserRole.GUEST
    )
    django_user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='view_user'
    )
    role_message_id = models.IntegerField(
        null=True, blank=True, help_text='ID сообщения в админ-канале для управления ролью'
    )
    is_anonymous = models.BooleanField(default=True, verbose_name='Анонимный')
    privacy_choice_made = models.BooleanField(default=False)

    def update_personal_details(
        self,
        username,
        name,
        language,
        is_active=None,
        photo_url=None,
        screen_width=None,
        screen_height=None,
    ):
        updated_fields = []

        if self.username != username:
            self.username = username
            updated_fields.append('username')

        if self.name != name:
            self.name = name
            updated_fields.append('name')

        if self.language != language:
            self.language = language
            updated_fields.append('language')

        if is_active is not None and self.is_bot_active != is_active:
            self.is_bot_active = is_active
            updated_fields.append('is_bot_active')

        if photo_url is not None and self.photo_url != photo_url:
            self.photo_url = photo_url
            updated_fields.append('photo_url')

        if screen_width is not None and self.screen_width != screen_width:
            self.screen_width = screen_width
            updated_fields.append('screen_width')

        if screen_height is not None and self.screen_height != screen_height:
            self.screen_height = screen_height
            updated_fields.append('screen_height')

        if updated_fields:
            self.save()

        return updated_fields

    def delete(self, *args, **kwargs):
        user = self.django_user
        super().delete(*args, **kwargs)
        if user:
            user.delete()

    def __str__(self):
        status_mark = '' if self.is_bot_active else ' [BLOCKED]'
        if self.name:
            return f'{self.name} ({self.role}){status_mark}'
        if self.username:
            return f'{self.username} ({self.role}){status_mark}'
        return f'{self.telegram_id} ({self.role}){status_mark}'

    class Meta:
        verbose_name = 'View User'
        verbose_name_plural = 'View Users'
        ordering = ['telegram_id']


class ViewUserGroup(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    users = models.ManyToManyField(ViewUser, related_name='groups', blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'View User Group'
        verbose_name_plural = 'View User Groups'


class Show(BaseModel):
    id = models.BigAutoField(primary_key=True)
    kinopub_id = models.IntegerField(
        null=True, blank=True, unique=True, db_index=True, verbose_name='KinoPub ID'
    )
    tmdb_id = models.IntegerField(
        null=True, blank=True, unique=True, db_index=True, verbose_name='TMDB ID'
    )
    tmdb_enrichment_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='TMDB enrichment checked at',
    )
    poiskkino_backfill_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Poiskkino backfill checked at',
    )
    imdb_id = models.CharField(
        max_length=20, null=True, blank=True, unique=True, db_index=True, verbose_name='IMDb ID'
    )
    title = models.CharField(max_length=255)
    original_title = models.CharField(max_length=255)
    type = models.CharField(max_length=50, default='Series', db_index=True)
    year = models.IntegerField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    kinopoisk_url = models.URLField(max_length=255, null=True, blank=True)
    kinopoisk_rating = models.FloatField(null=True, blank=True)
    kinopoisk_votes = models.IntegerField(null=True, blank=True)
    imdb_url = models.URLField(max_length=255, null=True, blank=True)
    imdb_rating = models.FloatField(null=True, blank=True)
    imdb_votes = models.IntegerField(null=True, blank=True)
    tmdb_poster_path = models.CharField(max_length=255, null=True, blank=True)
    plot = models.TextField(null=True, blank=True)
    countries = models.ManyToManyField(Country, blank=True)
    genres = models.ManyToManyField(Genre, blank=True)
    crew = models.ManyToManyField(
        Person,
        through='ShowCrew',
        through_fields=('show', 'person'),
        related_name='shows_as_crew',
        blank=True,
    )
    ignore_collision = models.BooleanField(
        default=False, verbose_name='Игнорировать коллизию в названии'
    )

    @property
    def display_genres(self):
        names = list(self.genres.values_list('name', flat=True))
        seen = set()
        result = []
        for n in names:
            norm = RAW_TO_NORMALIZED_GENRE.get(n, n)
            if norm not in seen:
                seen.add(norm)
                result.append(norm)
        return sorted(result)

    def get_internal_rating_data(self, current_user=None, override_public_user_id=None):
        ratings = self.ratings.select_related('user').all()
        if not ratings:
            return None, []

        user_ratings_sum = {}
        user_ratings_count = {}
        user_objects = {}

        for rating_entry in ratings:
            user_id = rating_entry.user.id
            if user_id not in user_ratings_sum:
                user_ratings_sum[user_id] = 0.0
                user_ratings_count[user_id] = 0
                user_objects[user_id] = rating_entry.user

            user_ratings_sum[user_id] += rating_entry.rating
            user_ratings_count[user_id] += 1

        user_results = []

        for user_id, total_rating in user_ratings_sum.items():
            user_average = total_rating / user_ratings_count[user_id]
            rater = user_objects[user_id]
            fmt = format_user_for_rating(rater, current_user, override_public_user_id)
            user_results.append(
                {'label': fmt['user'], 'rating': user_average, 'is_anonymous': fmt['is_anonymous']}
            )

        user_averages = [item['rating'] for item in user_results]
        mean_rating = sum(user_averages) / len(user_averages)
        median_rating = statistics.median(user_averages)

        if len(user_averages) <= 1:
            overall_rating = mean_rating
        else:
            weight = min(1.0, (len(user_averages) - 1) / 19)
            overall_rating = (1 - weight) * mean_rating + weight * median_rating

        user_results.sort(key=lambda x: (not x['is_anonymous'], x['rating']), reverse=True)

        return overall_rating, user_results

    def __str__(self):
        if self.title and self.original_title and self.title != self.original_title:
            return f'{self.title} ({self.original_title})'
        return self.title or self.original_title or f'Show {self.id}'

    class Meta:
        verbose_name = 'Show'
        verbose_name_plural = 'Shows'
        indexes = [
            models.Index(fields=['type', 'year'], name='idx_show_type_year'),
            models.Index(fields=['status', 'year'], name='idx_show_status_year'),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_kp_type_id',
                condition=Q(kinopub_id__isnull=False),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_missing_imdb',
                condition=Q(imdb_url__isnull=False) & ~Q(imdb_url=''),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_tmdb_type_id',
                condition=Q(tmdb_id__isnull=False) & Q(kinopub_id__isnull=True),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_kp_missing_plot',
                condition=Q(kinopub_id__isnull=False) & (Q(plot__isnull=True) | Q(plot='')),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_kp_missing_year',
                condition=Q(kinopub_id__isnull=False) & Q(year__isnull=True),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_kp_missing_status',
                condition=Q(kinopub_id__isnull=False) & (Q(status__isnull=True) | Q(status='')),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_kp_missing_imdb_id',
                condition=Q(kinopub_id__isnull=False) & (Q(imdb_id__isnull=True) | Q(imdb_id='')),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_tmdb_missing_year',
                condition=Q(tmdb_id__isnull=False)
                & Q(kinopub_id__isnull=True)
                & Q(year__isnull=True),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_tmdb_missing_status',
                condition=Q(tmdb_id__isnull=False)
                & Q(kinopub_id__isnull=True)
                & (Q(status__isnull=True) | Q(status='')),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_tmdb_missing_plot',
                condition=Q(tmdb_id__isnull=False)
                & Q(kinopub_id__isnull=True)
                & (Q(plot__isnull=True) | Q(plot='')),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_missing_tmdb',
                condition=Q(kinopub_id__isnull=False) & Q(tmdb_id__isnull=True),
            ),
            models.Index(
                fields=['type', 'id'],
                name='idx_show_tmdb_no_kp',
                condition=Q(tmdb_id__isnull=False)
                & (Q(kinopoisk_url__isnull=True) | Q(kinopoisk_url='')),
            ),
            GinIndex(
                OpClass(Upper('title'), name='gin_trgm_ops'),
                name='idx_show_title_upper_trgm',
            ),
            GinIndex(
                OpClass(Upper('original_title'), name='gin_trgm_ops'),
                name='idx_show_original_upper_trgm',
            ),
            GinIndex(
                OpClass(Upper('plot'), name='gin_trgm_ops'),
                name='idx_show_plot_upper_trgm',
            ),
        ]


class ViewHistory(BaseModel):
    SOURCE_MANUAL = 'manual'
    SOURCE_KINOPUB = 'kinopub'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_KINOPUB, 'KinoPub'),
    ]

    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    view_date = models.DateField(null=True, blank=True, db_index=True)
    date_precision = models.CharField(max_length=10, default='exact')
    season_number = models.IntegerField(default=0, null=True, blank=True)
    episode_number = models.IntegerField(default=0, null=True, blank=True)
    users = models.ManyToManyField(ViewUser, related_name='history', blank=True)
    is_checked = models.BooleanField(default=True, verbose_name='Учтено')
    telegram_message_id = models.IntegerField(null=True, blank=True)
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
        db_index=True,
        verbose_name='Источник',
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['is_checked', 'view_date'],
                name='idx_view_checked_date',
            ),
        ]
        unique_together = [['show', 'view_date', 'season_number', 'episode_number']]
        verbose_name = 'View history record'
        verbose_name_plural = 'View history records'


class ShowDuration(BaseModel):
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    season_number = models.IntegerField(null=True, blank=True)
    episode_number = models.IntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField()
    is_estimated = models.BooleanField(
        default=False, db_index=True, verbose_name='Оценочная длительность'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['show', 'season_number', 'episode_number'],
                name='uniq_show_duration_position',
                nulls_distinct=False,
            ),
        ]
        verbose_name = 'Show duration'
        verbose_name_plural = 'Show durations'


class LogEntry(BaseModel):
    level = models.CharField(max_length=10)
    module = models.CharField(max_length=100)
    message = models.TextField()
    traceback = models.TextField(blank=True, null=True)

    def __str__(self):
        return (
            f'[{self.created_at.strftime(DATETIME_FORMAT)}]'
            f' [{self.level}] {self.module}: {self.message}'
        )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log entry'
        verbose_name_plural = 'Log entries'


class UserRating(BaseModel):
    RATING_CHOICES = [(r, str(int(r)) if r.is_integer() else str(r)) for r in RATING_VALUES]

    user = models.ForeignKey(ViewUser, on_delete=models.CASCADE, related_name='ratings')
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='ratings')
    season_number = models.IntegerField(null=True, blank=True)
    episode_number = models.IntegerField(null=True, blank=True)
    rating = models.FloatField(choices=RATING_CHOICES)

    class Meta:
        verbose_name = 'User Rating'
        verbose_name_plural = 'User Ratings'
        unique_together = ('user', 'show', 'season_number', 'episode_number')
        indexes = [
            models.Index(
                fields=['user', 'show', 'season_number', 'episode_number'],
                name='app_userrat_user_id_22de90_idx',
            ),
            models.Index(
                fields=['show', 'season_number', 'episode_number'],
                name='idx_userrat_show_se_ep',
            ),
            models.Index(
                fields=['show', 'user'],
                name='idx_userrat_show_user',
            ),
        ]

    def __str__(self):
        suffix = ''
        if self.season_number and self.episode_number:
            suffix = f' ({format_se(self.season_number, self.episode_number)})'
        return f'{self.user.name}: {self.show.title}{suffix} - {self.rating}'


class TaskRun(BaseModel):
    STATUS_CHOICES = [
        (TaskRunStatus.QUEUED.value, 'В очереди'),
        (TaskRunStatus.RUNNING.value, 'Выполняется'),
        (TaskRunStatus.SUCCESS.value, 'Успешно'),
        (TaskRunStatus.FAILURE.value, 'Ошибка'),
        (TaskRunStatus.STOPPED.value, 'Остановлено'),
    ]

    command = models.CharField(max_length=255)
    arguments = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=TaskRunStatus.QUEUED)
    output = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Run'
        verbose_name_plural = 'Task Runs'

    def __str__(self):
        return f'{self.command} ({self.status})'


class TelegramLog(BaseModel):
    raw_data = models.JSONField(default=dict)
    is_alive = models.BooleanField(default=True, verbose_name='Alive')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Telegram Log'
        verbose_name_plural = 'Telegram Logs'
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        direction = self.raw_data.get('direction', '?')
        chat_id = self.raw_data.get('chat_id', '?')
        msg_id = self.raw_data.get('message_id', '?')
        return f'[{direction}] {chat_id}:{msg_id}'


class SharedStat(BaseModel):
    id = models.CharField(max_length=50, primary_key=True, default=uuid.uuid4)
    data = models.JSONField()

    class Meta:
        verbose_name = 'Shared Stat'
        verbose_name_plural = 'Shared Stats'

    def __str__(self):
        return f'Snapshot {self.id}'


class ExternalRating(BaseModel):
    show = models.OneToOneField(Show, on_delete=models.CASCADE, related_name='ext_rating')
    kp = models.FloatField(null=True, blank=True)
    imdb = models.FloatField(null=True, blank=True)
    tmdb = models.FloatField(null=True, blank=True)
    film_critics = models.FloatField(null=True, blank=True)
    russian_film_critics = models.FloatField(null=True, blank=True)
    await_rating = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = 'External Rating'
        verbose_name_plural = 'External Ratings'

    def __str__(self):
        return f'External Ratings for {self.show.id}'


class SiteMetric(BaseModel):
    key = models.CharField(max_length=100, db_index=True)
    data = JSONField()

    class Meta:
        verbose_name = 'Site Metric'
        verbose_name_plural = 'Site Metrics'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key', 'created_at']),
        ]

    def __str__(self):
        return f'{self.key} at {self.created_at.strftime(DATETIME_FORMAT)}'


class WishlistFolder(BaseModel):
    user = models.ForeignKey(ViewUser, on_delete=models.CASCADE, related_name='wishlist_folders')
    name = models.CharField(max_length=100, blank=True)
    icon = models.CharField(max_length=50, default='folder')
    color = models.CharField(max_length=20, default='#60a5fa')
    sort_order = models.IntegerField(default=0)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Wishlist Folder'
        verbose_name_plural = 'Wishlist Folders'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.user} - {self.name}'


class WishlistItem(BaseModel):
    user = models.ForeignKey(
        ViewUser, on_delete=models.CASCADE, related_name='wishlist_items', null=True, blank=True
    )
    folder = models.ForeignKey(
        WishlistFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='items'
    )
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    include_in_stats = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        ordering = ['-sort_order', '-id']
        indexes = [
            models.Index(
                fields=['folder', 'is_active'],
                name='idx_wl_folder_active',
            ),
            models.Index(
                fields=['user', 'is_active', 'include_in_stats'],
                name='idx_wl_user_stats',
            ),
            models.Index(
                fields=['user', 'show', 'is_active'],
                name='idx_wl_user_show_active',
            ),
            models.Index(
                fields=['show', 'is_active'],
                name='idx_wl_show_active',
            ),
        ]

    def __str__(self):
        folder_name = self.folder.name if self.folder else 'Deleted Folder'
        return f'{self.show.title} in {folder_name}'


class CasinoSpin(BaseModel):
    user = models.ForeignKey(ViewUser, on_delete=models.CASCADE, related_name='casino_spins')
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Casino Spin'
        verbose_name_plural = 'Casino Spins'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['user', 'is_deleted', 'created_at'],
                name='idx_casino_user_deleted',
            ),
        ]

    def __str__(self):
        return f'{self.user} - {self.show.title} at {self.created_at}'


class MutedShowNotification(BaseModel):
    user = models.ForeignKey(ViewUser, on_delete=models.CASCADE, related_name='muted_notifications')
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='muted_by_users')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'show')
        verbose_name = 'Muted Show Notification'
        verbose_name_plural = 'Muted Show Notifications'
        indexes = [
            models.Index(
                fields=['user', 'is_active'],
                name='idx_muted_user_active',
            ),
        ]

    def __str__(self):
        status = 'muted' if self.is_active else 'unmuted'
        return f'{self.user} {status} {self.show.title}'


class RejectedPersonPhoto(BaseModel):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='rejected_photos')
    photo_url = models.URLField(max_length=500, db_index=True)

    class Meta:
        unique_together = ('person', 'photo_url')
        verbose_name = 'Rejected Person Photo'
        verbose_name_plural = 'Rejected Person Photos'

    def __str__(self):
        return f'{self.person.name} - {self.photo_url}'
