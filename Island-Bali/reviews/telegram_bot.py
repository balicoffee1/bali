import asyncio
import telegram
from django.conf import settings

# Инициализируем бота с вашим токеном
bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)

def send_review_to_user(chat_id, review_text):
    import requests
    print(chat_id)
    print(type(chat_id))
    token = settings.TELEGRAM_BOT_TOKEN
    url_request = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={review_text}"
    result = requests.get(url_request)
    print(result.json())
