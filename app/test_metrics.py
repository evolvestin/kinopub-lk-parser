from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app.models import (
    Country,
    ExternalRating,
    Genre,
    LogEntry,
    Person,
    PersonMetricAggregate,
    PersonMetricSummaryDirty,
    PersonMetricSummaryState,
    Show,
    ShowCrew,
    ShowDuration,
    SiteMetric,
)
from app.services.metrics import (
    calculate_system_status_snapshot,
    calculate_duplicate_photo_urls_metric,
    calculate_en_professions_stats_metric,
    calculate_has_kp_metric,
    calculate_imdb_unrated_metric,
    calculate_kp_unrated_metric,
    calculate_missing_imdb_metric,
    calculate_missing_kp_metric,
    calculate_missing_durations_metric,
    calculate_missing_status_metric,
    calculate_persons_avatar_stats_metric,
    calculate_total_persons_by_show_type_metric,
    calculate_total_countries_metric,
    calculate_total_shows_metric,
    calculate_tmdb_missing_durations_metric,
    calculate_tmdb_missing_status_metric,
    calculate_tmdb_no_genres_metric,
    calculate_unused_persons_metric,
    _calculate_profession_stats,
    _profession_stats_from_summary,
    _total_persons_by_show_type_from_summary,
    _unused_persons_from_summary,
    _snapshot_show_metric,
    get_duplicate_photo_urls_page,
    get_duplicate_photo_url_group_members,
    get_global_metrics_history,
    get_has_rating_list,
    get_missing_status_list,
    get_profession_persons_list,
    get_total_persons_list,
    get_unused_persons_list,
    invalidate_duplicate_photo_urls_cache,
)
from app.services.show_metric_summary import (
    get_show_metric_aggregate_data,
    rebuild_show_metric_summaries,
)
from app.services.person_metric_summary import (
    get_person_metric_summary_data,
    rebuild_person_metric_summaries,
    refresh_dirty_person_metric_summaries,
)
from app.services.person_photo_metric_summary import (
    get_person_photo_metric_summary_data,
    rebuild_person_photo_metric_summaries,
)


class MetricsSnapshotPageTests(TestCase):
    def test_metrics_history_reads_only_the_snapshot_table(self):
        SiteMetric.objects.create(
            key='global_snapshot',
            data={
                'total_shows': [{'name': 'Фильм', 'value': 3}],
                '_system_status': {'errors_24h_count': 0},
            },
        )

        with CaptureQueriesContext(connection) as queries:
            history = get_global_metrics_history()

        self.assertEqual(history['total_shows']['now']['data'][0]['value'], 3)
        if connection.vendor == 'postgresql':
            self.assertEqual(len(queries), 1)


