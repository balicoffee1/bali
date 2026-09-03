import requests
from django.conf import settings

def send_review_to_user(chat_id, review_text):
    token = settings.TELEGRAM_BOT_TOKEN
    url_request = f"https://api.telegram.org/bot{token}/sendMessage"
    result = requests.post(
        url_request,
        data={"chat_id": chat_id, "text": review_text},
        timeout=(3.05, 10),
    )
    result.raise_for_status()
    return result.json()
