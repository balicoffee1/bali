import json
import logging
import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_session = None


def get_telegram_session():
    global _session
    if _session is None:
        _session = requests.Session()
        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=10,
            pool_maxsize=20,
        )
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


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

    session = get_telegram_session()
    result = session.post(
        url_request,
        data=payload,
        timeout=(15.0, 30.0),
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

    session = get_telegram_session()
    result = session.post(
        url_request,
        data=payload,
        timeout=(15.0, 30.0),
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

    session = get_telegram_session()
    result = session.post(
        url_request,
        data=payload,
        timeout=(15.0, 30.0),
    )
    if result.status_code != 200:
        logger.error("Telegram answerCallbackQuery error [%s]: %s", result.status_code, result.text)
    result.raise_for_status()
    return result.json()