class ImdbMetricSplitTests(TestCase):
    def test_missing_rating_metrics_distinguish_sync_error_from_unrated_title(self):
        Show.objects.create(
            title='Rated by IMDb but missing locally',
            original_title='Rated by IMDb but missing locally',
            type='Movie',
            year=2020,
            status='Finished',
            imdb_id='tt10000001',
            imdb_url='https://www.imdb.com/title/tt10000001/',
            imdb_rating_available=True,
        )
        Show.objects.create(
            title='No IMDb rating published',
            original_title='No IMDb rating published',
            type='Movie',
            year=2020,
            status='Finished',
            imdb_id='tt10000002',
            imdb_url='https://www.imdb.com/title/tt10000002/',
            imdb_rating_available=False,
        )

        self.assertEqual(calculate_missing_imdb_metric(), [{'name': 'Фильм', 'value': 1}])
        self.assertEqual(calculate_imdb_unrated_metric(), [{'name': 'Фильм', 'value': 1}])

    def test_kp_metrics_distinguish_sync_error_from_unrated_title(self):
        Show.objects.create(
            title='KP rating missing locally',
            original_title='KP rating missing locally',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/10000001/',
            kinopoisk_rating_available=True,
        )
        Show.objects.create(
            title='KP rating not published',
            original_title='KP rating not published',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/10000002/',
            poiskkino_updated_at=timezone.now(),
        )

        self.assertEqual(calculate_missing_kp_metric(), [{'name': 'Фильм', 'value': 1}])
        self.assertEqual(calculate_kp_unrated_metric(), [{'name': 'Фильм', 'value': 1}])

    def test_kp_rating_metric_and_details_use_the_same_authoritative_field(self):
        rated = Show.objects.create(
            title='KP rating in Show',
            original_title='KP rating in Show',
            type='Movie',
        )
        ExternalRating.objects.create(show=rated, kp=8.1)
        legacy_only = Show.objects.create(
            title='KP rating only in legacy row',
            original_title='KP rating only in legacy row',
            type='Movie',
            kinopoisk_rating=7.2,
        )

        self.assertEqual(calculate_has_kp_metric(), [{'name': 'Фильм', 'value': 1}])
        self.assertEqual(
            list(get_has_rating_list('Movie', 'kp')),
            [{'id': rated.id, 'title': rated.title, 'original_title': rated.original_title}],
        )

    def test_missing_status_metric_details_are_limited_to_series_types(self):
        series = Show.objects.create(
            title='Series without status',
            original_title='Series without status',
            type='Series',
            kinopub_id=1001,
        )
        Show.objects.create(
            title='Movie without status',
            original_title='Movie without status',
            type='Movie',
            kinopub_id=1002,
        )

        self.assertEqual(
            list(get_missing_status_list('Series')),
            [{'id': series.id, 'title': series.title, 'original_title': series.original_title}],
        )

    def test_duplicate_photo_metric_excludes_distinct_tmdb_identities(self):
        shared_photo = 'https://image.tmdb.org/t/p/w200/shared.jpg'
        Person.objects.create(name='Confirmed A', tmdb_id=10001, tmdb_photo_url=shared_photo)
        Person.objects.create(name='Confirmed B', tmdb_id=10002, tmdb_photo_url=shared_photo)
        Person.objects.create(
            name='Unresolved', tmdb_photo_url='https://image.tmdb.org/t/p/w200/x.jpg'
        )
        Person.objects.create(
            name='Confirmed C',
            tmdb_id=10003,
            tmdb_photo_url='https://image.tmdb.org/t/p/w200/x.jpg',
        )

        with CaptureQueriesContext(connection) as queries:
            metric = calculate_duplicate_photo_urls_metric()

        self.assertEqual(
            metric,
            [{'name': 'TMDB дубликаты', 'value': 1}, {'name': 'KP дубликаты', 'value': 0}],
        )
        self.assertTrue(any('EXISTS' in query['sql'].upper() for query in queries))

    def test_duplicate_photo_details_include_kinopoisk_person_id(self):
        shared_photo = 'https://image.kinopoisk.ru/kp/shared.jpg'
        first = Person.objects.create(
            name='KP Person A', kp_photo_url=shared_photo, kinopoisk_person_id=101
        )
        second = Person.objects.create(
            name='KP Person B', kp_photo_url=shared_photo, kinopoisk_person_id=202
        )
        invalidate_duplicate_photo_urls_cache()

        items, has_more = get_duplicate_photo_urls_page('KP', limit=10)

        self.assertFalse(has_more)
        self.assertEqual(len(items), 1)
        self.assertEqual(
            [(person['id'], person['kinopoisk_person_id']) for person in items[0]['persons']],
            [(first.id, 101), (second.id, 202)],
        )

    def test_large_duplicate_photo_group_members_are_loaded_in_bounded_pages(self):
        shared_photo = 'https://image.example.test/large-shared-kp.jpg'
        Person.objects.bulk_create(
            [Person(name=f'KP Person {index}', kp_photo_url=shared_photo) for index in range(55)]
        )
        rebuild_person_photo_metric_summaries()
        invalidate_duplicate_photo_urls_cache()

        items, has_more = get_duplicate_photo_urls_page('KP', limit=10)

        self.assertFalse(has_more)
        self.assertEqual(len(items), 1)
        group = items[0]
        self.assertEqual(len(group['persons']), 50)
        self.assertEqual(group['persons_total'], 55)
        self.assertTrue(group['persons_has_more'])

        next_page = get_duplicate_photo_url_group_members(
            'KP',
            shared_photo,
            after_id=group['persons_after_id'],
            limit=50,
        )
        self.assertEqual(next_page['total'], 55)
        self.assertEqual(len(next_page['items']), 5)
        self.assertFalse(next_page['has_more'])


