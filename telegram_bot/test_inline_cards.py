import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.inline import _inline_show_card_text, inline_search_handler


class InlineCardTests(unittest.IsolatedAsyncioTestCase):
    def test_card_uses_posterless_widget_fields_and_escapes_html(self):
        text = _inline_show_card_text(
            {
                'title': 'A & B <test>',
                'original_title': 'A & B',
                'countries': ['🇺🇸 США'],
                'year': 2024,
                'type': 'Movie',
                'status': 'Finished',
                'kinopoisk_rating': 8.1,
                'imdb_rating': 7.9,
                'internal_rating': 9.0,
                'genres': ['Драма', 'Фантастика'],
            }
        )

        self.assertIn('A &amp; B &lt;test&gt;', text)
        self.assertIn('🇺🇸 США', text)
        self.assertIn('🔴 КП 8.1', text)
        self.assertIn('🟡 IMDb 7.9', text)
        self.assertIn('⭐ Локальный 9.0', text)
        self.assertIn('🏷 Драма · Фантастика', text)
        self.assertNotIn('http', text)

    async def test_search_result_has_new_card_and_public_thumbnail(self):
        query = SimpleNamespace(
            query='интерстелла',
            from_user=SimpleNamespace(id=123),
            answer=AsyncMock(),
        )
        result = {
            'id': 8613,
            'title': 'Интерстеллар',
            'original_title': 'Interstellar',
            'year': 2014,
            'type': 'Movie',
            'status': 'Finished',
            'poster_url': 'https://kinopub.webredirect.org/api/image_proxy/?url=poster',
            'countries': ['🇬🇧 Великобритания', '🇺🇸 США'],
            'genres': ['Фантастика', 'Драма'],
            'kinopoisk_rating': 8.7,
            'imdb_rating': 8.7,
            'internal_rating': 10.0,
        }
        bot_instance = SimpleNamespace(
            get_bot_username=AsyncMock(return_value='kinopub_observer_bot')
        )
        with (
            patch('handlers.inline.client.search_shows', new=AsyncMock(return_value=[result])),
            patch('handlers.inline.BotInstance', return_value=bot_instance),
        ):
            await inline_search_handler(query)

        articles = query.answer.await_args.args[0]
        article = articles[0]
        self.assertEqual(
            article.thumbnail_url,
            'https://kinopub.webredirect.org/api/image_proxy/?url=poster',
        )
        self.assertIn('🎬 <b>Интерстеллар</b>', article.input_message_content.message_text)
        self.assertIn('⭐ Локальный 10.0', article.input_message_content.message_text)
        self.assertEqual(
            article.reply_markup.inline_keyboard[0][0].url,
            'https://t.me/kinopub_observer_bot/stats?startapp=show_8613',
        )


if __name__ == '__main__':
    unittest.main()
