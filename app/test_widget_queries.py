import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from app.models import (
    Country,
    ExternalRating,
    Person,
    Show,
    ShowCrew,
    ShowDuration,
    UserRating,
    ViewUser,
)
from app.services.widget_queries import widget_query


@override_settings(BOT_TOKEN='widget-test-token')
class WidgetQueryTests(TestCase):
    def setUp(self):
        self.user = ViewUser.objects.create(telegram_id=12345, name='Viewer')
        self.show = Show.objects.create(
            title='Тестовый фильм',
            original_title='Test',
            type='Movie',
            year=2020,
            imdb_rating=7.8,
            kinopoisk_rating=1.0,
        )
        ExternalRating.objects.create(show=self.show, kp=8.4)

    def test_endpoint_requires_bot_token_and_registered_user(self):
        data = json.dumps({'telegram_id': 12345, 'command': f'r:{self.show.pk}:kp'})
        self.assertEqual(
            self.client.post('/api/bot/widget/', data, content_type='application/json').status_code,
            403,
        )
        response = self.client.post(
            '/api/bot/widget/',
            data,
            content_type='application/json',
            HTTP_X_BOT_TOKEN='widget-test-token',
        )
        self.assertEqual(response.json()['value'], 8.4)
        self.assertIn('error', widget_query(99999, f'r:{self.show.pk}:kp'))

    def test_paginated_result_remains_within_telegram_limit(self):
        for index in range(12):
            Show.objects.create(
                title='Длинное название ' * 12 + str(index),
                original_title='Test',
                type='Movie',
                year=2025,
            )
        result = widget_query(12345, 'c:type:Movie:0')
        self.assertTrue(result['more'])
        self.assertGreater(len(result['items']), 0)
        self.assertLessEqual(
            len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()), 1024
        )
        second = widget_query(12345, f'c:type:Movie:{result["next"]}')
        self.assertNotEqual(result['items'][0][0], second['items'][0][0])

    def test_rejects_invalid_command(self):
        self.assertIn('error', widget_query(12345, 'c:type:Movie:-1'))
        self.assertIn('error', widget_query(12345, 'x' * 65))
        self.assertIn('error', widget_query(12345, f'i:{self.show.pk}:1'))

    def test_crew_person_and_episode_navigation(self):
        person = Person.objects.create(name='Актёр')
        ShowCrew.objects.create(show=self.show, person=person, profession='актеры')
        ShowDuration.objects.create(
            show=self.show, season_number=1, episode_number=1, duration_seconds=2700
        )
        groups = widget_query(12345, f's:{self.show.pk}:crew')['groups']
        people = widget_query(12345, f'p:{self.show.pk}:{groups[0]["id"]}:0')
        self.assertEqual(people['items'][0][0], person.pk)
        films = widget_query(12345, f'c:person:{person.pk}:0')
        self.assertEqual(films['items'][0][0], self.show.pk)
        self.assertEqual(
            widget_query(12345, f's:{self.show.pk}:seasons')['seasons'],
            [{'number': 1, 'duration_seconds': 2700, 'episode_count': 1, 'rating': None}],
        )
        self.assertEqual(
            widget_query(12345, f'e:{self.show.pk}:1:0')['items'][0]['duration_seconds'], 2700
        )
        self.assertEqual(
            widget_query(12345, f'e:{self.show.pk}:1.0:0')['items'][0]['duration_seconds'], 2700
        )
        self.assertIn('error', widget_query(12345, f'e:{self.show.pk}:1.5:0'))

    def test_anonymous_ratings_do_not_expose_other_viewer(self):
        self.user.role = 'viewer'
        self.user.save()
        other = ViewUser.objects.create(telegram_id=54321, name='Private Name', is_anonymous=True)
        UserRating.objects.create(user=other, show=self.show, rating=8.0)
        result = widget_query(12345, f'r:{self.show.pk}:local')
        self.assertEqual(result['value'], 8.0)
        self.assertNotIn('Private Name', json.dumps(result, ensure_ascii=False))
        self.assertIn('Анонимный зритель', result['details'][0])

    def test_episode_pages_fit_telegram_limit(self):
        for number in range(1, 15):
            ShowDuration.objects.create(
                show=self.show, season_number=1, episode_number=number, duration_seconds=2700
            )
        first_response = self.client.post(
            '/api/bot/widget/',
            json.dumps({'telegram_id': 12345, 'command': f'e:{self.show.pk}:1:0'}),
            content_type='application/json',
            HTTP_X_BOT_TOKEN='widget-test-token',
        )
        first = first_response.json()
        self.assertLessEqual(len(first_response.content), 1024)
        self.assertGreater(len(first['items']), 0)
        self.assertTrue(first['more'])
        second_response = self.client.post(
            '/api/bot/widget/',
            json.dumps({'telegram_id': 12345, 'command': f'e:{self.show.pk}:1:{first["next"]}'}),
            content_type='application/json',
            HTTP_X_BOT_TOKEN='widget-test-token',
        )
        second = second_response.json()
        self.assertLessEqual(len(second_response.content), 1024)
        self.assertEqual(len(first['items']) + len(second['items']), 14)

    def test_show_metadata_normalizes_countries_and_status(self):
        self.show.status = 'Finished'
        self.show.save()
        english = Country.objects.create(name='United States of America')
        russian = Country.objects.create(name='США')
        self.show.countries.add(english, russian)
        data = widget_query(12345, f's:{self.show.pk}:show')
        self.assertEqual(data['countries'], [{'id': russian.pk, 'name': 'США'}])
        self.assertEqual(data['status_label'], 'Завершен')
        self.assertEqual(widget_query(12345, 'c:status:Finished:0')['items'][0][0], self.show.pk)

    def test_theme_sync_requires_identity_and_rejects_invalid_value(self):
        with patch('app.views.get_webapp_user', return_value=None):
            response = self.client.post(
                '/api/webapp/theme/', json.dumps({'theme': 'light'}), content_type='application/json'
            )
        self.assertEqual(response.status_code, 403)
        with patch('app.views.get_webapp_user', return_value=self.user):
            bad = self.client.post(
                '/api/webapp/theme/', json.dumps({'theme': 'blue'}), content_type='application/json'
            )
            saved = self.client.post(
                '/api/webapp/theme/', json.dumps({'theme': 'light'}), content_type='application/json'
            )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(saved.json()['theme'], 'light')
        self.assertEqual(widget_query(12345, 't')['theme'], 'light')
        self.user.refresh_from_db()
        self.assertEqual(self.user.webapp_theme, 'light')

    def test_regular_widget_answer_includes_viewer_theme(self):
        self.user.webapp_theme = 'light'
        self.user.save(update_fields=['webapp_theme'])
        data = json.dumps({'telegram_id': 12345, 'command': f'r:{self.show.pk}:kp'})
        response = self.client.post(
            '/api/bot/widget/', data, content_type='application/json',
            HTTP_X_BOT_TOKEN='widget-test-token'
        )
        self.assertEqual(response.json()['theme'], 'light')
        self.assertLessEqual(len(response.content), 1024)