class ProfessionMetricTests(TestCase):
    def test_english_roles_use_the_english_crew_field(self):
        person = Person.objects.create(name='Known actor', en_name='Known actor')
        show = Show.objects.create(title='Test movie', original_title='Test movie', type='Movie')
        ShowCrew.objects.create(
            show=show,
            person=person,
            profession='В ролях',
            en_profession='Actor',
        )

        stats = calculate_en_professions_stats_metric()
        self.assertNotIn({'name': 'Неизвестно', 'value': 1}, stats)
        self.assertEqual(get_profession_persons_list('Actor', 'en').count(), 1)

    def test_backfilled_canonical_people_use_indexed_role_counts(self):
        person = Person.objects.create(name='Known actor', en_name='Known actor')
        show = Show.objects.create(title='Test movie', original_title='Test movie', type='Movie')
        ShowCrew.objects.create(
            show=show,
            person=person,
            canonical_person=person,
            profession='В ролях',
            en_profession='Actor',
        )

        stats = calculate_en_professions_stats_metric()

        self.assertIn({'name': 'Actor', 'value': 1}, stats)

    def test_backfilled_profession_counts_deduplicate_person_role_pairs_per_language(self):
        actor = Person.objects.create(name='Known actor', en_name='Known actor')
        alias = Person.objects.create(name='Actor alias', master_person=actor)
        unknown = Person.objects.create(name='Unknown crew member')
        show = Show.objects.create(title='Test show', original_title='Test show', type='Movie')
        ShowCrew.objects.create(
            show=show,
            person=actor,
            canonical_person=actor,
            profession='В ролях',
            en_profession='Actor',
        )
        ShowCrew.objects.create(
            show=show,
            person=alias,
            canonical_person=actor,
            profession='В ролях',
            en_profession='Actor',
        )
        ShowCrew.objects.create(
            show=show,
            person=unknown,
            canonical_person=unknown,
            profession='Unmapped role',
            en_profession='Unmapped role',
        )

        with CaptureQueriesContext(connection) as queries:
            stats = calculate_en_professions_stats_metric()

        self.assertIn({'name': 'Actor', 'value': 1}, stats)
        self.assertIn({'name': 'Неизвестно', 'value': 1}, stats)
        grouped_queries = [
            query['sql']
            for query in queries
            if 'GROUPING SETS' in query['sql'].upper()
        ]
        self.assertEqual(len(grouped_queries), 2)
        self.assertTrue(
            all('COUNT(DISTINCT' not in query.upper() for query in grouped_queries)
        )
        self.assertTrue(all('UNIQUE_ROLE_PEOPLE' in query.upper() for query in grouped_queries))
        raised_work_mem_queries = [
            query['sql']
            for query in queries
            if 'SET_CONFIG' in query['sql'].upper() and '256MB' in query['sql'].upper()
        ]
        self.assertEqual(len(raised_work_mem_queries), 2)
        raised_timeout_queries = [
            query['sql']
            for query in queries
            if 'STATEMENT_TIMEOUT' in query['sql'].upper() and '600000' in query['sql']
        ]
        self.assertEqual(len(raised_timeout_queries), 2)
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SHOW work_mem')
                self.assertNotEqual(cursor.fetchone()[0], '256MB')
                cursor.execute('SHOW statement_timeout')
                self.assertNotEqual(cursor.fetchone()[0], '600000ms')


