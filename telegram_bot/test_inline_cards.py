import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.inline import inline_search_handler


class InlineCardTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_legacy_card_and_keeps_public_thumbnail(self):
        query = SimpleNamespace(
            query='интерстелла',
            from_user=SimpleNamespace(id=123),
            answer=AsyncMock(),
        )
        poster_url = 'https://kinopub.webredirect.org/api/image_proxy/?url=poster'
        result = {
            'id': 8613,
            'title': 'Интерстеллар',
            'original_title': 'Interstellar',
            'year': 2014,
            'type': 'Movie',
            'status': 'Finished',
            'poster_url': poster_url,
            'countries': ['🇬🇧 Великобритания', '🇺🇸 США'],
            'genres': ['Фантастика', 'Драма'],
            'kinopoisk_rating': 8.7,
            'imdb_rating': 8.7,
            'kinopoisk_url': 'https://www.kinopoisk.ru/film/258687/',
            'imdb_url': 'https://www.imdb.com/title/tt0816692/',
            'internal_rating': 10.0,
            'user_ratings': None,
        }
        bot_instance = SimpleNamespace(
            get_bot_username=AsyncMock(return_value='kinopub_observer_bot')
        )
        with (
            patch('handlers.inline.client.check_user_role', new=AsyncMock(return_value='user')),
            patch('handlers.inline.client.search_shows', new=AsyncMock(return_value=[result])),
            patch('handlers.inline.BotInstance', return_value=bot_instance),
        ):
            await inline_search_handler(query)

        article = query.answer.await_args.args[0][0]
        message = article.input_message_content.message_text
        self.assertEqual(article.thumbnail_url, poster_url)
        self.assertIn('🎬 <b>Интерстеллар</b>', message)
        self.assertIn('<i>(Interstellar)</i>', message)
        self.assertIn('🇬🇧 Великобритания, 🇺🇸 США', message)
        self.assertIn('<a href="https://www.kinopoisk.ru/film/258687/">KP: 8.7</a>', message)
        self.assertIn('<a href="https://www.imdb.com/title/tt0816692/">IMDB: 8.7</a>', message)
        self.assertEqual(article.description, '2014 | Фильм | Interstellar')
        self.assertEqual(
            article.reply_markup.inline_keyboard[0][0].url,
            'https://t.me/kinopub_observer_bot/stats?startapp=show_8613',
        )


if __name__ == '__main__':
    unittest.main()
