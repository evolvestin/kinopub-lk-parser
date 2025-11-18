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


class Show(BaseModel):
    id = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=255)
    original_title = models.CharField(max_length=255)
    type = models.CharField(max_length=50, default='Series')
    year = models.IntegerField(null=True, blank=True)
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