class AvatarMetricTests(TestCase):
    def test_avatar_stats_are_calculated_in_one_aggregate(self):
        Person.objects.create(name='TMDB', tmdb_photo_url='tmdb')
        Person.objects.create(name='KP', kp_photo_url='kp')
        Person.objects.create(name='TMDB not found', is_photo_fetched=True)
        Person.objects.create(name='KP not found')
        waiting_kp = Person.objects.create(name='Waiting KP')
        Person.objects.create(name='Not found at all', is_photo_fetched=True)
        show = Show.objects.create(
            title='Waiting show',
            original_title='Waiting show',
            type='Movie',
            kinopoisk_url='https://kinopoisk.ru/film/123/',
        )
        ShowCrew.objects.create(show=show, person=waiting_kp)

        with CaptureQueriesContext(connection) as queries:
            stats = calculate_persons_avatar_stats_metric()

        self.assertEqual(
            {entry['name']: entry['value'] for entry in stats},
            {
                'Есть фото (TMDB)': 1,
                'Есть фото (KP)': 1,
                'TMDB не найдено': 2,
                'KP не найдено': 4,
                'В ожидании TMDB': 3,
                'В ожидании KP': 1,
                'Не найдено вообще': 2,
            },
        )
        self.assertEqual(
            sum('FROM "app_person"' in query['sql'] for query in queries),
            2,
        )
        waiting_stats_sql = [
            query['sql']
            for query in queries
            if 'FROM "app_person"' in query['sql']
        ][-1]
        self.assertIn('IN (SELECT', waiting_stats_sql.upper())
        self.assertNotIn('PERSON_ID IN (', waiting_stats_sql.upper())
        self.assertFalse(
            any(
                'EXISTS' in query['sql'].upper() and 'FROM "app_person"' in query['sql']
                for query in queries
            )
        )


class UnusedPersonMetricTests(TestCase):
    def test_roles_attached_to_an_alias_are_counted_for_the_canonical_person(self):
        master = Person.objects.create(name='Canonical person')
        alias = Person.objects.create(name='Alias person', master_person=master)
        show = Show.objects.create(title='Show', original_title='Show', type='Movie')
        ShowCrew.objects.create(show=show, person=alias, canonical_person=master)

        self.assertEqual(calculate_unused_persons_metric(), [{'name': 'Без ролей', 'value': 0}])
        self.assertFalse(get_unused_persons_list().filter(id=master.id).exists())

    def test_unused_person_metric_uses_indexed_correlated_exists(self):
        Person.objects.create(name='Unused person')
        with CaptureQueriesContext(connection) as queries:
            metric = calculate_unused_persons_metric()

        self.assertEqual(metric, [{'name': 'Без ролей', 'value': 1}])
        count_sql = next(
            query['sql']
            for query in queries
            if 'SELECT COUNT' in query['sql'].upper()
        )
        self.assertIn('EXISTS', count_sql.upper())
        self.assertEqual(count_sql.upper().count('FROM "APP_PERSON"'), 1)
        self.assertNotIn('LEFT OUTER JOIN "APP_PERSON"', count_sql.upper())

    def test_unused_person_metric_keeps_legacy_fallback_for_null_canonical_ids(self):
        used_person = Person.objects.create(name='Used person')
        Person.objects.create(name='Unused person')
        show = Show.objects.create(title='Show', original_title='Show', type='Movie')
        ShowCrew.objects.create(show=show, person=used_person)

        self.assertEqual(calculate_unused_persons_metric(), [{'name': 'Без ролей', 'value': 1}])

    def test_unused_person_details_use_correlated_exists(self):
        Person.objects.create(name='Unused person')
        with CaptureQueriesContext(connection) as queries:
            list(get_unused_persons_list()[:1])

        detail_sql = next(
            query['sql']
            for query in queries
            if 'SELECT "app_person"' in query['sql']
        )
        self.assertIn('EXISTS', detail_sql.upper())
        self.assertNotIn('IN (SELECT DISTINCT', detail_sql.upper())


