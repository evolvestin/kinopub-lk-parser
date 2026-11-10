import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.commands import handle_privacy_command


class PrivacyCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_policy_url_uses_public_webapp_address(self):
        message = SimpleNamespace(chat=SimpleNamespace(id=42))
        sender = SimpleNamespace(send_message=AsyncMock())
        with patch.dict(os.environ, {'WEBAPP_PUBLIC_URL': 'https://example.org/'}, clear=False):
            with patch('handlers.commands.MessageSender', return_value=sender):
                await handle_privacy_command(message, object())
        sender.send_message.assert_awaited_once_with(
            chat_id=42, text='Политика конфиденциальности: https://example.org/privacy/'
        )
