import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_review_to_user(chat_id, review_text, parse_mode=None, reply_markup=None):
    token = settings.TELEGRAM_BOT_TOKEN
    url_request = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": review_text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        if isinstance(reply_markup, (dict, list)):
            payload["reply_markup"] = json.dumps(reply_markup)
        else:
            payload["reply_markup"] = reply_markup

    result = requests.post(
        url_request,
        data=payload,
        timeout=(10.0, 30.0),
    )
    if result.status_code != 200:
        logger.error("Telegram sendMessage error [%s]: %s", result.status_code, result.text)
    result.raise_for_status()
    return result.json()


def edit_message_text(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    token = settings.TELEGRAM_BOT_TOKEN
    url_request = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        if isinstance(reply_markup, (dict, list)):
            payload["reply_markup"] = json.dumps(reply_markup)
        else:
            payload["reply_markup"] = reply_markup

    result = requests.post(
        url_request,
        data=payload,
        timeout=(10.0, 30.0),
    )
    if result.status_code != 200:
        logger.error("Telegram editMessageText error [%s]: %s", result.status_code, result.text)
    result.raise_for_status()
    return result.json()


def answer_callback_query(callback_query_id, text=None):
    token = settings.TELEGRAM_BOT_TOKEN
    url_request = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    result = requests.post(
        url_request,
        data=payload,
        timeout=(10.0, 30.0),
    )
    if result.status_code != 200:
        logger.error("Telegram answerCallbackQuery error [%s]: %s", result.status_code, result.text)
    result.raise_for_status()
    return result.json()