class TotalPersonsMetricTests(TestCase):
    def test_total_persons_uses_canonical_id_without_person_join_when_backfilled(self):
        person = Person.objects.create(name='Canonical person')
        show = Show.objects.create(
            title='Show', original_title='Show', type='Movie'
        )
        ShowCrew.objects.create(show=show, person=person, canonical_person=person)

        with CaptureQueriesContext(connection) as queries:
            metric = calculate_total_persons_by_show_type_metric()

        self.assertEqual(metric, [{'name': 'Фильм', 'value': 1}])
        aggregate_sql = next(
            query['sql']
            for query in queries
            if 'GROUP BY' in query['sql'].upper()
            and 'CANONICAL_PERSON_ID' in query['sql'].upper()
        )
        self.assertNotIn('JOIN "app_person"', aggregate_sql.upper())
        self.assertIn('COUNT(*)', aggregate_sql.upper())
        if connection.vendor == 'postgresql':
            work_mem_sql = next(
                query['sql']
                for query in queries
                if 'SET_CONFIG' in query['sql'].upper()
            )
            self.assertIn('256MB', work_mem_sql.upper())
            with connection.cursor() as cursor:
                cursor.execute('SHOW work_mem')
                self.assertNotEqual(cursor.fetchone()[0], '256MB')

    def test_total_person_details_use_correlated_exists_for_first_page(self):
        canonical = Person.objects.create(name='Canonical person')
        alias = Person.objects.create(name='Alias person', master_person=canonical)
        tv_show = Show.objects.create(title='TV show', original_title='TV show', type='TV Show')
        movie = Show.objects.create(title='Movie', original_title='Movie', type='Movie')
        ShowCrew.objects.create(
            show=tv_show,
            person=canonical,
            canonical_person=canonical,
        )
        ShowCrew.objects.create(show=tv_show, person=alias, canonical_person=canonical)
        ShowCrew.objects.create(show=movie, person=alias, canonical_person=canonical)

        with CaptureQueriesContext(connection) as queries:
            people = list(get_total_persons_list('TV Show', max_items=1))

        self.assertEqual([person['id'] for person in people], [canonical.id])
        detail_sql = next(
            query['sql']
            for query in queries
            if 'SELECT "app_person"' in query['sql']
        )
        self.assertIn('EXISTS', detail_sql.upper())
        self.assertNotIn('IN (SELECT DISTINCT', detail_sql.upper())

    def test_total_person_details_keep_legacy_alias_fallback(self):
        canonical = Person.objects.create(name='Canonical person')
        alias = Person.objects.create(name='Alias person', master_person=canonical)
        show = Show.objects.create(title='TV show', original_title='TV show', type='TV Show')
        ShowCrew.objects.create(show=show, person=alias)

        self.assertEqual(
            [person['id'] for person in get_total_persons_list('TV Show')],
            [canonical.id],
        )


