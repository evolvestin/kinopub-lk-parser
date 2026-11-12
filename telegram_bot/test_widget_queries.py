import json
import unittest
from unittest.mock import AsyncMock, patch

from aiogram.types import Update
from services.widget_queries import WidgetQueryMiddleware


class WidgetQueryMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_intercepts_unknown_update_and_uses_telegram_sender(self):
        event = Update.model_validate(
            {
                'update_id': 1,
                'widget_query': {'id': '42', 'from': {'id': 123}, 'data': 'c:type:Movie:0'},
            }
        )
        handler, bot = AsyncMock(), AsyncMock()
        with patch(
            'services.widget_queries.client._execute_request',
            new_callable=AsyncMock,
            return_value={'items': []},
        ) as backend:
            await WidgetQueryMiddleware()(handler, event, {'bot': bot})
        handler.assert_not_awaited()
        self.assertEqual(backend.await_args.kwargs['payload']['telegram_id'], 123)
        answer = bot.await_args.args[0]
        self.assertEqual(answer.widget_query_id, '42')
        self.assertEqual(json.loads(answer.data), {'items': []})

    async def test_ordinary_update_passes_through(self):
        event = Update.model_validate({'update_id': 1})
        handler = AsyncMock(return_value='ok')
        self.assertEqual(await WidgetQueryMiddleware()(handler, event, {}), 'ok')

    async def test_replaces_oversized_response(self):
        event = Update.model_validate(
            {'update_id': 1, 'widget_query': {'id': '42', 'from': {'id': 123}, 'data': 'r:1:kp'}}
        )
        bot = AsyncMock()
        with patch(
            'services.widget_queries.client._execute_request',
            new_callable=AsyncMock,
            return_value={'title': 'ф' * 1024},
        ):
            await WidgetQueryMiddleware()(AsyncMock(), event, {'bot': bot})
        self.assertLessEqual(len(bot.await_args.args[0].data.encode()), 1024)
        self.assertIn('error', json.loads(bot.await_args.args[0].data))
