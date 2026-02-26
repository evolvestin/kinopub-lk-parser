from django.contrib.auth.models import User
from django.db import models
import uuid
from shared.constants import DATETIME_FORMAT, RATING_VALUES, UserRole
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

    def __str__(self):
        if self.emoji_flag:
            return f'{self.emoji_flag} {self.name}'
        return self.name

    class Meta:
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'


class Genre(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'


class Person(BaseModel):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Person'
        verbose_name_plural = 'Persons'


class ViewUser(BaseModel):
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, default='')
    language = models.CharField(max_length=10, default='en')
    is_bot_active = models.BooleanField(default=True, verbose_name='Bot Active')

    role = models.CharField(
        max_length=20, choices=[(r.value, r.name) for r in UserRole], default=UserRole.GUEST
    )
    django_user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='view_user'
    )
    role_message_id = models.IntegerField(
        null=True, blank=True, help_text='ID сообщения в админ-канале для управления ролью'
    )

    def update_personal_details(self, username, name, language, is_active=None):
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
    id = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=255)
    original_title = models.CharField(max_length=255)
    type = models.CharField(max_length=50, default='Series')
    year = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    kinopoisk_url = models.URLField(max_length=255, null=True, blank=True)
    kinopoisk_rating = models.FloatField(null=True, blank=True)
    kinopoisk_votes = models.IntegerField(null=True, blank=True)
    imdb_url = models.URLField(max_length=255, null=True, blank=True)
    imdb_rating = models.FloatField(null=True, blank=True)
    imdb_votes = models.IntegerField(null=True, blank=True)
    plot = models.TextField(null=True, blank=True)
    countries = models.ManyToManyField(Country, blank=True)
    genres = models.ManyToManyField(Genre, blank=True)
    directors = models.ManyToManyField(Person, related_name='directed_shows', blank=True)
    actors = models.ManyToManyField(Person, related_name='acted_in_shows', blank=True)

    def get_internal_rating_data(self):
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
        total_average_sum = 0.0

        for user_id, total_rating in user_ratings_sum.items():
            user_average = total_rating / user_ratings_count[user_id]
            if username := user_objects[user_id].username:
                user_label = f'@{username}'
            else:
                user_label = user_objects[user_id].name
            user_results.append({'label': user_label, 'rating': user_average})
            total_average_sum += user_average

        overall_rating = total_average_sum / len(user_results)
        user_results.sort(key=lambda x: x['rating'], reverse=True)

        return overall_rating, user_results

    def __str__(self):
        if self.title and self.original_title and self.title != self.original_title:
            return f'{self.title} ({self.original_title})'
        return self.title or self.original_title or f'Show {self.id}'

    class Meta:
        verbose_name = 'Show'
        verbose_name_plural = 'Shows'


class ViewHistory(BaseModel):
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    view_date = models.DateField()
    season_number = models.IntegerField(default=0)
    episode_number = models.IntegerField(default=0)
    users = models.ManyToManyField(ViewUser, related_name='history', blank=True)
    is_checked = models.BooleanField(default=True, verbose_name='Учтено')
    telegram_message_id = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['show', 'view_date', 'season_number', 'episode_number'],
                name='idx_view',
            ),
        ]
        unique_together = [['show', 'view_date', 'season_number', 'episode_number']]
        verbose_name = 'View history record'
        verbose_name_plural = 'View history records'


class ShowDuration(BaseModel):
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    season_number = models.IntegerField(null=True)
    episode_number = models.IntegerField(null=True)
    duration_seconds = models.IntegerField()

    class Meta:
        indexes = [
            models.Index(fields=['show', 'season_number', 'episode_number'], name='idx_duration'),
        ]
        unique_together = [['show', 'season_number', 'episode_number']]
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
            models.Index(fields=['user', 'show', 'season_number', 'episode_number']),
        ]

    def __str__(self):
        suffix = ''
        if self.season_number and self.episode_number:
            suffix = f' ({format_se(self.season_number, self.episode_number)})'
        return f'{self.user.name}: {self.show.title}{suffix} - {self.rating}'


class TaskRun(BaseModel):
    STATUS_CHOICES = [
        ('QUEUED', 'В очереди'),
        ('RUNNING', 'Выполняется'),
        ('SUCCESS', 'Успешно'),
        ('FAILURE', 'Ошибка'),
        ('STOPPED', 'Остановлено'),
    ]

    command = models.CharField(max_length=255)
    arguments = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='QUEUED')
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
        return f"Snapshot {self.id}"