class PersonMetricSummaryTests(TestCase):
    def test_backfill_and_dirty_refresh_match_live_metrics(self):
        canonical = Person.objects.create(name='Canonical actor')
        alias = Person.objects.create(name='Actor alias', master_person=canonical)
        Person.objects.create(name='Unused person')
        show = Show.objects.create(
            title='Movie', original_title='Movie', type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/12345/',
        )
        crew = ShowCrew.objects.create(
            show=show,
            person=alias,
            profession='В ролях',
            en_profession='Actor',
        )
        second_show = Show.objects.create(
            title='Series', original_title='Series', type='TV Show',
        )
        ShowCrew.objects.create(
            show=second_show,
            person=canonical,
            profession='Режиссёр',
            en_profession='Director',
        )

        rebuild_person_metric_summaries(batch_size=1)
        with CaptureQueriesContext(connection) as queries:
            summary = get_person_metric_summary_data()
        self.assertFalse(
            any('FROM app_personmetricsummary ' in query['sql'].lower() for query in queries)
        )
        self.assertLessEqual(PersonMetricAggregate.objects.count(), 20)
        state = PersonMetricSummaryState.objects.get(pk=1)
        self.assertEqual(
            state.root_person_count,
            Person.objects.filter(master_person__isnull=True).count(),
        )
        self.assertEqual(state.used_person_count, 1)
        summary_professions = _profession_stats_from_summary(summary)
        live_professions = _calculate_profession_stats()
        self.assertEqual(
            tuple(sorted(rows, key=lambda row: row['name']) for rows in summary_professions),
            tuple(sorted(rows, key=lambda row: row['name']) for rows in live_professions),
        )
        self.assertEqual(
            _total_persons_by_show_type_from_summary(summary),
            calculate_total_persons_by_show_type_metric(),
        )
        self.assertEqual(
            _unused_persons_from_summary(summary),
            calculate_unused_persons_metric(),
        )

        self.assertEqual(
            calculate_persons_avatar_stats_metric(person_summary=summary),
            calculate_persons_avatar_stats_metric(),
        )
        with CaptureQueriesContext(connection) as queries:
            calculate_persons_avatar_stats_metric(person_summary=summary)
        self.assertFalse(
            any('app_showcrew' in query['sql'].lower() for query in queries)
        )

        ShowCrew.objects.filter(pk=crew.pk).update(
            profession='Сценарист',
            en_profession='Writer',
        )
        Show.objects.filter(pk=show.pk).update(type='TV Show')
        self.assertTrue(
            PersonMetricSummaryDirty.objects.filter(canonical_person_id=canonical.pk).exists()
        )
        self.assertGreater(refresh_dirty_person_metric_summaries(), 0)

        summary = get_person_metric_summary_data()
        summary_professions = _profession_stats_from_summary(summary)
        live_professions = _calculate_profession_stats()
        self.assertEqual(
            tuple(sorted(rows, key=lambda row: row['name']) for rows in summary_professions),
            tuple(sorted(rows, key=lambda row: row['name']) for rows in live_professions),
        )
        self.assertEqual(
            _total_persons_by_show_type_from_summary(summary),
            calculate_total_persons_by_show_type_metric(),
        )
        self.assertEqual(
            _unused_persons_from_summary(summary),
            calculate_unused_persons_metric(),
        )

        Show.objects.filter(pk=show.pk).update(kinopoisk_url='')
        self.assertTrue(
            PersonMetricSummaryDirty.objects.filter(canonical_person_id=canonical.pk).exists()
        )
        refresh_dirty_person_metric_summaries()
        summary = get_person_metric_summary_data()
        self.assertEqual(
            calculate_persons_avatar_stats_metric(person_summary=summary),
            calculate_persons_avatar_stats_metric(),
        )

        Show.objects.filter(pk=show.pk).update(
            kinopoisk_url='https://www.kinopoisk.ru/film/12345/'
        )
        refresh_dirty_person_metric_summaries()

        ExternalRating.objects.create(show=show, kp=7.0)
        self.assertTrue(
            PersonMetricSummaryDirty.objects.filter(canonical_person_id=canonical.pk).exists()
        )
        refresh_dirty_person_metric_summaries()
        summary = get_person_metric_summary_data()
        self.assertEqual(
            calculate_persons_avatar_stats_metric(person_summary=summary),
            calculate_persons_avatar_stats_metric(),
        )

        new_canonical = Person.objects.create(name='New canonical actor')
        self.assertEqual(
            PersonMetricSummaryState.objects.get(pk=1).root_person_count,
            Person.objects.filter(master_person__isnull=True).count(),
        )
        Person.objects.filter(pk=alias.pk).update(master_person=new_canonical)
        self.assertTrue(
            PersonMetricSummaryDirty.objects.filter(
                canonical_person_id__in=[canonical.pk, new_canonical.pk]
            ).count()
            >= 2
        )
        refresh_dirty_person_metric_summaries()
        summary = get_person_metric_summary_data()
        summary_professions = _profession_stats_from_summary(summary)
        live_professions = _calculate_profession_stats()
        self.assertEqual(
            tuple(sorted(rows, key=lambda row: row['name']) for rows in summary_professions),
            tuple(sorted(rows, key=lambda row: row['name']) for rows in live_professions),
        )

        ShowCrew.objects.filter(pk=crew.pk).delete()
        refresh_dirty_person_metric_summaries()
        summary = get_person_metric_summary_data()
        self.assertEqual(
            _unused_persons_from_summary(summary),
            calculate_unused_persons_metric(),
        )


