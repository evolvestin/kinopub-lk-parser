import requests
import logging
import time

from config import BOT_TOKEN, CHAT_ID, MAX_RETRIES, REQUEST_TIMEOUT


def send_message(message: str) -> int | None:
    """Sends a message to Telegram and returns the message_id."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error('BOT_TOKEN or CHAT_ID is not set.')
        return None
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {'chat_id': CHAT_ID, 'text': message}
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if data.get('ok'):
                message_id = data['result']['message_id']
                logging.info('Sent to Telegram: \'%s\' (msg_id: %d)', message, message_id)
                return message_id
            else:
                logging.error("Telegram API error: %s", data.get("description"))

        except requests.RequestException as e:
            logging.error('Telegram send error (attempt %d/%d): %s', attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    logging.error('Failed to send to Telegram after %d retries.', MAX_RETRIES)
    return None


def edit_message_to_expired(message_id: int):
    """Edits a Telegram message to indicate it has expired."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error('BOT_TOKEN or CHAT_ID is not set.')
        return
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText'
    payload = {
        'chat_id': CHAT_ID,
        'message_id': message_id,
        'text': '_Expired_',
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code == 400 and 'message is not modified' in response.text:
            logging.warning('Message %d was already marked as expired.', message_id)
        else:
            response.raise_for_status()
            logging.info('Edited message %d to Expired.', message_id)
    except requests.RequestException as e:
        logging.error('Failed to edit Telegram message %d: %s', message_id, e)
