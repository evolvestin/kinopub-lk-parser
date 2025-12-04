import re
from typing import Any

ESCAPE_SEQUENCES = {'{': '&#123;', '<': '&#60;', '}': '&#125;', "'": '&#39;'}


def bold(text: Any) -> str:
    return f'<b>{text}</b>'


def italic(text: Any) -> str:
    return f'<i>{text}</i>'


def under(text: Any) -> str:
    return f'<u>{text}</u>'


def code(text: Any) -> str:
    return f'<code>{text}</code>'


def html_link(link: str, text: str) -> str:
    return f'<a href="{link}">{text}</a>'


def sub_tag(text: str) -> str:
    return re.sub('<.*?>', '', str(text))


def blockquote(text: Any, expandable: bool = False) -> str:
    return f'{"<blockquote expandable>" if expandable else "<blockquote>"}{text}</blockquote>'


def html_secure(text: Any, reverse: bool = False) -> str:
    for pattern, value in ESCAPE_SEQUENCES.items():
        text = (
            re.sub(pattern, value, str(text)) if not reverse else re.sub(value, pattern, str(text))
        )
    return text