import requests
from django.conf import settings

def send_review_to_user(chat_id, review_text, parse_mode=None):
    token = settings.TELEGRAM_BOT_TOKEN
    url_request = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": review_text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    result = requests.post(
        url_request,
        data=payload,
        timeout=(3.05, 10),
    )
    result.raise_for_status()
    return result.json()
