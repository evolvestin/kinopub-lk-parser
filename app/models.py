from django.db import models


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

    def __str__(self):
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

    def __str__(self):
        if self.name:
            return self.name
        if self.username:
            return self.username
        return str(self.telegram_id)

    class Meta:
        verbose_name = 'View User'
        verbose_name_plural = 'View Users'


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
    countries = models.ManyToManyField(Country, blank=True)
    genres = models.ManyToManyField(Genre, blank=True)
    directors = models.ManyToManyField(Person, related_name='directed_shows', blank=True)
    actors = models.ManyToManyField(Person, related_name='acted_in_shows', blank=True)

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

    def __str__(self):
        return f'[{self.created_at.strftime("%Y-%m-%d %H:%M:%S")}] [{self.level}] {self.module}: {self.message}'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log entry'
        verbose_name_plural = 'Log entries'


class UserRating(BaseModel):
    RATING_CHOICES = [(float(i) / 2, str(float(i) / 2)) for i in range(21)]

    user = models.ForeignKey(ViewUser, on_delete=models.CASCADE, related_name='ratings')
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='ratings')
    rating = models.FloatField(choices=RATING_CHOICES)

    class Meta:
        verbose_name = 'User Rating'
        verbose_name_plural = 'User Ratings'
        unique_together = ('user', 'show')
        indexes = [
            models.Index(fields=['user', 'show']),
        ]

    def __str__(self):
        return f'{self.user.name}: {self.show.title} - {self.rating}'


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