class PersonPhotoMetricSummaryTests(TestCase):
    def assert_photo_metrics_match_live(self, summary):
        self.assertEqual(
            sorted(
                calculate_persons_avatar_stats_metric(photo_summary=summary),
                key=lambda item: item['name'],
            ),
            sorted(calculate_persons_avatar_stats_metric(), key=lambda item: item['name']),
        )
        self.assertEqual(
            sorted(
                calculate_duplicate_photo_urls_metric(photo_summary=summary),
                key=lambda item: item['name'],
            ),
            sorted(calculate_duplicate_photo_urls_metric(), key=lambda item: item['name']),
        )

    def test_avatar_and_duplicate_rollups_match_live_queries_and_refresh_dirty_people(self):
        show = Show.objects.create(
            title='Waiting for KP',
            original_title='Waiting for KP',
            type='Movie',
            kinopoisk_url='https://www.kinopoisk.ru/film/71201/',
        )
        shared_kp_photo = 'https://images.example.test/shared-kp.jpg'
        actor = Person.objects.create(
            name='Root actor',
            kp_photo_url=shared_kp_photo,
            is_photo_fetched=True,
        )
        alias = Person.objects.create(
            name='Alias actor',
            kp_photo_url=shared_kp_photo,
            is_photo_fetched=True,
        )
        waiting_actor = Person.objects.create(name='Actor without photo', is_photo_fetched=True)
        ShowCrew.objects.create(show=show, person=actor, profession='В ролях')
        ShowCrew.objects.create(show=show, person=alias, profession='В ролях')
        ShowCrew.objects.create(show=show, person=waiting_actor, profession='В ролях')

        rebuild_person_metric_summaries(batch_size=1)
        rebuild_person_photo_metric_summaries()
        summary = get_person_photo_metric_summary_data()
        self.assert_photo_metrics_match_live(summary)

        with CaptureQueriesContext(connection) as queries:
            snapshot_summary = get_person_photo_metric_summary_data()
            calculate_persons_avatar_stats_metric(photo_summary=snapshot_summary)
            calculate_duplicate_photo_urls_metric(photo_summary=snapshot_summary)
        sql = '\n'.join(query['sql'].lower() for query in queries)
        self.assertNotIn('from app_person ', sql)
        self.assertNotIn('from app_person p', sql)

        Person.objects.filter(pk=actor.pk).update(
            tmdb_photo_url='https://images.example.test/root-tmdb.jpg',
            tmdb_id=71201,
        )
        summary = get_person_photo_metric_summary_data()
        self.assert_photo_metrics_match_live(summary)

        Person.objects.filter(pk=alias.pk).update(master_person=actor)
        get_person_metric_summary_data()
        summary = get_person_photo_metric_summary_data()
        self.assert_photo_metrics_match_live(summary)

        ExternalRating.objects.create(show=show, kp=7.2)
        get_person_metric_summary_data()
        summary = get_person_photo_metric_summary_data()
        self.assert_photo_metrics_match_live(summary)

    def test_duplicate_photo_detail_uses_incremental_groups_and_refreshes_dirty_urls(self):
        shared_photo = 'https://images.example.test/shared-kp.jpg'
        first = Person.objects.create(name='First KP alias', kp_photo_url=shared_photo)
        second = Person.objects.create(name='Second KP alias', kp_photo_url=shared_photo)
        rebuild_person_photo_metric_summaries()
        invalidate_duplicate_photo_urls_cache()

        with CaptureQueriesContext(connection) as queries:
            items, has_more = get_duplicate_photo_urls_page('KP', limit=10)

        self.assertFalse(has_more)
        self.assertEqual(len(items), 1)
        self.assertEqual(
            {person['id'] for person in items[0]['persons']},
            {first.id, second.id},
        )
        candidate_queries = [
            query['sql'].lower()
            for query in queries
            if 'app_personphotogroup' in query['sql'].lower()
        ]
        self.assertTrue(candidate_queries)
        self.assertNotIn('group by', candidate_queries[0])

        Person.objects.filter(pk=second.pk).update(
            kp_photo_url='https://images.example.test/reassigned-kp.jpg'
        )
        invalidate_duplicate_photo_urls_cache()
        items, has_more = get_duplicate_photo_urls_page('KP', limit=10)
        self.assertEqual(items, [])
        self.assertFalse(has_more)


