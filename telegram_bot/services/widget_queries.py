"""Compatibility handler for Bot API widget updates on aiogram 3.15."""

import asyncio
import json
import logging
import re
from typing import ClassVar

import client
from aiogram import BaseMiddleware
from aiogram.methods import TelegramMethod


class AnswerWidgetQuery(TelegramMethod[bool]):
    __returning__ = bool
    __api_method__: ClassVar[str] = 'answerWidgetQuery'

    widget_query_id: str
    data: str | None = None


class WidgetQueryMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        query = (getattr(event, 'model_extra', None) or {}).get('widget_query')
        if query is None:
            return await handler(event, data)
        if not isinstance(query, dict):
            return None
        query_id, sender, command = query.get('id'), query.get('from'), query.get('data')
        if not isinstance(query_id, str) or not isinstance(sender, dict):
            return None
        sender_id = sender.get('id')
        if (
            not isinstance(sender_id, int)
            or not isinstance(command, str)
            or not 1 <= len(command.encode('utf-8')) <= 64
        ):
            result = {'error': 'Некорректный запрос'}
        else:
            try:
                result = await asyncio.wait_for(
                    client._execute_request(
                        'widget/',
                        method='POST',
                        payload={'telegram_id': sender_id, 'command': command},
                    ),
                    timeout=10,
                )
            except TimeoutError:
                result = None
            if not isinstance(result, dict):
                result = {'error': 'Данные временно недоступны'}
        operation = command.split(':', 1)[0] if isinstance(command, str) else ''
        if operation not in {'s', 'e', 'p', 'r', 'c', 'v', 'w', 'i', 'd'}:
            operation = 'other'
        logging.info('Widget query: operation=%s error=%s', operation, bool(result.get('error')))
        if operation == 'e' and result.get('error'):
            parts = command.split(':')
            logging.info(
                'Widget episode request shape: %s',
                ['numeric' if part.isdigit() else 'other' for part in parts[1:]],
            )
            if len(parts) == 4:
                middle = parts[2]
                diagnostic = (
                    middle if re.fullmatch(r'[0-9. -]{1,12}', middle) else f'length={len(middle)}'
                )
                logging.info('Widget season component: %s', diagnostic)
        answer = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        if len(answer.encode('utf-8')) > 1024:
            answer = json.dumps({'error': 'Ответ слишком большой'}, ensure_ascii=False)
        try:
            await data['bot'](AnswerWidgetQuery(widget_query_id=query_id, data=answer))
        except Exception:
            logging.warning('Unable to answer Telegram widget query')
        return None
