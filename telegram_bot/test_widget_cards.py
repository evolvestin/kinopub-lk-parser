import json
import unittest
import zlib
from unittest.mock import AsyncMock, patch

from services.widget_cards import SendWidget, build_widget_method, send_show_widget


class WidgetCardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.show = {
            'id': 8613,
            'title': 'Интерстеллар',
            'original': 'Interstellar',
            'year': 2014,
            'type': 'Movie',
            'status': 'Finished',
            'status_label': 'Завершен',
            'duration': 10144,
            'kp': 8.7,
            'imdb': 8.7,
            'local': 10.0,
            'genres': [{'id': 116, 'name': 'Фантастика'}],
            'countries': [{'id': 1, 'name': 'США'}],
            'plot': 'Описание фильма',
            'theme': 'dark',
        }

    def test_widget_is_compact_centered_and_has_no_poster_path(self):
        method = build_widget_method(123, self.show)
        self.assertIsInstance(method, SendWidget)
        self.assertEqual(method.__api_method__, 'sendWidget')
        self.assertEqual(method.height, 450)
        self.assertIsNone(method.caption)
        self.assertNotIn('poster', method.html.lower())
        self.assertNotIn('__poster', method.html)
        self.assertLessEqual(len(method.html.encode()), 32768)
        self.assertLessEqual(len(zlib.compress(method.html.encode(), 9)), 4096)
        self.assertIn('text-align:center', method.html)
        self.assertEqual(json.loads(method.chat_data)['s'][0], self.show['id'])
        self.assertEqual(json.loads(method.public_data)['theme'], 'dark')

    async def test_sends_widget_to_private_chat_using_backend_state(self):
        bot = AsyncMock()
        with patch(
            'services.widget_cards.client._execute_request', new=AsyncMock(return_value=self.show)
        ) as fetch:
            sent = await send_show_widget(bot, 123, 123, 8613)
        self.assertTrue(sent)
        fetch.assert_awaited_once_with(
            'widget/', method='POST',
            payload={'telegram_id': 123, 'command': 's:8613:full'},
        )
        bot.assert_awaited_once()
        self.assertIsInstance(bot.await_args.args[0], SendWidget)

    async def test_falls_back_when_backend_has_no_show(self):
        bot = AsyncMock()
        with patch(
            'services.widget_cards.client._execute_request', new=AsyncMock(return_value=None)
        ):
            sent = await send_show_widget(bot, 123, 123, 999)
        self.assertFalse(sent)
        bot.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