class SystemStatusMetricTests(TestCase):
    def test_latest_status_values_use_ordered_index_lookups(self):
        Show.objects.create(title='Latest show', original_title='Latest show', type='Movie')
        LogEntry.objects.create(
            level='ERROR',
            module='metrics-test',
            message='Parser session finished with an error',
        )

        with CaptureQueriesContext(connection) as queries:
            status = calculate_system_status_snapshot()

        self.assertNotEqual(status['last_actions']['shows'], 'Никогда')
        self.assertNotEqual(status['last_actions']['parser_run'], 'Никогда')
        self.assertEqual(status['errors_24h_count'], 1)
        sql = '\n'.join(query['sql'].lower() for query in queries)
        self.assertNotIn('max(', sql)
        self.assertIn('order by', sql)
        self.assertIn('limit 1', sql)


class CountryMetricTests(TestCase):
    def test_active_countries_use_country_indexed_existence_checks(self):
        active = Country.objects.create(name='Metric active country')
        Country.objects.create(name='Metric unused country')
        first = Show.objects.create(title='First country show', original_title='First', type='Movie')
        second = Show.objects.create(title='Second country show', original_title='Second', type='Movie')
        first.countries.add(active)
        second.countries.add(active)

        with CaptureQueriesContext(connection) as queries:
            result = calculate_total_countries_metric()

        self.assertEqual(
            {entry['name']: entry['value'] for entry in result},
            {'Активные': 1, 'Неиспользуемые': 1},
        )
        sql = '\n'.join(query['sql'].lower() for query in queries)
        self.assertIn('exists', sql)


class ShowMetricSummaryTests(TestCase):
    def assert_metric_matches_live(self, rows, key, live_metric):
        summarized = _snapshot_show_metric(rows, key, live_metric)
        live = live_metric()
        self.assertEqual(
            sorted(summarized, key=lambda item: item['name']),
            sorted(live, key=lambda item: item['name']),
        )

    def test_rollups_match_live_metrics_and_track_source_changes(self):
        kp_series = Show.objects.create(
            title='KP Series',
            original_title='KP Series',
            type='TV Show',
            kinopub_id=9001,
            kinopoisk_url='https://www.kinopoisk.ru/film/9001/',
            kinopoisk_rating_available=True,
            imdb_url='https://www.imdb.com/title/tt9001/',
            imdb_rating_available=True,
            status='',
        )
        tmdb_series = Show.objects.create(
            title='TMDB Series',
            original_title='TMDB Series',
            type='Series',
            tmdb_id=9002,
            plot='',
            status=None,
        )

        rebuild_show_metric_summaries(batch_size=1)
        rows = get_show_metric_aggregate_data()
        self.assert_metric_matches_live(rows, 'total_shows', calculate_total_shows_metric)
        self.assert_metric_matches_live(rows, 'missing_kp', calculate_missing_kp_metric)
        self.assert_metric_matches_live(rows, 'missing_status', calculate_missing_status_metric)
        self.assert_metric_matches_live(
            rows, 'tmdb_missing_status', calculate_tmdb_missing_status_metric
        )
        self.assert_metric_matches_live(
            rows, 'tmdb_missing_durations', calculate_tmdb_missing_durations_metric
        )
        self.assert_metric_matches_live(rows, 'tmdb_no_genres', calculate_tmdb_no_genres_metric)

        ExternalRating.objects.create(show=kp_series, kp=7.4)
        ShowDuration.objects.create(show=tmdb_series, duration_seconds=3600)
        genre = Genre.objects.create(name='Documentary')
        tmdb_series.genres.add(genre)
        Show.objects.filter(pk=tmdb_series.pk).update(type='Movie')

        rows = get_show_metric_aggregate_data()
        self.assert_metric_matches_live(rows, 'has_kp', calculate_has_kp_metric)
        self.assert_metric_matches_live(rows, 'missing_kp', calculate_missing_kp_metric)
        self.assert_metric_matches_live(
            rows, 'missing_durations', calculate_missing_durations_metric
        )
        self.assert_metric_matches_live(
            rows, 'tmdb_missing_durations', calculate_tmdb_missing_durations_metric
        )
